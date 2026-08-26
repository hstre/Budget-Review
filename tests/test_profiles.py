from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from budget_review.checks import deterministic_checks
from budget_review.ingest import ingest
from budget_review.pipeline import ReviewPipeline, load_packet
from budget_review.profiles import get_profile
from budget_review.prompts import extraction_prompt, reviewer_prompt
from budget_review.render import render_html


def _content_case(name: str):
    fixture_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "budget_review"
        / "fixtures"
        / "content_theatre"
    )
    source = ingest([fixture_dir / f"{name}.md"], document_id=f"content-{name}")
    packet = load_packet(fixture_dir / f"{name}_packet.json")
    return ReviewPipeline(profile="general").run(source, packet=packet)


def test_polished_but_broken_content_exposes_structure_failures() -> None:
    dossier = _content_case("polished")
    categories = [finding.category.value for finding in dossier.findings]

    assert dossier.profile == "general"
    assert categories.count("overgeneralization") == 2
    assert "internal_contradiction" in categories
    assert "logical_gap" not in categories


def test_unconnected_conclusion_is_exposed_as_logical_gap() -> None:
    dossier = _content_case("rough")
    recommendation = next(claim for claim in dossier.semantic.claims if claim.proposal_id == "C04")
    semantic = replace(
        dossier.semantic,
        relations=tuple(
            relation
            for relation in dossier.semantic.relations
            if relation.target_claim_node_id != recommendation.claim_node_id
        ),
    )

    findings = deterministic_checks(semantic, "general")

    assert any(
        finding.category.value == "logical_gap" and finding.claim_ids == ("C04",)
        for finding in findings
    )


def test_rough_but_supported_content_is_not_penalized_for_style() -> None:
    dossier = _content_case("rough")

    assert dossier.profile == "general"
    assert dossier.findings == ()
    html = render_html(dossier)
    assert "Kein Stil- oder Autorenurteil" in html
    assert "Inhaltsgerüst" in html
    assert "Home working can help some teams." in html
    assert "Keine maschinellen Prüfhinweise" in html


def test_general_prompts_explicitly_exclude_ai_detection() -> None:
    dossier = _content_case("rough")
    extraction_system, _ = extraction_prompt("example", "A text.", "general")
    review_system, _ = reviewer_prompt(dossier.semantic, "Argument skeptic", "general")

    assert "suspected AI authorship" in extraction_system
    assert "suspected AI authorship" in review_system
    assert "human-written or AI-written" in extraction_system


def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown review profile"):
        get_profile("style-detector")
