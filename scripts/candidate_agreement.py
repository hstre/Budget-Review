"""Does disagreement between repeats of one extraction predict that it is wrong?

The project has a gold-free signal already — the anchored share — and §4.4
showed it orders four documents by a recall it cannot see. But ordering is not
rejection: a signal can order correctly and still fail to pick out the bad case,
which is the only thing a warning light is for.

arXiv 2610.13236 makes that distinction the whole point. It derives an
uncertainty score from the *spread of several candidate parses* rather than from
one parse's self-report, and then refuses to judge the score by self-consistency:
it asks whether rejecting the cases the score calls uncertain actually removes
the bad ones. Its counter-finding matters as much as its method — more candidates
did not mean better uncertainty, and for one parser a larger beam made the score
worse than useless.

This script computes that spread over the repeats of the hand-annotated meaning
set, where every case has a gold answer, and puts it beside the gold outcome.

**The limitation is the measurement, not a footnote to it.** Of 72 stored runs,
69 satisfy their case. Three failures cannot calibrate anything: a score that
fires on them perfectly and a score that fires at random are told apart by a
sample this size only by luck. So the script reports the separation it finds and
the number of failures it rests on, side by side, and a reader who wants a
calibrated probability needs a harder case set rather than more repeats.

Agreement is computed three ways on purpose. 2610.13476's finding is that the
choice of similarity measure can change the reliability verdict, so a single
measure here would be the same mistake one layer up.

Usage:
    candidate_agreement.py DIR            # dossiers named <case_id>-<repeat>.json
    candidate_agreement.py DIR --json OUT
"""

from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cases_module = _load("semantic_cases")
semantic_score = _load("semantic_score")


def jaccard(left: set[str], right: set[str]) -> float:
    """Overlap of two sets, with two empty sets counted as agreeing.

    Two runs that both found nothing agree about the document. Calling that a
    disagreement would make the emptiest case look like the most uncertain one.
    """
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def token_agreement(contents: list[list[str]]) -> float:
    """Mean pairwise token overlap across the repeats of one case.

    Tokens rather than whole strings, because the wording is the unstable half of
    a claim (§4.5) and a measure that only sees exact strings reports every
    rephrasing as total disagreement. That would make the score fire on cases
    where the repeats said the same thing differently.
    """
    bags = [{word for text in run for word in text.lower().split()} for run in contents]
    pairs = list(itertools.combinations(bags, 2))
    return statistics.mean(jaccard(a, b) for a, b in pairs) if pairs else 1.0


def exact_agreement(contents: list[list[str]]) -> bool:
    """Whether every repeat produced the same set of claim texts."""
    return len({frozenset(run) for run in contents}) == 1


def count_agreement(counts: list[int]) -> bool:
    """Whether every repeat put the same number of claims on the span."""
    return len(set(counts)) == 1


def rows_for(directory: Path) -> dict[str, list[dict]]:
    cases = cases_module.load()
    return semantic_score.rescore(directory, cases)


def measure(directory: Path) -> dict:
    results = []
    for case_id, runs in sorted(rows_for(directory).items()):
        contents = [run["contents"] for run in runs]
        passed = [bool(run["meaning_preserved"]) for run in runs]
        results.append(
            {
                "case_id": case_id,
                "repeats": len(runs),
                "token_agreement": round(token_agreement(contents), 4),
                "same_claim_set": exact_agreement(contents),
                "same_claim_count": count_agreement([run["claims_on_span"] for run in runs]),
                "passed": sum(passed),
                "all_passed": all(passed),
            }
        )
    flagged = {r["case_id"] for r in results if not r["same_claim_set"]}
    failed = {r["case_id"] for r in results if not r["all_passed"]}
    return {
        "cases": results,
        "runs": sum(r["repeats"] for r in results),
        "failed_runs": sum(r["repeats"] - r["passed"] for r in results),
        "flagged_cases": sorted(flagged),
        "failed_cases": sorted(failed),
        # The three cells a separation claim has to be read against. A perfect
        # match between them is still only as strong as `failed_cases` is long.
        "flagged_and_failed": sorted(flagged & failed),
        "flagged_but_passed": sorted(flagged - failed),
        "failed_but_unflagged": sorted(failed - flagged),
    }


def report(result: dict) -> None:
    print(f"{'Fall':>12} {'Token':>7} {'Menge':>7} {'Zahl':>6}   Gold")
    print("-" * 48)
    for row in result["cases"]:
        marks = "+" * row["passed"] + "-" * (row["repeats"] - row["passed"])
        print(
            f"{row['case_id']:>12} {row['token_agreement']:>7.2f} "
            f"{'gleich' if row['same_claim_set'] else 'anders':>7} "
            f"{'=' if row['same_claim_count'] else '≠':>6}   {marks}"
        )
    print()
    print(f"Läufe: {result['runs']}, davon fehlgeschlagen: {result['failed_runs']}")
    print(f"Fälle mit uneinheitlicher Claim-Menge: {result['flagged_cases'] or '—'}")
    print(f"Fälle, die Gold verfehlen:             {result['failed_cases'] or '—'}")
    print()
    print(f"  markiert und durchgefallen: {result['flagged_and_failed'] or '—'}")
    print(f"  markiert, aber bestanden:   {result['flagged_but_passed'] or '—'}")
    print(f"  durchgefallen, unmarkiert:  {result['failed_but_unflagged'] or '—'}")
    print()
    failed = len(result["failed_cases"])
    if failed == 0:
        print("Kein Fall verfehlt Gold. Gegen diesen Bestand ist kein Signal prüfbar.")
    else:
        print(
            f"Die Trennung ruht auf {failed} durchgefallenen "
            f"{'Fall' if failed == 1 else 'Fällen'}. Das ist zu wenig für eine "
            "kalibrierte Aussage und reicht nur für den Satz, dass das Signal "
            "existiert."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()
    result = measure(args.directory)
    if not result["cases"]:
        print(f"keine bewertbaren Dossiers in {args.directory}", file=sys.stderr)
        return 1
    report(result)
    if args.json:
        args.json.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        print(f"\n{args.json} geschrieben")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
