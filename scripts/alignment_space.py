"""Does the rule that decides what counts as a match move the answer more than the answer does?

A recall figure is not a property of the extraction alone. Before any span is
counted, a rule has already decided when a live span *matches* a gold span, and
this project's rule is one number: a share of the gold span's characters that
some admitted claim has to cover. It was set to 0.8 once and never declared as a
condition. `measure_recall.py` reports two values, and `compare_runs.py` and
`gold_ceiling.py` carried one hard-coded.

arXiv 2610.13476 is the general form of the worry: in a comparison of
representations, the composition of the compared space moved the measured
distance by 2.5 times the effect under study, while the number of categories
moved it hardly at all. The authors' recommendation is to disclose the condition
space and compute its admissible variants rather than argue about the metric.

This script computes that variant space for our one condition, and it reports the
quantity that decides whether the worry applies at all: **the share of gold spans
whose verdict the threshold actually decides.** A gold span covered to 0 per cent
or to 100 per cent is counted the same way at every threshold; only a partially
covered span can change sides. If that band is empty, the threshold is free of
consequence and a sweep is wasted effort — and that is a measurement, not an
assumption.

It also reports two things that come from the same pass and cost nothing extra:

* the recall and anchored share a stored proposal packet reaches through today's
  gate, which is the re-run §4.4 left open — the question there was whether the
  gold-free warning light still orders documents once anchoring is repaired;
* which refusal reason dominates, because a structural decoding constraint
  (arXiv 2610.13896) can only help with refusals that are structural.

Nothing here calls a provider. Every figure comes from a stored artifact and the
gate in the working tree.

Usage:
    alignment_space.py <document> <gold-packet.json> <proposal-packet.json>
    alignment_space.py ... --json OUT
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from budget_review.gate import govern_packet  # noqa: E402
from budget_review.models import SemanticPacket  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "recall", Path(__file__).resolve().parent / "measure_recall.py"
)
recall = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recall)

# The variants of the one condition this comparison space has. The two the
# project already reports sit inside it, so a reader can place the published
# figures in the sweep rather than next to it.
SWEEP = (0.05, 0.25, 0.5, 0.8, 0.95, 1.0)

# A gold span covered this far counts as reached under every threshold in the
# sweep, and one covered 0 per cent counts as missed under every one. Only what
# lies between them is decided by the rule rather than by the extraction.
#
# It is derived from the sweep and must not be an independent constant. An
# earlier version set it to 0.95 while the sweep ran to 1.0, so a span covered
# 98 per cent was called settled and still changed sides between the last two
# thresholds — the band then under-reported the rule's leverage, which is the
# one thing it exists to state. A test holds the two together.
SETTLED_HIGH = max(SWEEP)

REFUSAL_BUCKETS = (
    ("Verankerung", ("anchor", "span", "not found", "nicht gefunden")),
    ("Doppelknoten", ("duplicate",)),
    ("Schema/Typ", ("schema", "type", "typ")),
)


def bucket_of(reason: str) -> str:
    """Group a refusal by what would have to change to prevent it.

    The buckets are coarse on purpose. The decision they inform is whether a
    structural constraint during decoding could have helped, and that turns on
    one distinction: a refusal is structural when the proposal violates the
    schema, and it is not when the proposal quotes text the document does not
    contain. No finer grouping changes that answer.
    """
    folded = reason.lower()
    for name, needles in REFUSAL_BUCKETS:
        if any(needle in folded for needle in needles):
            return name
    return "sonstige"


def covered_shares(
    gold: list[tuple[str, tuple[int, int], str]], union: list[list[int]]
) -> list[tuple[str, float]]:
    """How much of each gold span some admitted claim covers."""
    return [
        (proposal_id, recall.covered_characters(span, union) / max(1, span[1] - span[0]))
        for proposal_id, span, _ in gold
    ]


def decision_band(shares: list[float]) -> list[float]:
    """The gold spans whose verdict the threshold decides, rather than the extraction.

    Zero is excluded and so is a share at or above `SETTLED_HIGH`: those are
    reached under none of the thresholds, or under all of them, so the rule has
    no say in either case. What remains is the leverage the condition has, and
    it is the number to read before any sweep.

    Because the thresholds are nested, the size of this band is also the number
    of spans the published figure could move — the two are the same quantity
    seen from either end, and a test pins that they agree. The band is still
    worth reporting separately: as a share of the reference it says how much of
    the comparison the rule governs, which a swing in spans does not.
    """
    return [share for share in shares if 0.0 < share < SETTLED_HIGH]


def hits_by_threshold(shares: list[float]) -> dict[float, int]:
    """This script's sweep applied to `measure_recall`'s one counting function."""
    return recall.hits_by_threshold(shares, SWEEP)


def measure(document: str, gold_packet: dict, proposals: dict) -> dict:
    """Everything one stored case yields, in one pass over the governed packet."""
    gold = recall.gold_spans(gold_packet, document)
    if not gold:
        raise ValueError("no gold spans located")
    packet = SemanticPacket.from_dict(proposals)
    dossier = govern_packet(document, packet)
    union = recall.merged([(c.anchor_start, c.anchor_end) for c in dossier.claims])
    shares = [share for _, share in covered_shares(gold, union)]
    hits = hits_by_threshold(shares)
    refusals = collections.Counter(
        bucket_of(r.reason) for r in dossier.rejections if r.item_kind == "claim"
    )
    return {
        "gold_spans": len(gold),
        "proposed_claims": len(packet.claims),
        "admitted_claims": len(dossier.claims),
        "anchored_share": dossier.coverage.ratio,
        "hits": {str(t): n for t, n in hits.items()},
        "swing": max(hits.values()) - min(hits.values()),
        "decision_band": len(decision_band(shares)),
        "unreached": sum(1 for s in shares if s == 0.0),
        "settled_reached": sum(1 for s in shares if s >= SETTLED_HIGH),
        "refusals": dict(refusals),
    }


def report(name: str, result: dict) -> None:
    gold = result["gold_spans"]
    print(
        f"{name}  —  {gold} Gold-Spannen, {result['proposed_claims']} Vorschläge, "
        f"{result['admitted_claims']} zugelassen, "
        f"verankerter Anteil {result['anchored_share']:.2f}"
    )
    print()
    print("  Schwelle:  " + "  ".join(f"{t:>5.0%}" for t in SWEEP))
    print("  erreicht:  " + "  ".join(f"{result['hits'][str(t)]:>5}" for t in SWEEP))
    print(f"  Spanne:    {result['swing']} von {gold} Spannen")
    print()
    band = result["decision_band"]
    print(f"  Entscheidungsband:   {band} von {gold} = {band / gold:.0%}")
    print(f"    davon 0 % erreicht: {result['unreached']}")
    print(f"    davon >= {SETTLED_HIGH:.0%} erreicht: {result['settled_reached']}")
    if band == 0:
        print("    → Die Schwelle entscheidet hier nichts. Jede Spanne ist entweder")
        print("      gar nicht oder praktisch vollständig verankert.")
    else:
        print("    → Die Schwelle entscheidet mit. Ein Recall-Wert ohne sie ist")
        print("      unvollständig angegeben.")
    if result["refusals"]:
        print()
        total = sum(result["refusals"].values())
        print(f"  Abgelehnte Claims: {total}")
        for reason, count in sorted(result["refusals"].items(), key=lambda kv: -kv[1]):
            print(f"    {count:>4}  {reason}  ({count / total:.0%})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("gold_packet", type=Path)
    parser.add_argument("proposal_packet", type=Path)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    result = measure(
        args.document.read_text(encoding="utf-8"),
        json.loads(args.gold_packet.read_text(encoding="utf-8")),
        json.loads(args.proposal_packet.read_text(encoding="utf-8")),
    )
    report(args.document.stem, result)
    if args.json:
        args.json.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        print(f"\n{args.json} geschrieben")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
