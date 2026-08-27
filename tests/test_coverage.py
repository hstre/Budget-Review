from __future__ import annotations

from pathlib import Path

import pytest

from budget_review.checks import deterministic_checks
from budget_review.coverage import measure_coverage
from budget_review.gate import govern_packet
from budget_review.ingest import ingest
from budget_review.models import FindingCategory, GovernedClaim, SemanticPacket
from budget_review.pipeline import load_packet

FIXTURES = Path(__file__).resolve().parents[1] / "src" / "budget_review" / "fixtures"


def _claim(start: int, end: int) -> GovernedClaim:
    return GovernedClaim(
        claim_node_id=f"claim_{start}_{end}",
        proposal_id=f"C{start}",
        claim_type="fact",
        canonical_content="x",
        raw_span="x",
        anchor_start=start,
        anchor_end=end,
        anchor_ambiguous=False,
        confidence=0.9,
        source_ref="synthetic",
        semantic_state="proposed",
    )


def test_a_fully_anchored_document_reports_no_gap() -> None:
    document = "Alpha holds. Beta follows."

    coverage = measure_coverage(document, [_claim(0, 12), _claim(13, 26)])

    assert coverage.gaps == ()
    assert coverage.ratio == 1.0


def test_whitespace_never_counts_against_the_ratio() -> None:
    """Newlines between anchored sentences are not missing content."""
    document = "Alpha holds.\n\n\n\n\n\n\n\n\n\nBeta follows."

    coverage = measure_coverage(document, [_claim(0, 12), _claim(22, 35)])

    assert coverage.ratio == 1.0
    assert coverage.gaps == ()


def test_an_unanchored_passage_is_reported_with_its_wording() -> None:
    filler = "This paragraph was never turned into a claim by the extractor. " * 3
    document = f"Alpha holds. {filler}Beta follows."

    tail = _claim(len(document) - 13, len(document))
    coverage = measure_coverage(document, [_claim(0, 12), tail])

    assert len(coverage.gaps) == 1
    gap = coverage.gaps[0]
    assert "never turned into a claim" in gap.excerpt
    assert document[gap.start : gap.end].strip().startswith("This paragraph")
    assert coverage.ratio < 1.0


def test_short_connective_tissue_is_not_a_gap() -> None:
    document = "Alpha holds. Therefore, and for that reason, Beta follows."

    coverage = measure_coverage(document, [_claim(0, 12), _claim(45, 58)])

    assert coverage.gaps == ()


def test_the_gap_threshold_is_adjustable() -> None:
    document = "Alpha holds. " + "filler " * 5 + "Beta follows."

    assert measure_coverage(document, [_claim(0, 12)], minimum_gap=1000).gaps == ()
    assert measure_coverage(document, [_claim(0, 12)], minimum_gap=10).gaps


def test_overlapping_claims_count_a_character_once() -> None:
    document = "Alpha holds and beta follows."

    doubled = measure_coverage(document, [_claim(0, 29), _claim(0, 29), _claim(6, 20)])

    assert doubled.ratio == 1.0
    assert doubled.anchored_characters == doubled.document_characters


def test_a_long_passage_is_excerpted_not_dumped() -> None:
    document = "Alpha holds. " + "word " * 200

    gap = measure_coverage(document, [_claim(0, 12)]).gaps[0]

    assert gap.excerpt.endswith("…")
    assert len(gap.excerpt) < len(document)


def test_a_document_without_claims_is_one_gap_not_a_crash() -> None:
    document = "A paragraph that the extractor returned nothing at all for. " * 3

    coverage = measure_coverage(document, [])

    assert coverage.anchored_characters == 0
    assert coverage.ratio == 0.0
    assert len(coverage.gaps) == 1


def test_an_empty_document_does_not_divide_by_zero() -> None:
    coverage = measure_coverage("", [])

    assert coverage.ratio == 0.0
    assert coverage.gaps == ()


@pytest.mark.parametrize(
    ("name", "source", "packet", "document_id", "expected_gaps"),
    [
        ("polished", "content_theatre/polished.md", "content_theatre/polished_packet.json",
         "content-polished", 0),
        ("rough", "content_theatre/rough.md", "content_theatre/rough_packet.json",
         "content-rough", 0),
        ("budget", "coherence_theatre/proposal.md", "coherence_theatre/semantic_packet.json",
         "regional-skills-bridge", 2),
    ],
)
def test_the_frozen_controls_have_a_pinned_coverage(
    name, source, packet, document_id, expected_gaps
) -> None:
    """The budget fixture genuinely under-covers its own source; that is the point."""
    bundle = ingest([FIXTURES / source], document_id)
    dossier = govern_packet(bundle.text, load_packet(FIXTURES / packet))

    assert dossier.coverage is not None
    assert len(dossier.coverage.gaps) == expected_gaps
    if expected_gaps:
        assert dossier.coverage.ratio < 0.7
    else:
        assert dossier.coverage.ratio > 0.9


def test_the_budget_control_names_the_two_passages_it_misses(controlled_semantic) -> None:
    excerpts = " ".join(gap.excerpt for gap in controlled_semantic.coverage.gaps)

    assert "deliberately small cohort size" in excerpts
    assert "Shared scheduling" in excerpts


def test_a_coverage_gap_becomes_a_question_not_a_defect(controlled_semantic) -> None:
    gaps = [
        item
        for item in deterministic_checks(controlled_semantic, "budget")
        if item.category is FindingCategory.COVERAGE_GAP
    ]

    assert len(gaps) == 2
    for finding in gaps:
        assert finding.severity == "low"
        assert finding.claim_ids == (), "a gap is defined by the absence of a claim"
        assert finding.question_for_reviewer.strip().endswith("?")
        assert finding.state == "human_review_required"


def test_coverage_gaps_are_reported_for_the_general_profile_too(controlled_semantic) -> None:
    categories = [item.category for item in deterministic_checks(controlled_semantic, "general")]

    assert categories.count(FindingCategory.COVERAGE_GAP) == 2


def test_the_gap_finding_is_translated(controlled_semantic) -> None:
    def first_gap(language: str):
        return next(
            item
            for item in deterministic_checks(controlled_semantic, "budget", language=language)
            if item.category is FindingCategory.COVERAGE_GAP
        )

    german, english = first_gap("de"), first_gap("en")

    assert german.summary != english.summary
    assert "deliberately small cohort size" in german.explanation, "the quoted source stays put"
    assert "deliberately small cohort size" in english.explanation


def test_coverage_reaches_the_json_audit(controlled_semantic) -> None:
    payload = controlled_semantic.to_dict()["coverage"]

    assert payload["ratio"] == controlled_semantic.coverage.ratio
    assert len(payload["gaps"]) == 2
    assert payload["gaps"][0]["start"] < payload["gaps"][0]["end"]


def test_the_measurement_replays_identically(controlled_source, controlled_packet) -> None:
    first = govern_packet(controlled_source.text, controlled_packet)
    second = govern_packet(controlled_source.text, controlled_packet)

    assert first.coverage == second.coverage


def test_a_rejected_claim_lowers_the_coverage(controlled_source, controlled_packet) -> None:
    """Coverage measures what was admitted, not what was proposed."""
    full = govern_packet(controlled_source.text, controlled_packet)
    data = controlled_packet.to_dict()
    data["claims"][0]["confidence"] = 0.1
    reduced = govern_packet(controlled_source.text, SemanticPacket.from_dict(data))

    assert reduced.coverage.anchored_characters < full.coverage.anchored_characters

