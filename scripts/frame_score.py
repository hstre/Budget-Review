"""Deterministic scoring of the nine measures, and the two it is easiest to fake.

Nothing here asks a model anything. Every number comes from comparing closed
fields against gold declared before the run, because a procedure graded by a
model of the same family grades its own reading.

Two measures are deliberately kept apart from their mirror image, because a
single combined score rewards the wrong behaviour:

* **finding a contradiction** is counted only where gold declares one, and
  **inventing** one only where gold forbids one. A procedure that calls
  everything contradictory would score perfectly on the first and is caught by
  the second.
* **leaving a question open** is counted over the fields gold leaves open, and
  **deciding what is open** over the same set. A procedure that answers
  `undecided` everywhere wins the openness measure and loses correctness, which
  is the point: the two are reported side by side and never summed.

The gold convention does the rest of the work: a closed field that a stage does
not mention has to be `undecided`, so there is no unscored field where an
invented permission can sit.
"""

from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


frame_object = _load("frame_object")
frame_cases = _load("frame_cases")

CLOSED_FIELDS = frame_object.CLOSED_FIELDS
UNDECIDED = frame_object.UNDECIDED
REVISION_FIELDS = frame_cases.REVISION_FIELDS

# The nine measures, as counter pairs of hits and opportunities.
MEASURES = (
    "correct",            # 1 explicitly supported components
    "unsupported",        # 2 decisions the text does not license
    "excluded",           #   the sharp subset: a value gold forbids
    "contradiction_found",  # 3
    "contradiction_invented",  # 4
    "exception_kept",     # 5
    "left_open",          # 6
    "revised_when_due",   # 7
    "held_when_not_due",  # 8
    "citations",          # 9a
    "history",            # 9b
    "tolerated",          # contested decisions, reported apart
    "usable",             # parsed at all
)


def _normalise(text: str) -> str:
    return " ".join(text.split()).strip().lower()


def _quotes(parsed) -> list[str]:
    """Every quote the answer offers, blanks aside.

    An empty string is not a citation that failed, it is no citation, and
    counting it as a miss made the ceiling unreachable.
    """
    found = []
    for name in ("source_quote", "supporting_quotes", "contradicting_quotes"):
        value = parsed.open.get(name)
        if isinstance(value, str):
            found.append(value)
        elif isinstance(value, list):
            found.extend(item for item in value if isinstance(item, str))
    return [quote for quote in found if quote.strip()]


