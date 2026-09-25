"""The spread of the reviewer arms over a graph that cannot move.

Nothing about finding quality on this branch has ever been repeated. After the
two-stage run that is not an omission but a known error: every single-run
comparison here turned out to be unreadable against the spread of one
configuration.

On the reviewer side it is worse, and structurally so. The arms read the governed
ClaimGraph, and on one paper that graph varied between 77 and 115 admitted claims
under identical settings. A reviewer comparison over live extractions therefore
measures the extractor and attributes it to the reviewer. So this measures the
arms first, over an input that cannot move: the repository's frozen packet
through the real gate, N times, same document, same profile.

Two identities matter and both are reported. A finding is "the same" as another
if it flags the same claims for the same reason — category plus its claim ids —
because the wording of a summary varies without the finding changing. And the
graph is checked rather than assumed: if the document hash or the admitted claim
ids differ between runs, the input moved and the measurement says nothing.

Only the arms' findings are counted. The deterministic half is identical by
construction, and including it would report the rules' stability as the arms'.

Usage:
    reviewer_variance.py <output-dir> [--runs N] [--profile budget|general]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))

from budget_review.ingest import ingest  # noqa: E402
from budget_review.pipeline import ReviewPipeline, load_packet  # noqa: E402
from budget_review.provider import DeepSeekProvider, ProviderError  # noqa: E402

FIXTURES = HERE.parents[0] / "src" / "budget_review" / "fixtures"
CASES = {
    "budget": (
        "coherence_theatre",
        "proposal.md",
        "semantic_packet.json",
        "regional-skills-bridge",
    ),
    "general": ("content_theatre", "polished.md", "polished_packet.json", "content-polished"),
}


def finding_key(finding: dict) -> tuple[str, tuple[str, ...]]:
    """Same claims, same reason. The summary's wording is not part of it."""
    return (str(finding["category"]), tuple(sorted(finding["claim_ids"])))


def arm_findings(dossier: dict) -> list[dict]:
    return [f for f in dossier["findings"] if f["reviewer_kind"] == "llm"]


def graph_signature(dossier: dict) -> tuple[str, tuple[str, ...]]:
    """What has to be identical for the comparison to be about the arms."""
    semantic = dossier["semantic"]
    return (
        str(semantic["document_hash"]),
        tuple(claim["proposal_id"] for claim in semantic["claims"]),
    )


def stability(runs: list[set]) -> tuple[list, list[tuple]]:
    """Keys present in every run, and the rest with the number of runs holding them.

    A failed run is an empty set and therefore removes every key from "always",
    which is the point: a configuration that dies once in five is not stable.
    """
    if not runs:
        return [], []
    counts: Counter = Counter()
    for keys in runs:
        counts.update(keys)
    always = sorted(key for key, hits in counts.items() if hits == len(runs))
    flipping = sorted(
        ((key, hits) for key, hits in counts.items() if hits < len(runs)),
        key=lambda pair: (-pair[1], pair[0]),
    )
    return always, flipping


def always_share(always: list, runs: list[set]) -> float:
    """The stable core measured against how much an average run reports."""
    mean = sum(len(keys) for keys in runs) / max(1, len(runs))
    if mean == 0:
        return 0.0
    return len(always) / mean


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--profile", choices=sorted(CASES), default="budget")
    args = parser.parse_args()

    folder, document, packet_name, document_id = CASES[args.profile]
    source = ingest([FIXTURES / folder / document], document_id)
    packet = load_packet(FIXTURES / folder / packet_name)
    pipeline = ReviewPipeline(provider=DeepSeekProvider(), profile=args.profile, language="de")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    pooled: list[set] = []
    per_arm: dict[str, list[set]] = {}
    signatures: set = set()
    for index in range(1, args.runs + 1):
        try:
            dossier = pipeline.run(source, packet=packet, live_review=True).to_dict()
        except (ProviderError, SystemExit) as exc:
            print(f"Lauf {index}: fehlgeschlagen ({exc})", flush=True)
            pooled.append(set())
            for keys in per_arm.values():
                keys.append(set())
            continue
        (args.out_dir / f"reviewer-run-{index}.json").write_text(
            json.dumps(dossier, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        signatures.add(graph_signature(dossier))
        findings = arm_findings(dossier)
        pooled.append({finding_key(f) for f in findings})
        for finding in findings:
            per_arm.setdefault(finding["reviewer_id"], [set() for _ in range(index - 1)])
        for reviewer_id, keys in per_arm.items():
            keys.append({finding_key(f) for f in findings if f["reviewer_id"] == reviewer_id})
        substituted = [run for run in dossier["reviewer_runs"] if run.get("model_substituted")]
        # An arm that fails contributes no findings, which is part of the spread
        # rather than a reason to drop the run — but it has to be visible, or a
        # low count reads as a quiet arm instead of a missing one.
        failed_arms = [
            run["reviewer_id"] for run in dossier["reviewer_runs"] if run.get("status") == "failed"
        ]
        print(
            f"Lauf {index}: {len(findings)} Arm-Befunde "
            f"({len({finding_key(f) for f in findings})} verschieden), "
            f"{len(dossier['review_rejections'])} abgelehnt"
            + (f", Arm ohne Antwort: {', '.join(failed_arms)}" if failed_arms else "")
            + (f", Modell ersetzt in {len(substituted)} Aufruf(en)" if substituted else ""),
            flush=True,
        )

    if len(signatures) > 1:
        print("\nDer Graph war nicht identisch. Die Messung sagt nichts über die Arme.")
        return 1

    counts = [len(keys) for keys in pooled]
    always, flipping = stability(pooled)
    # Distinct keys, not findings: both arms can name the same claims for the
    # same reason, and that is one finding for this measurement. Printing only
    # the keys against a per-run findings count reads as an arithmetic error.
    print(f"\nVerschiedene Befunde je Lauf: {counts}")
    print(f"Streuung: {max(counts) - min(counts)}")
    print(f"In allen {len(pooled)} Läufen: {len(always)}")
    print(f"Anteil am Mittel eines Laufs: {always_share(always, pooled):.2f}")
    for reviewer_id in sorted(per_arm):
        arm_always, _ = stability(per_arm[reviewer_id])
        arm_counts = [len(keys) for keys in per_arm[reviewer_id]]
        print(
            f"  {reviewer_id}: {arm_counts}, in allen {len(arm_always)}, "
            f"Anteil {always_share(arm_always, per_arm[reviewer_id]):.2f}"
        )
    print("\nWechselnde Befunde (Treffer von " + str(len(pooled)) + "):")
    for key, hits in flipping:
        print(f"  {hits}x  {key[0]}  {','.join(key[1])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
