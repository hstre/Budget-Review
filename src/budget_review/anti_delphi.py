"""Independent reviewer arms over the governed ClaimGraph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .checks import deterministic_checks
from .models import (
    Finding,
    FindingCategory,
    ReviewDossier,
    ReviewRejection,
    SemanticDossier,
)
from .prompts import reviewer_prompt
from .provider import DeepSeekProvider, ModelConfig, ProviderError


@dataclass(frozen=True)
class ReviewerArm:
    reviewer_id: str
    role: str
    config: ModelConfig


DEFAULT_ARMS = (
    ReviewerArm(
        reviewer_id="flash-evidence-skeptic",
        role=(
            "Evidence skeptic. Focus on unsupported assumptions, missing baselines, "
            "and scope shifts."
        ),
        config=ModelConfig("deepseek-v4-flash", thinking=False),
    ),
    ReviewerArm(
        reviewer_id="pro-dependency-skeptic",
        role=(
            "Dependency skeptic. Trace whether targets follow from capacity, resources, "
            "methods, and budget."
        ),
        config=ModelConfig("deepseek-v4-pro", thinking=True, reasoning_effort="high"),
    ),
)


def review_claim_graph(
    dossier: SemanticDossier,
    provider: DeepSeekProvider | None = None,
    arms: tuple[ReviewerArm, ...] = DEFAULT_ARMS,
) -> ReviewDossier:
    findings = list(deterministic_checks(dossier))
    rejections: list[ReviewRejection] = []
    runs: list[dict[str, Any]] = [
        {
            "reviewer_id": "deterministic-checks",
            "kind": "deterministic",
            "model_id": "budget-rules/0.1",
            "status": "completed",
            "finding_count": len(findings),
        }
    ]
    if provider is not None:
        for arm in arms:
            system, user = reviewer_prompt(dossier, arm.role)
            try:
                payload, metadata = provider.complete_json(
                    system=system,
                    user=user,
                    config=arm.config,
                    max_tokens=8192,
                )
                admitted, rejected = govern_review_payload(dossier, arm, payload)
                findings.extend(admitted)
                rejections.extend(rejected)
                runs.append(
                    {
                        "reviewer_id": arm.reviewer_id,
                        "kind": "llm",
                        "model_id": str(metadata["model"]),
                        "status": "completed",
                        "finding_count": len(admitted),
                        "rejection_count": len(rejected),
                        "usage": metadata.get("usage", {}),
                        "output_hash": metadata.get("output_hash", ""),
                    }
                )
            except ProviderError as exc:
                rejections.append(ReviewRejection(arm.reviewer_id, "packet", str(exc)))
                runs.append(
                    {
                        "reviewer_id": arm.reviewer_id,
                        "kind": "llm",
                        "model_id": arm.config.model_id,
                        "status": "failed",
                        "error_type": type(exc).__name__,
                    }
                )
    return ReviewDossier(
        schema_version="budget-review.dossier/0.1",
        semantic=dossier,
        findings=tuple(findings),
        review_rejections=tuple(rejections),
        reviewer_runs=tuple(runs),
    )


def govern_review_payload(
    dossier: SemanticDossier,
    arm: ReviewerArm,
    payload: dict[str, Any],
) -> tuple[list[Finding], list[ReviewRejection]]:
    """Validate model findings without treating the reviewer as an authority."""
    admitted: list[Finding] = []
    rejected: list[ReviewRejection] = []
    valid_claims = {claim.proposal_id for claim in dossier.claims}
    raw_findings = payload.get("findings")
    if not isinstance(raw_findings, list):
        return [], [ReviewRejection(arm.reviewer_id, "packet", "findings_not_a_list")]
    seen: set[str] = set()
    allowed_keys = {
        "finding_id",
        "category",
        "severity",
        "summary",
        "claim_ids",
        "explanation",
        "question_for_reviewer",
        "confidence",
    }
    for index, item in enumerate(raw_findings, start=1):
        item_id = (
            str(item.get("finding_id", f"F{index:02d}"))
            if isinstance(item, dict)
            else f"F{index:02d}"
        )
        reason = _review_rejection_reason(item, allowed_keys, valid_claims, seen)
        if reason:
            rejected.append(ReviewRejection(arm.reviewer_id, item_id, reason))
            continue
        assert isinstance(item, dict)
        seen.add(item_id)
        admitted.append(
            Finding(
                finding_id=f"{arm.reviewer_id}:{item_id}",
                reviewer_id=arm.reviewer_id,
                reviewer_kind="llm",
                model_id=arm.config.model_id,
                category=FindingCategory(item["category"]),
                severity=item["severity"],
                summary=item["summary"].strip(),
                claim_ids=tuple(item["claim_ids"]),
                explanation=item["explanation"].strip(),
                question_for_reviewer=item["question_for_reviewer"].strip(),
                confidence=float(item["confidence"]),
            )
        )
    return admitted, rejected


def _review_rejection_reason(
    item: Any,
    allowed_keys: set[str],
    valid_claims: set[str],
    seen: set[str],
) -> str | None:
    if not isinstance(item, dict):
        return "finding_not_an_object"
    if set(item) != allowed_keys:
        return "finding_schema_mismatch"
    item_id = item.get("finding_id")
    if not isinstance(item_id, str) or not item_id or item_id in seen:
        return "invalid_or_duplicate_finding_id"
    try:
        FindingCategory(item.get("category"))
    except (TypeError, ValueError):
        return "unknown_category"
    if item.get("severity") not in {"low", "medium", "high", "critical"}:
        return "unknown_severity"
    claim_ids = item.get("claim_ids")
    if (
        not isinstance(claim_ids, list)
        or not claim_ids
        or any(claim_id not in valid_claims for claim_id in claim_ids)
    ):
        return "unknown_or_empty_claim_ids"
    for field in ("summary", "explanation", "question_for_reviewer"):
        if not isinstance(item.get(field), str) or not item[field].strip():
            return f"empty_{field}"
    confidence = item.get("confidence")
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not 0 <= confidence <= 1
    ):
        return "invalid_confidence"
    return None


__all__ = ["DEFAULT_ARMS", "ReviewerArm", "govern_review_payload", "review_claim_graph"]
