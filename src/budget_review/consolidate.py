"""Collapse overlapping reviewer findings into a small human review queue."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Finding, FindingCategory

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

CATEGORY_LABELS = {
    FindingCategory.ARITHMETIC_MISMATCH: "Rechenfehler",
    FindingCategory.BUDGET_MISMATCH: "Budgetabweichung",
    FindingCategory.CAPACITY_MISMATCH: "Kapazitätsproblem",
    FindingCategory.RESOURCE_MISMATCH: "Ressourcenproblem",
    FindingCategory.UNSUPPORTED_ASSUMPTION: "Unbelegte Annahme",
    FindingCategory.EVIDENCE_GAP: "Evidenzlücke",
    FindingCategory.CAUSAL_OVERCLAIM: "Kausalitätsproblem",
    FindingCategory.SCOPE_TENSION: "Unklarer Geltungsbereich",
    FindingCategory.INTERNAL_CONTRADICTION: "Innerer Widerspruch",
    FindingCategory.REVIEW_QUESTION: "Offene Prüffrage",
}

SEVERITY_LABELS = {
    "critical": "Kritisch",
    "high": "Hoch",
    "medium": "Mittel",
    "low": "Niedrig",
}

REVIEWER_LABELS = {
    "deterministic-checks": "Deterministische Rechenprüfung",
    "flash-evidence-skeptic": "Evidenzprüfung (Flash)",
    "flash-thinking-dependency-skeptic": "Abhängigkeitsprüfung (Flash + Thinking)",
}


@dataclass(frozen=True)
class ConsolidatedIssue:
    issue_id: str
    severity: str
    category: FindingCategory
    title: str
    explanation: str
    question: str
    claim_ids: tuple[str, ...]
    reviewer_ids: tuple[str, ...]
    findings: tuple[Finding, ...]

    @property
    def category_label(self) -> str:
        return CATEGORY_LABELS[self.category]

    @property
    def severity_label(self) -> str:
        return SEVERITY_LABELS.get(self.severity, self.severity)

    @property
    def reviewer_labels(self) -> tuple[str, ...]:
        return tuple(REVIEWER_LABELS.get(item, item) for item in self.reviewer_ids)


def consolidate_findings(findings: tuple[Finding, ...]) -> tuple[ConsolidatedIssue, ...]:
    """Cluster substantially overlapping findings without hiding the raw audit."""
    if not findings:
        return ()
    parent = list(range(len(findings)))

    def root(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = root(left), root(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left in range(len(findings)):
        for right in range(left + 1, len(findings)):
            if _same_issue(findings[left], findings[right]):
                union(left, right)

    groups: dict[int, list[Finding]] = {}
    for index, finding in enumerate(findings):
        groups.setdefault(root(index), []).append(finding)

    prepared = [_prepare_group(group) for group in groups.values()]
    prepared.sort(
        key=lambda item: (
            SEVERITY_ORDER.get(item["severity"], 9),
            item["category"].value,
            item["claim_ids"],
        )
    )
    return tuple(
        ConsolidatedIssue(issue_id=f"P{index:02d}", **item)
        for index, item in enumerate(prepared, start=1)
    )


def _same_issue(left: Finding, right: Finding) -> bool:
    left_claims, right_claims = set(left.claim_ids), set(right.claim_ids)
    overlap = len(left_claims & right_claims)
    if overlap == 0:
        return False
    union_size = len(left_claims | right_claims)
    jaccard = overlap / union_size
    if left.category == right.category:
        return jaccard >= 0.30 or overlap >= 2
    return jaccard >= 0.60


def _prepare_group(group: list[Finding]) -> dict:
    ordered = sorted(
        group,
        key=lambda item: (
            item.reviewer_kind != "deterministic",
            SEVERITY_ORDER.get(item.severity, 9),
            -item.confidence,
        ),
    )
    lead = ordered[0]
    severity = min((item.severity for item in group), key=lambda value: SEVERITY_ORDER[value])
    claim_ids = tuple(sorted({claim_id for item in group for claim_id in item.claim_ids}))
    reviewer_ids = tuple(dict.fromkeys(item.reviewer_id for item in ordered))
    return {
        "severity": severity,
        "category": lead.category,
        "title": lead.summary,
        "explanation": lead.explanation,
        "question": lead.question_for_reviewer,
        "claim_ids": claim_ids,
        "reviewer_ids": reviewer_ids,
        "findings": tuple(ordered),
    }


__all__ = [
    "CATEGORY_LABELS",
    "ConsolidatedIssue",
    "REVIEWER_LABELS",
    "SEVERITY_LABELS",
    "consolidate_findings",
]
