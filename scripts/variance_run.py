"""How much does one configuration move between two runs of itself?

Every prompt comparison in this repository was one call per arm, and each was
read as a measurement. Then the same production prompt, on the same document,
model and budget, at temperature 0, scored 16 of 24 gold spans in one run and
20 in another. Four spans is the entire size of the effect the prompt work
reported, which means none of those comparisons could have separated an effect
from the extractor's own spread.

This runs one arm repeatedly and reports that spread directly. It is the
cheapest experiment on the list and it decides the value of every other one:

  * a wide spread (>= 4 spans) says single-run comparisons of this kind are
    uninformative and that any future prompt claim needs repeats per arm;
  * a narrow spread (<= 1 span) says the extractor is close to deterministic
    and the 16-against-20 discrepancy has a cause other than sampling — a
    changed document, gate or measurement — which then has to be found;
  * anything in between fixes the resolution: an effect smaller than the
    spread cannot be shown with one call.

The per-span table is the second half of the answer. A run-to-run spread made
of the same few borderline spans flipping is a different fact than one made of
a different subset each time, and only the first leaves the extraction stable
where it matters.

Usage:
    variance_run.py <gold_data-directory> <output-directory> <decision-id>
                    [--runs 5] [--prompt production|neutral|decompose|vocabulary]
                    [--max-tokens N]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


echr = _load("echr_gold")
variant = _load("prompt_variant_extract")
recall = _load("measure_recall")

from budget_review.gate import govern_packet  # noqa: E402
from budget_review.models import SemanticPacket  # noqa: E402

THRESHOLD = 0.8


def found_spans(packet_data: dict, document: str, gold: list) -> tuple[set[str], int]:
    """Which gold spans this packet reaches, through the real gate."""
    semantic = govern_packet(document, SemanticPacket.from_dict(packet_data))
    union = recall.merged([(c.anchor_start, c.anchor_end) for c in semantic.claims])
    reached = {
        proposal_id
        for proposal_id, span, _ in gold
        if recall.covered_characters(span, union) / max(1, span[1] - span[0]) >= THRESHOLD
    }
    return reached, len(semantic.claims)


def stability(
    runs: list[set[str]], gold_ids: list[str]
) -> tuple[list[str], list[str], list[tuple[str, int]]]:
    """Split the gold spans into always found, never found, and flipping.

    The flipping ones carry their hit count, because one span found in four of
    five runs and four spans found in one each produce the same spread and mean
    very different things.
    """
    always, never, flipping = [], [], []
    for proposal_id in gold_ids:
        hits = sum(1 for reached in runs if proposal_id in reached)
        if hits == len(runs):
            always.append(proposal_id)
        elif hits == 0:
            never.append(proposal_id)
        else:
            flipping.append((proposal_id, hits))
    flipping.sort(key=lambda pair: (-pair[1], pair[0]))
    return always, never, flipping


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gold_data", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("decision")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument(
        "--prompt", default="production", choices=("production", *variant.EDITS, "neutral")
    )
    parser.add_argument("--max-tokens", type=int, default=16384)
    args = parser.parse_args()

    echr.build(args.gold_data, args.decision, args.out_dir)
    document = (args.out_dir / f"{args.decision}.txt").read_text(encoding="utf-8")
    gold_packet = json.loads(
        (args.out_dir / f"{args.decision}.gold.json").read_text(encoding="utf-8")
    )
    gold = recall.gold_spans(gold_packet, document)
    gold_ids = [proposal_id for proposal_id, _, _ in gold]

    if args.prompt == "production":
        system, user = variant.extraction_prompt(args.decision, document, "general")
    elif args.prompt == "neutral":
        system, user = variant.variant_prompt(args.decision, document)
    else:
        system, user = variant.variant_prompt(args.decision, document, (args.prompt,))

    runs: list[set[str]] = []
    claim_counts: list[int] = []
    for attempt in range(args.runs):
        try:
            packet = variant.extract_packet(args.decision, system, user, args.max_tokens)
        except (SystemExit, Exception) as error:  # noqa: BLE001
            # A failed run is part of the spread, not an excuse to discard it:
            # a configuration that dies once in five is exactly what the
            # earlier single runs could not see either.
            print(
                f"  Lauf {attempt + 1}: gescheitert ({type(error).__name__}: {error})",
                file=sys.stderr,
            )
            continue
        reached, claims = found_spans(packet, document, gold)
        runs.append(reached)
        claim_counts.append(claims)
        print(f"  Lauf {attempt + 1}: {len(reached)}/{len(gold)}, {claims} Claims", flush=True)

    if len(runs) < 2:
        print("weniger als zwei Laeufe geglueckt; keine Streuung messbar", file=sys.stderr)
        return 1

    scores = [len(reached) for reached in runs]
    always, never, flipping = stability(runs, gold_ids)
    union = set().union(*runs)

    print()
    print(f"Dokument       {args.decision}, {len(gold)} Gold-Spannen")
    print(f"Prompt         {args.prompt}, Budget {args.max_tokens}, Temperatur 0")
    print(f"Laeufe         {len(runs)} von {args.runs} geglueckt")
    print(
        f"Recall         {min(scores)}-{max(scores)} von {len(gold)}  "
        f"(Mittel {sum(scores) / len(scores):.1f})"
    )
    print(f"Streuung       {max(scores) - min(scores)} Spannen")
    print(f"Claims         {min(claim_counts)}-{max(claim_counts)}")
    print()
    print(f"immer gefunden {len(always)}")
    print(f"nie gefunden   {len(never)}  {' '.join(never)}")
    print(
        f"schwankend     {len(flipping)}  "
        f"{' '.join(f'{pid}({hits}/{len(runs)})' for pid, hits in flipping)}"
    )
    print(f"Vereinigung    {len(union)}/{len(gold)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
