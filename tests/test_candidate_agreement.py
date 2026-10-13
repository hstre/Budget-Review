"""Whether disagreement between repeats is a usable signal, and what it rests on.

The script's answer on the stored runs is a perfect separation, and the reason
to test it carefully is that a perfect separation on two failures is exactly the
kind of result that invites being overread. These tests pin the three agreement
measures, the arithmetic of the separation cells, and — most of all — that the
report states how few failures it rests on, since that sentence is the finding's
only guard against being quoted without it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "candidate_agreement", ROOT / "scripts" / "candidate_agreement.py"
)
agreement = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agreement)


def test_two_runs_that_found_nothing_agree_about_the_document() -> None:
    # Counting two empty runs as total disagreement would make the emptiest
    # case look like the most uncertain one, which inverts the signal.
    assert agreement.jaccard(set(), set()) == 1.0


def test_one_empty_run_against_a_non_empty_one_does_not_agree() -> None:
    assert agreement.jaccard(set(), {"a"}) == 0.0


def test_identical_repeats_agree_completely() -> None:
    runs = [["Die Regierung kündigte den Zuschlag an."]] * 3
    assert agreement.token_agreement(runs) == 1.0
    assert agreement.exact_agreement(runs) is True


def test_a_rephrasing_is_not_counted_as_total_disagreement() -> None:
    """Why the measure is over tokens and not over whole strings.

    The wording is the unstable half of a claim, so an exact-string measure
    reports every rephrasing as complete disagreement and the score fires on
    cases where the repeats said the same thing differently.
    """
    runs = [["alpha beta gamma"], ["alpha beta delta"]]
    assert agreement.exact_agreement(runs) is False
    assert 0.0 < agreement.token_agreement(runs) < 1.0


def test_a_single_repeat_cannot_disagree_with_itself() -> None:
    # One candidate is not a distribution. Reporting anything but full
    # agreement would invent a spread from a sample of one.
    assert agreement.token_agreement([["alpha"]]) == 1.0


def test_two_runs_with_nothing_in_common_agree_about_nothing() -> None:
    assert agreement.token_agreement([["alpha beta"], ["gamma delta"]]) == 0.0


@pytest.mark.parametrize(
    ("counts", "expected"),
    [([1, 1, 1], True), ([1, 2, 1], False), ([2, 2], True), ([0, 1], False)],
)
def test_the_claim_count_agreement_is_identity_across_repeats(
    counts: list[int], expected: bool
) -> None:
    assert agreement.count_agreement(counts) is expected


def _measured(monkeypatch: pytest.MonkeyPatch, rows: dict) -> dict:
    monkeypatch.setattr(agreement, "rows_for", lambda _directory: rows)
    return agreement.measure(Path("unused"))


def _run(contents: list[str], passed: bool) -> dict:
    return {
        "contents": contents,
        "claims_on_span": len(contents),
        "meaning_preserved": passed,
    }


def test_a_case_whose_repeats_differ_and_fail_lands_in_the_matching_cell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _measured(
        monkeypatch,
        {"sco": [_run(["alpha"], False), _run(["beta"], True), _run(["beta"], True)]},
    )
    assert result["flagged_and_failed"] == ["sco"]
    assert result["flagged_but_passed"] == []
    assert result["failed_but_unflagged"] == []
    assert result["failed_runs"] == 1


def test_a_case_that_fails_without_disagreeing_is_reported_as_a_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cell that would refute the signal, which has to be visible when it fills.

    Three repeats agreeing on the same wrong reading is precisely the failure a
    spread-based score cannot see. Folding it in with the rest would let the
    separation look perfect while the signal was blind.
    """
    result = _measured(
        monkeypatch,
        {"agree": [_run(["alpha"], False)] * 3},
    )
    assert result["failed_but_unflagged"] == ["agree"]
    assert result["flagged_and_failed"] == []


def test_a_case_that_disagrees_and_still_passes_is_a_false_alarm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _measured(
        monkeypatch,
        {"noisy": [_run(["alpha"], True), _run(["beta"], True)]},
    )
    assert result["flagged_but_passed"] == ["noisy"]
    assert result["failed_cases"] == []


def test_the_three_cells_account_for_every_flagged_or_failed_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = {
        "hit": [_run(["a"], False), _run(["b"], True)],
        "miss": [_run(["a"], False)] * 2,
        "alarm": [_run(["a"], True), _run(["b"], True)],
        "clean": [_run(["a"], True)] * 2,
    }
    result = _measured(monkeypatch, rows)
    accounted = (
        set(result["flagged_and_failed"])
        | set(result["flagged_but_passed"])
        | set(result["failed_but_unflagged"])
    )
    assert accounted == set(result["flagged_cases"]) | set(result["failed_cases"])
    assert "clean" not in accounted


def test_the_report_names_how_few_failures_the_separation_rests_on(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The separation is worth nothing without this sentence, so the sentence is
    # part of the output and not part of the prose around it.
    result = _measured(
        monkeypatch,
        {"sco": [_run(["alpha"], False), _run(["beta"], True), _run(["beta"], True)]},
    )
    agreement.report(result)
    printed = capsys.readouterr().out
    assert "1" in printed
    assert "kalibrierte" in printed


def test_a_set_with_no_failures_says_nothing_is_testable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    result = _measured(monkeypatch, {"clean": [_run(["a"], True)] * 3})
    agreement.report(result)
    printed = capsys.readouterr().out
    assert "kein signal prüfbar" in printed.lower()
