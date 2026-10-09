"""The review prompt must carry the set and not the results."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "semantic_cases_review_prompt.py"


def _module():
    spec = importlib.util.spec_from_file_location("review_prompt", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _module()


def test_the_live_prompt_carries_no_measured_result():
    prompt = MODULE.build(
        MODULE.BRIEF.read_text(encoding="utf-8"),
        __import__("json").loads(MODULE.CASES.read_text(encoding="utf-8")),
    )
    assert MODULE.leaks(prompt) == []


def test_the_cut_drops_the_defects_the_runs_found():
    brief = (
        "# Auftrag\n\nDie fünf Fragen.\n\n"
        "## Gefundene Gold-Mängel, offen bis zur Durchsicht\n\n"
        "**M-1:** 38 von 122 Claims kamen übersetzt zurück.\n"
    )
    kept = MODULE.brief_before_results(brief)
    assert "Die fünf Fragen." in kept
    assert "M-1" not in kept
    assert "122" not in kept


def test_a_brief_without_the_heading_is_refused_rather_than_guessed():
    # If the heading is ever renamed, cutting at a guessed offset would silently
    # send the results to a review that may not see them.
    with pytest.raises(SystemExit):
        MODULE.brief_before_results("# Auftrag\n\nKeine Mängelliste.\n")


@pytest.mark.parametrize(
    "smuggled",
    [
        "Der Lauf ergab M-2 als offenen Mangel.",
        "Siehe §3ah für den zweiten Lauf.",
        "38 von 122 Propositionen kamen auf Englisch zurück.",
        "Jetzt 0 von 123.",
        "Bedeutung erhalten: 69 von 72 Fall-Läufen.",
        "Die Schicht hat still übersetzt.",
    ],
)
def test_each_shape_of_a_result_is_caught(smuggled):
    assert MODULE.leaks(f"# Auftrag\n\n{smuggled}\n")


def test_a_brief_that_only_discusses_the_method_is_not_a_leak():
    assert MODULE.leaks("Die Bedingungen sind mechanisch und absichtlich grob.") == []


def test_the_prompt_explains_the_field_semantics_a_reviewer_needs():
    # Without these a reviewer cannot judge a token group or the fifth invariant,
    # and would review a set it has misread.
    assert "Wortgrenzen" in MODULE.PREAMBLE
    assert "Teilstring" in MODULE.PREAMBLE
    assert "abgeschaltet" in MODULE.PREAMBLE


def test_the_prompt_asks_for_the_cases_verbatim():
    cases = {"cases": [{"case_id": "neg-01-de", "span": "wirkt nicht"}]}
    prompt = MODULE.build("# Auftrag\n\n## Gefundene Gold-Mängel\n", cases)
    assert "neg-01-de" in prompt
    assert "wirkt nicht" in prompt


def test_disagreement_is_put_as_a_filter_and_not_as_a_vote():
    # The one rule that makes an advisory review mean anything; if it goes
    # missing the reviews become a majority vote on meaning.
    folded = " ".join(MODULE.TASK.split())
    assert "Filter auf Beispiele" in folded
    assert "keine Abstimmung über Bedeutung" in folded
