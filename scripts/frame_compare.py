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
SECONDARY = (("C", "B"), ("C", "D"), ("B_staged", "A"), ("D", "B"))
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
        frame_score.paired_difference(rows, left, right, measure)
        for left, right in SECONDARY
        for measure in ("correct", "left_open", "held_when_not_due", "revised_when_due")
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
              f"  diff {result['difference']:+.3f} interval {result['interval']}")

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
