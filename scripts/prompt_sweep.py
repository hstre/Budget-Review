"""Test one prompt edit across several documents instead of one.

A gain measured on a single document is not a property of the prompt, it is a
property of that document. The vocabulary note lifted recall on 001-141170 from
16 of 24 to 20, and the question this answers is whether that repeats: if it
does, a per-domain note is a sound design, and if it does not, tuning on one
decision was never an optimisation at all.

Everything is held constant except the prompt and the document. Each decision
runs twice, production first, and both packets go through the real gate so the
anchors are the ones the product would compute.

A document that fails is reported and skipped rather than ending the sweep — a
sweep that dies on its third of five would otherwise cost the whole run.

Usage:
    prompt_sweep.py <gold_data-directory> <output-directory> <decision-id> [more ...]
                    [--edit vocabulary|decompose|neutral] [--max-tokens N]
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


def score(packet_data: dict, document: str, gold: list) -> tuple[int, int]:
    """Gold spans reached, and claims admitted, through the real gate."""
    semantic = govern_packet(document, SemanticPacket.from_dict(packet_data))
    union = recall.merged([(c.anchor_start, c.anchor_end) for c in semantic.claims])
    found = sum(
        1
        for _, span, _ in gold
        if recall.covered_characters(span, union) / max(1, span[1] - span[0]) >= THRESHOLD
    )
    return found, len(semantic.claims)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gold_data", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("decisions", nargs="+")
    parser.add_argument("--edit", default="vocabulary")
    parser.add_argument("--max-tokens", type=int, default=16384)
    args = parser.parse_args()

    rows = []
    for decision in args.decisions:
        try:
            echr.build(args.gold_data, decision, args.out_dir)
            document = (args.out_dir / f"{decision}.txt").read_text(encoding="utf-8")
            gold_packet = json.loads(
                (args.out_dir / f"{decision}.gold.json").read_text(encoding="utf-8")
            )
            gold = recall.gold_spans(gold_packet, document)

            results = {}
            for label in ("production", args.edit):
                if label == "production":
                    system, user = variant.extraction_prompt(decision, document, "general")
                else:
                    system, user = variant.variant_prompt(decision, document, (label,))
                packet = variant.extract_packet(decision, system, user, args.max_tokens)
                results[label] = score(packet, document, gold)
            rows.append((decision, len(gold), results))
            print(f"  {decision}: fertig", flush=True)
        except (SystemExit, Exception) as error:  # noqa: BLE001
            print(f"  {decision}: uebersprungen ({type(error).__name__}: {error})", file=sys.stderr)

    print()
    print(f"{'Entscheidung':16} {'Gold':>5} {'Produktion':>12} {args.edit:>14} {'Differenz':>10}")
    total_before = total_after = 0
    for decision, gold_count, results in rows:
        before, _ = results["production"]
        after, _ = results[args.edit]
        total_before += before
        total_after += after
        print(
            f"{decision:16} {gold_count:>5} {before:>8}/{gold_count:<3} "
            f"{after:>10}/{gold_count:<3} {after - before:>+10}"
        )
    if rows:
        print()
        print(f"{'Summe':16} {'':>5} {total_before:>8}     {total_after:>10}     "
              f"{total_after - total_before:>+10}")
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
