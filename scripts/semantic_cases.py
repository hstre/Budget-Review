"""A hand-annotated set for meaning, and the checks that make it mechanical.

Every corpus this project has measured against annotates *where* an argument
unit sits. None annotates whether the claim that quotes it still means the same
thing. Negation, modality, the difference between correlation and cause, a
condition, a speaker, two assertions in one sentence — a claim can anchor
perfectly and reverse any of them, and span recall counts that as a hit.

So the set is ours: 24 short cases, twelve meanings in German and English, each
with declared requirements that a script can check without asking a model
anything. That constraint is the point. A model grading whether two sentences
mean the same would make the measurement circular — the system under test and
its examiner from one family — so the requirements are token groups and regexes
instead. They are crude on purpose: they catch the gross failure, a negation
simply gone or a cause invented, and they do not catch subtle drift. A check that
cannot be argued with is worth more here than one that is right more often.

What the set tests is **faithful rendering of the source**. The sources say
things that may well be false; that is not the measurement.

Five invariants keep the set honest, and the last two are the ones that would
catch me writing a check that proves nothing:

1. Every span occurs in its document exactly once.
2. Every requirement group has at least one of its tokens in the span itself, so
   a case cannot demand a word the source does not contain.
3. No `forbids` pattern matches the span, so a case cannot forbid the source's
   own wording.
4. Each pair carries both languages with the same phenomenon, the same number of
   groups and the same claim count, so language is a variable rather than a
   confound.
5. Every declared `permitted_readings` entry satisfies the requirements, and
   every `forbidden_readings` entry violates at least one. A case whose own
   worked failure passes its own checks is a case that measures nothing.

Usage:
    semantic_cases.py                 # validate the set against all five
    semantic_cases.py --list          # one line per case
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE.parents[0] / "src" / "budget_review" / "fixtures" / "semantic_cases" / "cases.json"


def load(path: Path = CASES) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def _present(text: str, token: str) -> bool:
    """Whether a token group member occurs in the text.

    A single word is matched on word boundaries, so "kann" does not fire inside
    "bekannt"; a phrase is matched as a substring, since its own boundaries are
    carried by its words. Case is ignored, which is what a rendering check wants.
    """
    needle = token.strip().casefold()
    haystack = text.casefold()
    if not needle:
        return False
    if " " in needle:
        return needle in haystack
    return re.search(rf"\b{re.escape(needle)}\b", haystack) is not None


def satisfies(text: str, groups: list[list[str]]) -> bool:
    """Every group contributes at least one of its renderings."""
    return all(any(_present(text, token) for token in group) for group in groups)


def violates(text: str, forbids: list[str]) -> list[str]:
    """The forbidden patterns this text matches."""
    return [pattern for pattern in forbids if re.search(pattern, text, re.IGNORECASE)]


def groups_of(case: dict) -> list[list[str]]:
    return list(case.get("requires_all_groups") or []) + list(
        case.get("requires_distinct_groups") or []
    )


def validate(cases: list[dict]) -> list[str]:
    """Every invariant the set has to hold, as a list of failures."""
    problems: list[str] = []
    by_pair: dict[str, list[dict]] = {}
    for case in cases:
        name = case["case_id"]
        document, span = case["document"], case["span"]

        occurrences = document.count(span)
        if occurrences != 1:
            problems.append(f"{name}: span occurs {occurrences} times in the document")

        for index, group in enumerate(groups_of(case)):
            if not any(_present(span, token) for token in group):
                problems.append(
                    f"{name}: requirement group {index} demands a rendering the span "
                    f"does not contain: {group}"
                )

        matched = violates(span, case.get("forbids") or [])
        if matched:
            problems.append(f"{name}: forbids the source's own wording: {matched}")

        for reading in case.get("permitted_readings") or []:
            if not satisfies(reading, case.get("requires_all_groups") or []):
                problems.append(f"{name}: a permitted reading fails the requirements: {reading!r}")
            hit = violates(reading, case.get("forbids") or [])
            if hit:
                problems.append(f"{name}: a permitted reading trips {hit}: {reading!r}")

        for reading in case.get("forbidden_readings") or []:
            fails = not satisfies(reading, case.get("requires_all_groups") or [])
            tripped = bool(violates(reading, case.get("forbids") or []))
            if not (fails or tripped) and case.get("min_claims_on_span", 1) < 2:
                problems.append(
                    f"{name}: a forbidden reading passes every check, so the checks "
                    f"prove nothing here: {reading!r}"
                )

        by_pair.setdefault(case["pair_id"], []).append(case)

    for pair, members in sorted(by_pair.items()):
        languages = sorted(case["language"] for case in members)
        if languages != ["de", "en"]:
            problems.append(f"{pair}: languages {languages}, expected de and en")
            continue
        first, second = members
        for field in ("phenomenon", "min_claims_on_span"):
            if first.get(field) != second.get(field):
                problems.append(f"{pair}: {field} differs between the languages")
        if len(groups_of(first)) != len(groups_of(second)):
            problems.append(f"{pair}: different number of requirement groups per language")
        if len(first.get("forbids") or []) != len(second.get("forbids") or []):
            problems.append(f"{pair}: different number of forbidden patterns per language")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    cases = load()
    if args.list:
        for case in cases:
            print(
                f"{case['case_id']:12} {case['language']}  {case['phenomenon']:26} "
                f"min {case.get('min_claims_on_span', 1)}  {case['span'][:58]}"
            )
        return 0

    problems = validate(cases)
    print(f"{len(cases)} Fälle, {len({c['pair_id'] for c in cases})} Paare, zwei Sprachen")
    if not problems:
        print("Alle fünf Invarianten erfüllt.")
        return 0
    print(f"\n{len(problems)} Verletzungen:")
    for problem in problems:
        print(f"  {problem}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
