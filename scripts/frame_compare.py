"""Read a run and decide the pre-registered criterion, mechanically.

The criterion in docs/prereg-frames-01.md has four parts, and all four have to
hold for the staged procedure to count as helping:

1. it beats the one-shot arm of equal information horizon on correctness, with
   the interval over minimal pairs excluding zero;
2. it does not lose openness;
3. it does not lose exception-keeping or contradiction-finding;
4. it does not invent more contradictions.

This script applies that, prints each part with its number, and says plainly
which parts failed. It does not choose the criterion — that was fixed before
the run — and it does not soften it when the answer is no.

    frame_compare.py runs/live
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


frame_score = _load("frame_score")

PRIMARY = ("C", "B_staged")
SECONDARY = (
    ("C", "B"), ("C", "D"), ("B_staged", "A"), ("D", "B"),
    ("C", "B_object"), ("B_object", "B"), ("B_staged", "B"),
)

# Arms are asked different numbers of questions. The local arm is asked once,
# about the first frame; the one-shot arms are asked once, about everything; the
# staged arms are asked at every frame. Summing each arm's own stages and
# dividing compares two different sets of questions — which is how the first
# reading of this run produced an effect that vanished stage for stage. Any
# comparison between arms with different stage sets is restricted to the stages
# both of them answer.
FIRST_STAGE_ONLY = ("A",)
LAST_STAGE_ONLY = ("B", "D", "B_object")
MUST_NOT_FALL = ("left_open", "exception_kept", "contradiction_found")
MUST_NOT_RISE = ("contradiction_invented",)
USABLE_FLOOR = 0.90


def read(directory: Path) -> tuple[list[dict], dict]:
    rows = [
        json.loads(line)
        for line in (directory / "rows.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    report = json.loads((directory / "report.json").read_text(encoding="utf-8"))
    return rows, report


def last_stage_of(rows: list[dict]) -> dict[str, str]:
    """The final stage each case reaches, read off the rows themselves."""
    final: dict[str, str] = {}
    for row in rows:
        current = final.get(row["case_id"])
        if current is None or row["stage"] > current:
            final[row["case_id"]] = row["stage"]
    return final


def comparable_rows(rows: list[dict], left: str, right: str) -> list[dict]:
    """The rows two arms can be compared on without changing the question.

    Restricting to one stage is not a narrowing of the comparison; it is what
    makes it one. An arm asked only about the whole text has no answer about an
    earlier information state, so its single answer must be set against the
    staged arm's answer at that same point and nowhere else.
    """
    first = left in FIRST_STAGE_ONLY or right in FIRST_STAGE_ONLY
    last = left in LAST_STAGE_ONLY or right in LAST_STAGE_ONLY
    if first and last:
        # Two arms that answer at opposite ends share a stage only where a case
        # has a single frame, and this set has none.
        return []
    if first:
        return [row for row in rows if row["stage"] == "F1"]
    if last:
        final = last_stage_of([row for row in rows if row["condition"] in LAST_STAGE_ONLY])
        return [row for row in rows if final.get(row["case_id"]) == row["stage"]]
    return rows


def _stage_label(left: str, right: str) -> str:
    if left in FIRST_STAGE_ONLY or right in FIRST_STAGE_ONLY:
        return "F1 only"
    if left in LAST_STAGE_ONLY or right in LAST_STAGE_ONLY:
        return "last stage only"
    return "all"


def _table(report: dict) -> str:
    lines = []
    width = 13
    head = f"{'arm':<10}" + "".join(f"{name[:11]:>{width}}" for name in frame_score.MEASURES)
    lines.append(head)
    for arm, block in report["report"].items():
        cells = []
        for name in frame_score.MEASURES:
            cell = block["overall"][name]
            value = frame_score.share(cell)
            cells.append("-" if value is None else f"{value:.2f}/{cell['total']}")
        lines.append(f"{arm:<10}" + "".join(f"{cell:>{width}}" for cell in cells))
    return "\n".join(lines)


def drift(rows: list[dict]) -> dict:
    """What one arm's own repeats say about the noise floor.

    Standing policy since the second frame run: a difference between two arms is
    only readable against the spread of one arm against itself. Where a run has
    no repeat, this returns nothing and the report says so, rather than letting
    a single draw be read as a settled figure.
    """
    repeats = sorted({row.get("repeat", 0) for row in rows})
    if len(repeats) < 2:
        return {}
    measured: dict[str, dict] = {}
    for measure in frame_score.MEASURES:
        shares = []
        for repeat in repeats:
            subset = [row for row in rows if row.get("repeat", 0) == repeat]
            hit = sum(row.get(f"{measure}_hit", 0) for row in subset)
            total = sum(row.get(f"{measure}_total", 0) for row in subset)
            shares.append(None if not total else hit / total)
        known = [share for share in shares if share is not None]
        if len(known) < 2:
            continue
        measured[measure] = {
            "shares": [None if s is None else round(s, 4) for s in shares],
            "spread": round(max(known) - min(known), 4),
        }
    return measured


def withdrawn(report: dict) -> list[str]:
    """The withdrawal rule: an arm that cannot return the object is not measured."""
    out = []
    for arm, block in report["report"].items():
        cell = block["overall"]["usable"]
        share = frame_score.share(cell)
        if share is not None and share < USABLE_FLOOR:
            out.append(f"{arm}: usable {share:.2f} below {USABLE_FLOOR:.2f}")
    return out


def criterion(rows: list[dict]) -> dict:
    left, right = PRIMARY
    parts = []

    primary = frame_score.paired_difference(rows, left, right, "correct")
    parts.append({
        "part": 1,
        "claim": f"{left} beats {right} on correctness, interval clear of zero",
        "detail": primary,
        "holds": bool(
            primary.get("difference") is not None
            and primary["difference"] > 0
            and primary.get("interval", [None])[0] is not None
            and primary["interval"][0] > 0
        ),
    })
    for measure in MUST_NOT_FALL:
        result = frame_score.paired_difference(rows, left, right, measure)
        interval = result.get("interval", [None, None])
        holds = not (interval[1] is not None and interval[1] < 0)
        parts.append({
            "part": 2 if measure == "left_open" else 3,
            "claim": f"{left} does not lose {measure}",
            "detail": result,
            "holds": bool(holds),
        })
    for measure in MUST_NOT_RISE:
        result = frame_score.paired_difference(rows, left, right, measure)
        interval = result.get("interval", [None, None])
        # "Does not invent more" means the avoidance share does not fall.
        holds = not (interval[1] is not None and interval[1] < 0)
        parts.append({
            "part": 4,
            "claim": f"{left} does not invent more contradictions than {right}",
            "detail": result,
            "holds": bool(holds),
        })
    return {"parts": parts, "met": all(part["holds"] for part in parts)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args(argv)

    rows, report = read(arguments.run)
    verdict = criterion(rows)
    secondary = [
        frame_score.paired_difference(
            comparable_rows(rows, left, right), left, right, measure
        )
        | {"stages": _stage_label(left, right)}
        for left, right in SECONDARY
        for measure in ("correct", "left_open", "held_when_not_due", "revised_when_due")
    ]
    secondary += [
        frame_score.paired_difference(rows, *PRIMARY, measure)
        | {"stages": "all"}
        for measure in ("revised_when_due", "held_when_not_due", "tolerated")
    ]
    voided = withdrawn(report)

    if arguments.json:
        print(json.dumps({
            "usage": report["usage"], "criterion": verdict,
            "secondary": secondary, "withdrawn": voided,
        }, ensure_ascii=False, indent=2))
        return 0

    print(_table(report))
    print(f"\ncalls {report['usage']['calls']}, failed {report['usage']['failed_calls']}, "
          f"tokens {report['usage']['prompt_tokens']}/{report['usage']['completion_tokens']}, "
          f"cost {report['usage']['cost']}")

    if voided:
        print("\nWITHDRAWN under the pre-registered rule:")
        for item in voided:
            print(f"  {item}")

    noise = {
        arm: drift([row for row in rows if row["condition"] == arm])
        for arm in sorted({row["condition"] for row in rows})
    }
    print("\n=== The noise floor: one arm against its own repeat ===")
    if not any(noise.values()):
        print("  no repeat in this run, so no noise floor was measured.")
        print("  Standing policy: a difference is read against one arm's own spread,")
        print("  and without it every figure below is a single draw.")
    else:
        for arm, measured in noise.items():
            if not measured:
                continue
            worst = sorted(measured.items(), key=lambda item: -item[1]["spread"])[:5]
            for measure, cell in worst:
                print(f"  {arm:<10} {measure:<24} {cell['shares']}  spread {cell['spread']}")

    print("\n=== The pre-registered criterion ===")
    for part in verdict["parts"]:
        detail = part["detail"]
        mark = "holds   " if part["holds"] else "FAILS   "
        if detail.get("comparable_pairs"):
            print(f"  {mark} ({part['part']}) {part['claim']}")
            print(f"            {detail['left']} {detail['left_share']} vs "
                  f"{detail['right']} {detail['right_share']}  "
                  f"difference {detail['difference']} interval {detail['interval']}  "
                  f"pairs {detail['pairs_favouring_left']}/{detail['pairs_level']}/"
                  f"{detail['pairs_favouring_right']}")
        else:
            print(f"  {mark} ({part['part']}) {part['claim']} — not comparable")
    print(f"\n  criterion met: {verdict['met']}")

    print("\n=== Secondary comparisons ===")
    for result in secondary:
        if not result.get("comparable_pairs"):
            continue
        print(f"  {result['left']:>9} vs {result['right']:<9} {result['measure']:<18}"
              f" {result['left_share']:.2f} vs {result['right_share']:.2f}"
              f"  diff {result['difference']:+.3f} interval {result['interval']}"
              f"  [{result['stages']}]")

    print("\n=== By category ===")
    categories = sorted({row["category"] for row in rows})
    for measure in ("correct", "left_open", "contradiction_found", "contradiction_invented",
                    "exception_kept", "revised_when_due", "held_when_not_due"):
        print(f"  {measure}")
        for arm in report["report"]:
            cells = []
            for category in categories:
                cell = report["report"][arm]["by_category"].get(category, {}).get(measure)
                value = frame_score.share(cell) if cell else None
                cells.append(f"{category}:" + ("   -" if value is None else f"{value:.2f}"))
            print(f"    {arm:<10} " + "  ".join(cells))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
