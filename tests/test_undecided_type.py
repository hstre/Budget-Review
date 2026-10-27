"""The extraction contract's way of declining, and what reads it.

§4.13 measured that two defensible labels for one sentence means there is no
fact of the matter, and §4.20 measured what a closed vocabulary without a way
to decline does: the model picks one, and the dossier records a decision the
document never made. The contract now offers `undecided` with named candidates.

The invariants are refusals rather than repairs, because both failure modes are
worse than a schema error: `undecided` without candidates lets an extractor
decline everything and say nothing, and a committed label carrying candidates is
two answers at once.
"""

from __future__ import annotations

import pytest

from budget_review.checks import LOGICAL_GAP_TYPES, deterministic_checks
from budget_review.gate import govern_packet
from budget_review.models import (
    ClaimProposal,
    ClaimType,
    ReviewDossier,
    SchemaError,
    SemanticPacket,
)
from budget_review.prompts import CLAIM_TYPES, extraction_prompt
from budget_review.render import render_markdown

BASE = {
    "proposal_id": "C01",
    "claim_type": "target",
    "canonical_content": "Eine Aussage.",
    "raw_span": "Eine Aussage.",
    "confidence": 0.9,
    "source_ref": "doc",
}


def _claim(**overrides) -> dict:
    return BASE | overrides


def test_a_committed_label_still_parses():
    claim = ClaimProposal.from_dict(_claim())
    assert claim.claim_type is ClaimType.TARGET
    assert claim.candidate_types == ()


def test_an_undecided_label_carries_its_candidates():
    claim = ClaimProposal.from_dict(
        _claim(claim_type="undecided", candidate_types=["target", "forecast"])
    )
    assert claim.claim_type is ClaimType.UNDECIDED
    assert claim.candidate_types == (ClaimType.TARGET, ClaimType.FORECAST)


def test_undecided_without_candidates_is_refused():
    """Otherwise declining everything would cost nothing and say nothing."""
    with pytest.raises(SchemaError, match="needs candidate_types"):
        ClaimProposal.from_dict(_claim(claim_type="undecided"))


def test_undecided_with_one_candidate_is_refused():
    with pytest.raises(SchemaError, match="at least two"):
        ClaimProposal.from_dict(
            _claim(claim_type="undecided", candidate_types=["target"])
        )


def test_a_committed_label_may_not_carry_candidates():
    with pytest.raises(SchemaError, match="only for claim_type undecided"):
        ClaimProposal.from_dict(_claim(candidate_types=["target", "forecast"]))


def test_an_empty_candidate_list_is_the_same_as_none():
    # to_dict emits the empty tuple, so a committed claim has to round-trip.
    claim = ClaimProposal.from_dict(_claim(candidate_types=[]))
    assert claim.candidate_types == ()


def test_undecided_cannot_be_its_own_candidate():
    with pytest.raises(SchemaError, match="its own candidate"):
        ClaimProposal.from_dict(
            _claim(claim_type="undecided", candidate_types=["undecided", "target"])
        )


def test_a_repeated_candidate_counts_once_and_then_fails_the_minimum():
    with pytest.raises(SchemaError, match="at least two"):
        ClaimProposal.from_dict(
            _claim(claim_type="undecided", candidate_types=["target", "target"])
        )


def test_an_unknown_candidate_is_refused():
    with pytest.raises(SchemaError, match="unknown candidate type"):
        ClaimProposal.from_dict(
            _claim(claim_type="undecided", candidate_types=["target", "conclusion"])
        )


def test_candidates_must_be_a_list():
    with pytest.raises(SchemaError, match="must be a list"):
        ClaimProposal.from_dict(_claim(claim_type="undecided", candidate_types="target"))


def test_the_contract_offers_the_value_and_says_when_to_use_it():
    system, _ = extraction_prompt("doc", "text")
    assert "undecided" in CLAIM_TYPES
    assert "candidate_types" in system
    assert "two defensible labels" in system


def test_the_round_trip_keeps_the_candidates():
    claim = ClaimProposal.from_dict(
        _claim(claim_type="undecided", candidate_types=["target", "forecast"])
    )
    again = ClaimProposal.from_dict(
        _claim(
            claim_type=claim.claim_type.value,
            candidate_types=[kind.value for kind in claim.candidate_types],
        )
    )
    assert again == claim


# ── what reads it ────────────────────────────────────────────────────────────


DOCUMENT = "Alle Standorte sollen den Abruf melden. Die Quote steigt auf neunzig Prozent."
SPAN = "Alle Standorte sollen den Abruf melden."


def _governed(claim_type: str, candidates: list[str] | None = None):
    claim = {
        "proposal_id": "C01",
        "claim_type": claim_type,
        "canonical_content": SPAN,
        "raw_span": SPAN,
        "confidence": 0.9,
        "source_ref": "synthetic",
    }
    if candidates is not None:
        claim["candidate_types"] = candidates
    packet = SemanticPacket.from_dict(
        {
            "schema_version": "content-review.semantic-packet/0.2",
            "document_id": "synthetic",
            "provenance": {
                "provider": "deepseek",
                "model_id": "deepseek-v4-flash",
                "run_id": "run-1",
                "prompt_hash": "a" * 16,
                "output_hash": "b" * 16,
            },
            "claims": [claim],
            "relations": [],
        }
    )
    return govern_packet(DOCUMENT, packet)


def _review(semantic):
    return ReviewDossier(
        schema_version="content-review.review-dossier/0.2",
        semantic=semantic,
        findings=(),
        review_rejections=(),
        profile="general",
    )


def test_the_rule_fires_on_a_committed_label():
    """The control: without it, the test below would prove nothing."""
    assert "recommendation" in {kind.value for kind in LOGICAL_GAP_TYPES}
    findings = deterministic_checks(_governed("recommendation"), "general")
    assert any(item.category.value == "logical_gap" for item in findings)


def test_the_rule_does_not_fire_on_a_label_the_extractor_declined():
    """A finding keyed on a label may not stand on one the document never gave."""
    findings = deterministic_checks(
        _governed("undecided", ["recommendation", "target"]), "general"
    )
    assert not any(item.category.value == "logical_gap" for item in findings)


def test_the_gate_carries_the_candidates_into_the_dossier():
    semantic = _governed("undecided", ["recommendation", "target"])
    assert semantic.claims[0].candidate_types == (
        ClaimType.RECOMMENDATION,
        ClaimType.TARGET,
    )


def test_a_reader_is_told_the_type_was_left_open():
    dossier = _review(_governed("undecided", ["recommendation", "target"]))
    page = render_markdown(dossier, language="de")
    assert "Typ nicht entschieden zwischen" in page
    assert "recommendation" in page
    english = render_markdown(dossier, language="en")
    assert "type left undecided between" in english


def test_a_committed_claim_gets_no_note():
    dossier = _review(_governed("recommendation"))
    assert "Typ nicht entschieden" not in render_markdown(dossier, language="de")
