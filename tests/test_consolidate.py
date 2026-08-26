from __future__ import annotations

from dataclasses import replace

from budget_review.anti_delphi import review_claim_graph
from budget_review.consolidate import _same_issue, consolidate_findings
from budget_review.models import Finding, FindingCategory
from budget_review.render import render_html


def _first_with_claims(dossier):
    """Coverage findings carry no claim ids by design, so they never cluster."""
    return next(item for item in dossier.findings if item.claim_ids)


def test_overlapping_reviewer_finding_becomes_one_issue(controlled_semantic) -> None:
    dossier = review_claim_graph(controlled_semantic, profile="budget")
    original = _first_with_claims(dossier)
    duplicate = replace(
        original,
        finding_id="flash:F01",
        reviewer_id="flash-evidence-skeptic",
        reviewer_kind="llm",
        model_id="deepseek-v4-flash",
        explanation="Independent reviewer confirms the same capacity gap.",
    )
    issues = consolidate_findings((*dossier.findings, duplicate))

    assert len(issues) == 10
    merged = next(
        issue
        for issue in issues
        if original.finding_id in {finding.finding_id for finding in issue.findings}
    )
    assert len(merged.findings) == 2
    assert len(merged.reviewer_ids) == 2


def test_unrelated_findings_remain_separate(controlled_semantic) -> None:
    dossier = review_claim_graph(controlled_semantic, profile="budget")
    issues = consolidate_findings(dossier.findings)
    assert len(issues) == len(dossier.findings) == 10


def test_html_escapes_model_and_source_text(controlled_semantic) -> None:
    dossier = review_claim_graph(controlled_semantic, profile="budget")
    malicious = replace(
        _first_with_claims(dossier),
        summary='<script>alert("x")</script>',
    )
    html = render_html(replace(dossier, findings=(malicious, *dossier.findings[1:])))

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_html_keeps_multiple_paths_from_same_reviewer(controlled_semantic) -> None:
    dossier = review_claim_graph(controlled_semantic, profile="budget")
    original = _first_with_claims(dossier)
    second_path = replace(
        original,
        finding_id="deterministic:second-path",
        explanation="Zweiter Prüfweg zum gleichen Sachverhalt.",
    )

    html = render_html(replace(dossier, findings=(original, second_path)))

    assert "Einzelne Prüfwege (2)" in html
    assert "Zweiter Prüfweg zum gleichen Sachverhalt." in html


def _finding(finding_id: str, severity: str, claim_ids: tuple[str, ...], **overrides):
    base = dict(
        finding_id=finding_id,
        reviewer_id="flash-evidence-skeptic",
        reviewer_kind="llm",
        model_id="deepseek-v4-flash",
        category=FindingCategory.LOGICAL_GAP,
        severity=severity,
        summary=f"summary {finding_id}",
        claim_ids=claim_ids,
        explanation=f"explanation {finding_id}",
        question_for_reviewer=f"question {finding_id}",
        confidence=0.8,
    )
    return Finding(**{**base, **overrides})


def test_issue_headline_comes_from_the_finding_that_sets_the_severity() -> None:
    """The badge and the text next to it must describe the same finding."""
    mild = _finding(
        "D01", "medium", ("C01",), reviewer_id="deterministic-checks", reviewer_kind="deterministic"
    )
    severe = _finding("F01", "critical", ("C01",))

    issue = consolidate_findings((mild, severe))[0]

    assert issue.severity == "critical"
    assert issue.title == severe.summary
    assert issue.explanation == severe.explanation
    assert issue.question == severe.question_for_reviewer
    assert len(issue.findings) == 2


def test_deterministic_finding_leads_among_equally_severe_ones() -> None:
    model = _finding("F01", "high", ("C01",))
    rules = _finding(
        "D01", "high", ("C01",), reviewer_id="deterministic-checks", reviewer_kind="deterministic"
    )

    issue = consolidate_findings((model, rules))[0]

    assert issue.title == rules.summary


def test_chained_overlap_does_not_merge_unrelated_findings() -> None:
    """_same_issue is not transitive; clustering must not treat it as if it were."""
    left = _finding("F01", "low", ("C01", "C02"), category=FindingCategory.REVIEW_QUESTION)
    middle = _finding("F02", "low", ("C02", "C03"), category=FindingCategory.REVIEW_QUESTION)
    right = _finding("F03", "low", ("C03", "C04"), category=FindingCategory.REVIEW_QUESTION)

    assert _same_issue(left, middle) and _same_issue(middle, right)
    assert not _same_issue(left, right)
    assert len(consolidate_findings((left, middle, right))) == 2


def test_unknown_severity_does_not_break_consolidation() -> None:
    issue = consolidate_findings((_finding("F01", "unbekannt", ("C01",)),))[0]
    assert issue.severity == "unbekannt"
