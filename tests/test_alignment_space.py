"""The rule that decides what counts as a match, and whether it decides anything.

A recall figure is a joint property of the extraction and of a threshold that
says when a live span reaches a gold span. These tests pin the quantity that
settles whether the threshold matters: the share of gold spans whose verdict it
decides. They also pin the refusal grouping, because the decision it informs —
whether a structural decoding constraint could help — turns on one distinction,
and a grouping that blurred it would answer the wrong question.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "alignment_space", ROOT / "scripts" / "alignment_space.py"
)
alignment_space = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(alignment_space)


def test_a_fully_covered_and_an_untouched_span_are_both_outside_the_band() -> None:
    # The two settled cases. Counting either one as decided would report
    # leverage the threshold does not have.
    assert alignment_space.decision_band([0.0, 1.0]) == []


def test_a_partially_covered_span_is_in_the_band() -> None:
    assert alignment_space.decision_band([0.6]) == [0.6]


def test_the_settled_mark_is_the_strict_end_of_the_sweep_and_not_a_free_constant() -> None:
    """The invariant whose absence this file caught during its own writing.

    The mark started as 0.95 while the sweep ran to 1.0, so a span covered 98
    per cent was reported as settled and still changed sides between the last
    two thresholds. The band then understated the rule's leverage, which is the
    only thing it is for.
    """
    assert alignment_space.SETTLED_HIGH == max(alignment_space.SWEEP)


def test_the_band_excludes_a_share_the_whole_sweep_already_agrees_on() -> None:
    assert alignment_space.decision_band([max(alignment_space.SWEEP)]) == []


def test_an_empty_band_means_the_sweep_cannot_move_the_count() -> None:
    """The property the band is a shorthand for, asserted rather than trusted.

    The band is only worth reporting if it really predicts that the sweep is
    flat; otherwise it is a number that sounds like a guarantee.
    """
    settled = [0.0, 0.0, 1.0, 1.0, 0.0]
    assert alignment_space.decision_band(settled) == []
    hits = alignment_space.hits_by_threshold(settled)
    assert len(set(hits.values())) == 1


def test_a_non_empty_band_is_what_lets_the_sweep_move() -> None:
    mixed = [0.0, 0.6, 1.0]
    assert alignment_space.decision_band(mixed)
    hits = alignment_space.hits_by_threshold(mixed)
    assert max(hits.values()) > min(hits.values())


@pytest.mark.parametrize(
    "shares",
    [
        [0.0, 0.6, 1.0],
        [0.0, 0.0, 1.0, 1.0],
        [0.1, 0.4, 0.94, 0.99],
        [1.0],
        [0.0],
    ],
)
def test_the_band_and_the_swing_are_the_same_quantity(shares: list[float]) -> None:
    # Nested thresholds make these two readings of the same fact: a span the
    # rule decides is exactly a span that changes sides across the sweep. If a
    # future condition is not nested, this is the test that says so.
    hits = alignment_space.hits_by_threshold(shares)
    swing = max(hits.values()) - min(hits.values())
    assert len(alignment_space.decision_band(shares)) == swing


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("anchor not found in document", "Verankerung"),
        ("Spanne nicht gefunden", "Verankerung"),
        ("duplicate_claim_node", "Doppelknoten"),
        ("unknown claim_type: comparison", "Schema/Typ"),
        ("schema rejection", "Schema/Typ"),
    ],
)
def test_a_refusal_is_grouped_by_what_would_have_to_change(reason: str, expected: str) -> None:
    assert alignment_space.bucket_of(reason) == expected


def test_an_unrecognised_refusal_is_not_silently_called_structural() -> None:
    # The grouping exists to answer whether a structural constraint would help.
    # Folding an unknown reason into either named bucket would answer it with a
    # guess, so an unknown reason gets its own name.
    assert alignment_space.bucket_of("the provider hung up") == "sonstige"


def test_the_published_thresholds_lie_inside_the_sweep() -> None:
    # A reader has to be able to place the project's own figures in the sweep
    # rather than beside it, and 0.5 and 0.8 are the two it publishes.
    assert {0.5, 0.8} <= set(alignment_space.SWEEP)


def _case(document: str, gold_span: str, proposed: str) -> dict:
    return alignment_space.measure(
        document,
        {
            "document_id": "d",
            "claims": [{"proposal_id": "G1", "raw_span": gold_span}],
        },
        {
            "schema_version": "content-review.semantic-packet/0.2",
            "document_id": "d",
            "provenance": {
                "provider": "test",
                "model_id": "test",
                "run_id": "r" * 16,
                "prompt_hash": "0" * 64,
                "output_hash": "0" * 64,
                "temperature": 0.0,
            },
            "claims": [
                {
                    "proposal_id": "C1",
                    "claim_type": "fact",
                    "canonical_content": proposed,
                    "raw_span": proposed,
                    "confidence": 0.9,
                    "source_ref": "d",
                }
            ],
            "relations": [],
        },
    )


def test_a_claim_quoting_the_gold_span_reaches_it_at_every_threshold() -> None:
    result = _case("Alpha beta gamma delta.", "beta gamma", "beta gamma")
    assert result["decision_band"] == 0
    assert result["swing"] == 0
    assert result["hits"]["1.0"] == 1


def test_a_claim_quoting_half_the_gold_span_lands_in_the_band() -> None:
    result = _case("Alpha beta gamma delta.", "beta gamma", "beta")
    assert result["decision_band"] == 1
    assert result["swing"] >= 1
    # Reached at the loose end of the sweep and missed at the strict end: that
    # is the whole of what "the threshold decides it" means.
    assert result["hits"]["0.05"] == 1
    assert result["hits"]["1.0"] == 0


def test_a_claim_the_document_does_not_contain_is_refused_not_scored() -> None:
    result = _case("Alpha beta gamma delta.", "beta gamma", "epsilon zeta")
    assert result["admitted_claims"] == 0
    assert result["refusals"].get("Verankerung") == 1
    assert result["unreached"] == 1


def test_a_case_with_no_locatable_gold_is_an_error_rather_than_a_zero() -> None:
    # Scoring against nothing would report a clean 0 of 0, which reads like a
    # measurement instead of a broken fixture.
    with pytest.raises(ValueError):
        alignment_space.measure("Alpha.", {"document_id": "d", "claims": []}, {})


def test_the_json_payload_carries_the_band_and_the_swing() -> None:
    result = _case("Alpha beta gamma delta.", "beta gamma", "beta")
    round_tripped = json.loads(json.dumps(result))
    assert round_tripped["decision_band"] == result["decision_band"]
    assert round_tripped["swing"] == result["swing"]
