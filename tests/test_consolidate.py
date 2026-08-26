from __future__ import annotations

from dataclasses import replace

from budget_review.anti_delphi import review_claim_graph
from budget_review.consolidate import consolidate_findings
from budget_review.render import render_html


def test_overlapping_reviewer_finding_becomes_one_issue(controlled_semantic) -> None:
    dossier = review_claim_graph(controlled_semantic, profile="budget")
    original = dossier.findings[0]
    duplicate = replace(
        original,
        finding_id="flash:F01",
        reviewer_id="flash-evidence-skeptic",
        reviewer_kind="llm",
        model_id="deepseek-v4-flash",
        explanation="Independent reviewer confirms the same capacity gap.",
    )
    issues = consolidate_findings((*dossier.findings, duplicate))

    assert len(issues) == 8
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
    assert len(issues) == len(dossier.findings) == 8


def test_html_escapes_model_and_source_text(controlled_semantic) -> None:
    dossier = review_claim_graph(controlled_semantic, profile="budget")
    malicious = replace(
        dossier.findings[0],
        summary='<script>alert("x")</script>',
    )
    html = render_html(replace(dossier, findings=(malicious, *dossier.findings[1:])))

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_html_keeps_multiple_paths_from_same_reviewer(controlled_semantic) -> None:
    dossier = review_claim_graph(controlled_semantic, profile="budget")
    original = dossier.findings[0]
    second_path = replace(
        original,
        finding_id="deterministic:second-path",
        explanation="Zweiter Prüfweg zum gleichen Sachverhalt.",
    )

    html = render_html(replace(dossier, findings=(original, second_path)))

    assert "Einzelne Prüfwege (2)" in html
    assert "Zweiter Prüfweg zum gleichen Sachverhalt." in html
