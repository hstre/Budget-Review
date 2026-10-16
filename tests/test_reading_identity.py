"""The harder set's invariants, and whether they have teeth.

A validator that passes on the first run is the thing to distrust: the first
meaning set validated cleanly while half of it could be passed by renderings that
lose the meaning. So most of these tests break a case on purpose and require the
validator to say so.

The invariant that matters most is the one an outside paper forces: a case whose
span leaves a plural open has to forbid *both* resolutions. Forbidding only the
universal one would pass a projection that commits to the explicit non-universal
reading, which is the error that paper measures models making on 84 per cent of
negated plurals.
"""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "reading_identity", ROOT / "scripts" / "reading_identity.py"
)
reading_identity = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reading_identity)


@pytest.fixture
def data() -> dict:
    return copy.deepcopy(reading_identity.load())


def _case(data: dict, case_id: str) -> dict:
    return next(case for case in data["cases"] if case["case_id"] == case_id)


def test_the_shipped_set_holds_every_invariant(data: dict) -> None:
    assert reading_identity.validate(data) == []


def test_the_set_covers_all_four_statuses(data: dict) -> None:
    # The whole point of the set is keeping these apart, so a set missing one is
    # not a smaller version of it but a different instrument.
    assert {case["reading_status"] for case in data["cases"]} == set(data["reading_statuses"])


def test_every_pair_is_german_and_english(data: dict) -> None:
    pairs: dict[str, list[str]] = {}
    for case in data["cases"]:
        pairs.setdefault(case["pair_id"], []).append(case["language"])
    assert all(sorted(languages) == ["de", "en"] for languages in pairs.values()), pairs


def test_a_status_the_set_does_not_declare_is_refused(data: dict) -> None:
    """The check no test exercised, found by a mutation that removed it.

    Every shipped case uses a declared status, so deleting the check changed
    nothing and the mutation survived. A status nobody declared would carry no
    meaning for the scorer and would read as a fourth category that exists.
    """
    _case(data, "par-01-de")["reading_status"] = "probably_fine"

    problems = reading_identity.validate(data)

    assert any("undeclared reading_status" in problem for problem in problems), problems


def test_a_declared_status_with_no_case_is_reported(data: dict) -> None:
    # The other direction: a status the set documents but never exercises is a
    # category it claims to separate and does not.
    data["reading_statuses"]["counterfactual"] = "nothing uses this"

    problems = reading_identity.validate(data)

    assert any("no case declares the status" in problem for problem in problems), problems


def test_an_ambiguous_case_with_one_reading_is_refused(data: dict) -> None:
    case = _case(data, "amb-01-de")
    case["readings"] = case["readings"][:1]

    problems = reading_identity.validate(data)

    assert any("only 1 reading" in problem for problem in problems), problems


def test_a_determinate_case_with_two_readings_is_refused(data: dict) -> None:
    case = _case(data, "par-01-de")
    case["readings"] = case["readings"] + [{"gloss": "zweite", "renderings": ["Etwas anderes."]}]

    problems = reading_identity.validate(data)

    assert any("2 readings declared" in problem for problem in problems), problems


def test_two_readings_sharing_a_gloss_are_not_two_readings(data: dict) -> None:
    case = _case(data, "amb-01-de")
    case["readings"][1]["gloss"] = case["readings"][0]["gloss"]

    problems = reading_identity.validate(data)

    assert any("share a gloss" in problem for problem in problems), problems


@pytest.mark.parametrize("case_id", ["plu-01-de", "plu-01-en", "plu-02-de", "plu-02-en"])
def test_an_open_plural_must_forbid_the_universal_resolution(data: dict, case_id: str) -> None:
    case = _case(data, case_id)
    case["forbidden_readings"] = [
        reading
        for reading in case["forbidden_readings"]
        if not any(m in reading.lower() for m in ("alle", "all ", "kein", "none"))
    ]

    problems = reading_identity.validate(data)

    assert any("forbidden universal" in problem for problem in problems), problems


