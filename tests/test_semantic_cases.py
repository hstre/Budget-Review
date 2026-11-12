"""The hand-annotated meaning set, and the invariants that keep it honest.

The set is authored by the same kind of model the system under test uses, so its
value rests entirely on its checks being mechanical and on those checks being
able to fail. These tests exist to make the validator bite: each one feeds it a
case that is broken in a way a careless author would not notice.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "semantic_cases", ROOT / "scripts" / "semantic_cases.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cases_module = _module()


def _case(**overrides) -> dict:
    base = {
        "case_id": "probe-de",
        "pair_id": "probe",
        "language": "de",
        "phenomenon": "negation",
        "document": "Ein Satz davor. Die Maßnahme wirkt nicht. Ein Satz danach.",
        "span": "Die Maßnahme wirkt nicht.",
        "requires_all_groups": [["nicht", "kein"]],
        "forbids": [],
        "forbidden_claim_types": [],
        "min_claims_on_span": 1,
        "permitted_readings": ["Die Maßnahme wirkt nicht auf die Quote."],
        "forbidden_readings": ["Die Maßnahme wirkt auf die Quote."],
    }
    return {**base, **overrides}


def _pair(german: dict, english_forbidden: list[str] | None = None) -> list[dict]:
    english = {
        **german,
        "case_id": "probe-en",
        "language": "en",
        "document": "A sentence before. The measure does not work. A sentence after.",
        "span": "The measure does not work.",
        "requires_all_groups": [["not", "no "]],
        "permitted_readings": ["The measure does not affect the rate."],
        "forbidden_readings": english_forbidden or ["The measure affects the rate."],
    }
    return [german, english]


def test_the_shipped_set_holds_every_invariant() -> None:
    cases = cases_module.load()

    assert cases_module.validate(cases) == []
    assert len(cases) == 38
    assert len({case["pair_id"] for case in cases}) == 19
    # Ten phenomena since the set gained temporal scope, concession and
    # implicatives. The published 69 of 72 was measured on the first
    # twenty-four and stays attached to them: a figure over a larger set is a
    # different figure.
    assert len({case["phenomenon"] for case in cases}) == 10


def test_a_requirement_the_span_does_not_contain_is_refused() -> None:
    """Otherwise a case could demand a word the source never uses."""
    broken = _case(requires_all_groups=[["keinesfalls"]])

    problems = cases_module.validate(_pair(broken))

    assert any("does not contain" in problem for problem in problems)


def test_forbidding_the_sources_own_wording_is_refused() -> None:
    broken = _case(forbids=[r"\bwirkt\b"])

    problems = cases_module.validate(_pair(broken))

    assert any("own wording" in problem for problem in problems)


def test_a_forbidden_reading_that_passes_every_check_is_refused() -> None:
    """The invariant that would catch a check proving nothing.

    Here the forbidden reading keeps the negation, so the declared requirement
    cannot tell it from a faithful claim — and the case would score a distortion
    as a pass.
    """
    broken = _case(forbidden_readings=["Die Maßnahme wirkt nicht, aber anders gemeint."])

    problems = cases_module.validate(_pair(broken))

    assert any("prove nothing" in problem for problem in problems)


def test_a_permitted_reading_that_fails_its_own_requirements_is_refused() -> None:
    broken = _case(permitted_readings=["Die Maßnahme wirkt auf die Quote."])

    problems = cases_module.validate(_pair(broken))

    assert any("permitted reading fails" in problem for problem in problems)


def test_a_span_occurring_twice_is_refused() -> None:
    """An ambiguous anchor would make the measurement depend on which one was taken."""
    broken = _case(
        document="Die Maßnahme wirkt nicht. Die Maßnahme wirkt nicht.",
        span="Die Maßnahme wirkt nicht.",
    )

    problems = cases_module.validate(_pair(broken))

    assert any("occurs 2 times" in problem for problem in problems)


def test_a_pair_whose_languages_differ_in_structure_is_refused() -> None:
    german = _case()
    pair = _pair(german)
    pair[1] = {**pair[1], "min_claims_on_span": 2}

    problems = cases_module.validate(pair)

    assert any("min_claims_on_span differs" in problem for problem in problems)


def test_a_pair_missing_a_language_is_refused() -> None:
    problems = cases_module.validate([_case()])

    assert any("expected de and en" in problem for problem in problems)


def test_a_single_word_requirement_does_not_fire_inside_another_word() -> None:
    """ "kann" must not be satisfied by "bekannt", or the check is noise."""
    assert cases_module.satisfies("Das ist bekannt.", [["kann"]]) is False
    assert cases_module.satisfies("Das kann wirken.", [["kann"]]) is True


def test_a_phrase_requirement_matches_as_a_phrase() -> None:
    assert cases_module.satisfies("Nicht alle Schulen.", [["nicht alle"]]) is True
    assert cases_module.satisfies("Nicht jede Schule.", [["nicht alle"]]) is False


def test_every_group_has_to_contribute() -> None:
    groups = [["Regierung"], ["Gerichtshof"]]

    assert cases_module.satisfies("Die Regierung trug vor.", groups) is False
    assert cases_module.satisfies("Regierung und Gerichtshof.", groups) is True


def test_the_temporal_cases_catch_both_ways_of_losing_a_bound() -> None:
    """Dropping the bound and reversing it are different errors, both caught.

    The requirement group catches the drop; the forbidden pattern catches the
    reversal, which carries the date and would otherwise satisfy every group.
    """
    cases = [case for case in cases_module.load() if case["phenomenon"] == "temporal_scope"]
    assert len(cases) == 4
    for case in cases:
        dropped, reversed_ = case["forbidden_readings"]
        assert not cases_module.satisfies(dropped, case["requires_all_groups"]), case["case_id"]
        assert cases_module.satisfies(reversed_, case["requires_all_groups"]), case["case_id"]
        assert cases_module.violates(reversed_, case["forbids"]), case["case_id"]


def test_the_concession_cases_catch_the_conceded_clause_standing_in_for_the_asserted_one() -> None:
    cases = [case for case in cases_module.load() if case["phenomenon"] == "concession"]
    assert len(cases) == 4
    for case in cases:
        conceded = case["forbidden_readings"][0]
        assert not cases_module.satisfies(conceded, case["requires_all_groups"]), case["case_id"]


def test_the_concession_blind_spot_is_recorded_rather_than_hidden() -> None:
    """A reading that flattens the concession into a conjunction is not caught.

    It carries the asserted clause's token, so every group passes and no
    pattern fires. The set says so in `must_preserve` instead of pretending the
    check is finer than it is — which is why this phenomenon is called
    concession and not salience: the general notion needs a judge of paraphrase.
    """
    case = next(
        case for case in cases_module.load()
        if case["case_id"] == "conc-01-de"
    )
    flattened = "Die Mittel sind knapp, und das Projekt wird fortgesetzt."
    assert cases_module.satisfies(flattened, case["requires_all_groups"])
    assert not cases_module.violates(flattened, case["forbids"])
    assert "gleichrangig" in case["must_preserve"]


def test_the_implicative_cases_cover_all_three_polarities() -> None:
    """A positive, a negative and a non-implicative verb.

    Without all three the set would test whether a main verb is read at all,
    not whether its polarity is read: the interesting failure is treating
    "failed to X" as "tried to X", and that needs both to be present.
    """
    cases = [case for case in cases_module.load() if case["phenomenon"] == "implicative"]
    assert len(cases) == 6
    spans = " ".join(case["span"] for case in cases)
    for marker in ("geschafft", "versäumt", "versucht", "managed", "failed", "tried"):
        assert marker in spans, marker


def test_both_checks_do_work_in_every_implicative_case() -> None:
    """The weakness the temporal cases had on their first draft.

    If every forbidden reading already fails a requirement group, the forbidden
    patterns are decoration and the case rests on one check while appearing to
    rest on two. Each implicative case has to have at least one forbidden
    reading caught by each of them.
    """
    for case in cases_module.load():
        if case["phenomenon"] != "implicative":
            continue
        groups = case["requires_all_groups"]
        readings = case["forbidden_readings"]
        caught_by_group = [r for r in readings if not cases_module.satisfies(r, groups)]
        caught_by_pattern = [
            r for r in readings
            if cases_module.satisfies(r, groups) and cases_module.violates(r, case["forbids"])
        ]
        assert caught_by_group, case["case_id"]
        assert caught_by_pattern, case["case_id"]


def test_an_implicative_is_not_the_same_test_as_a_speaker_attribution() -> None:
    # Attribution is about who asserts the embedded claim; an implicative is
    # about whether the main verb itself settles the embedded event. No case
    # carried an implicative verb before these were written.
    cases = cases_module.load()
    speaker = {case["span"] for case in cases if case["phenomenon"] == "speaker"}
    implicative = {case["span"] for case in cases if case["phenomenon"] == "implicative"}
    assert speaker and implicative
    assert not (speaker & implicative)


def test_a_pattern_no_worked_failure_needs_is_refused() -> None:
    """Invariant 6, on its failure path.

    Twelve of the twenty-four cases carrying patterns were in this state when
    the check was written: every forbidden reading already failed a requirement
    group, so a pattern could have been misspelled or redundant and the set
    would have looked healthy.
    """
    broken = _case(
        forbids=[r"\b42\b"],
        forbidden_readings=["Die Maßnahme wirkt auf die Abbrecherquote."],
    )

    problems = cases_module.validate(_pair(broken))

    assert any("no worked failure needs" in problem for problem in problems)


def test_a_pattern_a_worked_failure_exercises_is_accepted() -> None:
    kept = _case(
        forbids=[r"\b42\b"],
        forbidden_readings=[
            "Die Maßnahme wirkt auf die Abbrecherquote.",
            "Die Maßnahme wirkt nicht auf 42 Prozent der Quote.",
        ],
    )

    pair = _pair(
        kept,
        english_forbidden=[
            "The measure affects the rate.",
            "The measure does not affect 42 per cent of the rate.",
        ],
    )

    assert cases_module.validate(pair) == []


def test_a_case_without_patterns_is_not_asked_for_one() -> None:
    # Eighteen cases rest on their requirement groups alone, concession among
    # them. The invariant is about patterns that exist, not about requiring any.
    without = _case(forbids=[], forbidden_readings=["Die Maßnahme wirkt auf die Abbrecherquote."])

    assert cases_module.validate(_pair(without)) == []
