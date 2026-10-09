"""The research report's claims about this repository, checked against it.

The report states its own test count, its number of measurement scripts and the
range of log sections it synthesises. Three of those went stale unnoticed, and the
cause is worth pinning down: an edit updated them with a string replacement aimed
at a figure the branch did not carry, so the replacement matched nothing and
changed nothing — and a no-op replacement looks exactly like a success unless the
result is checked against reality.

These tests are that check. They say nothing about whether the report's findings
are right; they only hold it to the facts it can be held to mechanically.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPORT = (ROOT / "docs" / "research-report.md").read_text(encoding="utf-8")
LOG = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")


def test_the_script_count_matches_the_scripts() -> None:
    actual = len(list((ROOT / "scripts").glob("*.py")))
    for pattern in (r"(\d+) measurement scripts", r"(\d+) Messskripte"):
        claimed = re.findall(pattern, REPORT)
        assert claimed, pattern
        assert {int(n) for n in claimed} == {actual}, (pattern, claimed, actual)


def test_the_test_file_count_is_not_claimed_as_a_test_count() -> None:
    # The report states a test count, which only a run can establish, so this
    # asserts the shape rather than the number: one figure, stated identically in
    # both language halves. A mismatch between the halves means one was edited.
    english = re.findall(r"(\d+) tests and one skipped", REPORT)
    german = re.findall(r"(\d+) Tests und einer übersprungen", REPORT)
    assert english and german
    assert set(english) == set(german), (english, german)


def test_the_claimed_log_range_ends_at_the_last_section_the_log_has() -> None:
    sections = re.findall(r"^## (3[a-z]+)\.", LOG, re.M)
    assert sections, "the log has no numbered sections"
    last = max(sections, key=lambda name: (len(name), name))
    claimed = set(re.findall(r"§3a–§(3[a-z]+)", REPORT))
    assert claimed == {last}, (claimed, last)


def test_the_log_sections_are_in_order() -> None:
    # Two branches inserting before the same heading put them out of order once,
    # which makes a chronological record stop being one.
    sections = re.findall(r"^## (3[a-z]+)\.", LOG, re.M)
    assert sections == sorted(sections, key=lambda name: (len(name), name)), sections


@pytest.mark.parametrize("heading", ["## 1. Summary", "## 1. Zusammenfassung"])
def test_the_report_carries_both_language_halves(heading: str) -> None:
    assert REPORT.count(heading) == 1, heading


def test_every_section_of_four_exists_in_both_halves() -> None:
    # §4.16 was written in English only and nothing noticed.
    halves: dict[str, list[str]] = {"EN": [], "DE": []}
    current: str | None = None
    for line in REPORT.split("\n"):
        if line.startswith("## 1. Summary"):
            current = "EN"
        elif line.startswith("## 1. Zusammenfassung"):
            current = "DE"
        elif line.startswith("### 4.") and current:
            halves[current].append(line.split()[1])
    assert halves["EN"], "no English sections found"
    assert halves["EN"] == halves["DE"], (halves["EN"], halves["DE"])
