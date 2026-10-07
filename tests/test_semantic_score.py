"""Scoring the meaning set, pinned where a lenient score would flatter the system.

Four ways this could report preserved meaning that is not there: counting a claim
anchored somewhere else in the document, letting one faithful claim excuse a
distorting sibling, letting one claim satisfy two speaker groups at once, and
ignoring how many claims a passage was supposed to carry.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scorer = _module("semantic_score")

DOCUMENT = "Ein Satz davor. Die Maßnahme wirkt nicht. Ein Satz danach."
SPAN = "Die Maßnahme wirkt nicht."


def _case(**overrides) -> dict:
    base = {
        "case_id": "probe-de",
        "language": "de",
        "document": DOCUMENT,
        "span": SPAN,
        "requires_all_groups": [["nicht", "kein"]],
        "forbids": [],
        "forbidden_claim_types": [],
        "min_claims_on_span": 1,
    }
    return {**base, **overrides}


def _claim(content: str, span: str = SPAN, claim_type: str = "fact") -> dict:
    start = DOCUMENT.index(span)
    return {
        "canonical_content": content,
        "claim_type": claim_type,
        "anchor_start": start,
        "anchor_end": start + len(span),
        "anchor_normalised": False,
    }


def test_a_faithful_claim_on_the_span_preserves_the_meaning() -> None:
    row = scorer.score(_case(), [_claim("Die Maßnahme wirkt nicht auf die Quote.")])

    assert row["anchored"] is True
    assert row["meaning_preserved"] is True
    assert row["distortions"] == []


def test_a_claim_that_drops_the_negation_fails() -> None:
    row = scorer.score(_case(), [_claim("Die Maßnahme wirkt auf die Quote.")])

    assert row["anchored"] is True, "it anchored perfectly, which is the whole problem"
    assert row["meaning_preserved"] is False


def test_a_claim_anchored_elsewhere_does_not_count() -> None:
    """Otherwise a claim about the neighbouring sentence would score this passage."""
    elsewhere = _claim("Irgendetwas nicht.", span="Ein Satz danach.")

    row = scorer.score(_case(), [elsewhere])

    assert row["claims_on_span"] == 0
    assert row["anchored"] is False


def test_a_faithful_sibling_does_not_excuse_a_distorting_claim() -> None:
    """A human reads both claims, so a distortion in the dossier is a defect."""
    case = _case(forbids=[r"\bwirkt sicher\b"])
    row = scorer.score(
        case,
        [_claim("Die Maßnahme wirkt nicht."), _claim("Die Maßnahme wirkt sicher.")],
    )

    assert row["requirements_met"] is True, "one claim does satisfy the requirement"
    assert len(row["distortions"]) == 1, "and the other is still recorded"


def test_a_forbidden_claim_type_is_a_distortion() -> None:
    case = _case(forbidden_claim_types=["causal"])

    row = scorer.score(case, [_claim("Die Maßnahme wirkt nicht.", claim_type="causal")])

    assert row["distortions"][0]["claim_type"] == "causal"


def test_two_speaker_groups_need_two_different_claims() -> None:
    """The speaker-collapse case: one claim naming both is not two speech acts."""
    case = _case(
        requires_all_groups=[],
        requires_distinct_groups=[["Regierung"], ["Gerichtshof"]],
        min_claims_on_span=2,
    )

    both_in_one = scorer.score(case, [_claim("Regierung und Gerichtshof äußerten sich.")])
    assert both_in_one["distinct_met"] is False
    assert both_in_one["meaning_preserved"] is False

    two_claims = scorer.score(
        case,
        [_claim("Die Regierung trug vor."), _claim("Der Gerichtshof stellte fest.")],
    )
    assert two_claims["distinct_met"] is True
    assert two_claims["meaning_preserved"] is True


def test_a_passage_that_should_carry_two_claims_is_not_satisfied_by_one() -> None:
    case = _case(min_claims_on_span=2)

    row = scorer.score(case, [_claim("Die Maßnahme wirkt nicht.")])

    assert row["requirements_met"] is True
    assert row["enough_claims"] is False
    assert row["meaning_preserved"] is False


def test_a_normalised_anchor_is_counted() -> None:
    """On single-line hand-written sentences this should never fire."""
    claim = {**_claim("Die Maßnahme wirkt nicht."), "anchor_normalised": True}

    assert scorer.score(_case(), [claim])["normalised_anchors"] == 1


def test_the_language_guess_classifies_every_shipped_document() -> None:
    """The heuristic has to pass 24 texts of known language before it may judge a claim.

    It is function words counted, nothing more. If it cannot place the cases'
    own documents it is not fit to place a claim.
    """
    cases = _module("semantic_cases").load()

    wrong = [
        (case["case_id"], scorer.language_of(case["document"]))
        for case in cases
        if scorer.language_of(case["document"]) != case["language"]
    ]

    assert wrong == []


def test_a_faithful_translation_is_counted_as_a_language_failure_not_a_meaning_one() -> None:
    """What the first run found: 38 of 122 German claims came back in English.

    The rendering below preserves the scope perfectly. Without a separate axis it
    would read as lost meaning, and the fix would look like a wider token list.
    """
    case = _case(
        case_id="sco-01-de",
        document="Die Auswertung unterscheidet Regionen. In ländlichen Gebieten senkt das "
        "Programm die Quote. Für Städte liegen keine Daten vor.",
        span="In ländlichen Gebieten senkt das Programm die Quote.",
        requires_all_groups=[["ländlichen"]],
    )
    document = case["document"]
    start = document.index(case["span"])
    claim = {
        "canonical_content": "In rural areas the program lowers the rate.",
        "claim_type": "fact",
        "anchor_start": start,
        "anchor_end": start + len(case["span"]),
        "anchor_normalised": False,
    }

    row = scorer.score({**case, "language": "de"}, [claim])

    assert row["anchored"] is True
    assert row["in_source_language"] is False
    assert row["translated"] == ["In rural areas the program lowers the rate."]


def test_a_claim_in_the_documents_language_is_not_flagged() -> None:
    row = scorer.score(
        {**_case(), "language": "de"}, [_claim("Die Maßnahme wirkt nicht auf die Quote.")]
    )

    assert row["in_source_language"] is True
    assert row["translated"] == []


def test_an_undecidable_claim_is_not_called_a_translation() -> None:
    """Three words carry no function words, and a guess there would be noise."""
    assert scorer.language_of("Haushalt steigt") == "?"

    row = scorer.score({**_case(), "language": "de"}, [_claim("Haushalt steigt")])

    assert row["translated"] == []