@pytest.mark.parametrize("case_id", ["plu-01-de", "plu-01-en", "plu-02-de", "plu-02-en"])
def test_an_open_plural_must_forbid_the_non_universal_resolution(
    data: dict, case_id: str
) -> None:
    """The half a careless set would leave out, and the one the paper is about."""
    case = _case(data, case_id)
    case["forbidden_readings"] = [
        reading
        for reading in case["forbidden_readings"]
        if not any(m in reading.lower() for m in ("nicht alle", "not all", "einige", "some"))
    ]

    problems = reading_identity.validate(data)

    assert any("forbidden non-universal" in problem for problem in problems), problems


def test_the_quantifier_controls_have_to_exist(data: dict) -> None:
    # Without "all" and "not all" stated explicitly, a set cannot tell an
    # extractor that adds a quantifier from one that drops one.
    data["cases"] = [
        case
        for case in data["cases"]
        if case["phenomenon"] not in ("explicit_universal", "explicit_non_universal")
    ]

    problems = reading_identity.validate(data)

    assert sum("controls are incomplete" in problem for problem in problems) == 2, problems


def test_a_span_that_occurs_twice_is_refused(data: dict) -> None:
    case = _case(data, "par-01-de")
    case["document"] = case["document"] + " " + case["span"]

    problems = reading_identity.validate(data)

    assert any("span occurs 2 times" in problem for problem in problems), problems


def test_a_requirement_the_span_cannot_satisfy_is_refused(data: dict) -> None:
    case = _case(data, "par-01-de")
    case["requires_all_groups"] = [["Herbst"]]

    problems = reading_identity.validate(data)

    assert any("the span does not contain" in problem for problem in problems), problems


def test_forbidding_the_source_wording_is_refused(data: dict) -> None:
    # A case that forbids what the document itself says cannot be passed at all,
    # and would read as a model failure.
    case = _case(data, "par-01-de")
    case["forbids"] = ["Frühjahr"]

    problems = reading_identity.validate(data)

    assert any("forbids the source's own wording" in problem for problem in problems), problems


def test_a_rendering_that_trips_its_own_forbids_is_refused(data: dict) -> None:
    case = _case(data, "par-01-de")
    case["readings"][0]["renderings"].append("Der Ausbau soll im Frühjahr abgeschlossen werden.")

    problems = reading_identity.validate(data)

    assert any("a rendering trips" in problem for problem in problems), problems


def test_a_reading_with_no_rendering_is_refused(data: dict) -> None:
    case = _case(data, "amb-01-de")
    case["readings"][1]["renderings"] = []

    problems = reading_identity.validate(data)

    assert any("has no rendering" in problem for problem in problems), problems


def test_a_forbidden_reading_that_passes_everything_is_refused(data: dict) -> None:
    """The non-vacuity check, which the first set needed and got late."""
    case = _case(data, "par-01-de")
    case["forbidden_readings"] = ["Der Ausbau wird im Frühjahr abgeschlossen."]

    problems = reading_identity.validate(data)

    assert any("prove nothing here" in problem for problem in problems), problems


def test_a_pair_whose_languages_disagree_on_the_status_is_refused(data: dict) -> None:
    _case(data, "plu-01-en")["reading_status"] = "determinate"

    problems = reading_identity.validate(data)

    assert any("reading_status differs" in problem for problem in problems), problems


def test_a_pair_whose_languages_declare_different_reading_counts_is_refused(data: dict) -> None:
    case = _case(data, "amb-01-en")
    case["readings"] = case["readings"][:1]

    problems = reading_identity.validate(data)

    assert any("different number of readings" in problem for problem in problems), problems


def test_the_one_reading_several_wordings_case_really_carries_several(data: dict) -> None:
    # It exists to make the distinction the first set could not express, so one
    # rendering would make it an ordinary determinate case.
    for case_id in ("par-01-de", "par-01-en"):
        readings = _case(data, case_id)["readings"]
        assert len(readings) == 1
        assert len(readings[0]["renderings"]) >= 3, case_id


