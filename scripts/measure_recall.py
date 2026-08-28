"""Compare a live extraction against a frozen gold packet for the same document.

Coverage says how much of the source the admitted claims touch. It cannot say
whether the claims that matter were among them: a run can anchor most of a
document and still miss the one sentence a check reasons about. Recall needs a
reference, and the frozen packets are one — hand-built for this extraction
contract, so their scope matches what the extractor is asked for, which is
exactly what a general argument-mining corpus cannot offer.

A gold claim counts as found when enough of its span is covered by the union of
the live anchors. Matching on overlap rather than on identity is deliberate:
two extractions may split the same sentence differently and still both be
right, and this measures whether the content reached the graph, not whether the
segmentation agreed.

Usage:
    measure_recall.py <live-dossier.json> <gold-packet.json> <source-document>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

OVERLAP_THRESHOLDS = (0.5, 0.8)


def merged(spans: list[tuple[int, int]]) -> list[list[int]]:
    out: list[list[int]] = []
    for start, end in sorted(spans):
        if out and start <= out[-1][1]:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return out


def covered_characters(span: tuple[int, int], union: list[list[int]]) -> int:
    start, end = span
    return sum(max(0, min(end, u_end) - max(start, u_start)) for u_start, u_end in union)


def gold_spans(packet: dict, document: str) -> list[tuple[str, tuple[int, int], str]]:
    """Locate each gold claim in the source. Unfindable spans are a fixture bug.

    A packet that carries its own offsets is believed once they are checked to
    quote the same characters. Searching for the text instead would be wrong on
    a long document: legal and administrative prose repeats whole formulas, so
    the first match can sit in a different passage than the one annotated, and
    recall would then be scored against the wrong place.
    """
    located = []
    for claim in packet["claims"]:
        raw = claim["raw_span"]
        proposal_id = claim["proposal_id"]
        begin, end = claim.get("begin"), claim.get("end")
        if begin is not None and end is not None:
            if document[begin:end] != raw:
                print(f"  ! gold offsets do not quote the span: {proposal_id}", file=sys.stderr)
                continue
            located.append((proposal_id, (begin, end), raw))
            continue
        offset = document.find(raw)
        if offset < 0:
            print(f"  ! gold span not in source: {proposal_id}", file=sys.stderr)
            continue
        located.append((proposal_id, (offset, offset + len(raw)), raw))
    return located


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    dossier = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    packet = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    document = Path(sys.argv[3]).read_text(encoding="utf-8")

    semantic = dossier["semantic"] if "semantic" in dossier else dossier
    live = [(c["anchor_start"], c["anchor_end"]) for c in semantic["claims"]]
    union = merged(live)
    gold = gold_spans(packet, document)
    if not gold:
        print("no gold spans located", file=sys.stderr)
        return 1

    print(f"Gold-Claims:  {len(gold)}")
    print(f"Live-Claims:  {len(live)}")
    coverage = semantic.get("coverage")
    if coverage:
        print(f"Live-Rate:    {coverage['ratio']:.2f}  ({len(coverage['gaps'])} Lücken)")
    print()

    results = {}
    for threshold in OVERLAP_THRESHOLDS:
        found = [
            proposal_id
            for proposal_id, span, _ in gold
            if covered_characters(span, union) / max(1, span[1] - span[0]) >= threshold
        ]
        results[threshold] = found
        print(f"Recall @ {threshold:.0%} Span-Überlappung: "
              f"{len(found)}/{len(gold)} = {len(found) / len(gold):.0%}")
    print()

    strict = set(results[max(OVERLAP_THRESHOLDS)])
    missed = [
        (proposal_id, span, raw) for proposal_id, span, raw in gold if proposal_id not in strict
    ]
    if missed:
        # The covered fraction separates two different failures that the pass
        # counts alone cannot tell apart: a passage the extraction never
        # reached, and one it reached into without working through. The first
        # is a missing claim, the second an unfinished one, and they call for
        # different fixes.
        print(f"Nicht gefunden ({len(missed)}, bei {max(OVERLAP_THRESHOLDS):.0%}):")
        for proposal_id, span, raw in missed:
            share = covered_characters(span, union) / max(1, span[1] - span[0])
            print(f"  {proposal_id}  [{share:.0%} verankert]  {raw[:80]}")
        untouched = sum(
            1
            for _, span, _ in missed
            if covered_characters(span, union) / max(1, span[1] - span[0]) < 0.5
        )
        print()
        print(
            f"  davon gar nicht erreicht (unter 50 %): {untouched} von {len(missed)} — "
            f"der Rest ist angefasst, aber nicht ausgeschöpft"
        )
    else:
        print("Alle Gold-Claims erreicht.")

    unmatched = sum(
        1
        for span in live
        if not any(
            covered_characters(gold_span, [list(span)]) / max(1, gold_span[1] - gold_span[0]) >= 0.5
            for _, gold_span, _ in gold
        )
    )
    print()
    print(f"Live-Claims ohne Gold-Entsprechung: {unmatched} "
          f"(nicht zwingend falsch — das Gold-Packet ist nicht erschöpfend)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
