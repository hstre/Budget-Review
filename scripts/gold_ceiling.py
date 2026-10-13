"""What the gold answer scores against itself, and why that is not a ceiling.

Recall is measured against the union of the live anchors, so the reference can
only be reached as far as the gate can anchor it. On the legal corpus that
distinction did not matter — feeding the gold spans back in as an extraction
admitted all of them and scored every span. On argument-annotated papers it
matters a great deal: the components are clause-sized, a median of 33
characters, and the same fragment occurs several times in a paper. The gate then
collapses two gold spans with identical wording into one content address, and
anchors an ambiguous span at its first occurrence, so the gold answer scores 85
per cent against itself.

**It is not an upper bound, and calling it a ceiling was wrong.** A repair run
later reached 210 of 219 on A24 where this reports 186. Feeding the gold spans
back as claims is a pathological input for a content-addressed gate: identical
short fragments collapse into one node, so the gold answer loses spans to
itself. A real extraction writes sentence-sized claims, covers several short
gold fragments with one of them, and never hits that collision.

What the number does say is how much of a reference consists of repeated
fragments — a diagnostic worth printing before a paid run, and the reason recall
on such a corpus is not comparable to recall on one whose spans are unique. Read
it as a property of the reference, never as the score an extraction could not
exceed.

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

# Several thresholds rather than one. What counts as a reached span is a
# condition of this diagnostic and not a property of the reference, and on a
# long court decision it decides half the spans (arXiv 2610.13476). Stating one
# number would hide which of the two the figure is about.
SWEEP = (0.5, 0.8, 0.95)


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
    shares = [
        recall.covered_characters(span, union) / max(1, span[1] - span[0])
        for _, span, _ in located
    ]
    reached = recall.hits_by_threshold(shares, SWEEP)
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
    spans = max(1, result["spans"])
    print("Was die Referenz gegen sich selbst erreicht, je Schwelle:")
    for threshold in SWEEP:
        reached = result["reached"][threshold]
        print(f"  bei {threshold:>4.0%}: {reached}/{result['spans']} = {reached / spans:.0%}")
    values = list(result["reached"].values())
    if max(values) == min(values):
        print("  → Die Schwelle entscheidet hier nichts.")
    else:
        print(f"  → Die Schwelle bewegt {max(values) - min(values)} Spannen. Die Zahl ist")
        print("    eine Aussage über Referenz *und* Zuordnungsregel, nicht über")
        print("    die Referenz allein.")
    print(f"  Gate laesst zu:  {result['admitted']}/{result['spans']}")
    print(f"  mehrdeutig:      {result['ambiguous']}")
    for reason, count in sorted(result["rejections"].items()):
        print(f"  {reason}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
