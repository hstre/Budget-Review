"""The repair pass's admission rule, decided before the pass exists.

A second call over the uncovered passages is only worth making if what comes
back cannot re-say what is already in the graph. The double run measured what
happens without such a rule: 141 claims without a gold match for two extra gold
spans. So the rule is pinned here, and the paid experiment can come later.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location("repair", ROOT / "scripts" / "repair_merge.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


repair = _module()
GAPS = [(100, 200), (400, 500)]


def test_a_new_claim_inside_a_requested_gap_is_admitted() -> None:
    assert repair.verdict((100, 200), "new", GAPS, [], set()) == ("admit", "new_claim")


def test_a_claim_outside_every_requested_gap_is_rejected() -> None:
    """The pass was asked about specific passages; elsewhere it is a second opinion."""
    assert repair.verdict((300, 350), "new", GAPS, [], set()) == (
        "reject",
        "outside_requested_gap",
    )


def test_a_claim_that_adds_no_uncovered_text_is_rejected() -> None:
    """The near-duplicate the double run produced in bulk."""
    assert repair.verdict((100, 200), "new", GAPS, [(90, 210)], set()) == (
        "reject",
        "adds_no_uncovered_text",
    )


def test_half_new_characters_is_enough() -> None:
    assert repair.verdict((100, 200), "new", GAPS, [(100, 150)], set())[0] == "admit"


def test_just_under_half_is_not() -> None:
    assert repair.verdict((100, 200), "new", GAPS, [(100, 151)], set())[0] == "reject"


def test_known_content_at_a_new_anchor_is_admitted_and_flagged() -> None:
    """Two speech acts, not one claim with two anchors — the case that matters."""
    assert repair.verdict((100, 200), "known", GAPS, [], {"known"}) == (
        "admit",
        "duplicate_content_other_anchor",
    )


def test_known_content_over_covered_text_is_still_rejected() -> None:
    """Being a second speech act does not excuse adding no new anchor."""
    assert repair.verdict((100, 200), "known", GAPS, [(90, 210)], {"known"}) == (
        "reject",
        "adds_no_uncovered_text",
    )


def test_a_claim_reaching_into_a_gap_counts_as_inside_it() -> None:
    """A gap boundary is deterministic, an argument is not; touching is enough."""
    assert repair.verdict((150, 250), "new", GAPS, [], set())[0] == "admit"
