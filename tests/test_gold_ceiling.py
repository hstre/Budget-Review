"""The measurement ceiling, checked where it would otherwise flatter a run.

Recall is scored against the union of live anchors, so a gold reference the gate
cannot fully anchor is not fully reachable. On clause-sized annotations that is
not a corner case: identical fragments collapse into one content address, and an
ambiguous span is anchored at its first occurrence. A run reported without that
number would look worse than it is, by an amount nobody had measured.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "gold_ceiling", ROOT / "scripts" / "gold_ceiling.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ceiling = _module()
DOCUMENT = "The method is fast. The method is fast again, and the result is new."


def _gold(*spans: str) -> dict:
    claims = []
    for index, text in enumerate(spans, start=1):
        begin = DOCUMENT.index(text)
        claims.append(
            {
                "proposal_id": f"G{index:02d}",
                "raw_span": text,
                "begin": begin,
                "end": begin + len(text),
            }
        )
    return {"document_id": "d", "claims": claims}


def test_a_reference_the_gate_can_anchor_is_fully_reachable() -> None:
    result = ceiling.ceiling(_gold("The method is fast.", "the result is new"), DOCUMENT, "d")

    assert (result["reached"], result["spans"]) == (2, 2)
    assert result["rejections"] == {}


def test_two_identical_fragments_collapse_and_cost_the_ceiling() -> None:
    """Both are annotated; the content address knows only one of them."""
    gold = _gold("The method is fast", "the result is new")
    second = dict(gold["claims"][0])
    second["proposal_id"] = "G03"
    second["begin"] = DOCUMENT.index("The method is fast", 20)
    second["end"] = second["begin"] + len(second["raw_span"])
    gold["claims"].append(second)

    result = ceiling.ceiling(gold, DOCUMENT, "d")

    assert result["rejections"] == {"duplicate_claim_node": 1}
    assert result["reached"] < result["spans"]


def test_a_repeated_fragment_is_reported_as_ambiguously_anchored() -> None:
    result = ceiling.ceiling(_gold("The method is fast"), DOCUMENT, "d")

    assert result["ambiguous"] == 1
