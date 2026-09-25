"""What a gate that tolerated typesetting would have scored on runs already paid for.

Whitespace-tolerant anchoring exists in the repair pass and is off by default,
because whether it changes recall rather than merely admission had never been
measured. It can be measured without a single new call: the packets of finished
runs are on disk, the gate is local, and the recall measurement is local. This
re-gates a packet twice — as it was, and with every span that differs from the
document only in whitespace replaced by the document's own slice — and reports
both figures.

The replacement is the one the repair pass already makes: the document's text,
never the model's wording, so an amended claim still quotes the source exactly.
A span the document does not contain apart from whitespace is left alone and
stays rejected; this measures tolerance of typesetting, not of paraphrase.

What it cannot say: the model is not asked again, so this is what the same
proposals would have scored under a different gate, not what a run under that
gate would produce. Second-order effects — a coverage measurement that reports
different gaps, a repair pass that is therefore asked about different passages —
are outside it.

Usage:
    gate_counterfactual.py <packet.json> <document.txt> <gold-packet.json>
"""

from __future__ import annotations

import argparse
import copy
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


repair = _load("repair_extract")
recall = _load("measure_recall")

from budget_review.gate import govern_packet  # noqa: E402
from budget_review.models import SemanticPacket  # noqa: E402

EXPERIMENT_KEYS = ("claim_rejections", "relation_rejections")


def amended(packet: dict, document: str) -> tuple[dict, int]:
    """A copy whose whitespace-only spans carry the document's text instead.

    The original is never touched: an amendment that also moved the baseline
    would compare the tolerance against itself.
    """
    copied = copy.deepcopy(packet)
    replaced = 0
    for claim in copied["claims"]:
        if claim["raw_span"] in document:
            continue
        slice_ = repair.relaxed_span(document, claim["raw_span"])
        if slice_ is None:
            continue
        claim["raw_span"] = slice_
        replaced += 1
    return copied, replaced


def scored(packet: dict, document: str, gold: list) -> tuple[int, int, int]:
    """Admitted claims, anchoring rejections, and gold spans reached at 80 %."""
    stripped = {k: v for k, v in packet.items() if k not in EXPERIMENT_KEYS}
    dossier = govern_packet(document, SemanticPacket.from_dict(stripped)).to_dict()
    union = recall.merged([(c["anchor_start"], c["anchor_end"]) for c in dossier["claims"]])
    reached = [
        proposal_id
        for proposal_id, span, _ in gold
        if recall.covered_characters(span, union) / max(1, span[1] - span[0]) >= 0.8
    ]
    refused = sum(
        1
        for r in dossier["rejections"]
        if r["item_kind"] == "claim" and r["reason"] == "source_span_not_found"
    )
    return len(dossier["claims"]), refused, len(reached)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("document", type=Path)
    parser.add_argument("gold_packet", type=Path)
    args = parser.parse_args()

    document = args.document.read_text(encoding="utf-8")
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    gold = recall.gold_spans(json.loads(args.gold_packet.read_text(encoding="utf-8")), document)
    if not gold:
        print("no gold spans located", file=sys.stderr)
        return 1

    tolerant, replaced = amended(packet, document)
    for label, candidate in (("wie gemessen", packet), ("mit Leerraum-Toleranz", tolerant)):
        claims, refused, reached = scored(candidate, document, gold)
        print(
            f"{label:22} Claims {claims:4}  Anker abgelehnt {refused:3}  "
            f"Recall@80 {reached}/{len(gold)} = {reached / len(gold):.0%}"
        )
    print(f"{replaced} Spannen über Leerraum ersetzt, je durch die Textstelle des Dokuments")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
