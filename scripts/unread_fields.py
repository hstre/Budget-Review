"""Which fields of a dossier does the product itself ever read?

`anchor_ambiguous` was set by the gate from the day it was built and read by no
part of the product — only by a measurement script. That was found by accident
while adding a different flag (§3ai), and the lesson taken from it was that a
marker nothing renders is not a safeguard. This script asks the question for every
field instead of waiting for the next accident.

The answer is not "unread means wrong". Two of the four unread fields are
**provenance**: `anchor_normalised` and `proposed_span` exist so that an auditor
can see what the model sent beside what the document says, and sitting in the JSON
is the whole job. Nothing should branch on them.

The one that matters is `semantic_state`, and arXiv 2610.06496 is what named why.
Its finding is that models confuse "mentioned" with "still in force" — after a
proposal is rejected, the inactive content reappears in 59.63 per cent of the new
errors. A claim graph needs the distinction as a state: proposed, accepted,
rejected, superseded. We have the field and it is **a state machine with no
transitions**: two values the gate can set, one of them observed across every
stored claim, and no reader anywhere.

What this script does *not* do is judge. It reports writes against reads, by field,
and leaves the four-way distinction above to prose, because "is this field
provenance or a dead safeguard" is not a question a grep can answer.

Usage:
    unread_fields.py            # one line per field of the governed dossier
    unread_fields.py --json OUT
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCT = ROOT / "src" / "budget_review"
# The dataclasses whose fields travel into a dossier a reader or a later run sees.
CARRIERS = ("GovernedClaim", "GovernedRelation", "Finding")
# Where the fields are declared, so a declaration is not counted as a use.
DECLARED_IN = "models.py"


def fields_of(carriers: tuple[str, ...]) -> list[tuple[str, str]]:
    """Every (carrier, field) declared, read from the source tree.

    Keyed by the pair rather than by the field, because `semantic_state` is
    declared on two carriers and a field-keyed map silently kept only the last —
    which is how the first version of this script reported it as belonging to the
    relation alone.
    """
    tree = ast.parse((PRODUCT / DECLARED_IN).read_text(encoding="utf-8"))
    found: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name in carriers:
            for statement in node.body:
                if isinstance(statement, ast.AnnAssign) and isinstance(
                    statement.target, ast.Name
                ):
                    found.append((node.name, statement.target.id))
    return found


def uses(field: str) -> tuple[int, int]:
    """How often the product writes this field, and how often it reads it.

    A write is `field=` in a constructor call; a read is attribute access or a
    subscript on a parsed dict. The declaration file is excluded from both, since
    declaring a field is neither.
    """
    writes = reads = 0
    for path in sorted(PRODUCT.rglob("*.py")):
        if path.name == DECLARED_IN:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == field:
                writes += 1
            elif isinstance(node, ast.Attribute) and node.attr == field:
                reads += 1
            elif (
                isinstance(node, ast.Subscript)
                and isinstance(node.slice, ast.Constant)
                and node.slice.value == field
            ):
                reads += 1
    return writes, reads


def measure() -> dict:
    rows = []
    for carrier, field in sorted(fields_of(CARRIERS)):
        writes, reads = uses(field)
        rows.append({"field": field, "carrier": carrier, "writes": writes, "reads": reads})
    # A field on two carriers is one field as far as the grep goes, so report the
    # distinct names rather than counting it twice.
    unread = sorted({r["field"] for r in rows if r["writes"] and not r["reads"]})
    never_written = sorted({r["field"] for r in rows if not r["writes"] and not r["reads"]})
    return {"fields": rows, "unread": unread, "never_written": never_written}


def report(result: dict) -> None:
    print(f"{'Feld':24}{'Träger':20}{'geschrieben':>12}{'gelesen':>9}")
    for row in result["fields"]:
        mark = "  <-- ungelesen" if row["writes"] and not row["reads"] else ""
        print(
            f"{row['field']:24}{row['carrier']:20}"
            f"{row['writes']:>12}{row['reads']:>9}{mark}"
        )
    unread = result["unread"]
    print(f"\nGeschrieben und vom Produkt nie gelesen: {len(unread)}")
    for field in unread:
        print(f"  {field}")
    if result["never_written"]:
        print(f"\nNie gesetzt und nie gelesen: {len(result['never_written'])}")
        for field in result["never_written"]:
            print(f"  {field}  (traegt nur seinen Vorgabewert)")
    print(
        "\nUngelesen heißt nicht falsch. Provenienzfelder sollen im JSON stehen und\n"
        "sonst nichts tun. Die Unterscheidung trifft die Prosa, nicht dieses Skript."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()
    result = measure()
    report(result)
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
