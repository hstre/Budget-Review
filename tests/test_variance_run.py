"""The spread report, checked where it decides what the run means.

This experiment exists to say whether a four-span difference between two runs
is sampling or a real effect, so its own arithmetic has to be right: a
stability split that miscounts would turn an unstable extractor into a stable
one and retroactively justify every single-run comparison in this repository.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location("variance", ROOT / "scripts" / "variance_run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


variance = _module()
GOLD = ["G01", "G02", "G03", "G04"]


def test_a_span_every_run_reaches_is_stable_not_flipping() -> None:
    always, never, flipping = variance.stability([{"G01"}, {"G01"}, {"G01"}], GOLD)

    assert always == ["G01"]
    assert flipping == []
    assert never == ["G02", "G03", "G04"]


def test_a_span_no_run_reaches_is_never_not_flipping() -> None:
    _, never, flipping = variance.stability([{"G01"}, {"G01"}], GOLD)

    assert never == ["G02", "G03", "G04"]
    assert flipping == []


def test_flipping_spans_carry_their_hit_count() -> None:
    """A span found in three runs of four is not stable, and the count says so."""
    runs = [{"G01", "G02"}, {"G01"}, {"G01"}, {"G03"}]

    always, never, flipping = variance.stability(runs, GOLD)

    assert always == []
    assert never == ["G04"]
    assert flipping == [("G01", 3), ("G02", 1), ("G03", 1)]


def test_the_ranking_puts_the_most_often_found_span_first() -> None:
    runs = [{"G01", "G02"}, {"G02"}, {"G03"}]

    _, _, flipping = variance.stability(runs, GOLD)

    assert [pid for pid, _ in flipping] == ["G02", "G01", "G03"]
    assert dict(flipping) == {"G02": 2, "G01": 1, "G03": 1}


def test_a_span_missing_from_the_gold_list_is_not_reported() -> None:
    """The gold list is the reference; an id only a run carries is not a span."""
    always, never, flipping = variance.stability([{"G01", "X99"}, {"G01"}], GOLD)

    assert "X99" not in always + never + [pid for pid, _ in flipping]
