"""The live Anti-Delphi loop, driven by a scripted provider instead of the API.

Every case exercises review_claim_graph with a provider attached. Nothing here
reaches the network or costs money.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from budget_review.anti_delphi import review_claim_graph, reviewer_arms
from budget_review.provider import ProviderError

REQUESTED_MODEL = "deepseek-v4-flash"


@dataclass
class Reply:
    """One scripted API response, including the provenance the adapter records."""

    payload: dict[str, Any]
    model: str = REQUESTED_MODEL
    usage: dict[str, int] = field(default_factory=lambda: {"total_tokens": 1234})
    output_hash: str = "0123456789abcdef"


class FakeProvider:
    def __init__(self, *outcomes: Reply | ProviderError) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []

    def complete_json(
        self, *, system: str, user: str, config: Any, max_tokens: int = 8192
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        self.calls.append(
            {"system": system, "user": user, "config": config, "max_tokens": max_tokens}
        )
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, ProviderError):
            raise outcome
        return outcome.payload, {
            "model": outcome.model,
            "usage": outcome.usage,
            "output_hash": outcome.output_hash,
        }


def finding(finding_id: str = "F01", claim_ids: tuple[str, ...] = ("C07",), **overrides) -> dict:
    base = {
        "finding_id": finding_id,
        "category": "evidence_gap",
        "severity": "medium",
        "summary": "Baseline source is not identified",
        "claim_ids": list(claim_ids),
        "explanation": "The graph contains a benchmark but no evidence claim.",
        "question_for_reviewer": "What source supports the benchmark?",
        "confidence": 0.8,
    }
    return {**base, **overrides}


def reply(*findings: dict, **kwargs) -> Reply:
    return Reply(payload={"findings": list(findings)}, **kwargs)


def llm_runs(dossier) -> list[dict[str, Any]]:
    return [run for run in dossier.reviewer_runs if run["kind"] == "llm"]


DETERMINISTIC_FINDINGS = 10


def test_both_arms_are_asked_and_their_findings_join_the_deterministic_ones(
    controlled_semantic,
) -> None:
    provider = FakeProvider(reply(finding("F01")), reply(finding("F01", ("C09",))))

    dossier = review_claim_graph(controlled_semantic, provider=provider, profile="budget")

    assert len(provider.calls) == 2
    assert len(dossier.findings) == DETERMINISTIC_FINDINGS + 2
    assert dossier.review_rejections == ()
    assert [run["status"] for run in llm_runs(dossier)] == ["completed", "completed"]


def test_the_deterministic_path_stays_first_in_the_ledger(controlled_semantic) -> None:
    provider = FakeProvider(reply(finding()), reply(finding()))

    dossier = review_claim_graph(controlled_semantic, provider=provider, profile="budget")

    assert dossier.reviewer_runs[0]["reviewer_id"] == "deterministic-checks"
    assert dossier.reviewer_runs[0]["kind"] == "deterministic"
    assert dossier.reviewer_runs[0]["finding_count"] == DETERMINISTIC_FINDINGS
    assert len(dossier.reviewer_runs) == 3


def test_each_arm_reviews_the_same_graph_without_seeing_the_other_answer(
    controlled_semantic,
) -> None:
    """Anti-Delphi: perspective separation, not a conversation between arms."""
    first = reply(finding("F01", summary="Only the first arm said this"))
    provider = FakeProvider(first, reply(finding("F02", ("C09",))))

    review_claim_graph(controlled_semantic, provider=provider, profile="budget")

    opening, second = provider.calls
    assert opening["user"] == second["user"], "both arms must see the identical graph"
    assert opening["system"] != second["system"], "each arm must carry its own role"
    for call in provider.calls:
        assert "Only the first arm said this" not in call["system"]
        assert "Only the first arm said this" not in call["user"]


def test_one_failing_arm_does_not_stop_the_other(controlled_semantic) -> None:
    provider = FakeProvider(
        ProviderError("DeepSeek request failed: HTTP 503"),
        reply(finding("F01", ("C09",), summary="The surviving arm reported this")),
    )

    dossier = review_claim_graph(controlled_semantic, provider=provider, profile="budget")

    summaries = [item.summary for item in dossier.findings]
    assert "The surviving arm reported this" in summaries
    assert len(dossier.findings) == DETERMINISTIC_FINDINGS + 1

    failed, completed = llm_runs(dossier)
    assert failed["status"] == "failed"
    assert failed["error_type"] == "ProviderError"
    assert completed["status"] == "completed"


def test_a_failing_arm_is_recorded_as_a_rejection_naming_the_arm(controlled_semantic) -> None:
    arms = reviewer_arms("budget")
    provider = FakeProvider(ProviderError("DeepSeek request failed: HTTP 503"), reply())

    dossier = review_claim_graph(controlled_semantic, provider=provider, profile="budget")

    assert len(dossier.review_rejections) == 1
    rejection = dossier.review_rejections[0]
    assert rejection.reviewer_id == arms[0].reviewer_id
    assert rejection.item_id == "packet"
    assert "HTTP 503" in rejection.reason


def test_every_arm_failing_still_leaves_a_usable_dossier(controlled_semantic) -> None:
    provider = FakeProvider(ProviderError("timeout"), ProviderError("timeout"))

    dossier = review_claim_graph(controlled_semantic, provider=provider, profile="budget")

    assert len(dossier.findings) == DETERMINISTIC_FINDINGS
    assert len(dossier.review_rejections) == 2
    assert [run["status"] for run in llm_runs(dossier)] == ["failed", "failed"]
    assert "letzte Entscheidung liegt beim Menschen" in dossier.authority_note


def test_the_ledger_records_the_model_the_api_reported(controlled_semantic) -> None:
    """Provenance is observed, never asserted by the arm that asked for it."""
    provider = FakeProvider(
        reply(finding(), model="deepseek-v4-flash-0711"),
        reply(finding("F02", ("C09",)), model="deepseek-v4-flash-0711"),
    )

    dossier = review_claim_graph(controlled_semantic, provider=provider, profile="budget")

    assert {run["model_id"] for run in llm_runs(dossier)} == {"deepseek-v4-flash-0711"}
    assert {call["config"].model_id for call in provider.calls} == {REQUESTED_MODEL}


def test_a_failed_run_records_the_requested_model(controlled_semantic) -> None:
    provider = FakeProvider(ProviderError("timeout"), reply())

    dossier = review_claim_graph(controlled_semantic, provider=provider, profile="budget")

    assert llm_runs(dossier)[0]["model_id"] == REQUESTED_MODEL


def test_usage_and_output_hash_reach_the_audit(controlled_semantic) -> None:
    provider = FakeProvider(
        reply(finding(), usage={"total_tokens": 4711}, output_hash="feedfacecafebeef"),
        reply(),
    )

    dossier = review_claim_graph(controlled_semantic, provider=provider, profile="budget")

    run = llm_runs(dossier)[0]
    assert run["usage"] == {"total_tokens": 4711}
    assert run["output_hash"] == "feedfacecafebeef"


def test_malformed_findings_are_rejected_while_the_run_still_completes(
    controlled_semantic,
) -> None:
    provider = FakeProvider(
        reply(finding("F01", ("C999",)), finding("F02", ("C09",))),
        reply(),
    )

    dossier = review_claim_graph(controlled_semantic, provider=provider, profile="budget")

    run = llm_runs(dossier)[0]
    assert run["status"] == "completed"
    assert run["finding_count"] == 1
    assert run["rejection_count"] == 1
    assert "C999" not in {claim for item in dossier.findings for claim in item.claim_ids}
    assert dossier.review_rejections[0].reason == "unknown_or_empty_claim_ids"


def test_a_reviewer_cannot_smuggle_a_verdict_through_the_loop(controlled_semantic) -> None:
    provider = FakeProvider(reply(finding("F01", funding_verdict="reject")), reply())

    dossier = review_claim_graph(controlled_semantic, provider=provider, profile="budget")

    assert len(dossier.findings) == DETERMINISTIC_FINDINGS
    assert dossier.review_rejections[0].reason == "finding_schema_mismatch"


def test_findings_from_different_arms_cannot_collide(controlled_semantic) -> None:
    """Both arms may answer with F01; the dossier must keep them apart."""
    provider = FakeProvider(reply(finding("F01")), reply(finding("F01", ("C09",))))

    dossier = review_claim_graph(controlled_semantic, provider=provider, profile="budget")

    llm_findings = [item for item in dossier.findings if item.reviewer_kind == "llm"]
    ids = [item.finding_id for item in llm_findings]
    assert len(set(ids)) == 2
    for item in llm_findings:
        assert item.finding_id.startswith(f"{item.reviewer_id}:")


def test_agreement_between_arms_is_recorded_twice_not_resolved(controlled_semantic) -> None:
    """Overlap is evidence of overlap, never of truth."""
    agreed = finding("F01", ("C07",), summary="Both arms flag the same benchmark")
    provider = FakeProvider(reply(agreed), reply(dict(agreed)))

    dossier = review_claim_graph(controlled_semantic, provider=provider, profile="budget")

    matching = [item for item in dossier.findings if item.summary == agreed["summary"]]
    assert len(matching) == 2
    assert {item.reviewer_id for item in matching} == {
        arm.reviewer_id for arm in reviewer_arms("budget")
    }
    assert {item.state for item in matching} == {"human_review_required"}


def test_arms_are_called_in_their_configured_thinking_modes(controlled_semantic) -> None:
    provider = FakeProvider(reply(), reply())

    review_claim_graph(controlled_semantic, provider=provider, profile="budget")

    configs = [call["config"] for call in provider.calls]
    assert [config.thinking for config in configs] == [False, True]
    assert {call["max_tokens"] for call in provider.calls} == {8192}


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        ("budget", ("flash-evidence-skeptic", "flash-thinking-dependency-skeptic")),
        ("general", ("flash-evidence-skeptic", "flash-thinking-argument-skeptic")),
    ],
)
def test_each_profile_asks_its_own_arms(controlled_semantic, profile, expected) -> None:
    provider = FakeProvider(reply(), reply())

    dossier = review_claim_graph(controlled_semantic, provider=provider, profile=profile)

    assert tuple(run["reviewer_id"] for run in llm_runs(dossier)) == expected


def test_the_failed_run_survives_serialization_into_the_json_audit(controlled_semantic) -> None:
    provider = FakeProvider(ProviderError("DeepSeek request failed: HTTP 503"), reply(finding()))

    audit = review_claim_graph(controlled_semantic, provider=provider, profile="budget").to_dict()

    failed = [run for run in audit["reviewer_runs"] if run.get("status") == "failed"]
    assert len(failed) == 1
    assert failed[0]["error_type"] == "ProviderError"
    assert [item["reason"] for item in audit["review_rejections"]] == [
        "DeepSeek request failed: HTTP 503"
    ]


def test_no_provider_means_no_calls_and_no_llm_runs(controlled_semantic) -> None:
    dossier = review_claim_graph(controlled_semantic, provider=None, profile="budget")

    assert llm_runs(dossier) == []
    assert len(dossier.findings) == DETERMINISTIC_FINDINGS


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ({"category": "funding_decision"}, "unknown_category"),
        ({"category": None}, "unknown_category"),
        ({"severity": "catastrophic"}, "unknown_severity"),
        ({"claim_ids": []}, "unknown_or_empty_claim_ids"),
        ({"claim_ids": "C07"}, "unknown_or_empty_claim_ids"),
        ({"summary": "   "}, "empty_summary"),
        ({"explanation": ""}, "empty_explanation"),
        ({"question_for_reviewer": None}, "empty_question_for_reviewer"),
        ({"confidence": 1.5}, "invalid_confidence"),
        ({"confidence": True}, "invalid_confidence"),
        ({"confidence": "high"}, "invalid_confidence"),
        ({"finding_id": ""}, "invalid_or_duplicate_finding_id"),
        ({"finding_id": 7}, "invalid_or_duplicate_finding_id"),
    ],
)
def test_the_second_gate_names_why_a_finding_was_refused(
    controlled_semantic, mutation, reason
) -> None:
    provider = FakeProvider(reply(finding(**mutation)), reply())

    dossier = review_claim_graph(controlled_semantic, provider=provider, profile="budget")

    assert len(dossier.findings) == DETERMINISTIC_FINDINGS
    assert [item.reason for item in dossier.review_rejections] == [reason]


def test_a_finding_that_is_not_an_object_is_refused(controlled_semantic) -> None:
    provider = FakeProvider(Reply(payload={"findings": ["just a sentence"]}), reply())

    dossier = review_claim_graph(controlled_semantic, provider=provider, profile="budget")

    assert dossier.review_rejections[0].reason == "finding_not_an_object"
    assert dossier.review_rejections[0].item_id == "F01"


def test_a_duplicate_finding_id_within_one_arm_is_refused(controlled_semantic) -> None:
    provider = FakeProvider(reply(finding("F01"), finding("F01", ("C09",))), reply())

    dossier = review_claim_graph(controlled_semantic, provider=provider, profile="budget")

    assert len(dossier.findings) == DETERMINISTIC_FINDINGS + 1
    assert dossier.review_rejections[0].reason == "invalid_or_duplicate_finding_id"


def test_a_payload_without_a_findings_list_is_refused_whole(controlled_semantic) -> None:
    provider = FakeProvider(Reply(payload={"findings": "none"}), reply())

    dossier = review_claim_graph(controlled_semantic, provider=provider, profile="budget")

    assert dossier.review_rejections[0].reason == "findings_not_a_list"
    assert dossier.review_rejections[0].item_id == "packet"
    assert llm_runs(dossier)[0]["status"] == "completed"
