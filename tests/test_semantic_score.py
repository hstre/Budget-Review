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


def test_two_speaker_claims_need_two_different_claims() -> None:
    """The speaker-collapse case: one claim naming both is not two speech acts."""
    case = _case(
        requires_all_groups=[],
        requires_distinct_claims=[[["Regierung"]], [["Gerichtshof"]]],
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


def test_a_distinct_claim_must_satisfy_all_of_its_groups_not_one() -> None:
    """What both independent reviews broke: a keyword per claim is not an assertion.

    Two bare fragments satisfied a group of ["Haushalt", "vier Prozent"] one word
    at a time, so a case whose point was that two assertions survive passed on
    two nouns.
    """
    case = _case(
        requires_all_groups=[],
        requires_distinct_claims=[
            [["Haushalt"], ["steigt"]],
            [["Schulen"], ["Anteil"]],
        ],
        min_claims_on_span=2,
    )

    fragments = scorer.score(case, [_claim("Haushalt."), _claim("Schulen.")])
    assert fragments["distinct_met"] is False
    assert fragments["meaning_preserved"] is False

    assertions = scorer.score(
        case,
        [_claim("Der Haushalt steigt."), _claim("Die Schulen erhalten den Anteil.")],
    )
    assert assertions["distinct_met"] is True
    assert assertions["meaning_preserved"] is True


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


# --- a distortion must fail the case, which it did not until the reviews ---


def test_a_tripped_forbidden_pattern_now_fails_the_case() -> None:
    # `distortions` was reported beside `meaning_preserved` and never entered it,
    # so a claim that tripped a forbidden pattern still counted as preserved.
    row = scorer.score(
        _case(forbids=[r"\bsenkt\b"]),
        [_claim("Die Maßnahme senkt die Quote nicht, sagt man.")],
    )

    assert row["distortions"]
    assert row["meaning_preserved"] is False


def test_a_forbidden_claim_type_now_fails_the_case() -> None:
    row = scorer.score(
        _case(forbidden_claim_types=["causal"]),
        [_claim("Die Maßnahme wirkt nicht auf die Quote.", claim_type="causal")],
    )

    assert row["distortions"]
    assert row["meaning_preserved"] is False


def test_a_declared_forbidden_reading_fails_the_case_beside_a_compliant_claim() -> None:
    # The gap both independent reviews walked into from the other side: the
    # forbidden reading satisfies no requirement and trips no regex, so with a
    # compliant claim next to it the case passed and the invented claim stayed in
    # the graph. The validator only ever checked that a forbidden reading
    # violates something, never whether a live claim is one.
    row = scorer.score(
        _case(forbidden_readings=["Die Maßnahme wirkt."]),
        [
            _claim("Die Maßnahme wirkt nicht auf die Quote."),
            _claim("Die Maßnahme wirkt."),
        ],
    )

    assert row["requirements_met"] is True, "a compliant claim is present"
    assert any(d.get("forbidden_reading") for d in row["distortions"])
    assert row["meaning_preserved"] is False


def test_a_forbidden_reading_is_matched_past_spacing_case_and_a_full_stop() -> None:
    for variant in ("die maßnahme wirkt", "Die   Maßnahme  wirkt.", "Die Maßnahme wirkt"):
        row = scorer.score(_case(forbidden_readings=["Die Maßnahme wirkt."]), [_claim(variant)])
        assert any(d.get("forbidden_reading") for d in row["distortions"]), variant


def test_a_different_proposition_is_not_mistaken_for_a_forbidden_reading() -> None:
    # Folding must not become a fuzzy match: a claim that merely resembles the
    # forbidden reading is a different claim and the case must not fail on it.
    row = scorer.score(
        _case(forbidden_readings=["Die Maßnahme wirkt."]),
        [_claim("Die Maßnahme wirkt nicht.")],
    )
    assert not any(d.get("forbidden_reading") for d in row["distortions"])


def test_rescoring_reads_stored_dossiers_and_calls_no_provider(tmp_path) -> None:
    import json

    case = _case()
    dossier = {"claims": [_claim("Die Maßnahme wirkt nicht auf die Quote.")]}
    for repeat in (1, 2):
        (tmp_path / f"probe-de-{repeat}.json").write_text(
            json.dumps(dossier), encoding="utf-8"
        )
    (tmp_path / "semantic-score.json").write_text("{}", encoding="utf-8")

    rows = scorer.rescore(tmp_path, [case])

    assert set(rows) == {"probe-de"}
    assert len(rows["probe-de"]) == 2
    assert all(row["meaning_preserved"] for row in rows["probe-de"])


def test_rescoring_ignores_a_file_that_is_not_a_dossier(tmp_path) -> None:
    import json

    (tmp_path / "probe-de-1.json").write_text(json.dumps({"summary": "no claims"}), "utf-8")
    (tmp_path / "probe-de-2.json").write_text(json.dumps({"summary": "no claims"}), "utf-8")

    assert scorer.rescore(tmp_path, [_case()]) == {}
