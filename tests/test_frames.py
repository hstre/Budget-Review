"""The frame comparison: its set, its conditions and its scoring.

Three kinds of test, and the middle one is the one that would catch the
measurement proving what it set out to prove:

* the set's invariants hold, and the validator notices when they are broken on
  purpose — a validator that only ever passes is decoration
* the scoring separates finding an error from avoiding one, demonstrated on
  strategies whose ranking is known before the run: always-undecided,
  always-contradictory, never-revising, unreadable
* no prompt carries information from a frame later than the stage it is asked
  about, which is what makes the sequential comparison a sequential one
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


frame_object = _load("frame_object")
frame_cases = _load("frame_cases")
frame_conditions = _load("frame_conditions")
frame_score = _load("frame_score")
frame_run = _load("frame_run")

TEST = frame_cases.load(frame_cases.TEST_SET)
DEV = frame_cases.load(frame_cases.DEV_SET)


# ── the set ──────────────────────────────────────────────────────────────────


def test_the_declared_set_is_consistent():
    assert frame_cases.validate(TEST) == []
    assert frame_cases.validate(DEV, expect_pairs=False) == []


def test_the_set_has_the_declared_shape():
    assert len(TEST["cases"]) == 48
    by_category: dict[str, int] = {}
    for case in TEST["cases"]:
        by_category[case["category"]] = by_category.get(case["category"], 0) + 1
    assert by_category == {letter: 8 for letter in "ABCDEF"}
    assert len({case["pair"] for case in TEST["cases"]}) == 24


def test_nothing_in_the_held_out_set_comes_from_the_development_set():
    assert frame_cases.disjoint(DEV, TEST) == []


def test_no_prompt_carries_a_case_id_a_category_or_a_gold_note():
    assert frame_cases.leaks(TEST, frame_conditions.render) == []
    assert frame_cases.leaks(DEV, frame_conditions.render) == []


def test_every_trait_the_brief_asks_for_is_present():
    traits = {trait for case in TEST["cases"] for trait in case["traits"]}
    for required in ("local_already_correct", "irrelevant_context", "stays_ambiguous",
                     "salient_global_vs_local_exception"):
        assert required in traits, required


def test_both_revision_expectations_occur_often_enough_to_measure():
    counted: dict[str, int] = {}
    for case in TEST["cases"]:
        for stage in case["gold"]:
            counted[stage["revision"]] = counted.get(stage["revision"], 0) + 1
    assert counted["required"] >= 20
    assert counted["forbidden"] >= 20


def test_every_closed_field_is_required_somewhere():
    required = {
        name for case in TEST["cases"] for stage in case["gold"] for name in stage["must"]
    }
    assert required == set(frame_object.CLOSED_FIELDS)


# ── the validator's failure paths ────────────────────────────────────────────


def _broken(change):
    payload = copy.deepcopy(TEST)
    change(payload)
    return frame_cases.validate(payload)


def test_a_value_outside_the_vocabulary_is_caught():
    def change(payload):
        payload["cases"][0]["gold"][0]["must"]["permission"] = "maybe"
    assert any("not in vocabulary" in problem for problem in _broken(change))


def test_a_field_required_and_forbidden_at_once_is_caught():
    def change(payload):
        stage = payload["cases"][0]["gold"][1]
        stage["must_not"]["permission"] = [stage["must"]["permission"]]
    assert any("required and forbidden" in problem for problem in _broken(change))


def test_a_field_required_and_tolerated_at_once_is_caught():
    def change(payload):
        stage = payload["cases"][0]["gold"][1]
        stage.setdefault("tolerated", {})["permission"] = ["granted"]
    assert any("required and tolerated" in problem for problem in _broken(change))


def test_a_required_revision_that_gold_does_not_make_is_caught():
    def change(payload):
        case = next(c for c in payload["cases"] if c["case_id"] == "A01")
        case["gold"][1]["must"] = dict(case["gold"][0]["must"])
    assert any("does not make" in problem for problem in _broken(change))


def test_a_forbidden_revision_that_gold_makes_is_caught():
    def change(payload):
        case = next(c for c in payload["cases"] if c["case_id"] == "A05")
        case["gold"][1]["must"]["permission"] = "granted"
    assert any("revision forbidden" in problem for problem in _broken(change))


def test_a_pair_whose_decisive_frame_does_not_differ_is_caught():
    def change(payload):
        base = next(c for c in payload["cases"] if c["case_id"] == "A01")
        variant = next(c for c in payload["cases"] if c["case_id"] == "A02")
        variant["frames"][1]["text"] = base["frames"][1]["text"]
    assert any("does not differ" in problem for problem in _broken(change))


def test_a_pair_that_differs_before_the_decisive_frame_is_caught():
    def change(payload):
        variant = next(c for c in payload["cases"] if c["case_id"] == "A04")
        variant["frames"][0]["text"] = "Etwas ganz anderes."
    assert any("before the decisive frame" in problem for problem in _broken(change))


def test_a_stage_that_requires_nothing_is_caught():
    def change(payload):
        payload["cases"][0]["gold"][0]["must"] = {}
    assert any("measures nothing" in problem for problem in _broken(change))


def test_a_leak_planted_in_a_prompt_is_caught():
    leaked = copy.deepcopy(TEST)
    leaked["cases"] = leaked["cases"][:1]

    def render(case, after, condition):
        return frame_conditions.render(case, after, condition) + f"\n[{case['case_id']}]"

    assert frame_cases.leaks(leaked, render)


def test_an_overlap_planted_between_the_sets_is_caught():
    overlapping = copy.deepcopy(TEST)
    overlapping["cases"][0]["frames"][0]["text"] = DEV["cases"][0]["frames"][0]["text"]
    assert frame_cases.disjoint(DEV, overlapping)


# ── the conditions ───────────────────────────────────────────────────────────


def test_no_prompt_shows_a_frame_later_than_its_stage():
    """Future text must not be available to an earlier decision."""
    for case in TEST["cases"]:
        labels = [frame["frame"] for frame in case["frames"]]
        for condition in frame_conditions.CONDITIONS:
            for after in frame_conditions.plan(case, condition):
                prompt = frame_conditions.render(case, after, condition)
                for later in case["frames"][labels.index(after) + 1:]:
                    assert later["text"] not in prompt, (
                        case["case_id"], condition, after, later["frame"])


def test_the_local_condition_sees_only_the_first_frame():
    case = next(c for c in TEST["cases"] if len(c["frames"]) == 3)
    prompt = frame_conditions.render(case, "F1", "A")
    assert case["frames"][0]["text"] in prompt
    for later in case["frames"][1:]:
        assert later["text"] not in prompt


def test_the_one_shot_condition_sees_every_frame():
    case = next(c for c in TEST["cases"] if len(c["frames"]) == 3)
    prompt = frame_conditions.render(case, case["frames"][-1]["frame"], "B")
    for frame in case["frames"]:
        assert frame["text"] in prompt


def test_the_revision_control_gets_as_many_calls_as_the_staged_procedure():
    """D exists to rule out that extra calls, not the frames, are the cause."""
    for case in TEST["cases"]:
        assert len(frame_conditions.plan(case, "D")) == len(frame_conditions.plan(case, "C"))


def test_the_staged_one_shot_arm_has_the_same_horizon_as_the_procedure():
    for case in TEST["cases"]:
        assert frame_conditions.plan(case, "B_staged") == frame_conditions.plan(case, "C")


def test_the_staged_procedure_carries_its_previous_object_and_only_the_new_section():
    case = next(c for c in TEST["cases"] if len(c["frames"]) == 3)
    _, user = frame_conditions.build(case, "F3", "C", previous='{"permission": "granted"}')
    assert '"permission": "granted"' in user
    assert case["frames"][2]["text"] in user
    # The middle frame reaches the model through the object, not again as text.
    assert case["frames"][1]["text"] not in user


def test_the_revision_control_is_given_the_whole_text_every_pass():
    case = next(c for c in TEST["cases"] if len(c["frames"]) == 3)
    _, user = frame_conditions.build(case, "F3", "D", previous="{}", passes_done=1)
    for frame in case["frames"]:
        assert frame["text"] in user


def test_an_unknown_condition_is_refused():
    with pytest.raises(ValueError):
        frame_conditions.build(TEST["cases"][0], "F1", "Z")


# ── the object ───────────────────────────────────────────────────────────────


def test_a_reply_wrapped_in_prose_is_still_parsed():
    payload = {name: "undecided" for name in frame_object.CLOSED_FIELDS}
    parsed = frame_object.parse(f"Hier das Objekt:\n```json\n{json.dumps(payload)}\n```\nSoweit.")
    assert parsed.usable
    assert parsed.closed["permission"] == "undecided"


def test_a_value_outside_the_vocabulary_is_a_complaint_and_not_a_repair():
    payload = {name: "undecided" for name in frame_object.CLOSED_FIELDS}
    payload["permission"] = "vielleicht"
    parsed = frame_object.parse(json.dumps(payload))
    assert not parsed.usable
    assert "permission" not in parsed.closed


def test_a_missing_field_is_a_complaint():
    payload = {name: "undecided" for name in frame_object.CLOSED_FIELDS}
    del payload["status"]
    assert not frame_object.parse(json.dumps(payload)).usable


def test_a_boolean_is_read_as_yes_or_no():
    payload = {name: "undecided" for name in frame_object.CLOSED_FIELDS}
    payload["negated"] = True
    assert frame_object.parse(json.dumps(payload)).closed["negated"] == "yes"


def test_only_a_changed_decision_counts_as_a_revision():
    payload = {name: "undecided" for name in frame_object.CLOSED_FIELDS}
    before = frame_object.parse(json.dumps(payload | {"preferred_reading": "eine Lesart"}))
    after = frame_object.parse(json.dumps(payload | {"preferred_reading": "andere Worte"}))
    assert frame_object.differences(before, after) == []
    moved = frame_object.parse(json.dumps(payload | {"permission": "granted"}))
    assert frame_object.differences(before, moved) == ["permission"]


# ── the scoring ──────────────────────────────────────────────────────────────


def _dry(strategy: str, limit: int = 0) -> dict:
    rows: list[dict] = []
    records: list[dict] = []
    cases = TEST["cases"][:limit] if limit else TEST["cases"]
    for case in cases:
        for condition in frame_conditions.CONDITIONS:
            rows.extend(frame_run.run_case(
                case, condition, None, strategy=strategy, records=records, repeat=0))
    return frame_score.aggregate(rows)


def _share(report, condition, measure):
    return frame_score.share(report[condition]["overall"][measure])


def test_the_declared_expectation_is_reachable():
    """The ceiling: an answer equal to gold has to score one everywhere.

    Anything less means the scorer asks for something gold does not declare, or
    gold contradicts itself — and the measurement would be against an
    unreachable standard.
    """
    report = _dry("gold")
    for condition in frame_conditions.CONDITIONS:
        for measure in frame_score.MEASURES:
            cell = report[condition]["overall"][measure]
            if cell["total"]:
                assert frame_score.share(cell) == 1.0, (condition, measure, cell)


def test_answering_undecided_everywhere_cannot_win():
    report = _dry("undecided")
    assert _share(report, "C", "left_open") == 1.0
    assert _share(report, "C", "correct") == 0.0
    assert _share(report, "C", "contradiction_found") == 0.0
    assert _share(report, "C", "revised_when_due") == 0.0
    assert _share(report, "C", "exception_kept") == 0.0


def test_calling_everything_contradictory_takes_detection_and_loses_its_mirror():
    report = _dry("contrarian")
    assert _share(report, "C", "contradiction_found") == 1.0
    assert _share(report, "C", "contradiction_invented") == 0.0


def test_deciding_every_field_loses_openness():
    report = _dry("confident")
    assert _share(report, "C", "left_open") == 0.0
    assert _share(report, "C", "unsupported") == 0.0


def test_never_revising_holds_what_it_should_and_misses_what_it_should_not():
    report = _dry("never_revise")
    assert _share(report, "C", "held_when_not_due") == 1.0
    assert _share(report, "C", "revised_when_due") == 0.0


def test_an_unreadable_answer_earns_nothing_anywhere():
    """Not even the avoidance measures: silence is not a careful reading."""
    report = _dry("malformed")
    assert _share(report, "C", "usable") == 0.0
    for measure in ("correct", "left_open", "contradiction_found",
                    "contradiction_invented", "exception_kept", "unsupported"):
        assert _share(report, "C", measure) == 0.0, measure


def test_a_fabricated_quote_is_not_counted_as_a_citation():
    case = TEST["cases"][0]
    payload = {name: "undecided" for name in frame_object.CLOSED_FIELDS}
    payload |= {"supporting_quotes": ["Diesen Satz gibt es im Text nicht."]}
    row = frame_score.score_stage(
        case, case["gold"][0], frame_object.parse(json.dumps(payload)),
        None, condition="A", stage_index=0)
    assert row["citations_total"] == 1
    assert row["citations_hit"] == 0


def test_a_quote_from_the_text_is_counted():
    case = TEST["cases"][0]
    payload = {name: "undecided" for name in frame_object.CLOSED_FIELDS}
    payload |= {"supporting_quotes": [case["frames"][0]["text"]]}
    row = frame_score.score_stage(
        case, case["gold"][0], frame_object.parse(json.dumps(payload)),
        None, condition="A", stage_index=0)
    assert row["citations_hit"] == 1


# ── the comparison ───────────────────────────────────────────────────────────


def _rows(strategy: str, condition: str, label: str) -> list[dict]:
    rows: list[dict] = []
    records: list[dict] = []
    for case in TEST["cases"]:
        rows.extend(
            row | {"condition": label}
            for row in frame_run.run_case(
                case, condition, None, strategy=strategy, records=records, repeat=0)
        )
    return rows


def test_two_identical_arms_differ_by_nothing_and_the_interval_contains_zero():
    rows = _rows("gold", "C", "one") + _rows("gold", "C", "two")
    result = frame_score.paired_difference(rows, "one", "two", "correct", draws=300)
    assert result["difference"] == 0.0
    assert result["interval"] == [0.0, 0.0]
    assert result["comparable_pairs"] == 24


def test_a_better_arm_shows_a_positive_difference_clear_of_zero():
    rows = _rows("gold", "C", "good") + _rows("undecided", "C", "poor")
    result = frame_score.paired_difference(rows, "good", "poor", "correct", draws=300)
    assert result["difference"] == 1.0
    assert result["interval"][0] > 0.5
    assert result["pairs_favouring_left"] == 24


def test_the_comparison_resamples_pairs_and_not_cases():
    # Minimal pairs are not independent of each other: the two halves differ in
    # one sentence. Resampling cases would narrow the interval by pretending
    # there are 48 independent observations where there are 24 constructions.
    rows = _rows("gold", "C", "good") + _rows("undecided", "C", "poor")
    result = frame_score.paired_difference(rows, "good", "poor", "correct", draws=50)
    assert result["comparable_pairs"] == 24


def test_a_measure_no_arm_offers_is_reported_as_incomparable():
    rows = _rows("gold", "A", "left") + _rows("gold", "A", "right")
    result = frame_score.paired_difference(rows, "left", "right", "history", draws=50)
    assert result.get("comparable_pairs") == 0


def test_a_tolerated_field_is_read_as_the_whole_set_and_not_one_value():
    """What `implied` hands back decides whether a revision check is sound.

    Collapsing a tolerated set to its first value survived every other test on
    the current set, because no stage happens to tolerate a non-bookkeeping
    field that includes the previous stage's value. It would stop surviving the
    moment one did, and the contract is worth asserting directly.
    """
    stage = {"must": {"permission": "granted"},
             "tolerated": {"capability": ["affirmed", "undecided"]}}
    assert frame_cases.implied(stage, "permission") == "granted"
    assert frame_cases.implied(stage, "capability") == ["affirmed", "undecided"]
    assert frame_cases.implied(stage, "quantifier") == frame_object.UNDECIDED


def test_a_stage_that_tolerates_the_earlier_value_cannot_demand_a_revision():
    before = {"after": "F1", "must": {"permission": "granted"}, "must_not": {},
              "revision": "n/a", "note": "x"}
    after = {"after": "F2", "must": {}, "tolerated": {"permission": ["granted", "conditional"]},
             "must_not": {}, "revision": "required", "note": "x"}
    case = {"case_id": "X", "gold": [before, after]}
    problems = frame_cases._stage_problems(case, after, before)
    assert any("does not make" in problem for problem in problems)


# ── the pre-registered criterion ─────────────────────────────────────────────

frame_compare = _load("frame_compare")


def _rows_with(left_hits: int, right_hits: int, measure: str = "correct") -> list[dict]:
    """Twenty-four pairs, one opportunity each, with the hits spread evenly."""
    rows = []
    for index in range(24):
        for condition, hits in (("C", left_hits), ("B_staged", right_hits)):
            rows.append({
                "condition": condition, "pair": f"p{index}", "case_id": f"c{index}",
                "category": "A", "stage": "F1",
                f"{measure}_hit": 1 if index < hits else 0,
                f"{measure}_total": 1,
            })
    return rows


def test_a_gain_whose_interval_crosses_zero_does_not_meet_the_criterion():
    """A difference in the right direction is not enough, by design."""
    verdict = frame_compare.criterion(_rows_with(13, 11))
    primary = verdict["parts"][0]
    assert primary["detail"]["difference"] > 0
    assert primary["holds"] is False
    assert verdict["met"] is False


def test_a_clear_gain_meets_the_first_part():
    verdict = frame_compare.criterion(_rows_with(24, 2))
    assert verdict["parts"][0]["holds"] is True


def test_a_measure_that_falls_clearly_fails_its_part():
    rows = _rows_with(24, 2) + _rows_with(1, 23, "left_open")
    verdict = frame_compare.criterion(rows)
    openness = next(part for part in verdict["parts"] if "left_open" in part["claim"])
    assert openness["holds"] is False
    assert verdict["met"] is False


def test_a_measure_that_merely_wobbles_does_not_fail_its_part():
    rows = _rows_with(24, 2) + _rows_with(12, 13, "left_open")
    openness = next(
        part for part in frame_compare.criterion(rows)["parts"] if "left_open" in part["claim"]
    )
    assert openness["holds"] is True


def test_every_part_of_the_declared_criterion_is_checked():
    verdict = frame_compare.criterion(_rows_with(24, 2))
    assert {part["part"] for part in verdict["parts"]} == {1, 2, 3, 4}


def test_an_arm_that_cannot_return_the_object_is_withdrawn():
    report = {"report": {"C": {"overall": {"usable": {"hit": 50, "total": 100}}}}}
    assert frame_compare.withdrawn(report) == ["C: usable 0.50 below 0.90"]


def test_an_arm_that_answers_is_not_withdrawn():
    report = {"report": {"C": {"overall": {"usable": {"hit": 99, "total": 100}}}}}
    assert frame_compare.withdrawn(report) == []


def test_a_comparison_with_the_local_arm_is_restricted_to_the_stage_both_answer():
    """The defect the first reading of the live run carried.

    A is asked once, about the first frame; the staged arms are asked at every
    frame. Summing each arm's own stages made context look as though it cost
    correctness, clear of zero, where the stage-for-stage comparison showed no
    difference. Any comparison involving A has to ask the same question of both.
    """
    rows = [
        {"condition": "A", "pair": "p1", "case_id": "c1", "category": "A", "stage": "F1",
         "correct_hit": 1, "correct_total": 1},
        {"condition": "B_staged", "pair": "p1", "case_id": "c1", "category": "A",
         "stage": "F1", "correct_hit": 1, "correct_total": 1},
        {"condition": "B_staged", "pair": "p1", "case_id": "c1", "category": "A",
         "stage": "F2", "correct_hit": 0, "correct_total": 1},
    ]
    restricted = frame_compare.comparable_rows(rows, "B_staged", "A")
    assert len(restricted) == 2
    assert all(row["stage"] == "F1" for row in restricted)
    fair = frame_score.paired_difference(restricted, "A", "B_staged", "correct", draws=50)
    assert fair["difference"] == 0.0
    unfair = frame_score.paired_difference(rows, "A", "B_staged", "correct", draws=50)
    assert unfair["difference"] > 0


def test_a_comparison_between_two_staged_arms_keeps_every_stage():
    rows = [
        {"condition": "C", "pair": "p1", "case_id": "c1", "category": "A", "stage": "F2",
         "correct_hit": 1, "correct_total": 1},
        {"condition": "B_staged", "pair": "p1", "case_id": "c1", "category": "A",
         "stage": "F2", "correct_hit": 0, "correct_total": 1},
    ]
    assert frame_compare.comparable_rows(rows, "C", "B_staged") == rows


# ── the sixth arm: bookkeeping without staging ───────────────────────────────


def test_the_object_arm_sees_the_whole_text_in_one_call():
    case = next(c for c in TEST["cases"] if len(c["frames"]) == 3)
    assert frame_conditions.plan(case, "B_object") == [case["frames"][-1]["frame"]]
    prompt = frame_conditions.render(case, case["frames"][-1]["frame"], "B_object")
    for frame in case["frames"]:
        assert frame["text"] in prompt


def test_the_object_arm_asks_for_what_the_staged_arm_asks_for():
    """It is C's bookkeeping minus C's staging — that is the whole point of it."""
    case = TEST["cases"][0]
    _, first = frame_conditions.build(case, "F1", "C")
    _, later = frame_conditions.build(
        case, case["frames"][-1]["frame"], "C", previous="{}")
    _, once = frame_conditions.build(case, case["frames"][-1]["frame"], "B_object")
    for demand in ("mehrere Lesarten", "undecided", "history", "Präzisierung"):
        assert demand in first + later, demand
        assert demand in once, demand


def test_the_object_arm_is_not_given_a_previous_object():
    case = TEST["cases"][0]
    _, once = frame_conditions.build(case, case["frames"][-1]["frame"], "B_object")
    assert "Bisheriges Objekt" not in once
    assert "Neu hinzugekommener Abschnitt" not in once


def test_the_one_shot_arms_are_compared_on_the_stage_they_answer():
    rows = [
        {"condition": "C", "pair": "p1", "case_id": "c1", "category": "A", "stage": "F1",
         "correct_hit": 0, "correct_total": 1},
        {"condition": "C", "pair": "p1", "case_id": "c1", "category": "A", "stage": "F2",
         "correct_hit": 1, "correct_total": 1},
        {"condition": "B", "pair": "p1", "case_id": "c1", "category": "A", "stage": "F2",
         "correct_hit": 1, "correct_total": 1},
    ]
    restricted = frame_compare.comparable_rows(rows, "C", "B")
    assert [row["stage"] for row in restricted] == ["F2", "F2"]
    fair = frame_score.paired_difference(restricted, "C", "B", "correct", draws=50)
    assert fair["difference"] == 0.0


def test_the_last_stage_is_read_off_the_rows_and_not_assumed():
    rows = [
        {"condition": "B", "case_id": "two", "stage": "F2"},
        {"condition": "B", "case_id": "three", "stage": "F3"},
    ]
    assert frame_compare.last_stage_of(rows) == {"two": "F2", "three": "F3"}


def test_two_arms_that_answer_at_opposite_ends_are_not_compared_at_all():
    rows = [
        {"condition": "A", "pair": "p", "case_id": "c", "category": "A", "stage": "F1"},
        {"condition": "B", "pair": "p", "case_id": "c", "category": "A", "stage": "F2"},
    ]
    assert frame_compare.comparable_rows(rows, "A", "B") == []


def test_an_arm_asked_for_a_history_is_scored_on_it():
    case = next(c for c in TEST["cases"] if len(c["frames"]) > 1)
    payload = {name: "undecided" for name in frame_object.CLOSED_FIELDS}
    without = frame_score.score_stage(
        case, case["gold"][-1], frame_object.parse(json.dumps(payload)), None,
        condition="B_object", stage_index=0)
    assert without["history_total"] == 1
    assert without["history_hit"] == 0
    payload["history"] = [{"frame": "F2", "change": "x", "reason": "y"}]
    with_one = frame_score.score_stage(
        case, case["gold"][-1], frame_object.parse(json.dumps(payload)), None,
        condition="B_object", stage_index=0)
    assert with_one["history_hit"] == 1


def test_the_one_shot_arms_without_a_history_demand_are_not_scored_on_one():
    case = next(c for c in TEST["cases"] if len(c["frames"]) > 1)
    payload = {name: "undecided" for name in frame_object.CLOSED_FIELDS}
    row = frame_score.score_stage(
        case, case["gold"][-1], frame_object.parse(json.dumps(payload)), None,
        condition="B", stage_index=0)
    assert row["history_total"] == 0


# ── the standing policy: a difference is read against one arm's own spread ───


def test_a_run_without_a_repeat_has_no_noise_floor():
    """And the report has to say so rather than let a single draw read as settled."""
    rows = [{"condition": "C", "repeat": 0, "correct_hit": 1, "correct_total": 1}]
    assert frame_compare.drift(rows) == {}


def test_a_repeated_arm_reports_its_own_spread():
    rows = [
        {"condition": "C", "repeat": 0, "correct_hit": 10, "correct_total": 10},
        {"condition": "C", "repeat": 1, "correct_hit": 8, "correct_total": 10},
    ]
    measured = frame_compare.drift(rows)
    assert measured["correct"]["shares"] == [1.0, 0.8]
    assert measured["correct"]["spread"] == 0.2


def test_a_measure_only_one_repeat_offers_is_left_out():
    rows = [
        {"condition": "C", "repeat": 0, "history_hit": 1, "history_total": 1,
         "correct_hit": 1, "correct_total": 1},
        {"condition": "C", "repeat": 1, "correct_hit": 1, "correct_total": 1},
    ]
    measured = frame_compare.drift(rows)
    assert "correct" in measured
    assert "history" not in measured


def test_the_paid_workflow_asks_for_two_repeats_by_default():
    workflow = (ROOT / ".github" / "workflows" / "live-deepseek.yml").read_text(
        encoding="utf-8"
    )
    block = workflow[workflow.index("frame_repeats:"):]
    block = block[: block.index("frame_max_tokens:")]
    assert 'default: "2"' in block
