"""The overlap threshold is a condition of the comparison, and has to be stated as one.

Three scripts decide when a live span reaches a gold span, and two of them fixed
the decision at one hard-coded value. That is only harmless where the threshold
decides nothing — and on a long court decision it decides 38 of 49 spans, so a
verdict stated at one value can be a statement about the rule rather than about
the runs.

These tests hold the three scripts to one condition space, and hold
`compare_runs` to saying whether its verdict survives it.
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compare_runs = _load("compare_runs")
gold_ceiling = _load("gold_ceiling")
measure_recall = _load("measure_recall")
alignment_space = _load("alignment_space")


@pytest.mark.parametrize("module", [compare_runs, gold_ceiling])
def test_no_script_carries_a_single_hard_coded_threshold(module) -> None:
    # The name is gone on purpose: a lone THRESHOLD is what let the condition go
    # undeclared in the first place, and a reader who greps for it should find
    # the sweep instead of a constant.
    assert not hasattr(module, "THRESHOLD"), module.__name__
    assert len(module.SWEEP) > 1


@pytest.mark.parametrize("module", [compare_runs, gold_ceiling])
def test_every_sweep_contains_the_two_values_the_project_publishes(module) -> None:
    # Otherwise a published figure cannot be located in the sweep, and the
    # sweep becomes a second set of numbers rather than context for the first.
    assert {0.5, 0.8} <= set(module.SWEEP), module.__name__


def test_the_recall_script_still_reports_more_than_one_threshold() -> None:
    assert len(measure_recall.OVERLAP_THRESHOLDS) > 1


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ({"a"}, {"a", "b"}, "strikte Verbesserung"),
        ({"a", "b"}, {"a"}, "strikte Verschlechterung"),
        ({"a", "b"}, {"a", "c"}, "Tausch"),
        ({"a"}, {"a"}, "identisch"),
        (set(), set(), "identisch"),
    ],
)
def test_the_verdict_names_the_four_shapes_a_comparison_can_have(
    left: set[str], right: set[str], expected: str
) -> None:
    assert compare_runs.verdict_for(left, right) == expected


def test_an_empty_run_against_a_full_one_is_not_called_a_trade() -> None:
    # A run that found nothing is a strict loss, not a trade. Calling it a trade
    # would make the union argument look applicable where there is nothing to
    # union.
    assert compare_runs.verdict_for(set(), {"a", "b"}) == "strikte Verbesserung"
    assert compare_runs.verdict_for({"a", "b"}, set()) == "strikte Verschlechterung"


def test_a_verdict_can_differ_between_two_thresholds() -> None:
    """The case the sweep exists for, constructed so it cannot be argued away.

    Two runs where one reaches a gold span fully and the other reaches it in
    part: at a loose threshold they are identical, at a strict one the second
    has lost a span. A comparison reported at one threshold would state one of
    those two as the fact.
    """
    loose = compare_runs.verdict_for({"G1"}, {"G1"})
    strict = compare_runs.verdict_for({"G1"}, set())
    assert loose != strict
    assert loose == "identisch"
    assert strict == "strikte Verschlechterung"


def test_the_count_responds_to_the_threshold_it_is_given() -> None:
    """What `test_the_ceiling_reports_one_figure_per_threshold` did not check.

    That test asserted one figure per threshold and nothing about the figures,
    so a version that counted every threshold at 0.8 passed it. The mutation
    survived, which is how the gap was found — and the fix was one counting
    function for all three scripts rather than a third expression.
    """
    shares = [0.0, 0.6, 0.85, 1.0]
    hits = measure_recall.hits_by_threshold(shares, (0.5, 0.8, 0.95))
    assert hits == {0.5: 3, 0.8: 2, 0.95: 1}


def test_the_ceiling_counts_through_that_one_function() -> None:
    # Not style: a second copy of the expression is what let a single threshold
    # sit in two scripts while a third reported two.
    assert "hits_by_threshold" in inspect.getsource(gold_ceiling.ceiling)
    assert "hits_by_threshold" in inspect.getsource(alignment_space.hits_by_threshold)


def test_the_ceiling_reports_one_figure_per_threshold() -> None:
    gold = {
        "document_id": "d",
        "claims": [
            {"proposal_id": "G1", "raw_span": "alpha beta"},
            {"proposal_id": "G2", "raw_span": "gamma delta"},
        ],
    }
    result = gold_ceiling.ceiling(gold, "alpha beta and gamma delta.", "d")
    assert set(result["reached"]) == set(gold_ceiling.SWEEP)
    assert result["spans"] == 2
