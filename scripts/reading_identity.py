"""The harder set: what a reading is, and which status a span's reading has.

The first meaning set measures whether a projection preserves *the* reading of a
span. That presupposes there is one, and on that set there always is: every case
has exactly one right answer. Two findings made the presupposition visible.

The first came from inside. A separation between cases whose repeats agree and
cases that fail their gold looked like evidence that spread detects error — but on
a set where disagreement is error by construction, it cannot show anything else.
Eight of those 24 cases do declare two permitted readings, and all eight pairs
turn out to be two *wordings* of one reading, which the old field cannot
distinguish from two admissible readings.

The second came from outside. arXiv 2610.14438 builds 1,000 minimal pairs where a
plural statement is neither true nor false: with three of five children having
run, "the children ran" and "the children did not run" are both gaps under a
homogeneity semantics, while "all ran" is false and "not all ran" is true. Seven
models resolve the underlying set relations almost perfectly and still force the
plural into a binary verdict; negated plurals come back as false 84 per cent of
the time. The lesson here is not about truth — this product never judges whether a
claim is true — but about **what must be kept apart**: missing evidence, several
admissible readings, probabilistic uncertainty, and a span that leaves a plural
open are four different things, and a set that conflates them cannot tell which
one a projection got wrong.

So each case declares one of four statuses, and renderings are grouped under the
reading they express:

* `determinate` — the span settles one reading;
* `ambiguous` — several readings, and the span does not choose;
* `underdetermined_quantifier` — the span leaves a plural open, so *both* the
  universal resolution and the explicit non-universal one add a commitment;
* `evidence_absent` — the span asserts what the document does not support, and
  the projection must render the assertion without softening it.

The quantifier cases come with their controls, which is what makes the status
measurable rather than asserted: `plu-03` and `plu-04` say "all" and "not all"
explicitly, so an extractor that drops a quantifier fails them, while `plu-01`
and `plu-02` fail an extractor that adds one. Their documents also state the
mixed situation (three of five), so a projection that resolves the plural from
context rather than from the span is caught.

The matching convention comes from `semantic_cases` rather than being written
again. One set with two notions of what counts as a rendering would compare as
different where it is only spelled differently.

Usage:
    reading_identity.py            # validate the set
    reading_identity.py --json OUT
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


semantic_cases = _load("semantic_cases")

CASES = (
    HERE.parents[0] / "src" / "budget_review" / "fixtures" / "reading_identity" / "cases.json"
)

SINGLE_READING_STATUSES = frozenset(
    {"determinate", "underdetermined_quantifier", "evidence_absent"}
)

SENTENCE_END = (".", "!", "?")


def looks_like_a_sentence(span: str) -> bool:
    """Whether a span is a complete sentence, which makes the case measure nothing.

    The first paid run settled this. Of the 14 cases whose span was a whole
    sentence, the extractor returned it verbatim in 42 of 42 claims on the span:
    a complete sentence is already an atomic proposition, so the projection is
    the identity function and no question about what it supplies can arise. The
    one case whose span was a clause had 0 of 14 verbatim. A heuristic — capital
    first letter and sentence-final punctuation — and it classified all 16
    correctly, which is the only evidence offered for it.
    """
    stripped = span.strip()
    if not stripped:
        return False
    return stripped[0].isupper() and stripped.endswith(SENTENCE_END)


def load(path: Path = CASES) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def renderings_of(case: dict) -> list[str]:
    return [text for reading in case["readings"] for text in reading["renderings"]]


def validate(data: dict) -> list[str]:
    """Every invariant this set has to hold, as a list of failures."""
    problems: list[str] = []
    statuses = set(data["reading_statuses"])
    by_pair: dict[str, list[dict]] = {}

    for case in data["cases"]:
        name = case["case_id"]
        document, span = case["document"], case["span"]
        status = case["reading_status"]

        if status not in statuses:
            problems.append(f"{name}: undeclared reading_status {status!r}")

        occurrences = document.count(span)
        if occurrences != 1:
            problems.append(f"{name}: span occurs {occurrences} times in the document")

        if looks_like_a_sentence(span):
            problems.append(
                f"{name}: the span is a complete sentence, so the projection can "
                f"copy it and the case measures the identity function"
            )

        for pattern in case.get("forbidden_anywhere") or []:
            if semantic_cases.violates(document, [pattern]):
                problems.append(
                    f"{name}: forbidden_anywhere {pattern!r} matches the document's "
                    f"own wording, so a verbatim quote would be punished"
                )

        readings = case["readings"]
        if status == "ambiguous" and len(readings) < 2:
            problems.append(f"{name}: ambiguous, but only {len(readings)} reading declared")
        if status in SINGLE_READING_STATUSES and len(readings) != 1:
            problems.append(f"{name}: {status}, but {len(readings)} readings declared")

        glosses = [reading["gloss"] for reading in readings]
        if len(set(glosses)) != len(glosses):
            problems.append(f"{name}: two readings share a gloss, so they are not two readings")

        groups = case.get("requires_all_groups") or []
        for index, group in enumerate(groups):
            if not any(semantic_cases._present(span, token) for token in group):
                problems.append(
                    f"{name}: requirement group {index} demands a rendering the span "
                    f"does not contain: {group}"
                )

        tripped = semantic_cases.violates(span, case.get("forbids") or [])
        if tripped:
            problems.append(f"{name}: forbids the source's own wording: {tripped}")

        for reading in readings:
            if not reading["renderings"]:
                problems.append(f"{name}: reading {reading['gloss']!r} has no rendering")
            for text in reading["renderings"]:
                hit = semantic_cases.violates(text, case.get("forbids") or [])
                if hit:
                    problems.append(f"{name}: a rendering trips {hit}: {text!r}")

        # Only the first reading of an ambiguous case has to satisfy the
        # requirements: the groups describe what any admissible projection must
        # carry, and a second reading differs precisely in what it commits to.
        for text in readings[0]["renderings"] if readings else []:
            if not semantic_cases.satisfies(text, groups):
                problems.append(f"{name}: the first reading fails the requirements: {text!r}")

        for text in case.get("forbidden_readings") or []:
            fails = not semantic_cases.satisfies(text, groups)
            hit = bool(semantic_cases.violates(text, case.get("forbids") or []))
            if not (fails or hit):
                problems.append(
                    f"{name}: a forbidden reading passes every check, so the checks "
                    f"prove nothing here: {text!r}"
                )

        if status == "underdetermined_quantifier":
            problems.extend(_quantifier_problems(name, case))

        problems.extend(_interpretation_problems(name, case, data))

        by_pair.setdefault(case["pair_id"], []).append(case)

    problems.extend(_pair_problems(by_pair))
    problems.extend(_coverage_problems(data))
    return problems


def _quantifier_problems(name: str, case: dict) -> list[str]:
    """Both resolutions of an open plural have to be forbidden, or the case is idle.

    This is the one invariant the outside paper forces. A case that forbids only
    the universal resolution would pass a projection that commits to the explicit
    non-universal one — and that is the error the paper measures models making
    84 per cent of the time on negated plurals.
    """
    forbidden = " ".join(case.get("forbidden_readings") or []).lower()
    missing = [
        label
        for label, markers in (
            ("universal", ("alle", "all ", "kein", "none")),
            ("non-universal", ("nicht alle", "not all", "einige", "some")),
        )
        if not any(marker in forbidden for marker in markers)
    ]
    return [
        f"{name}: underdetermined_quantifier without a forbidden {label} resolution"
        for label in missing
    ]


def _interpretation_problems(name: str, case: dict, data: dict) -> list[str]:
    """The field record, and the one place it has to agree with the status.

    Two axes that never meet would be two annotations of the same case with no
    way to catch a contradiction between them. The quantifier field is where
    they meet: a span that leaves a plural open is exactly a span that does not
    state a quantifier, and a control that states "all" is exactly one that
    does. Everything else the field record says is description; this is the part
    that can be wrong.
    """
    problems: list[str] = []
    fields = case.get("interpretation") or {}
    declared = set(data["interpretation_fields"])
    values = set(data["interpretation_values"])

    missing = declared - set(fields)
    if missing:
        problems.append(f"{name}: no interpretation recorded for {sorted(missing)}")
    for field, value in sorted(fields.items()):
        if field not in declared:
            problems.append(f"{name}: undeclared interpretation field {field!r}")
        if value not in values:
            problems.append(f"{name}: undeclared interpretation value {value!r} for {field}")

    quantifier = fields.get("quantifier")
    status = case["reading_status"]
    if status == "underdetermined_quantifier" and quantifier != "unstated":
        problems.append(
            f"{name}: the span leaves a plural open, so its quantifier cannot be "
            f"{quantifier!r}"
        )
    if status != "underdetermined_quantifier" and quantifier == "unstated":
        problems.append(
            f"{name}: an unstated quantifier is what underdetermined_quantifier "
            f"means, so the status cannot be {status!r}"
        )
    if case["phenomenon"] in ("explicit_universal", "explicit_non_universal"):
        if quantifier != "stated":
            problems.append(
                f"{name}: a control that names its quantifier must record it as stated"
            )
    if not case.get("turns_on"):
        problems.append(f"{name}: does not say what its difficulty turns on")
    return problems


def _pair_problems(by_pair: dict[str, list[dict]]) -> list[str]:
    problems: list[str] = []
    for pair, members in sorted(by_pair.items()):
        languages = sorted(case["language"] for case in members)
        if languages != ["de", "en"]:
            problems.append(f"{pair}: languages {languages}, expected de and en")
            continue
        first, second = members
        if first.get("interpretation") != second.get("interpretation"):
            problems.append(f"{pair}: the interpretation record differs between the languages")
        if first.get("turns_on") != second.get("turns_on"):
            problems.append(f"{pair}: turns_on differs between the languages")
        for field in ("phenomenon", "reading_status", "min_claims_on_span"):
            if first.get(field) != second.get(field):
                problems.append(f"{pair}: {field} differs between the languages")
        if len(first["readings"]) != len(second["readings"]):
            problems.append(f"{pair}: different number of readings per language")
        if len(first.get("forbidden_readings") or []) != len(
            second.get("forbidden_readings") or []
        ):
            problems.append(f"{pair}: different number of forbidden readings per language")
    return problems


def _coverage_problems(data: dict) -> list[str]:
    """The set is only worth running if it covers what it was built to separate.

    A set that lost its ambiguous cases would still validate case by case and
    would answer none of the questions it exists for, which is how the first set
    came to measure one thing while being read as measuring another.
    """
    present = {case["reading_status"] for case in data["cases"]}
    missing = set(data["reading_statuses"]) - present
    problems = [f"no case declares the status {status!r}" for status in sorted(missing)]
    phenomena = {case["phenomenon"] for case in data["cases"]}
    for required in ("explicit_universal", "explicit_non_universal"):
        if required not in phenomena:
            problems.append(f"the controls are incomplete: no case with phenomenon {required!r}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()
    data = load()
    problems = validate(data)

    cases = data["cases"]
    print(f"{len(cases)} Fälle, {len({c['pair_id'] for c in cases})} Paare")
    by_status: dict[str, int] = {}
    for case in cases:
        by_status[case["reading_status"]] = by_status.get(case["reading_status"], 0) + 1
    for status, count in sorted(by_status.items()):
        print(f"  {status:30} {count}")
    print(f"  Lesarten insgesamt: {sum(len(c['readings']) for c in cases)}")
    print(f"  Formulierungen insgesamt: {sum(len(renderings_of(c)) for c in cases)}")

    if problems:
        print(f"\n{len(problems)} Problem(e):")
        for problem in problems:
            print(f"  ! {problem}")
    else:
        print("\nAlle Invarianten halten.")

    if args.json:
        args.json.write_text(
            json.dumps({"problems": problems, "statuses": by_status}, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(f"{args.json} geschrieben")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
