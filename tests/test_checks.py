from __future__ import annotations

from collections import Counter

from budget_review.checks import deterministic_checks


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
