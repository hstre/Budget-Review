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

import argparse
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


def shares(
    gold: list[tuple[str, tuple[int, int], str]], union: list[list[int]]
) -> list[tuple[str, float, int]]:
    """Covered share and length per gold span, most covered first."""
    return sorted(
        (
            (
                proposal_id,
                covered_characters(span, union) / max(1, span[1] - span[0]),
                span[1] - span[0],
            )
            for proposal_id, span, _ in gold
        ),
        key=lambda row: -row[1],
    )


def knife_edge(
    rows: list[tuple[str, float, int]], threshold: float, margin: float = 0.05
) -> list[tuple[str, float]]:
    """Spans whose verdict a small change in coverage would flip.

    A pass count is only worth as much as its distance from the threshold. If
    the spans cluster just above and just below it, the number moves with any
    change to how the extractor splits a sentence, and comparing two runs by it
    measures the splitting rather than what reached the graph.
    """
    # The tolerance is for binary floats, not for the band: 0.8 - 0.75 is
    # 0.05000000000000004, so an exact edge would fall out of its own band.
    return [
        (proposal_id, share)
        for proposal_id, share, _ in rows
        if abs(share - threshold) <= margin + 1e-9
    ]


def actor_spans(packet: dict, document: str) -> list[tuple[str, tuple[int, int]]]:
    """The gold spans that name who is speaking, with their offsets.

    The ECHR annotation records an actor per span — applicant, Government,
    Court. That makes a property testable that the claim contract never asked
    for: whether an anchor stays inside one speaker.
    """
    located = []
    for claim in packet["claims"]:
        actor = claim.get("actor")
        begin, end = claim.get("begin"), claim.get("end")
        if not actor or begin is None or end is None:
            continue
        if document[begin:end] != claim["raw_span"]:
            continue
        located.append((actor, (begin, end)))
    return located


def boundary_crossings(
    live: list[tuple[int, int]],
    actors: list[tuple[str, tuple[int, int]]],
    tolerance: int = 10,
) -> list[tuple[tuple[int, int], list[str]]]:
    """Live anchors that reach into more than one speaker's text.

    A claim spanning the Government's submission and the Court's reply merges
    two epistemic positions into one node, and no downstream check can take
    them apart again — the anchor is the only record of who said it. Overlaps
    below the tolerance are ignored: a few characters of a neighbouring span
    are an off-by-a-clause, not a merged speaker.
    """
    crossings = []
    for span in live:
        reached = {
            actor
            for actor, actor_span in actors
            if covered_characters(actor_span, [list(span)]) >= tolerance
        }
        if len(reached) > 1:
            crossings.append((span, sorted(reached)))
    return crossings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dossier", type=Path)
    parser.add_argument("gold_packet", type=Path)
    parser.add_argument("document", type=Path)
    parser.add_argument(
        "--watch",
        default="",
        help="comma-separated gold ids to report separately, e.g. the hard cases",
    )
    args = parser.parse_args()
    dossier = json.loads(args.dossier.read_text(encoding="utf-8"))
    packet = json.loads(args.gold_packet.read_text(encoding="utf-8"))
    document = args.document.read_text(encoding="utf-8")

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
        print(
            f"Recall @ {threshold:.0%} Span-Überlappung: "
            f"{len(found)}/{len(gold)} = {len(found) / len(gold):.0%}"
        )
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

    strict_threshold = max(OVERLAP_THRESHOLDS)
    rows = shares(gold, union)
    print()
    print("Deckungsanteil je Gold-Spanne (Zeichen):")
    for proposal_id, share, length in rows:
        mark = "+" if share >= strict_threshold else " "
        print(f"  {mark} {proposal_id}  {share:6.0%}  {length:>5}")
    edge = knife_edge(rows, strict_threshold)
    print()
    print(
        f"  im Grenzband um {strict_threshold:.0%} (+/- 5 Punkte): {len(edge)} von {len(rows)}"
        f"{'  ' + ' '.join(pid for pid, _ in edge) if edge else ''}"
    )

    watched = [name.strip() for name in args.watch.split(",") if name.strip()]
    if watched:
        by_id = {proposal_id: share for proposal_id, share, _ in rows}
        print()
        print("Beobachtete Spannen (Anteil, nicht bestanden/verfehlt):")
        for name in watched:
            # A hard case is scored by its covered share rather than by the
            # threshold it fails: four binary items move with any run, while
            # the share shows whether a change reached the passage at all.
            share = by_id.get(name)
            print(f"  {name}  {'--' if share is None else format(share, '.0%')}")

    actors = actor_spans(packet, document)
    if actors:
        crossings = boundary_crossings(live, actors)
        print()
        print(f"Anker über eine Sprechergrenze hinweg: {len(crossings)} von {len(live)}")
        for span, reached in crossings[:5]:
            print(f"  [{span[0]}:{span[1]}]  {' + '.join(reached)}")

    unmatched = sum(
        1
        for span in live
        if not any(
            covered_characters(gold_span, [list(span)]) / max(1, gold_span[1] - gold_span[0]) >= 0.5
            for _, gold_span, _ in gold
        )
    )
    print()
    print(
        f"Live-Claims ohne Gold-Entsprechung: {unmatched} "
        f"(nicht zwingend falsch — das Gold-Packet ist nicht erschöpfend)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
