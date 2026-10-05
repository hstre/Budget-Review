"""Re-keying finished runs, pinned where a looser key could flatter itself.

The measurement exists to decide whether the surface text belongs in a claim's
identity. Two ways it could answer yes without cause: a rung that silently drops
claims rather than merging them, and merges inside one run that are not charged
to the rung that caused them.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "identity_ladder", ROOT / "scripts" / "identity_ladder.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ladder = _module()


def _claim(content: str, span: str, claim_type: str = "fact") -> dict:
    return {"claim_type": claim_type, "canonical_content": content, "raw_span": span}


def test_a_line_break_in_the_span_is_the_same_claim_one_rung_up() -> None:
    wrapped = _claim("The budget rises.", "the budget\nrises by four per cent")
    flowing = _claim("The budget rises.", "the budget rises by four per cent")

    assert ladder.key(wrapped, "exact") != ladder.key(flowing, "exact")
    assert ladder.key(wrapped, "span") == ladder.key(flowing, "span")


def test_a_rewording_is_the_same_proposition_but_not_the_same_content() -> None:
    first = _claim("Remote work increases productivity.", "a")
    second = _claim("productivity increases remote work", "b")

    assert ladder.key(first, "content") != ladder.key(second, "content")
    # Order is thrown away, so this rung cannot tell a reversal from a rewording.
    # That is a known collision of the stand-in, measured as a merge rather than
    # hidden, and the reason the rung is a bound and not a CIK.
    assert ladder.key(first, "proposition") == ladder.key(second, "proposition")


def test_the_claim_type_stays_part_of_every_key() -> None:
    fact = _claim("The budget rises.", "x", "fact")
    forecast = _claim("The budget rises.", "x", "forecast")

    for rung in ladder.RUNGS:
        assert ladder.key(fact, rung) != ladder.key(forecast, rung)


def test_merges_are_counted_against_the_exact_key() -> None:
    """Two proposals already identical today must not be charged to the rung."""
    duplicate = [_claim("Same.", "x"), _claim("Same.", "x")]

    assert ladder.merges(duplicate, "proposition") == 0

    folded = [_claim("The budget rises.", "x"), _claim("the  budget rises", "y")]
    assert ladder.merges(folded, "proposition") == 1


def test_the_stable_core_is_what_every_run_holds() -> None:
    runs = [{"a", "b"}, {"a", "c"}, {"a", "b", "c"}]

    assert ladder.stable_core(runs) == 1
    assert ladder.stable_core([]) == 0


def test_jaccard_is_averaged_over_pairs_not_over_runs() -> None:
    assert ladder.mean_jaccard([{"a"}, {"a"}]) == 1.0
    assert ladder.mean_jaccard([{"a"}, {"b"}]) == 0.0
    assert ladder.mean_jaccard([{"a"}]) == 0.0


def test_the_report_grows_the_core_without_losing_claims(capsys) -> None:
    """End to end: the same proposition worded differently in two runs."""
    run_one = [_claim("The budget rises.", "the budget\nrises"), _claim("Only here.", "z")]
    run_two = [_claim("the  budget  rises", "the budget rises")]

    rows = ladder.report("probe", [run_one, run_two])

    assert rows["exact"]["core"] == 0, "nothing matches on the exact key"
    assert rows["proposition"]["core"] == 1, "one proposition is in both runs"
    assert rows["proposition"]["claims"] == 3
    assert "Kern exact → proposition: 0 → 1" in capsys.readouterr().out
