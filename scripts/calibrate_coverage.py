"""Check the coverage measurement's two calibration claims on a gold corpus.

Two properties of the measurement are asserted in the README and in
docs/architecture.md, and both were first established on 1700-character
abstracts: that the gap threshold is not a sensitive knob, and that the named
gaps decompose the anchored share rather than sampling it. Neither is
self-evident at another document length, so this re-derives both from the ECHR
gold spans, which run from 2k to 135k characters.

Feeding gold spans in as if they were admitted claims is the point: they are
what a perfect extractor would have anchored, so whatever the measurement says
here is its behaviour with extraction quality held fixed.

Usage:
    calibrate_coverage.py <gold_data-directory>
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from echr_gold import read_decision  # noqa: E402

from budget_review.coverage import measure_coverage  # noqa: E402
from budget_review.models import GovernedClaim  # noqa: E402

THRESHOLDS = (60, 120, 200, 300, 500)


def as_claims(spans: list[tuple[int, int]]) -> list[GovernedClaim]:
    return [
        GovernedClaim(
            claim_node_id=f"n{index}",
            proposal_id=f"G{index:02d}",
            claim_type="fact",
            canonical_content="x",
            raw_span="x",
            anchor_start=start,
            anchor_end=end,
            anchor_ambiguous=False,
            confidence=0.9,
            source_ref="echr",
            semantic_state="proposed",
        )
        for index, (start, end) in enumerate(spans)
    ]


def regions(gold_data: Path):
    """Each decision's argumentation region, with its gold spans re-based."""
    for path in sorted(gold_data.glob("*.xmi")):
        parsed = read_decision(path)
        if parsed is None:
            continue
        text, spans = parsed
        low, high = spans[0][0], spans[-1][1]
        if high - low < 2000:
            continue
        yield text[low:high], [(begin - low, end - low) for begin, end, _, _ in spans]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    cases = list(regions(Path(sys.argv[1])))
    if not cases:
        print("no regions found", file=sys.stderr)
        return 1
    print(f"Argumentationsregionen: {len(cases)}")

    print("\nSchwellwert-Sweep")
    for threshold in THRESHOLDS:
        counts = [
            len(measure_coverage(text, as_claims(spans), minimum_gap=threshold).gaps)
            for text, spans in cases
        ]
        print(f"  {threshold:>4} Zeichen: Ø {statistics.mean(counts):.2f} Lücken je Dokument")

    print("\nZerlegt die Lückenliste den unverankerten Text?")
    by_length: list[tuple[int, float]] = []
    for text, spans in cases:
        coverage = measure_coverage(text, as_claims(spans))
        unanchored = coverage.document_characters - coverage.anchored_characters
        if unanchored <= 0:
            continue
        named = sum(
            sum(1 for character in text[gap.start : gap.end] if not character.isspace())
            for gap in coverage.gaps
        )
        by_length.append((len(text), named / unanchored))

    shares = [share for _, share in by_length]
    short = [share for length, share in by_length if length < 15000]
    long = [share for length, share in by_length if length >= 30000]
    print(f"  insgesamt:        Median {statistics.median(shares):.2f}  (n={len(shares)})")
    print(f"  < 15.000 Zeichen: Median {statistics.median(short):.2f}  (n={len(short)})")
    print(f"  >= 30.000 Zeichen: Median {statistics.median(long):.2f}  (n={len(long)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
