"""Run the comparison, offline against a stub or live against the provider.

The offline run comes first and costs nothing. It exists for two reasons: to
exercise the whole path before any money is spent, and to check the scoring
against strategies whose ranking is known in advance. A scorer that cannot tell
an answer of `undecided` everywhere from a careful reading would make the paid
run meaningless, and the only way to find that out is to feed it one.

    frame_run.py --stub gold        --out runs/dry-gold
    frame_run.py --stub undecided   --out runs/dry-undecided
    frame_run.py --stub confident   --out runs/dry-confident
    frame_run.py --stub never_revise --out runs/dry-never
    frame_run.py --stub malformed   --out runs/dry-malformed
    frame_run.py --live --out runs/live        # paid; needs DEEPSEEK_API_KEY

Every call is written out whole — prompt, reply, token counts, seconds — so the
run can be read back without rerunning it. Tokens are always recorded; a price
is only ever reported when one is passed in, because a number this file made up
would be worse than none.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import queue
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


frame_object = _load("frame_object")
frame_cases = _load("frame_cases")
frame_conditions = _load("frame_conditions")
frame_score = _load("frame_score")

CLOSED_FIELDS = frame_object.CLOSED_FIELDS
UNDECIDED = frame_object.UNDECIDED

# One call may not outlast this, whatever the socket does. A peer that trickles
# a body resets a socket timeout on every chunk, and this project has already
# paid 45 minutes for one unbounded read.
CALL_BUDGET_SECONDS = 90.0
RUN_BUDGET_SECONDS = 2700.0
CONSECUTIVE_FAILURE_LIMIT = 6


# ── offline strategies ───────────────────────────────────────────────────────


def _answer_from(closed: dict, note: str) -> str:
    payload = {name: closed.get(name, UNDECIDED) for name in CLOSED_FIELDS}
    payload.update({
        "object_id": "stub",
        "source_quote": "",
        "candidate_readings": [],
        "preferred_reading": closed.get("preferred", UNDECIDED),
        "supporting_quotes": [],
        "contradicting_quotes": [],
        "reason": note,
        "history": [],
    })
    return json.dumps(payload, ensure_ascii=False)


def stub_reply(strategy: str, case: dict, stage: dict, stage_index: int) -> str:
    """A reply built without calling anything.

    `gold` reads the declared expectation and answers it: the ceiling the
    measurement can reach, and a check that gold is self-consistent. The others
    are the failure modes the scoring has to separate.
    """
    if strategy == "gold":
        closed = dict(stage.get("must", {}))
        for name, values in stage.get("tolerated", {}).items():
            closed[name] = values[0]
        history = [{"frame": stage["after"], "change": "stub", "reason": "stub"}] * max(
            stage_index, 0
        )
        payload = json.loads(_answer_from(closed, "gold stub"))
        payload["history"] = history
        payload["supporting_quotes"] = [
            frame["text"] for frame in frame_cases.frames_up_to(case, stage["after"])
        ]
        return json.dumps(payload, ensure_ascii=False)
    if strategy == "undecided":
        return _answer_from({}, "alles offen")
    if strategy == "confident":
        # The first value that is not `undecided`, for every field: the shape of
        # an answer that never declines.
        closed = {name: allowed[0] for name, allowed in CLOSED_FIELDS.items()}
        return _answer_from(closed, "immer entschieden")
    if strategy == "never_revise":
        first = case["gold"][0]
        closed = dict(first.get("must", {}))
        for name, values in first.get("tolerated", {}).items():
            closed[name] = values[0]
        return _answer_from(closed, "erste Lesart festgehalten")
    if strategy == "contrarian":
        # Everything is a contradiction: the strategy the fourth measure exists
        # for. It should take the detection measure and lose its mirror.
        closed = {"status": "contradictory"}
        return _answer_from(closed, "immer widersprüchlich")
    if strategy == "malformed":
        return "Die Aussage ist mehrdeutig, deshalb kann ich hier kein JSON liefern."
    raise ValueError(f"unknown stub strategy {strategy!r}")


# ── the live call, bounded ───────────────────────────────────────────────────


def _call_with_deadline(function, budget: float):
    """Run one call in a worker and give up on it when the budget is spent.

    A thread cannot be killed, so a call that overruns is abandoned rather than
    stopped. That is the point: the run continues, and the abandoned call is
    recorded as a failure instead of becoming the whole run.
    """
    outcome: queue.Queue = queue.Queue(maxsize=1)

    def work():
        try:
            outcome.put(("ok", function()))
        except BaseException as error:  # noqa: BLE001 - recorded, not handled
            outcome.put(("error", error))

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    try:
        kind, value = outcome.get(timeout=budget)
    except queue.Empty:
        raise TimeoutError(f"call did not finish within {budget:.0f}s") from None
    if kind == "error":
        raise value
    return value


class LiveCaller:
    """The provider, with usage read back off every call."""

    def __init__(self, model: str, max_tokens: int) -> None:
        from budget_review.provider import DeepSeekProvider, ModelConfig

        self.provider = DeepSeekProvider(timeout=45.0, retries=1)
        self.config = ModelConfig(model_id=model, thinking=False)
        self.max_tokens = max_tokens

    def __call__(self, system: str, user: str) -> tuple[str, dict]:
        parsed, metadata = _call_with_deadline(
            lambda: self.provider.complete_json(
                system=system, user=user, config=self.config, max_tokens=self.max_tokens
            ),
            CALL_BUDGET_SECONDS,
        )
        return json.dumps(parsed, ensure_ascii=False), metadata


# ── orchestration ────────────────────────────────────────────────────────────


def run_case(case: dict, condition: str, caller, *, strategy: str | None,
             records: list[dict], repeat: int) -> list[dict]:
    """One case under one condition. Every call is stateless."""
    stages = frame_conditions.plan(case, condition)
    gold_by_stage = {stage["after"]: stage for stage in case["gold"]}
    previous_reply: str | None = None
    parsed_history: list = []
    rows: list[dict] = []

    for index, after in enumerate(stages):
        system, user = frame_conditions.build(
            case, after, condition, previous=previous_reply, passes_done=index
        )
        started = time.monotonic()
        if strategy is not None:
            reply = stub_reply(strategy, case, gold_by_stage[after], index)
            metadata = {"usage": {}, "model": f"stub:{strategy}"}
            failure = ""
        else:
            try:
                reply, metadata = caller(system, user)
                failure = ""
            except Exception as error:  # noqa: BLE001 - a failed call is a result
                reply, metadata, failure = "", {"usage": {}}, f"{type(error).__name__}: {error}"
        seconds = time.monotonic() - started

        parsed = frame_object.parse(reply) if reply else frame_object.parse("")
        records.append({
            "case_id": case["case_id"], "condition": condition, "stage": after,
            "call_index": index, "repeat": repeat,
            "system": system, "user": user, "reply": reply,
            "failure": failure, "usage": metadata.get("usage", {}),
            "model": metadata.get("model", ""), "seconds": round(seconds, 3),
            "parse_complaints": parsed.complaints,
        })

        # Only the staged arms are scored at every stage. B and D are asked
        # about the whole text, so their earlier passes are not answers about
        # an earlier information state and are not scored as such.
        scored_here = condition in ("A", "B_staged", "C") or index == len(stages) - 1
        if scored_here:
            previous_parsed = parsed_history[-1] if condition in ("B_staged", "C") and parsed_history else None
            rows.append(frame_score.score_stage(
                case, gold_by_stage[after], parsed, previous_parsed,
                condition=condition, stage_index=index,
            ) | {"repeat": repeat, "seconds": round(seconds, 3), "failure": failure})
        parsed_history.append(parsed)
        previous_reply = reply or previous_reply
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="directory for the run's record")
    parser.add_argument("--stub", default=None,
                        help="offline strategy: gold, undecided, confident, contrarian, "
                             "never_revise, malformed")
    parser.add_argument("--live", action="store_true", help="call the provider (paid)")
    parser.add_argument("--set", default="test", choices=("test", "dev"))
    parser.add_argument("--conditions", default=",".join(frame_conditions.CONDITIONS))
    parser.add_argument("--cases", type=int, default=0, help="first N cases only (0 = all)")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--price-in", type=float, default=None,
                        help="price per million input tokens; omitted means no cost is claimed")
    parser.add_argument("--price-out", type=float, default=None)
    arguments = parser.parse_args(argv)

    if bool(arguments.stub) == bool(arguments.live):
        parser.error("pass exactly one of --stub and --live")

    payload = frame_cases.load(
        frame_cases.TEST_SET if arguments.set == "test" else frame_cases.DEV_SET
    )
    problems = frame_cases.validate(payload, expect_pairs=arguments.set == "test")
    problems += frame_cases.leaks(payload, frame_conditions.render)
    if problems:
        print(f"the set is not usable: {len(problems)} problems")
        for problem in problems[:10]:
            print(f"  {problem}")
        return 1

    cases = payload["cases"][: arguments.cases] if arguments.cases else payload["cases"]
    conditions = [name.strip() for name in arguments.conditions.split(",") if name.strip()]
    caller = LiveCaller(arguments.model, arguments.max_tokens) if arguments.live else None

    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    rows: list[dict] = []
    started = time.monotonic()
    consecutive_failures = 0

    for repeat in range(arguments.repeats):
        for case in cases:
            for condition in conditions:
                if time.monotonic() - started > RUN_BUDGET_SECONDS:
                    print(f"run budget of {RUN_BUDGET_SECONDS:.0f}s spent; stopping early")
                    repeat = arguments.repeats
                    break
                produced = run_case(
                    case, condition, caller, strategy=arguments.stub,
                    records=records, repeat=repeat,
                )
                rows.extend(produced)
                if any(row.get("failure") for row in produced):
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0
                if consecutive_failures >= CONSECUTIVE_FAILURE_LIMIT:
                    print(f"{consecutive_failures} case-runs failed in a row; stopping")
                    break
            else:
                continue
            break

    report = frame_score.aggregate(rows)
    usage = {
        "prompt_tokens": sum(r["usage"].get("prompt_tokens", 0) for r in records),
        "completion_tokens": sum(r["usage"].get("completion_tokens", 0) for r in records),
        "calls": len(records),
        "failed_calls": sum(1 for r in records if r["failure"]),
        "seconds": round(sum(r["seconds"] for r in records), 1),
        "models": sorted({r["model"] for r in records if r["model"]}),
    }
    if arguments.price_in is not None and arguments.price_out is not None:
        usage["price_per_million"] = {"input": arguments.price_in, "output": arguments.price_out}
        usage["cost"] = round(
            usage["prompt_tokens"] / 1e6 * arguments.price_in
            + usage["completion_tokens"] / 1e6 * arguments.price_out,
            6,
        )
    else:
        usage["cost"] = None
        usage["cost_note"] = (
            "Tokens gezählt, kein Preis behauptet: --price-in und --price-out setzen, "
            "um die Kosten mit erklärten Preisen auszurechnen."
        )

    (out / "records.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8")
    (out / "rows.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    (out / "report.json").write_text(
        json.dumps({
            "arm": arguments.stub or arguments.model,
            "live": bool(arguments.live),
            "set": arguments.set,
            "cases": len(cases),
            "conditions": conditions,
            "repeats": arguments.repeats,
            "settings": {"temperature": 0.0, "max_tokens": arguments.max_tokens,
                         "response_format": "json_object", "thinking": False,
                         "fresh_context_per_call": True},
            "usage": usage,
            "report": report,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8")

    print(f"{usage['calls']} calls, {usage['failed_calls']} failed, {usage['seconds']}s")
    print(f"tokens in/out: {usage['prompt_tokens']}/{usage['completion_tokens']}  cost: {usage['cost']}")
    header = f"{'condition':<10}" + "".join(f"{name[:11]:>13}" for name in frame_score.MEASURES[:9])
    print(header)
    for condition in conditions:
        if condition not in report:
            continue
        cells = []
        for name in frame_score.MEASURES[:9]:
            cell = report[condition]["overall"][name]
            value = frame_score.share(cell)
            cells.append("        -" if value is None else f"{value:>8.2f}/{cell['total']:<4}")
        print(f"{condition:<10}" + "".join(f"{cell:>13}" for cell in cells))
    print()
    tail = frame_score.MEASURES[9:]
    print(f"{'condition':<10}" + "".join(f"{name[:11]:>13}" for name in tail))
    for condition in conditions:
        if condition not in report:
            continue
        cells = []
        for name in tail:
            cell = report[condition]["overall"][name]
            value = frame_score.share(cell)
            cells.append("        -" if value is None else f"{value:>8.2f}/{cell['total']:<4}")
        print(f"{condition:<10}" + "".join(f"{cell:>13}" for cell in cells))
    print(f"\nwritten to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
