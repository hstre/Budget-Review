from __future__ import annotations

import json
from pathlib import Path

import pytest

from budget_review.checks import _MESSAGES, deterministic_checks
from budget_review.ingest import ingest
from budget_review.pipeline import ReviewPipeline, load_packet
from budget_review.profiles import BUDGET, GENERAL, authority_note
from budget_review.prompts import reviewer_prompt
from budget_review.render import _TEXT, render_markdown
from budget_review.settings import LANGUAGES

FIXTURES = Path(__file__).resolve().parents[1] / "src" / "budget_review" / "fixtures"


def _dossier(profile: str, language: str):
    if profile == "budget":
        source = ingest([FIXTURES / "coherence_theatre" / "proposal.md"], "regional-skills-bridge")
        packet = load_packet(FIXTURES / "coherence_theatre" / "semantic_packet.json")
    else:
        source = ingest([FIXTURES / "content_theatre" / "polished.md"], "content-polished")
        packet = load_packet(FIXTURES / "content_theatre" / "polished_packet.json")
    return ReviewPipeline(profile=profile, language=language).run(source, packet=packet)


def test_every_message_is_translated() -> None:
    for key, translations in _MESSAGES.items():
        assert set(translations) == LANGUAGES, f"{key} is missing a language"
        for language, parts in translations.items():
            assert len(parts) == 3, f"{key}/{language}"
            assert all(part.strip() for part in parts), f"{key}/{language} has empty text"


@pytest.mark.parametrize("profile", ["general", "budget"])
def test_findings_are_written_in_the_selected_language(profile: str) -> None:
    german = _dossier(profile, "de")
    english = _dossier(profile, "en")

    assert german.findings and english.findings
    for left, right in zip(german.findings, english.findings, strict=True):
        assert left.summary != right.summary, "finding prose must follow the language"
        assert left.explanation != right.explanation


@pytest.mark.parametrize("profile", ["general", "budget"])
def test_language_never_moves_a_structural_field(profile: str) -> None:
    """Category, severity, claims, confidence and provenance stay language independent."""
    german = _dossier(profile, "de")
    english = _dossier(profile, "en")

    def structure(dossier):
        return [
            (f.category, f.severity, f.claim_ids, f.confidence, f.reviewer_id)
            for f in dossier.findings
        ]

    assert structure(german) == structure(english)
    assert german.semantic == english.semantic


def test_quoted_claims_keep_their_original_wording() -> None:
    english = _dossier("general", "en")
    markdown = render_markdown(english, "en")

    for claim in english.semantic.claims:
        assert claim.raw_span in markdown or claim.canonical_content in markdown


def test_markdown_chrome_is_translated() -> None:
    dossier = _dossier("general", "de")

    german = render_markdown(dossier, "de")
    english = render_markdown(dossier, "en")

    assert german.startswith("# Content Review — Prüferdossier")
    assert english.startswith("# Content Review — Reviewer dossier")
    assert "## Inhaltsgerüst" in german
    assert "## Content map" in english
    assert "**Prüffrage:**" in german
    assert "**Review question:**" in english


def test_markdown_falls_back_to_german_for_an_unknown_language() -> None:
    dossier = _dossier("general", "de")
    assert render_markdown(dossier, "kl") == render_markdown(dossier, "de")


def test_written_dossier_uses_one_language_for_both_formats(tmp_path) -> None:
    dossier = _dossier("general", "en")

    _, markdown_path, html_path = ReviewPipeline.write(dossier, tmp_path, "en")

    assert "Reviewer dossier" in markdown_path.read_text(encoding="utf-8")
    html = html_path.read_text(encoding="utf-8")
    assert 'lang="en"' in html
    assert "Prüferdossier" not in html


def test_reviewer_arms_are_told_the_dossier_language() -> None:
    dossier = _dossier("general", "de")

    assert "clear German" in reviewer_prompt(dossier.semantic, "role", language="de")[0]
    assert "clear English" in reviewer_prompt(dossier.semantic, "role", language="en")[0]


def test_authority_note_has_both_languages() -> None:
    for profile in (GENERAL, BUDGET):
        assert authority_note(profile, "de") == profile.authority_note
        assert authority_note(profile, "en") != profile.authority_note
        assert authority_note(profile, "en").strip()


def test_json_audit_stays_machine_readable_in_both_languages(tmp_path) -> None:
    for language in sorted(LANGUAGES):
        json_path, _, _ = ReviewPipeline.write(
            _dossier("budget", language), tmp_path / language, language
        )
        audit = json.loads(json_path.read_text(encoding="utf-8"))
        categories = [finding["category"] for finding in audit["findings"]]
        assert categories == [
            "coverage_gap",
            "coverage_gap",
            "capacity_mismatch",
            "resource_mismatch",
            "arithmetic_mismatch",
            "arithmetic_mismatch",
            "unsupported_assumption",
            "budget_mismatch",
            "budget_mismatch",
            "causal_overclaim",
        ]


def test_unknown_language_falls_back_in_the_checks(controlled_semantic) -> None:
    german = deterministic_checks(controlled_semantic, "budget", language="de")
    fallback = deterministic_checks(controlled_semantic, "budget", language="kl")

    assert [f.summary for f in german] == [f.summary for f in fallback]


def test_both_languages_cover_the_same_catalogue_keys() -> None:
    assert set(_TEXT["de"]) == set(_TEXT["en"])
