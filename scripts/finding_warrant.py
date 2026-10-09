"""Does a deterministic finding reproduce across byte-identical runs?

§3ai measured one half of this: the *claim type* a rule keys on changes in 8 of 24
documents. It then reported that `logical_gap`'s type precondition flips in 0 of
24, which is true and nearly empty — only one document in the whole set carries a
claim typed `thesis`, `inference` or `recommendation` at all, so the precondition
is almost never met and "it does not flip" says next to nothing.

The other half is the one that matters, and arXiv 2610.07753 is what named it. Its
distinction is between an outcome being right and the evidence for it having been
established before the action. `logical_gap` is an **argument from silence**: it
fires when a claim of those types has *no* incoming SUPPORTS or ENTAILS and *no*
outgoing EVIDENCED_BY. Absence is its trigger. And this project has measured, over
and over, that extraction misses much of the argument structure — so the finding
reads as a property of the document while part of it is a property of this run's
extraction.

So this script does not re-implement any rule. It reconstructs the packet from a
stored dossier, re-gates it against the document, and runs the **real**
`deterministic_checks`, then compares the finding set across repeats of the same
document. A finding that does not reproduce under identical input cannot be
warranted by the document.

**What this is not.** 2610.07753 scores outcome against warrant, and the obvious
transfer — score every finding once by whether it was right and once by whether it
was warranted — is not available here. There is no gold answer anywhere in this
project about whether a `logical_gap` is *correct*; the benchmark has task success
and we have nothing of the kind. Reproducibility is a **lower bound** on the
warrant question, not a measurement of it.

Usage:
    finding_warrant.py CASES DIR     # cases.json and <case_id>-<repeat>.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from budget_review.checks import TRIGGER_RESTS_ON, deterministic_checks  # noqa: E402
from budget_review.gate import govern_packet  # noqa: E402
from budget_review.models import SemanticPacket  # noqa: E402

LABEL_KEYED = sorted(key for key, rests in TRIGGER_RESTS_ON.items() if "claim_type" in rests)


def is_governed(stored: dict) -> bool:
    """Whether this file is a gated dossier rather than a pre-gate packet.

    Both are stored by this project's runs, and they differ in how a relation
    names its ends: a packet by proposal id, a dossier by claim node id.
    """
    claims = stored.get("claims") or ()
    return bool(claims) and "claim_node_id" in claims[0]


def prompt_hashes(runs: list[dict]) -> set[str]:
    return {run.get("provenance", {}).get("prompt_hash", "") for run in runs}


def as_packet(dossier: dict) -> SemanticPacket:
    """The proposals behind a stored run, so the real gate can run again.

    A pre-gate packet is already in this shape and is passed through. A gated
    dossier holds governed claims keyed by node id, and the packet form wants
    proposal ids, so relations are translated back through the node-to-proposal
    map rather than rebuilt from anything this script decides.
    """
    if not is_governed(dossier):
        return SemanticPacket.from_dict(dossier)
    proposal_of = {claim["claim_node_id"]: claim["proposal_id"] for claim in dossier["claims"]}
    return SemanticPacket.from_dict(
        {
            "schema_version": "content-review.semantic-packet/0.2",
            "document_id": dossier["document_id"],
            "provenance": dossier["provenance"],
            "claims": [
                {
                    "proposal_id": claim["proposal_id"],
                    "claim_type": claim["claim_type"],
                    "canonical_content": claim["canonical_content"],
                    "raw_span": claim["raw_span"],
                    "confidence": claim["confidence"],
                    "source_ref": claim["source_ref"],
                }
                for claim in dossier["claims"]
            ],
            "relations": [
                {
                    "source_id": proposal_of[relation["source_claim_node_id"]],
                    "relation_type": relation["relation_type"],
                    "target_id": proposal_of[relation["target_claim_node_id"]],
                    "confidence": relation["confidence"],
                    "rationale": relation["rationale"],
                }
                for relation in dossier.get("relations", ())
                if relation["source_claim_node_id"] in proposal_of
                and relation["target_claim_node_id"] in proposal_of
            ],
        }
    )


def fired(dossier: dict, document: str) -> Counter[str]:
    """Which finding categories the real rules produce, counted."""
    regated = govern_packet(document, as_packet(dossier))
    return Counter(finding.category.value for finding in deterministic_checks(regated, "general"))


def group(directory: Path) -> dict[str, list[dict]]:
    runs: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(directory.glob("*.json")):
        stem, _, repeat = path.stem.rpartition("-")
        if not repeat.isdigit() or not stem:
            continue
        dossier = json.loads(path.read_text(encoding="utf-8"))
        if "claims" in dossier and "document_id" in dossier:
            runs[stem].append(dossier)
    return {stem: group for stem, group in runs.items() if len(group) > 1}


def measure(cases: dict, directory: Path) -> dict:
    documents = {case["case_id"]: case["document"] for case in cases["cases"]}
    unstable: list[dict] = []
    stable = 0
    for case_id, runs in sorted(group(directory).items()):
        document = documents.get(case_id)
        if document is None:
            continue
        per_run = [fired(dossier, document) for dossier in runs]
        categories = {name for counts in per_run for name in counts}
        moved = {
            name: [counts.get(name, 0) for counts in per_run]
            for name in sorted(categories)
            if len({counts.get(name, 0) for counts in per_run}) > 1
        }
        if moved:
            unstable.append({"case_id": case_id, "moved": moved})
        else:
            stable += 1
    return {"documents": stable + len(unstable), "stable": stable, "unstable": unstable}


def report(result: dict) -> None:
    print(f"Dokumente mit mehr als einem Lauf: {result['documents']}")
    print(f"identische Befundmenge über alle Läufe: {result['stable']}")
    print(f"**wechselnde Befundmenge**: {len(result['unstable'])}\n")
    for entry in result["unstable"]:
        print(f"  {entry['case_id']}")
        for category, counts in entry["moved"].items():
            print(f"    {category:26} je Lauf: {counts}")
    print(
        "\nEin Befund, der unter identischer Eingabe nicht wiederkehrt, kann vom "
        "Dokument nicht gedeckt sein.\nEin Befund, der wiederkehrt, ist damit "
        "nicht gedeckt — Reproduzierbarkeit ist eine untere Schranke."
    )


def measure_runs(document: str, runs: list[dict]) -> dict:
    """One document, the runs given explicitly, for a corpus not in the repo.

    The long documents this project measures against — a court decision, a paper —
    are fetched at run time and never vendored, so their repeats sit in separate
    downloaded artifacts rather than in one directory under a naming convention.
    """
    per_run = [fired(run, document) for run in runs]
    categories = {name for counts in per_run for name in counts}
    moved = {
        name: [counts.get(name, 0) for counts in per_run]
        for name in sorted(categories)
        if len({counts.get(name, 0) for counts in per_run}) > 1
    }
    # A category reaches `categories` only by appearing in some run, and one that
    # is not in `moved` has equal counts in all of them, so it is non-zero in all.
    # A category no run produced is in neither dict, which is the honest answer:
    # a rule that never had a chance to fire held nothing.
    held = {name: per_run[0][name] for name in sorted(categories - set(moved))}
    return {"runs": len(runs), "moved": moved, "held": held}


def report_runs(result: dict) -> None:
    print(f"Läufe: {result['runs']}")
    print(f"Befundarten, die über alle Läufe gleich bleiben: {len(result['held'])}")
    for name, count in result["held"].items():
        print(f"    {name:26} {count}× in jedem Lauf")
    print(f"\n**Befundarten, deren Zahl wechselt**: {len(result['moved'])}")
    for name, counts in result["moved"].items():
        print(f"    {name:26} je Lauf: {counts}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "cases", type=Path, nargs="?", help="cases.json, for the documents"
    )
    parser.add_argument(
        "directory", type=Path, nargs="?", help="stored runs, <case_id>-<repeat>.json"
    )
    parser.add_argument("--document", type=Path, default=None, help="one document, read as text")
    parser.add_argument(
        "--runs", type=Path, nargs="+", default=None, help="stored runs over that document"
    )
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    if args.document is not None or args.runs is not None:
        if args.document is None or not args.runs:
            parser.error("--document and --runs go together")
        if len(args.runs) < 2:
            parser.error("one run says nothing about reproducibility")
        runs = [json.loads(path.read_text(encoding="utf-8")) for path in args.runs]
        hashes = prompt_hashes(runs)
        if len(hashes) > 1:
            # Without this the measurement would report configuration differences
            # as run-to-run instability. It has already caught one set of runs
            # that the research log describes as three runs of one arm.
            print(
                "the runs do not share a prompt hash, so they are not repeats of "
                f"one configuration: {sorted(hashes)}",
                file=sys.stderr,
            )
            return 1
        result = measure_runs(args.document.read_text(encoding="utf-8"), runs)
        result["prompt_hash"] = hashes.pop()
        report_runs(result)
        if args.json:
            args.json.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        return 0

    if args.cases is None or args.directory is None:
        parser.error("give cases.json and a directory, or --document with --runs")
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    result = measure(cases, args.directory)
    if not result["documents"]:
        print(f"no document in {args.directory} has more than one stored run", file=sys.stderr)
        return 1
    report(result)
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
