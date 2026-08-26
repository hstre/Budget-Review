from __future__ import annotations

import string
from collections import Counter

from budget_review.checks import (
    _MESSAGES,
    _Builder,
    _check_capacity,
    _check_completion_rate,
    _number,
    deterministic_checks,
)
from budget_review.gate import govern_packet
from budget_review.models import SemanticPacket


def test_control_case_finds_all_eight_known_problems(controlled_semantic) -> None:
    findings = deterministic_checks(controlled_semantic, "budget")
    assert len(findings) == 8


def test_expected_categories(controlled_semantic) -> None:
    counts = Counter(
        finding.category.value for finding in deterministic_checks(controlled_semantic, "budget")
    )
    assert counts == {
        "capacity_mismatch": 1,
        "resource_mismatch": 1,
        "arithmetic_mismatch": 2,
        "unsupported_assumption": 1,
        "budget_mismatch": 2,
        "causal_overclaim": 1,
    }


def test_expected_claim_groups_are_covered(controlled_semantic, expected_findings) -> None:
    actual = [
        (finding.category.value, set(finding.claim_ids))
        for finding in deterministic_checks(controlled_semantic, "budget")
    ]
    for expected in expected_findings:
        expected_claims = set(expected["claims"])
        assert any(
            category == expected["category"] and expected_claims <= claims
            for category, claims in actual
        )


def test_budget_total_calculation_is_exposed(controlled_semantic) -> None:
    finding = next(
        item
        for item in deterministic_checks(controlled_semantic, "budget")
        if "beantragte Gesamtsumme" in item.summary
    )
    assert "100,000" in finding.explanation
    assert "96,000" in finding.explanation


def test_fte_calculation_is_exposed(controlled_semantic) -> None:
    finding = next(
        item
        for item in deterministic_checks(controlled_semantic, "budget")
        if "FTE" in item.summary
    )
    assert "30,000" in finding.explanation
    assert "42,000" in finding.explanation


def test_findings_never_become_verdicts(controlled_semantic) -> None:
    findings = deterministic_checks(controlled_semantic, "budget")
    assert all(finding.state == "human_review_required" for finding in findings)
    assert all(finding.question_for_reviewer.endswith("?") for finding in findings)


def _budget_findings(texts: dict[str, str]) -> list[str]:
    builder = _Builder("budget")
    _check_capacity(texts, builder, 0.01)
    _check_completion_rate(texts, builder, 0.01)
    return [finding.category.value for finding in builder.findings]


_CAPACITY_CASE = {
    "C02": "we will serve 300 participants serve 300 participants",
    "C03": "four cohorts of 25 four cohorts of 25",
}


def test_keyword_only_claim_does_not_mask_a_later_match() -> None:
    """A claim holding the keyword but no number must be skipped, not consumed."""
    distractor = {"C01": "the programme will serve the region serve the region"}

    assert _budget_findings(_CAPACITY_CASE) == ["capacity_mismatch"]
    assert _budget_findings({**distractor, **_CAPACITY_CASE}) == ["capacity_mismatch"]


def test_unreadable_number_word_is_skipped_instead_of_raising() -> None:
    unreadable = {"C01": "several cohorts of 25 several cohorts of 25"}

    assert _budget_findings({**unreadable, **_CAPACITY_CASE}) == ["capacity_mismatch"]


def test_completion_rate_survives_an_earlier_keyword_claim() -> None:
    texts = {
        "C00": "we serve the community serve the community",
        "C01": "we will serve 300 participants serve 300 participants",
        "C02": "we expect completion of 80 percent expect completion 80 percent",
        "C03": "graduates target is 200 graduates 200",
    }

    assert _budget_findings(texts) == ["arithmetic_mismatch"]


def test_unreadable_number_is_never_silently_zero() -> None:
    assert _number("several") is None
    assert _number("four") == 4.0
    assert _number("1,200") == 1200.0


def _general_dossier(document: str, claims: list[dict], relations: list[dict]):
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
            "claims": claims,
            "relations": relations,
        }
    )
    return govern_packet(document, packet)


