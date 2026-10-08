"""Three outcomes, measured apart: anchoring, meaning, relations.

Span recall cannot tell a faithful claim from one that anchors on the right
sentence and reverses it. So the hand-annotated set in
`fixtures/semantic_cases/cases.json` is scored on separate axes, and the point of
separating them is that a change can look better by capturing *more text* while
producing worse structure.

    anchored    does any admitted claim overlap the annotated passage
    language    is the claim written in the language of the document
    meaning     do the declared requirements hold for a claim on it, and does
                any claim on it trip a forbidden pattern or claim type
    relations   are the edges between claims right

The language axis was added after the first run, because it is what that run
found: 38 of 122 claims from German sources came back in English, and none of 126
from English sources came back in German. Without the axis that shows up as a
meaning failure, since a requirement written as German tokens cannot be satisfied
by a faithful English rendering — which is why it is a separate outcome and not a
wider token list.

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
import re
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

# Crude on purpose, like the meaning checks: function words, counted. It has to
# classify the 24 case documents correctly, which the test suite asserts, before
# it is allowed to classify a claim.
GERMAN_MARKERS = frozenset(
    "der die das und dass nicht den dem ein eine mit im in auf wird werden sei war"
    " ist alle für von zu sich des beim wenn".split()
)
ENGLISH_MARKERS = frozenset(
    "the and that not of to in on is was are were will all for with does if by"
    " from this its".split()
)


def language_of(text: str) -> str:
    """ "de", "en", or "?" when the markers do not separate."""
    words = set(re.findall(r"[\wäöüß]+", text.casefold()))
    german = len(words & GERMAN_MARKERS)
    english = len(words & ENGLISH_MARKERS)
    if german == english:
        return "?"
    return "de" if german > english else "en"


def _folded(text: str) -> str:
    """Whitespace, case and a trailing full stop ignored; nothing else."""
    return " ".join(text.split()).casefold().rstrip(".")


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

    # One entry per claim the span has to carry, and an entry is the groups that
    # *one* claim must satisfy together. A single group per claim let two bare
    # fragments pass; see §3am.
    distinct = cases_module.distinct_claims(case)
    assigned: list[str] = []
    for claim_groups in distinct:
        for text in contents:
            if text in assigned:
                continue
            if cases_module.satisfies(text, claim_groups):
                assigned.append(text)
                break
    distinct_met = len(assigned) == len(distinct)

    forbidden_types = {t.lower() for t in (case.get("forbidden_claim_types") or [])}
    # A case's own worked failures. The validator checks that each one violates
    # some requirement, which proves the case is not vacuous; it never checked
    # whether a live claim *is* one. Found by the independent reviews: a forbidden
    # reading standing beside a compliant claim satisfied the requirements and
    # tripped no regex, so the case passed with the invented claim in the graph.
    forbidden_readings = {
        _folded(reading) for reading in (case.get("forbidden_readings") or [])
    }
    distortions = []
    for claim in on_span:
        tripped = cases_module.violates(claim["canonical_content"], case.get("forbids") or [])
        if tripped:
            distortions.append({"claim": claim["canonical_content"][:90], "forbids": tripped})
        if str(claim["claim_type"]).lower() in forbidden_types:
            distortions.append(
                {"claim": claim["canonical_content"][:90], "claim_type": claim["claim_type"]}
            )
        if _folded(claim["canonical_content"]) in forbidden_readings:
            distortions.append(
                {"claim": claim["canonical_content"][:90], "forbidden_reading": True}
            )

    needed = case.get("min_claims_on_span", 1)
    languages = [language_of(text) for text in contents]
    translated = [
        text
        for text, found in zip(contents, languages, strict=True)
        if found not in (case["language"], "?")
    ]
    return {
        "case_id": case["case_id"],
        "anchored": bool(on_span),
        "claims_on_span": len(on_span),
        "enough_claims": len(on_span) >= needed,
        "requirements_met": bool(satisfied) if groups else True,
        "distinct_met": distinct_met,
        # A distortion now fails the case. It did not before: `distortions` was
        # reported beside `meaning_preserved` and never entered it, so a claim
        # that tripped a forbidden pattern or carried a forbidden claim type
        # still counted as meaning preserved. No run had ever produced one, so
        # no published figure moves — but the check could not have caught it.
        "meaning_preserved": (bool(satisfied) if groups else True)
        and distinct_met
        and len(on_span) >= needed
        and not distortions,
        "distortions": distortions,
        "translated": translated,
        "in_source_language": bool(contents) and not translated,
        "normalised_anchors": sum(1 for c in on_span if c.get("anchor_normalised")),
        "contents": contents,
    }


def rescore(directory: Path, cases: list[dict]) -> dict[str, list[dict]]:
    """Score stored dossiers again under the current scorer, at no cost.

    The figures in §3af and §3ah were produced by a scorer in which a distortion
    did not fail a case. When that is fixed the honest question is whether any
    published figure moves, and the dossiers are on disk, so the answer costs
    nothing. Reads `<case_id>-<repeat>.json` and calls no provider.
    """
    by_id = {case["case_id"]: case for case in cases}
    rows: dict[str, list[dict]] = {}
    for path in sorted(directory.glob("*.json")):
        stem, _, repeat = path.stem.rpartition("-")
        case = by_id.get(stem)
        if case is None or not repeat.isdigit():
            continue
        stored = json.loads(path.read_text(encoding="utf-8"))
        if "claims" not in stored:
            continue
        rows.setdefault(stem, []).append(score(case, stored["claims"]))
    return rows


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
    parser.add_argument(
        "--rescore",
        action="store_true",
        help="score the dossiers already in out_dir; calls no provider, costs nothing",
    )
    args = parser.parse_args()

    cases = cases_module.load()
    problems = cases_module.validate(cases)
    if problems:
        print(f"Der Prüfbestand verletzt {len(problems)} Invarianten; es wird nicht gemessen.")
        for problem in problems:
            print(f"  {problem}")
        return 1

    rows: dict[str, list[dict]] = {}
    failures: Counter = Counter()

    if args.rescore:
        rows = rescore(args.out_dir, cases)
        if not rows:
            print(f"keine gespeicherten Dossiers in {args.out_dir}", file=sys.stderr)
            return 1
        return report(cases, rows, failures, args.out_dir)

    provider = DeepSeekProvider()
    args.out_dir.mkdir(parents=True, exist_ok=True)

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

    return report(cases, rows, failures, args.out_dir)


def report(
    cases: list[dict],
    rows: dict[str, list[dict]],
    failures: Counter,
    out_dir: Path,
) -> int:
    """The three outcomes plus the language axis, printed and stored.

    Split out of main() so that --rescore reports identically to a paid run:
    a second reporting path would be a second thing to keep in step.
    """
    print("\n" + "=" * 72)
    print(
        f"{'Fall':12}{'verankert':>11}{'Sprache':>9}{'Bedeutung':>11}{'Claims':>9}{'Verzerrt':>10}"
    )
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
        language = sum(r["in_source_language"] for r in runs)
        print(
            f"{case['case_id']:12}{anchored:>8}/{len(runs)}{language:>6}/{len(runs)}"
            f"{meaning:>8}/{len(runs)}{claims:>9.1f}{distorted:>10}"
        )
        by_phenomenon.setdefault(case["phenomenon"], []).extend(
            r["meaning_preserved"] for r in runs
        )

    print("\nBedeutung erhalten, nach Phänomen:")
    for phenomenon, results in sorted(by_phenomenon.items()):
        print(f"  {phenomenon:26} {sum(results)}/{len(results)}")

    for source in ("de", "en"):
        subset = [
            r for case in cases if case["language"] == source for r in rows.get(case["case_id"], [])
        ]
        if subset:
            kept = sum(r["in_source_language"] for r in subset)
            moved = sum(len(r["translated"]) for r in subset)
            print(
                f"\nQuelle {source}: {kept}/{len(subset)} Fall-Läufe durchgehend in der "
                f"Sprache der Quelle, {moved} übersetzte Claims"
            )

    normalised = sum(r["normalised_anchors"] for runs in rows.values() for r in runs)
    print(f"\nÜber Leerraum verankert: {normalised} (auf einzeiligen Sätzen erwartet: 0)")
    if failures:
        print(f"Fehlgeschlagene Aufrufe: {dict(failures)}")
    print("\nRelationen: auf diesem Bestand nicht messbar, die Fälle annotieren keine Kanten.")
    (out_dir / "semantic-score.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
