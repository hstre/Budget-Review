"""The case set, and the invariants that keep it from measuring nothing.

48 held-out cases, eight per category, in 24 minimal pairs. Each case shows a
statement at one context level and then adds levels; each stage of each case
declares what the text at that point explicitly supports, what it excludes, and
what it leaves open. The last of those is the one a set like this usually gets
wrong: if openness is not declared, a procedure that decides everything scores
the same as one that decides only what the text decides.

One convention makes the gold complete: **every closed field that a stage does
not mention must be `undecided`**. So there is no unscored corner where an
invented permission or an invented contradiction can hide.

Seven invariants, and the last three are the ones that would catch me writing a
set that proves what I want:

1. Eight cases per category, in pairs of a base and a variant.
2. Within a pair, every frame before the declared decisive frame is identical,
   and the decisive frame differs. Frames after it may differ, because what
   follows a decisive change depends on it; how many do is reported.
3. Frame labels come from F1–F4, start at F1, and increase.
4. Every gold field and value is in the closed vocabulary, and `must` and
   `must_not` never contradict each other.
5. A stage declared `revision: required` must differ from the one before it in
   at least one meaning field, and one declared `forbidden` must not differ in
   any. `status` is excluded from that comparison: it is the procedure's own
   bookkeeping, not a statement about the text.
6. No rendered prompt contains a case id, a category, a trait or a gold note.
   What a prompt may contain is the field vocabulary, which is the answer
   format and not the answer.
7. The development set and the test set share no frame text, so nothing tuned
   on the examples from the brief is measured as a result.

Usage:
    frame_cases.py                # validate both sets
    frame_cases.py --list         # one line per case
    frame_cases.py --stats        # coverage of categories, traits and fields
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parents[0] / "src" / "budget_review" / "fixtures" / "frames"
TEST_SET = FIXTURES / "test_cases.json"
DEV_SET = FIXTURES / "dev_cases.json"

_spec = importlib.util.spec_from_file_location("frame_object", HERE / "frame_object.py")
frame_object = importlib.util.module_from_spec(_spec)
sys.modules["frame_object"] = frame_object
_spec.loader.exec_module(frame_object)

CLOSED_FIELDS = frame_object.CLOSED_FIELDS
UNDECIDED = frame_object.UNDECIDED

# Revision is a change of what the text is taken to say. `status` records how
# the procedure currently holds the object, which can move while the reading
# stands still — corroboration by a second source is the plain example.
REVISION_FIELDS = tuple(name for name in CLOSED_FIELDS if name != "status")

FRAME_ORDER = ("F1", "F2", "F3", "F4")
REVISIONS = ("n/a", "required", "forbidden", "free")
CATEGORIES = ("A", "B", "C", "D", "E", "F")
TRAITS = (
    "local_already_correct",
    "irrelevant_context",
    "stays_ambiguous",
    "salient_global_vs_local_exception",
    "negative_control",
    "contested",
    "development",
)


def load(path: Path = TEST_SET) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def implied(stage: dict, name: str) -> str | list[str]:
    """What gold requires of one field: a value, a tolerated set, or undecided."""
    if name in stage.get("must", {}):
        return stage["must"][name]
    if name in stage.get("tolerated", {}):
        return list(stage["tolerated"][name])
    return UNDECIDED


def may_hold(previous_value, current) -> bool:
    """Whether an answer could keep the earlier value and still satisfy gold.

    A stage that tolerates the value the stage before it required does not
    demand a revision: the same answer satisfies both. Comparing the two for
    plain inequality called that a required revision, which would have scored a
    model for standing still as though it had moved.
    """
    if isinstance(current, list):
        if isinstance(previous_value, list):
            return bool(set(previous_value) & set(current))
        return previous_value in current
    if isinstance(previous_value, list):
        return current in previous_value
    return previous_value == current


def frames_up_to(case: dict, after: str) -> list[dict]:
    index = [frame["frame"] for frame in case["frames"]].index(after)
    return case["frames"][: index + 1]


def _stage_problems(case: dict, stage: dict, previous: dict | None) -> list[str]:
    problems: list[str] = []
    where = f"{case['case_id']}/{stage['after']}"

    if stage["revision"] not in REVISIONS:
        problems.append(f"{where}: revision {stage['revision']!r} unknown")
    if previous is None and stage["revision"] != "n/a":
        problems.append(f"{where}: the first stage cannot revise anything")
    if previous is not None and stage["revision"] == "n/a":
        problems.append(f"{where}: a later stage needs a revision expectation")

    for block in ("must", "tolerated"):
        for name, value in stage.get(block, {}).items():
            if name not in CLOSED_FIELDS:
                problems.append(f"{where}: {block} names unknown field {name!r}")
                continue
            values = value if isinstance(value, list) else [value]
            for item in values:
                if item not in CLOSED_FIELDS[name]:
                    problems.append(f"{where}: {block}.{name} = {item!r} not in vocabulary")
    for name, forbidden in stage.get("must_not", {}).items():
        if name not in CLOSED_FIELDS:
            problems.append(f"{where}: must_not names unknown field {name!r}")
            continue
        for item in forbidden:
            if item not in CLOSED_FIELDS[name]:
                problems.append(f"{where}: must_not.{name} = {item!r} not in vocabulary")
        if name in stage.get("must", {}) and stage["must"][name] in forbidden:
            problems.append(f"{where}: {name} is required and forbidden at once")
        for item in stage.get("tolerated", {}).get(name, []):
            if item in forbidden:
                problems.append(f"{where}: {name} = {item!r} is tolerated and forbidden at once")
        if name in stage.get("must", {}) and name in stage.get("tolerated", {}):
            problems.append(f"{where}: {name} is both required and tolerated")

    if not stage.get("must"):
        problems.append(f"{where}: a stage that requires nothing measures nothing")
    if not stage.get("note"):
        problems.append(f"{where}: no reason given for the expectation")

    if previous is not None and stage["revision"] in ("required", "forbidden"):
        if stage["revision"] == "required":
            # Only a field the answer cannot keep counts: a tolerated set that
            # still contains the earlier value demands nothing.
            moved = [
                name
                for name in REVISION_FIELDS
                if not may_hold(implied(previous, name), implied(stage, name))
            ]
        else:
            moved = [
                name
                for name in REVISION_FIELDS
                if implied(previous, name) != implied(stage, name)
            ]
        if stage["revision"] == "required" and not moved:
            problems.append(f"{where}: declared a required revision that gold does not make")
        if stage["revision"] == "forbidden" and moved:
            problems.append(f"{where}: declared revision forbidden, but gold moves {moved}")
    return problems


def validate(payload: dict, *, expect_pairs: bool = True) -> list[str]:
    problems: list[str] = []
    cases = payload["cases"]
    ids = [case["case_id"] for case in cases]
    if len(set(ids)) != len(ids):
        problems.append("duplicate case ids")

    for case in cases:
        where = case["case_id"]
        if case["category"] not in CATEGORIES:
            problems.append(f"{where}: category {case['category']!r} unknown")
        for trait in case.get("traits", []):
            if trait not in TRAITS:
                problems.append(f"{where}: trait {trait!r} unknown")

        labels = [frame["frame"] for frame in case["frames"]]
        if not labels or labels[0] != "F1":
            problems.append(f"{where}: the first frame has to be F1")
        if any(label not in FRAME_ORDER for label in labels):
            problems.append(f"{where}: frame labels outside F1-F4")
        elif [FRAME_ORDER.index(label) for label in labels] != sorted(
            FRAME_ORDER.index(label) for label in labels
        ):
            problems.append(f"{where}: frames out of order")
        if len(set(labels)) != len(labels):
            problems.append(f"{where}: a frame label twice")
        if case.get("decisive_frame") not in labels:
            problems.append(f"{where}: decisive_frame is not one of its frames")

        stages = [stage["after"] for stage in case["gold"]]
        if stages != labels:
            problems.append(f"{where}: gold stages {stages} do not match frames {labels}")
        previous = None
        for stage in case["gold"]:
            problems.extend(_stage_problems(case, stage, previous))
            previous = stage

    if expect_pairs:
        by_category: dict[str, list[dict]] = {}
        for case in cases:
            by_category.setdefault(case["category"], []).append(case)
        for category, members in sorted(by_category.items()):
            if len(members) != 8:
                problems.append(f"category {category}: {len(members)} cases, expected eight")
        pairs: dict[str, list[dict]] = {}
        for case in cases:
            pairs.setdefault(case["pair"], []).append(case)
        for name, members in sorted(pairs.items()):
            roles = sorted(case["role"] for case in members)
            if roles != ["base", "variant"]:
                problems.append(f"pair {name}: roles {roles}, expected a base and a variant")
                continue
            base = next(case for case in members if case["role"] == "base")
            variant = next(case for case in members if case["role"] == "variant")
            if base["decisive_frame"] != variant["decisive_frame"]:
                problems.append(f"pair {name}: the two halves name different decisive frames")
                continue
            decisive = base["decisive_frame"]
            for label in FRAME_ORDER[: FRAME_ORDER.index(decisive)]:
                before = {
                    case["case_id"]: next(
                        (f["text"] for f in case["frames"] if f["frame"] == label), None
                    )
                    for case in (base, variant)
                }
                if len(set(before.values())) != 1:
                    problems.append(f"pair {name}: {label} differs before the decisive frame")
            texts = {
                case["case_id"]: next(
                    (f["text"] for f in case["frames"] if f["frame"] == decisive), None
                )
                for case in (base, variant)
            }
            if len(set(texts.values())) == 1:
                problems.append(f"pair {name}: the decisive frame {decisive} does not differ")
    return problems


def leaks(payload: dict, render) -> list[str]:
    """Invariant 6: what a prompt may never carry.

    `render(case, after, condition)` is the prompt builder. The check is run
    over every case and stage of both sets, for every condition, because a leak
    in one condition would hand that condition the answer.
    """
    found: list[str] = []
    for case in payload["cases"]:
        forbidden = [case["case_id"], f"Kategorie {case['category']}"]
        forbidden += list(case.get("traits", []))
        forbidden += [stage["note"] for stage in case["gold"]]
        for stage in case["gold"]:
            for condition in ("A", "B", "B_staged", "C", "D"):
                text = render(case, stage["after"], condition)
                for needle in forbidden:
                    if needle and needle in text:
                        found.append(
                            f"{case['case_id']}/{stage['after']}/{condition}: prompt carries {needle!r}"
                        )
    return found


def disjoint(dev: dict, test: dict) -> list[str]:
    """Invariant 7: no frame text is shared between development and test."""
    dev_texts = {
        frame["text"] for case in dev["cases"] for frame in case["frames"]
    }
    shared = sorted(
        frame["text"]
        for case in test["cases"]
        for frame in case["frames"]
        if frame["text"] in dev_texts
    )
    return [f"shared with the development set: {text!r}" for text in shared]


def _stats(payload: dict) -> str:
    from collections import Counter

    lines = []
    cases = payload["cases"]
    lines.append(f"cases: {len(cases)}  pairs: {len({c['pair'] for c in cases})}")
    lines.append(f"stages: {sum(len(c['gold']) for c in cases)}")
    lines.append("by category: " + str(dict(sorted(Counter(c["category"] for c in cases).items()))))
    traits = Counter(trait for case in cases for trait in case.get("traits", []))
    lines.append("traits: " + str(dict(sorted(traits.items()))))
    revisions = Counter(
        stage["revision"] for case in cases for stage in case["gold"]
    )
    lines.append("revision expectations: " + str(dict(sorted(revisions.items()))))
    required = Counter(
        name for case in cases for stage in case["gold"] for name in stage.get("must", {})
    )
    lines.append("fields required at least once: " + str(dict(sorted(required.items()))))
    untouched = sorted(set(CLOSED_FIELDS) - set(required))
    lines.append("fields never required: " + (str(untouched) if untouched else "none"))
    tolerated = [
        f"{case['case_id']}/{stage['after']}:{name}"
        for case in cases
        for stage in case["gold"]
        for name in stage.get("tolerated", {})
    ]
    lines.append(f"tolerated (contested) field decisions: {len(tolerated)}")
    for item in tolerated:
        lines.append(f"  {item}")
    contested = [c["case_id"] for c in cases if "contested" in c.get("traits", [])]
    lines.append(f"cases marked contested: {contested or 'none'}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--stats", action="store_true")
    arguments = parser.parse_args(argv)

    test, dev = load(TEST_SET), load(DEV_SET)

    if arguments.list:
        for case in test["cases"]:
            frames = " | ".join(f["text"] for f in case["frames"])
            print(f"{case['case_id']} {case['role']:<7} {case['decisive_frame']}  {frames}")
        return 0
    if arguments.stats:
        print(_stats(test))
        return 0

    problems = validate(test)
    problems += [f"dev: {problem}" for problem in validate(dev, expect_pairs=False)]
    problems += disjoint(dev, test)
    if problems:
        print(f"{len(problems)} problems:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print(f"{len(test['cases'])} test cases and {len(dev['cases'])} development cases are consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