def test_the_ambiguous_cases_offer_genuinely_different_commitments(data: dict) -> None:
    """What distinguishes this set from the first one, asserted rather than assumed.

    Two readings that shared every rendering would be one reading written twice,
    which is exactly the confusion found in the first set — eight of its cases
    declare two permitted readings and all eight are two wordings of one.
    """
    for case in data["cases"]:
        if case["reading_status"] != "ambiguous":
            continue
        rendered = [set(reading["renderings"]) for reading in case["readings"]]
        for left, right in zip(rendered, rendered[1:], strict=False):
            assert not left & right, case["case_id"]


def test_the_matching_convention_is_not_written_a_second_time() -> None:
    # One set with two notions of what counts as a rendering would compare as
    # different where it is only spelled differently.
    source = (ROOT / "scripts" / "reading_identity.py").read_text(encoding="utf-8")
    assert "semantic_cases.satisfies" in source
    assert "semantic_cases.violates" in source
    assert "def satisfies" not in source
    assert "def violates" not in source


def test_an_open_plural_must_record_its_quantifier_as_unstated(data: dict) -> None:
    """Where the status axis and the field axis meet, and can contradict.

    Two annotations of the same case with no point of contact would be two
    unverifiable opinions. This is the one place a contradiction is catchable.
    """
    _case(data, "plu-01-de")["interpretation"]["quantifier"] = "stated"

    problems = reading_identity.validate(data)

    assert any("cannot be 'stated'" in problem for problem in problems), problems


def test_a_case_with_an_unstated_quantifier_must_carry_that_status(data: dict) -> None:
    _case(data, "par-01-de")["interpretation"]["quantifier"] = "unstated"

    problems = reading_identity.validate(data)

    assert any("the status cannot be" in problem for problem in problems), problems


@pytest.mark.parametrize("case_id", ["plu-03-de", "plu-04-en"])
def test_a_control_must_record_its_quantifier_as_stated(data: dict, case_id: str) -> None:
    _case(data, case_id)["interpretation"]["quantifier"] = "absent"

    problems = reading_identity.validate(data)

    assert any("must record it as stated" in problem for problem in problems), problems


def test_a_missing_interpretation_field_is_refused(data: dict) -> None:
    del _case(data, "amb-01-de")["interpretation"]["modality"]

    problems = reading_identity.validate(data)

    assert any("no interpretation recorded" in problem for problem in problems), problems


def test_an_undeclared_interpretation_value_is_refused(data: dict) -> None:
    # The paper's third value, inferred against default, is a property of a run
    # and not of a span, so it is not one of ours and must not creep in.
    _case(data, "amb-01-de")["interpretation"]["modality"] = "inferred"

    problems = reading_identity.validate(data)

    assert any("undeclared interpretation value" in problem for problem in problems), problems


def test_an_undeclared_interpretation_field_is_refused(data: dict) -> None:
    # The two fields refused on principle — what evidence suffices, and against
    # what it is compared — must not arrive by the back door.
    _case(data, "amb-01-de")["interpretation"]["support_threshold"] = "stated"

    problems = reading_identity.validate(data)

    assert any("undeclared interpretation field" in problem for problem in problems), problems


def test_the_refused_fields_are_not_in_the_schema(data: dict) -> None:
    declared = set(data["interpretation_fields"])
    assert "support_threshold" not in declared
    assert "comparison_basis" not in declared


def test_every_case_says_what_its_difficulty_turns_on(data: dict) -> None:
    assert all(case.get("turns_on") for case in data["cases"])


def test_a_case_without_turns_on_is_refused(data: dict) -> None:
    # The assertion above holds on the shipped set and says nothing about the
    # check: a mutation removing it survived, for the third time in this
    # repository. A check needs a test of its failure path, not of the happy one.
    del _case(data, "amb-01-de")["turns_on"]

    problems = reading_identity.validate(data)

    assert any("turns on" in problem for problem in problems), problems


def test_a_pair_whose_languages_record_different_fields_is_refused(data: dict) -> None:
    _case(data, "plu-01-en")["interpretation"]["conditions"] = "stated"

    problems = reading_identity.validate(data)

    assert any("interpretation record differs" in problem for problem in problems), problems


