"""A finding says what its trigger rests on, and the dossier shows it.

The computation is deterministic; its inputs are not all equally knowable. Two
shipped rules fire on a claim type the extraction contract never defines, and
`anchor_ambiguous` is the precedent for why a flag that nothing renders is not a
safeguard — so these tests cover the table, the finding and both renderers.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from budget_review.anti_delphi import review_claim_graph
from budget_review.checks import (
    _MESSAGES,
    LOGICAL_GAP_TYPES,
    TRIGGER_RESTS_ON,
    UNSUPPORTED_ASSUMPTION_TYPE,
    deterministic_checks,
)
from budget_review.gate import govern_packet
from budget_review.models import SemanticPacket
from budget_review.render import _TEXT, render_html, render_markdown

KINDS = {"document", "content", "relation_type", "claim_type"}


def test_every_rule_declares_what_its_trigger_rests_on() -> None:
    # The point of the table: a rule cannot be added without saying this.
    assert set(TRIGGER_RESTS_ON) == set(_MESSAGES)


def test_no_rule_declares_an_unknown_kind_of_input() -> None:
    for key, rests_on in TRIGGER_RESTS_ON.items():
        assert rests_on, key
        assert set(rests_on) <= KINDS, (key, rests_on)


def test_the_marker_discriminates_rather_than_being_constant() -> None:
    # If every rule rested on a label the field would carry no information.
    label_keyed = {k for k, v in TRIGGER_RESTS_ON.items() if "claim_type" in v}
    assert label_keyed == {"logical_gap", "unsupported_assumption"}
    assert TRIGGER_RESTS_ON["coverage_gap"] == ("document",)


def test_the_hoisted_type_sets_are_the_ones_the_rules_use() -> None:
    # They exist so the measurement script imports them instead of restating
    # them; if a rule stopped using them the script would drift silently.
    assert {t.value for t in LOGICAL_GAP_TYPES} == {"thesis", "inference", "recommendation"}
    assert UNSUPPORTED_ASSUMPTION_TYPE.value == "assumption"


def test_a_finding_carries_its_trigger_provenance(controlled_semantic) -> None:
    findings = deterministic_checks(controlled_semantic, "budget")
    assert findings
    for finding in findings:
        assert finding.trigger_rests_on == TRIGGER_RESTS_ON[_key_of(finding)]


def _key_of(finding):
    """The message key behind a finding, found by its rendered summary."""
    for key, messages in _MESSAGES.items():
        if messages["de"][0] == finding.summary or messages["en"][0] == finding.summary:
            return key
    raise AssertionError(f"no message key for {finding.summary!r}")


def test_the_provenance_reaches_the_dossier_json(controlled_semantic) -> None:
    # A reflection run reads the JSON, not the dataclass.
    dossier = review_claim_graph(controlled_semantic, profile="budget")
    data = dossier.to_dict()
    assert any(finding["trigger_rests_on"] for finding in data["findings"])


def test_a_reviewers_own_finding_claims_no_trigger_provenance(controlled_semantic) -> None:
    # An LLM reviewer reasons over the whole graph; pretending otherwise would
    # be a stronger statement than anything measured.
    dossier = review_claim_graph(controlled_semantic, profile="budget")
    for finding in dossier.findings:
        if finding.reviewer_kind != "deterministic":
            assert finding.trigger_rests_on == ()


# The two label-keyed rules live in `_check_general_structure`, which runs only
# for the general profile — the budget profile never reaches them. So the
# exposure to an undefined label is profile-specific, and this is the dossier
# that has it: a recommendation nothing supports.
GENERAL_DOCUMENT = "The pilot ran in one clinic. Every hospital should adopt it."


def _general_dossier():
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
            "claims": [
                {
                    "proposal_id": "C01",
                    "claim_type": "evidence",
                    "canonical_content": "The pilot ran in one clinic.",
                    "raw_span": "The pilot ran in one clinic.",
                    "confidence": 0.9,
                    "source_ref": "synthetic",
                },
                {
                    "proposal_id": "C02",
                    "claim_type": "recommendation",
                    "canonical_content": "Every hospital should adopt it.",
                    "raw_span": "Every hospital should adopt it.",
                    "confidence": 0.9,
                    "source_ref": "synthetic",
                },
            ],
            "relations": [
                {
                    "source_id": "C01",
                    "relation_type": "SCOPE_TENSION",
                    "target_id": "C02",
                    "confidence": 0.9,
                    "rationale": "structural",
                }
            ],
        }
    )
    return review_claim_graph(govern_packet(GENERAL_DOCUMENT, packet), profile="general")


def test_the_label_keyed_rules_only_run_in_the_general_profile(controlled_semantic) -> None:
    budget = deterministic_checks(controlled_semantic, "budget")
    assert budget
    assert not [f for f in budget if "claim_type" in f.trigger_rests_on]
    assert [f for f in _general_dossier().findings if "claim_type" in f.trigger_rests_on]


@pytest.mark.parametrize("language", ["de", "en"])
def test_both_renderers_show_the_caveat_for_a_label_keyed_finding(language) -> None:
    dossier = _general_dossier()
    assert [f for f in dossier.findings if "claim_type" in f.trigger_rests_on]

    expected = _TEXT[language]["trigger_claim_type"]
    assert expected in render_markdown(dossier, language)
    assert expected in render_html(dossier, language)


@pytest.mark.parametrize("language", ["de", "en"])
def test_neither_renderer_shows_the_caveat_when_no_finding_rests_on_a_label(language) -> None:
    dossier = _general_dossier()
    cleaned = replace(
        dossier,
        findings=tuple(
            replace(finding, trigger_rests_on=("content",)) for finding in dossier.findings
        ),
    )
    expected = _TEXT[language]["trigger_claim_type"]
    assert expected not in render_markdown(cleaned, language)
    assert expected not in render_html(cleaned, language)


def test_the_caveat_attaches_no_number() -> None:
    # Measured on cases of one to three sentences. Putting 8-of-24 next to a
    # finding on a 27,000-character decision would borrow precision from the
    # wrong corpus, which is the failure this repository keeps retracting.
    for language in ("de", "en"):
        caveat = _TEXT[language]["trigger_claim_type"]
        assert not any(character.isdigit() for character in caveat), caveat