def score_stage(
    case: dict,
    stage: dict,
    parsed,
    previous=None,
    *,
    condition: str,
    stage_index: int,
) -> dict:
    """One answer against one declared stage. Counters, not verdicts."""
    shown = _normalise(
        " ".join(frame["text"] for frame in frame_cases.frames_up_to(case, stage["after"]))
    )
    must = stage.get("must", {})
    tolerated = stage.get("tolerated", {})
    must_not = stage.get("must_not", {})
    # Gold's convention: anything not required and not tolerated is open.
    open_fields = [name for name in CLOSED_FIELDS if name not in must and name not in tolerated]

    row = {f"{name}_hit": 0 for name in MEASURES}
    row.update({f"{name}_total": 0 for name in MEASURES})
    row["case_id"] = case["case_id"]
    row["pair"] = case["pair"]
    row["category"] = case["category"]
    row["stage"] = stage["after"]
    row["condition"] = condition
    row["usable_total"] = 1
    row["usable_hit"] = 1 if parsed.usable else 0
    row["wrong_fields"] = []
    row["unsupported_fields"] = []

    if not parsed.usable:
        # An unparsable answer is a failed case on every opportunity the stage
        # offers, never a skipped one: silently dropping it would let a
        # condition improve its score by failing to answer.
        row["correct_total"] = len(must)
        row["tolerated_total"] = len(tolerated)
        row["left_open_total"] = len(open_fields)
        row["unsupported_total"] = len(open_fields)
        row["excluded_total"] = sum(len(values) for values in must_not.values())
        if must.get("status") == "contradictory":
            row["contradiction_found_total"] = 1
        if "contradictory" in must_not.get("status", []):
            # No credit for avoiding an error by not answering. An unreadable
            # reply gave no reading, so it neither found nor invented anything,
            # and crediting the avoidance would let silence beat an attempt.
            row["contradiction_invented_total"] = 1
        if must.get("exception_present") == "yes" or "all" in must_not.get("quantifier", []):
            row["exception_kept_total"] = 1
        return row

    answered = parsed.closed

    # 1 — the components the text explicitly supports.
    row["correct_total"] = len(must)
    for name, value in must.items():
        if answered.get(name) == value:
            row["correct_hit"] += 1
        else:
            row["wrong_fields"].append(f"{name}={answered.get(name)!r} want {value!r}")

    # contested decisions, counted but kept out of the headline
    row["tolerated_total"] = len(tolerated)
    for name, values in tolerated.items():
        if answered.get(name) in values:
            row["tolerated_hit"] += 1

    # 6 and 2 — openness, and its complement
    row["left_open_total"] = len(open_fields)
    row["unsupported_total"] = len(open_fields)
    for name in open_fields:
        if not frame_object.is_decided(answered.get(name)):
            row["left_open_hit"] += 1
            row["unsupported_hit"] += 1
        else:
            row["unsupported_fields"].append(f"{name}={answered.get(name)!r}")

    # the sharp subset: a value gold excludes
    row["excluded_total"] = sum(len(values) for values in must_not.values())
    for name, values in must_not.items():
        for value in values:
            if answered.get(name) != value:
                row["excluded_hit"] += 1

    # 3 and 4 — found against invented
    if must.get("status") == "contradictory":
        row["contradiction_found_total"] = 1
        row["contradiction_found_hit"] = 1 if answered.get("status") == "contradictory" else 0
    if "contradictory" in must_not.get("status", []):
        row["contradiction_invented_total"] = 1
        row["contradiction_invented_hit"] = 0 if answered.get("status") == "contradictory" else 1

    # 5 — a local exception survives, and does not become a general permission
    if must.get("exception_present") == "yes" or "all" in must_not.get("quantifier", []):
        row["exception_kept_total"] = 1
        kept = True
        if must.get("exception_present") == "yes":
            kept = kept and answered.get("exception_present") == "yes"
        if "all" in must_not.get("quantifier", []):
            kept = kept and answered.get("quantifier") != "all"
        if "granted" in must_not.get("permission", []):
            kept = kept and answered.get("permission") != "granted"
        row["exception_kept_hit"] = 1 if kept else 0

    # 7 and 8 — revising when due, holding when not
    if previous is not None and previous.usable and stage["revision"] in ("required", "forbidden"):
        moved = frame_object.differences(previous, parsed)
        moved = [name for name in moved if name in REVISION_FIELDS]
        if stage["revision"] == "required":
            row["revised_when_due_total"] = 1
            row["revised_when_due_hit"] = 1 if moved else 0
        else:
            row["held_when_not_due_total"] = 1
            row["held_when_not_due_hit"] = 0 if moved else 1
            row["moved_fields"] = moved

    # 9a — every quote has to be in the text shown so far
    for quote in _quotes(parsed):
        row["citations_total"] += 1
        if _normalise(quote) and _normalise(quote) in shown:
            row["citations_hit"] += 1

    # 9b — the staged procedure has to keep its own history
    if condition == "C" and stage_index > 0:
        row["history_total"] = 1
        history = parsed.open.get("history")
        row["history_hit"] = 1 if isinstance(history, list) and len(history) >= stage_index else 0
    return row


