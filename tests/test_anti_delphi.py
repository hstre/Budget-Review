from __future__ import annotations

from budget_review.anti_delphi import DEFAULT_ARMS, govern_review_payload, review_claim_graph


def _valid_finding() -> dict:
    return {
        "finding_id": "F01",
        "category": "evidence_gap",
        "severity": "medium",
        "summary": "Baseline source is not identified",
        "claim_ids": ["C07"],
        "explanation": "The graph contains a benchmark but no evidence claim.",
        "question_for_reviewer": "What source supports the benchmark?",
        "confidence": 0.8,
    }


def test_valid_model_finding_is_admitted(controlled_semantic) -> None:
    admitted, rejected = govern_review_payload(
        controlled_semantic,
        DEFAULT_ARMS[0],
        {"findings": [_valid_finding()]},
    )
    assert len(admitted) == 1
    assert rejected == []
    assert admitted[0].state == "human_review_required"


def test_unknown_claim_reference_is_rejected(controlled_semantic) -> None:
    finding = _valid_finding()
    finding["claim_ids"] = ["C999"]
    admitted, rejected = govern_review_payload(
        controlled_semantic,
        DEFAULT_ARMS[0],
        {"findings": [finding]},
    )
    assert admitted == []
    assert rejected[0].reason == "unknown_or_empty_claim_ids"


def test_extra_verdict_field_is_rejected(controlled_semantic) -> None:
    finding = _valid_finding()
    finding["funding_verdict"] = "reject"
    admitted, rejected = govern_review_payload(
        controlled_semantic,
        DEFAULT_ARMS[0],
        {"findings": [finding]},
    )
    assert admitted == []
    assert rejected[0].reason == "finding_schema_mismatch"


def test_offline_anti_delphi_contains_deterministic_arm(controlled_semantic) -> None:
    dossier = review_claim_graph(controlled_semantic)
    assert len(dossier.findings) == 8
    assert dossier.reviewer_runs[0]["reviewer_id"] == "deterministic-checks"
    assert "human reviewer remains the merge authority" in dossier.authority_note


def test_default_live_arms_use_flash_in_distinct_modes() -> None:
    assert {arm.config.model_id for arm in DEFAULT_ARMS} == {"deepseek-v4-flash"}
    assert {arm.config.thinking for arm in DEFAULT_ARMS} == {False, True}
    assert len({arm.reviewer_id for arm in DEFAULT_ARMS}) == 2
