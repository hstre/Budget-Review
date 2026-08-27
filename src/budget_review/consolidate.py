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
    FindingCategory.LOGICAL_GAP: "Logische Lücke",
    FindingCategory.OVERGENERALIZATION: "Unzulässige Verallgemeinerung",
    FindingCategory.DEFINITION_SHIFT: "Begriffsverschiebung",
    FindingCategory.RELEVANCE_GAP: "Fehlender Bezug",
    FindingCategory.COVERAGE_GAP: "Nicht erfasster Abschnitt",
    FindingCategory.REVIEW_QUESTION: "Offene Prüffrage",
}

SEVERITY_LABELS = {
    "critical": "Kritisch",
    "high": "Hoch",
    "medium": "Mittel",
    "low": "Niedrig",
}

REVIEWER_LABELS = {
    "deterministic-checks": "Deterministische Struktur- und Rechenprüfung",
    "flash-evidence-skeptic": "Evidenzprüfung (Flash)",
    "flash-thinking-dependency-skeptic": "Abhängigkeitsprüfung (Flash + Thinking)",
    "flash-thinking-argument-skeptic": "Argumentprüfung (Flash + Thinking)",
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
    groups: list[list[Finding]] = []
    for finding in findings:
        for group in groups:
            # Complete linkage: a finding joins a group only if it overlaps every
            # member. _same_issue is not transitive, so chaining pairwise matches
            # would merge two issues that the rule itself calls unrelated.
            if all(_same_issue(finding, member) for member in group):
                group.append(finding)
                break
        else:
            groups.append([finding])

    prepared = [_prepare_group(group) for group in groups]
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
    # Severity first: the finding that sets the group's severity is the finding
    # whose title, category and question the examiner reads next to that badge.
    # Deterministic findings still lead among equally severe ones.
    ordered = sorted(
        group,
        key=lambda item: (
            SEVERITY_ORDER.get(item.severity, 9),
            item.reviewer_kind != "deterministic",
            -item.confidence,
        ),
    )
    lead = ordered[0]
    claim_ids = tuple(sorted({claim_id for item in group for claim_id in item.claim_ids}))
    reviewer_ids = tuple(dict.fromkeys(item.reviewer_id for item in ordered))
    return {
        "severity": lead.severity,
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
