"""The drift screen, checked in both directions.

A screen that never reports is worthless and a screen that reports correct work
is worse than nothing, because the noise buries the one case that matters. Both
directions are pinned here: the frozen packets must stay silent, and a number
the quoted span does not contain must be named.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "src" / "budget_review" / "fixtures"


def _module():
    spec = importlib.util.spec_from_file_location("drift", ROOT / "scripts" / "measure_drift.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


drift = _module()

PACKETS = sorted(FIXTURES.rglob("*packet*.json"))


def test_the_fixtures_carry_packets_to_check() -> None:
    assert len(PACKETS) >= 3


@pytest.mark.parametrize("packet", PACKETS, ids=lambda path: path.stem)
def test_a_hand_built_packet_reports_no_invented_number(packet, capsys) -> None:
    """These were written by hand, so every report here is a false alarm."""
    flagged = drift.report(packet)

    assert flagged == 0, capsys.readouterr().out


def test_a_number_the_span_does_not_contain_is_reported(tmp_path, capsys) -> None:
    packet = {
        "claims": [
            {
                "proposal_id": "C01",
                "canonical_content": "The programme will graduate at least 1100 participants.",
                "raw_span": "graduate at least 110 of them",
            }
        ]
    }
    path = tmp_path / "packet.json"
    path.write_text(json.dumps(packet), encoding="utf-8")

    assert drift.report(path) == 1
    assert "1100" in capsys.readouterr().out


def test_a_spelled_out_number_in_the_span_is_not_a_finding() -> None:
    """The contract asks for normalised content, so 12 against "twelve" is correct."""
    assert (
        drift.numbers("the first 12 months") - drift.numbers("During the first twelve months")
        == set()
    )


def test_a_leading_one_is_read_as_an_article_not_a_quantity() -> None:
    """ "One six-person team" reported a correct claim before this was handled."""
    claim = "One six-person team completed 48 rather than 40 tickets"
    span = "In our six-person team, completed tickets rose from 40 to 48"

    assert drift.numbers(claim) - drift.numbers(span) == set()


def test_a_thousands_separator_does_not_invent_a_difference() -> None:
    assert drift.numbers("1,200 laptops") == drift.numbers("1200 laptops")


def test_trailing_zeros_are_kept_so_250_never_matches_25() -> None:
    assert drift.numbers("250") - drift.numbers("25") == {"250"}


def test_word_overlap_ignores_function_words() -> None:
    assert drift.content_words("the cohort of the programme") == {"cohort", "programme"}


def _claim(identifier: str, content: str, start: int, end: int) -> dict:
    return {
        "claim_node_id": identifier,
        "canonical_content": content,
        "raw_span": content,
        "anchor_start": start,
        "anchor_end": end,
    }


def test_the_same_statement_at_two_places_is_reported() -> None:
    """Two speech acts, and the pair a repair pass would otherwise re-create."""
    claims = [
        _claim("A", "The Government contended the remedy was effective", 0, 50),
        _claim("B", "The Government contended the remedy was effective", 400, 450),
    ]

    assert [(a, b) for a, b, _ in drift.near_duplicates(claims)] == [("A", "B")]


def test_overlapping_anchors_are_the_ordinary_case_not_a_duplicate() -> None:
    claims = [
        _claim("A", "The Government contended the remedy was effective", 0, 50),
        _claim("B", "The Government contended the remedy was effective", 40, 90),
    ]

    assert drift.near_duplicates(claims) == []


def test_different_statements_at_different_places_are_not_a_pair() -> None:
    claims = [
        _claim("A", "The applicant exhausted every domestic remedy", 0, 50),
        _claim("B", "The Court declared the application admissible", 400, 450),
    ]

    assert drift.near_duplicates(claims) == []


def test_claims_without_anchors_are_skipped_rather_than_guessed() -> None:
    """A raw packet carries no anchors; there is nothing to be disjoint about."""
    claims = [
        {"proposal_id": "A", "canonical_content": "same words here", "raw_span": "x"},
        {"proposal_id": "B", "canonical_content": "same words here", "raw_span": "y"},
    ]

    assert drift.near_duplicates(claims) == []
