"""Three outcomes, measured apart: anchoring, meaning, relations.

Span recall cannot tell a faithful claim from one that anchors on the right
sentence and reverses it. So the hand-annotated set in
`fixtures/semantic_cases/cases.json` is scored on separate axes, and the point of
separating them is that a change can look better by capturing *more text* while
producing worse structure.

    anchored    does any admitted claim overlap the annotated passage
    meaning     do the declared requirements hold for a claim on it, and does
                any claim on it trip a forbidden pattern or claim type
    relations   are the edges between claims right

The third one is **not measurable on this set**, and that is a defect in the set
rather than in this script: the cases declare what meaning must survive and say
nothing about which edges should exist. Found by trying to implement it. It is
reported as not measured rather than quietly dropped, and the review round has to
add the annotation.

What the first run of this is for: the set is a draft written by one model, so
these numbers are not a verdict on the extractor. They are a check that the
apparatus functions and that the gold is right — in particular whether the two
cases predicted to contain a false alarm actually produce one.

No token group may be extended on the strength of a run. A requirement that
fires on a faithful claim is a defect in the case, fixed through the review brief
with a dated note, never by widening the list until the run passes.

Usage:
    semantic_score.py <output-dir> [--repeats N] [--profile general|budget]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cases_module = _load("semantic_cases")

from budget_review.gate import govern_packet  # noqa: E402
from budget_review.ingest import SourceBundle  # noqa: E402
from budget_review.provider import DeepSeekProvider, ProviderError  # noqa: E402


def claims_on_span(claims: list[dict], document: str, span: str) -> list[dict]:
    """Admitted claims whose anchor overlaps the annotated passage."""
    start = document.index(span)
    end = start + len(span)
    return [c for c in claims if c["anchor_start"] < end and c["anchor_end"] > start]


def score(case: dict, claims: list[dict]) -> dict:
    """The outcomes for one case, from the claims the gate admitted on its span."""
    on_span = claims_on_span(claims, case["document"], case["span"])
    contents = [c["canonical_content"] for c in on_span]

    groups = case.get("requires_all_groups") or []
    satisfied = [text for text in contents if cases_module.satisfies(text, groups)]

    distinct = case.get("requires_distinct_groups") or []
    assigned: list[str] = []
    for group in distinct:
        for text in contents:
            if text in assigned:
                continue
            if cases_module.satisfies(text, [group]):
                assigned.append(text)
                break
    distinct_met = len(assigned) == len(distinct)

    forbidden_types = {t.lower() for t in (case.get("forbidden_claim_types") or [])}
    distortions = []
    for claim in on_span:
        tripped = cases_module.violates(claim["canonical_content"], case.get("forbids") or [])
        if tripped:
            distortions.append({"claim": claim["canonical_content"][:90], "forbids": tripped})
        if str(claim["claim_type"]).lower() in forbidden_types:
            distortions.append(
                {"claim": claim["canonical_content"][:90], "claim_type": claim["claim_type"]}
            )

    needed = case.get("min_claims_on_span", 1)
    return {
        "case_id": case["case_id"],
        "anchored": bool(on_span),
        "claims_on_span": len(on_span),
        "enough_claims": len(on_span) >= needed,
        "requirements_met": bool(satisfied) if groups else True,
        "distinct_met": distinct_met,
        "meaning_preserved": (bool(satisfied) if groups else True)
        and distinct_met
        and len(on_span) >= needed,
        "distortions": distortions,
        "normalised_anchors": sum(1 for c in on_span if c.get("anchor_normalised")),
        "contents": contents,
    }


def extract(provider, case: dict, profile: str) -> dict:
    """The production extraction path, so the run measures what the product does.

    No budget override: provider.extract carries the production default, and a
    flag that silently did nothing would be worse than no flag.
    """
    packet = provider.extract(case["case_id"], case["document"], profile=profile)
    source = SourceBundle(document_id=case["case_id"], text=case["document"], source_files=())
    dossier = govern_packet(source.text, packet)
    return dossier.to_dict()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--profile", default="general")
    args = parser.parse_args()

    cases = cases_module.load()
    problems = cases_module.validate(cases)
    if problems:
        print(f"Der Prüfbestand verletzt {len(problems)} Invarianten; es wird nicht gemessen.")
        for problem in problems:
            print(f"  {problem}")
        return 1

    provider = DeepSeekProvider()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows: dict[str, list[dict]] = {}
    failures: Counter = Counter()

    for index in range(1, args.repeats + 1):
        for case in cases:
            try:
                dossier = extract(provider, case, args.profile)
            except (ProviderError, SystemExit, KeyError, ValueError) as exc:
                failures[case["case_id"]] += 1
                print(f"  {case['case_id']} Lauf {index}: fehlgeschlagen ({exc})", flush=True)
                continue
            (args.out_dir / f"{case['case_id']}-{index}.json").write_text(
                json.dumps(dossier, ensure_ascii=False, indent=1), encoding="utf-8"
            )
            row = score(case, dossier["claims"])
            row["rejections"] = [r["reason"] for r in dossier["rejections"]]
            rows.setdefault(case["case_id"], []).append(row)
            mark = "ok " if row["meaning_preserved"] else "FEHL"
            print(
                f"  {case['case_id']:12} Lauf {index}: {mark} "
                f"{row['claims_on_span']} Claims auf der Spanne, "
                f"{len(row['distortions'])} Verzerrungen",
                flush=True,
            )

    print("\n" + "=" * 72)
    print(f"{'Fall':12}{'verankert':>11}{'Bedeutung':>11}{'Claims':>9}{'Verzerrt':>10}")
    by_phenomenon: dict[str, list[bool]] = {}
    for case in cases:
        runs = rows.get(case["case_id"], [])
        if not runs:
            print(f"{case['case_id']:12}{'kein Lauf':>11}")
            continue
        anchored = sum(r["anchored"] for r in runs)
        meaning = sum(r["meaning_preserved"] for r in runs)
        claims = sum(r["claims_on_span"] for r in runs) / len(runs)
        distorted = sum(len(r["distortions"]) for r in runs)
        print(
            f"{case['case_id']:12}{anchored:>8}/{len(runs)}{meaning:>8}/{len(runs)}"
            f"{claims:>9.1f}{distorted:>10}"
        )
        by_phenomenon.setdefault(case["phenomenon"], []).extend(
            r["meaning_preserved"] for r in runs
        )

    print("\nBedeutung erhalten, nach Phänomen:")
    for phenomenon, results in sorted(by_phenomenon.items()):
        print(f"  {phenomenon:26} {sum(results)}/{len(results)}")

    normalised = sum(r["normalised_anchors"] for runs in rows.values() for r in runs)
    print(f"\nÜber Leerraum verankert: {normalised} (auf einzeiligen Sätzen erwartet: 0)")
    if failures:
        print(f"Fehlgeschlagene Aufrufe: {dict(failures)}")
    print("\nRelationen: auf diesem Bestand nicht messbar, die Fälle annotieren keine Kanten.")
    (args.out_dir / "semantic-score.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