def test_half_the_pairs_turn_on_something_the_field_list_does_not_cover(data: dict) -> None:
    """The finding that came out of adopting the card, recorded as a test.

    Attachment and quantifier scope are not among the nine fields, and
    evidential support is the one refused above. A field list is worth having
    and does not localise everything, and overstating its reach later would be
    easy without this.
    """
    declared = set(data["interpretation_fields"])
    uncovered = {
        case["pair_id"] for case in data["cases"] if case["turns_on"] not in declared
    }
    assert uncovered == {"amb-01", "amb-02", "evi-01"}, uncovered


def test_the_scorer_does_not_read_the_interpretation_record(data: dict) -> None:
    """Why the pre-registration survives this addition.

    The record is description. If scoring depended on it, adding it after the
    criterion was fixed would have changed what the run measures.
    """
    source = (ROOT / "scripts" / "semantic_score.py").read_text(encoding="utf-8")
    assert "interpretation" not in source
    assert "turns_on" not in source


# --- the three repairs the first paid run forced ---


@pytest.mark.parametrize(
    ("span", "is_sentence"),
    [
        ("Die Schulen des Bezirks haben den Zuschlag erhalten.", True),
        ("The schools in the district received the supplement.", True),
        ("dass die Schulen des Bezirks den Zuschlag erhalten haben", False),
        ("that the schools in the district received the supplement", False),
        ("Mittel für die Betreuung der Kinder aus dem Stadtteil", False),
        # A clause that happens to swallow the sentence's final full stop. Both
        # halves of the test are needed: punctuation alone calls this a
        # sentence, and a mutation dropping the capital-letter half survived
        # until this case existed.
        ("dass die Schulen den Zuschlag erhalten haben.", False),
        ("that construction is completed in spring.", False),
        # And the mirror: a capitalised noun phrase with no full stop.
        ("Mittel für die Betreuung", False),
        ("", False),
    ],
)
def test_a_complete_sentence_is_told_from_a_clause(span: str, is_sentence: bool) -> None:
    assert reading_identity.looks_like_a_sentence(span) is is_sentence


def test_no_span_in_the_set_is_a_complete_sentence(data: dict) -> None:
    """The repair, as a property of the set rather than a note about it.

    In the first run the 14 cases whose span was a whole sentence had it returned
    verbatim in 42 of 42 claims: a complete sentence is already an atomic
    proposition, so the projection is the identity and the case measures nothing.
    The one fragment span had 0 of 14 verbatim.
    """
    offenders = [
        case["case_id"]
        for case in data["cases"]
        if reading_identity.looks_like_a_sentence(case["span"])
    ]
    assert offenders == [], offenders


def test_a_sentence_span_is_refused(data: dict) -> None:
    case = _case(data, "plu-01-de")
    case["document"] = "Die Schulen haben den Zuschlag erhalten. Drei Standorte melden."
    case["span"] = "Die Schulen haben den Zuschlag erhalten."
    case["requires_all_groups"] = [["Schulen"], ["Zuschlag"]]

    problems = reading_identity.validate(data)

    assert any("complete sentence" in problem for problem in problems), problems


def test_a_pattern_matching_the_document_itself_is_refused(data: dict) -> None:
    """Otherwise the instrument punishes a verbatim quote, which is the job.

    The forbidden-anywhere patterns name the *inferred* resolution. A pattern
    that also matched the document's own second sentence would fail a run for
    quoting the source correctly.
    """
    case = _case(data, "plu-01-de")
    case["forbidden_anywhere"] = ["\\bdrei der fünf\\b"]

    problems = reading_identity.validate(data)

    assert any("own wording" in problem for problem in problems), problems


def test_the_open_plural_cases_forbid_something_off_the_span(data: dict) -> None:
    # The whole point of the repair: the resolution appeared one sentence over,
    # 23 times across 24 runs, where nothing was looking.
    for case in data["cases"]:
        if case["reading_status"] == "underdetermined_quantifier":
            assert case.get("forbidden_anywhere"), case["case_id"]
