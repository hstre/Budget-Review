"""The sweep's scoring, checked against an answer that is known in advance.

The sweep exists to tell a prompt effect from a document effect, which only
works if the score itself is trustworthy. It runs each packet through the real
gate, so a mistake here would mis-score every arm at once and in the same
direction — the kind of error that leaves the comparison looking sensible.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "src" / "budget_review" / "fixtures" / "coherence_theatre"


def _module():
    spec = importlib.util.spec_from_file_location("sweep", ROOT / "scripts" / "prompt_sweep.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sweep = _module()


@pytest.fixture
def case() -> tuple[str, dict, list]:
    document = (FIXTURES / "proposal.md").read_text(encoding="utf-8")
    packet = json.loads((FIXTURES / "semantic_packet.json").read_text(encoding="utf-8"))
    return document, packet, sweep.recall.gold_spans(packet, document)


def _as_packet(claims: list[dict]) -> dict:
    return {
        "schema_version": "content-review.semantic-packet/0.2",
        "document_id": "regional-skills-bridge",
        "provenance": {
            "provider": "gold",
            "model_id": "m",
            "run_id": "r" * 16,
            "prompt_hash": "a" * 64,
            "output_hash": "b" * 64,
            "temperature": 0.0,
        },
        "claims": claims,
        "relations": [],
    }


def test_the_gold_answer_scores_every_span(case) -> None:
    document, packet, gold = case

    found, admitted = sweep.score(_as_packet(packet["claims"]), document, gold)

    assert found == len(gold)
    assert admitted == len(packet["claims"])


def test_withholding_claims_lowers_the_score_by_exactly_that_many(case) -> None:
    document, packet, gold = case

    found, admitted = sweep.score(_as_packet(packet["claims"][:12]), document, gold)

    assert found == 12
    assert admitted == 12


def test_a_span_the_document_does_not_contain_is_not_counted(case) -> None:
    """The gate refuses to anchor it, so it must not reach the score either."""
    document, packet, gold = case
    invented = dict(packet["claims"][0])
    invented["raw_span"] = "This sentence appears nowhere in the proposal."

    found, admitted = sweep.score(_as_packet([invented]), document, gold)

    assert (found, admitted) == (0, 0)