def _claim(proposal_id: str, claim_type: str, span: str) -> dict:
    return {
        "proposal_id": proposal_id,
        "claim_type": claim_type,
        "canonical_content": span,
        "raw_span": span,
        "confidence": 0.9,
        "source_ref": "synthetic",
    }


def _relation(source: str, relation_type: str, target: str) -> dict:
    return {
        "source_id": source,
        "relation_type": relation_type,
        "target_id": target,
        "confidence": 0.9,
        "rationale": "structural",
    }


SCOPE_DOCUMENT = "The pilot ran in one clinic. Every hospital should adopt it."
ASSUMPTION_DOCUMENT = "Funding will be renewed. The team will grow to ten people."


def test_a_scope_tension_edge_is_reported(controlled_source) -> None:
    """Neither this rule nor the general unsupported-assumption rule had a case."""
    dossier = _general_dossier(
        SCOPE_DOCUMENT,
        [
            _claim("C01", "evidence", "The pilot ran in one clinic."),
            _claim("C02", "recommendation", "Every hospital should adopt it."),
        ],
        [_relation("C01", "SCOPE_TENSION", "C02"), _relation("C01", "SUPPORTS", "C02")],
    )

    findings = deterministic_checks(dossier, "general")

    scope = [item for item in findings if item.category.value == "scope_tension"]
    assert len(scope) == 1
    assert scope[0].claim_ids == ("C01", "C02")
    assert scope[0].severity == "medium"
    assert scope[0].summary.strip()
    assert scope[0].question_for_reviewer.strip()


def test_a_scope_tension_is_reported_in_english_too() -> None:
    dossier = _general_dossier(
        SCOPE_DOCUMENT,
        [
            _claim("C01", "evidence", "The pilot ran in one clinic."),
            _claim("C02", "recommendation", "Every hospital should adopt it."),
        ],
        [_relation("C01", "SCOPE_TENSION", "C02"), _relation("C01", "SUPPORTS", "C02")],
    )

    german = deterministic_checks(dossier, "general", language="de")[0]
    english = deterministic_checks(dossier, "general", language="en")[0]

    assert german.summary != english.summary
    assert german.category == english.category


def test_a_load_bearing_assumption_without_evidence_is_reported() -> None:
    dossier = _general_dossier(
        ASSUMPTION_DOCUMENT,
        [
            _claim("C01", "assumption", "Funding will be renewed."),
            _claim("C02", "forecast", "The team will grow to ten people."),
        ],
        [_relation("C01", "ASSUMPTION_FOR", "C02")],
    )

    findings = deterministic_checks(dossier, "general")

    unsupported = [item for item in findings if item.category.value == "unsupported_assumption"]
    assert len(unsupported) == 1
    assert unsupported[0].claim_ids == ("C01",)
    assert unsupported[0].confidence == 0.95
    assert unsupported[0].summary.strip()


def test_an_evidenced_assumption_is_not_reported() -> None:
    """The rule fires on missing evidence, not on the mere presence of an assumption."""
    dossier = _general_dossier(
        ASSUMPTION_DOCUMENT,
        [
            _claim("C01", "assumption", "Funding will be renewed."),
            _claim("C02", "forecast", "The team will grow to ten people."),
        ],
        [_relation("C01", "ASSUMPTION_FOR", "C02"), _relation("C01", "EVIDENCED_BY", "C02")],
    )

    findings = deterministic_checks(dossier, "general")

    assert not [item for item in findings if item.category.value == "unsupported_assumption"]


def test_every_message_template_renders_in_both_languages() -> None:
    """A template that no rule reaches in the suite must still be well formed."""
    for key, translations in _MESSAGES.items():
        for language, (summary, explanation, question) in translations.items():
            placeholders = {
                name
                for _, name, _, _ in string.Formatter().parse(explanation)
                if name is not None
            }
            rendered = explanation.format(**dict.fromkeys(placeholders, 1))
            assert rendered.strip(), f"{key}/{language} renders empty"
            assert summary.strip() and question.strip(), f"{key}/{language}"
