from __future__ import annotations

from collections import Counter

from budget_review.checks import (
    _Builder,
    _check_capacity,
    _check_completion_rate,
    _number,
    deterministic_checks,
)


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
