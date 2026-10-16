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


def test_the_claimed_test_count_agrees_between_the_language_halves() -> None:
    # A mismatch between the halves means one of them was edited and the other
    # forgotten, which is how §4.16 came to exist in English only.
    english = re.findall(r"(\d+) tests and one skipped", REPORT)
    german = re.findall(r"(\d+) Tests und einer übersprungen", REPORT)
    assert english and german
    assert set(english) == set(german), (english, german)


def test_the_claimed_test_count_is_at_least_the_test_functions_on_disk() -> None:
    """A necessary condition, and worth being plain about its limit.

    Only a run establishes the real count, and a test cannot run the suite inside
    itself. But every `def test_` is at least one case and parametrisation only
    adds, so the claimed figure must not fall below the functions on disk. That
    catches the drift that actually happened — the report said 384 where the
    files already held 404 — and it does **not** catch a near miss such as 448
    against 455. For that, the figure has to be set from a run, which is what the
    changelog entry beside this test says.
    """
    functions = sum(
        len(re.findall(r"^def test_", path.read_text(encoding="utf-8"), re.M))
        for path in (ROOT / "tests").glob("test_*.py")
    )
    assert functions > 0
    claimed = {int(n) for n in re.findall(r"(\d+) tests and one skipped", REPORT)}
    assert claimed, "the report states no test count"
    assert min(claimed) >= functions, (claimed, functions)


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


NUMBER_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5,
                "Ein": 1, "Zwei": 2, "Drei": 3, "Vier": 4, "Fünf": 5}


def _external_input_count(half: str) -> tuple[str, int, int]:
    """Which language §8 is in, what it claims about itself, and what it names.

    The section opens by naming how many external inputs shaped the work and then
    introduces each one in a paragraph that starts bold. The claim and the count
    drifted apart when a third input was added: the English half kept saying two
    while naming three, and nothing noticed, because the symmetry that had been
    checked was section numbering rather than prose.

    The language comes back with the figures because the two halves agree, and a
    test that reads one of them twice therefore passes. A mutation proved that:
    it collapsed the half selection and survived. Returning the language lets the
    caller assert it read the half it meant to.
    """
    body = half.split("## 8.")[1].split("\n## 9.")[0]
    claimed = re.search(
        r"^(\w+) (external inputs shaped|externe Eingaben haben)", body, re.M
    )
    assert claimed, "§8 no longer opens by naming how many inputs shaped the work"
    language = "EN" if claimed.group(2).startswith("external") else "DE"
    # Paragraph start, not line start: the prose is hard-wrapped, so a bold span
    # in mid-sentence can begin a line and would be counted as an input. That is
    # the same class of mistake as the one this test exists for.
    paragraphs = [block.strip() for block in body.split("\n\n")]
    introduced = [block for block in paragraphs if block.startswith("**")]
    return language, NUMBER_WORDS[claimed.group(1)], len(introduced)


def test_each_half_names_as_many_external_inputs_as_it_claims() -> None:
    halves = REPORT.split("# Forschungsbericht (Deutsch)")
    assert len(halves) == 2, "the two halves are no longer separated as expected"
    english = _external_input_count(halves[0])
    german = _external_input_count(halves[1])
    # Each half is read, and proved to be the half it was meant to be.
    assert (english[0], german[0]) == ("EN", "DE"), (english[0], german[0])
    for language, claimed, introduced in (english, german):
        assert claimed == introduced, (language, claimed, introduced)
    assert english[1] == german[1], (english[1], german[1])


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
