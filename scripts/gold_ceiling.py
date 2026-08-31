"""What a perfect extraction would score against a gold reference.

Recall is measured against the union of the live anchors, so the reference can
only be reached as far as the gate can anchor it. On the legal corpus that
distinction did not matter — feeding the gold spans back in as an extraction
admitted all of them and scored every span. On argument-annotated papers it
matters a great deal: the components are clause-sized, a median of 33
characters, and the same fragment occurs several times in a paper. The gate then
collapses two gold spans with identical wording into one content address, and
anchors an ambiguous span at its first occurrence, so the gold answer scores 85
per cent against itself.

That ceiling is a property of the reference, not of the extractor. Reporting a
raw recall figure against such a corpus would understate the extraction by
whatever the ceiling withholds, which is why this runs before the paid call and
prints the number the run should be read against.

Usage:
    gold_ceiling.py <gold-packet.json> <document>
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


recall = _load("measure_recall")

from budget_review.gate import govern_packet  # noqa: E402
from budget_review.models import SemanticPacket  # noqa: E402

THRESHOLD = 0.8


def as_packet(gold: dict, document_id: str) -> dict:
    """The gold spans as if an extractor had proposed exactly them."""
    return {
        "schema_version": "content-review.semantic-packet/0.2",
        "document_id": document_id,
        "provenance": {
            "provider": "gold",
            "model_id": "gold",
            "run_id": "g" * 16,
            "prompt_hash": "0" * 64,
            "output_hash": "0" * 64,
            "temperature": 0.0,
        },
        "claims": [
            {
                "proposal_id": claim["proposal_id"],
                "claim_type": "fact",
                "canonical_content": claim["raw_span"],
                "raw_span": claim["raw_span"],
                "confidence": 0.9,
                "source_ref": document_id,
            }
            for claim in gold["claims"]
        ],
        "relations": [],
    }


def ceiling(gold: dict, document: str, document_id: str) -> dict:
    """Score the gold answer against itself through the real gate."""
    semantic = govern_packet(document, SemanticPacket.from_dict(as_packet(gold, document_id)))
    union = recall.merged([(c.anchor_start, c.anchor_end) for c in semantic.claims])
    located = recall.gold_spans(gold, document)
    reached = sum(
        1
        for _, span, _ in located
        if recall.covered_characters(span, union) / max(1, span[1] - span[0]) >= THRESHOLD
    )
    return {
        "spans": len(located),
        "admitted": len(semantic.claims),
        "reached": reached,
        "ambiguous": sum(1 for claim in semantic.claims if claim.anchor_ambiguous),
        "rejections": dict(Counter(rejection.reason for rejection in semantic.rejections)),
    }


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    gold = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    document = Path(sys.argv[2]).read_text(encoding="utf-8")
    result = ceiling(gold, document, gold.get("document_id", "gold"))
    print(
        f"Decke der Messung: {result['reached']}/{result['spans']} = "
        f"{result['reached'] / max(1, result['spans']):.0%}"
    )
    print(f"  Gate laesst zu:  {result['admitted']}/{result['spans']}")
    print(f"  mehrdeutig:      {result['ambiguous']}")
    for reason, count in sorted(result["rejections"].items()):
        print(f"  {reason}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