def aggregate(rows: list[dict]) -> dict:
    """Totals per condition, and the same split by category."""
    report: dict = {}
    for condition in sorted({row["condition"] for row in rows}):
        subset = [row for row in rows if row["condition"] == condition]
        report[condition] = {
            "stages": len(subset),
            "overall": {
                name: {
                    "hit": sum(row.get(f"{name}_hit", 0) for row in subset),
                    "total": sum(row.get(f"{name}_total", 0) for row in subset),
                }
                for name in MEASURES
            },
            "by_category": {
                category: {
                    name: {
                        "hit": sum(
                            row.get(f"{name}_hit", 0) for row in subset
                            if row["category"] == category
                        ),
                        "total": sum(
                            row.get(f"{name}_total", 0) for row in subset
                            if row["category"] == category
                        ),
                    }
                    for name in MEASURES
                }
                for category in sorted({row["category"] for row in subset})
            },
        }
    return report


def share(cell: dict) -> float | None:
    return None if not cell["total"] else cell["hit"] / cell["total"]


def _by_pair(rows: list[dict], condition: str, measure: str) -> dict[str, tuple[int, int]]:
    """Hits and opportunities per minimal pair.

    The pair is the unit of resampling: its two halves differ in one sentence
    and are not independent of each other, and repeats of the same case are
    measurements of one model rather than of several annotators.
    """
    collected: dict[str, list[int]] = {}
    for row in rows:
        if row["condition"] != condition:
            continue
        hit, total = row.get(f"{measure}_hit", 0), row.get(f"{measure}_total", 0)
        bucket = collected.setdefault(row["pair"], [0, 0])
        bucket[0] += hit
        bucket[1] += total
    return {pair: (hit, total) for pair, (hit, total) in collected.items()}


def paired_difference(
    rows: list[dict], left: str, right: str, measure: str, *, draws: int = 2000,
    seed: int = 20261025,
) -> dict:
    """The difference between two conditions on one measure, resampled by pair.

    Reported as the plain difference of shares plus a percentile interval from
    resampling whole pairs. The interval says how far the estimate would move
    with a different draw of pairs from the same construction; it says nothing
    about a different model, a different language or real documents.
    """
    left_pairs = _by_pair(rows, left, measure)
    right_pairs = _by_pair(rows, right, measure)
    shared = sorted(set(left_pairs) & set(right_pairs))
    if not shared:
        return {"measure": measure, "left": left, "right": right, "comparable_pairs": 0}

    def ratio(pairs, keys):
        hit = sum(pairs[key][0] for key in keys)
        total = sum(pairs[key][1] for key in keys)
        return None if not total else hit / total

    observed_left, observed_right = ratio(left_pairs, shared), ratio(right_pairs, shared)
    if observed_left is None or observed_right is None:
        return {"measure": measure, "left": left, "right": right, "comparable_pairs": 0}

    generator = random.Random(seed)
    differences = []
    for _ in range(draws):
        drawn = [generator.choice(shared) for _ in shared]
        one, two = ratio(left_pairs, drawn), ratio(right_pairs, drawn)
        if one is not None and two is not None:
            differences.append(one - two)
    differences.sort()
    low = differences[int(0.025 * len(differences))] if differences else None
    high = differences[int(0.975 * len(differences)) - 1] if differences else None
    wins = sum(
        1 for key in shared
        if left_pairs[key][1] and right_pairs[key][1]
        and left_pairs[key][0] / left_pairs[key][1] > right_pairs[key][0] / right_pairs[key][1]
    )
    losses = sum(
        1 for key in shared
        if left_pairs[key][1] and right_pairs[key][1]
        and left_pairs[key][0] / left_pairs[key][1] < right_pairs[key][0] / right_pairs[key][1]
    )
    return {
        "measure": measure,
        "left": left,
        "right": right,
        "comparable_pairs": len(shared),
        "left_share": round(observed_left, 4),
        "right_share": round(observed_right, 4),
        "difference": round(observed_left - observed_right, 4),
        "interval": [None if low is None else round(low, 4),
                     None if high is None else round(high, 4)],
        "pairs_favouring_left": wins,
        "pairs_favouring_right": losses,
        "pairs_level": len(shared) - wins - losses,
    }
