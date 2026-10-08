"""Is a claim's type reproducible, and does a deterministic finding depend on it?

The extraction contract names twenty-one claim types and **defines none of them.**
The relation vocabulary at least gets a direction gloss for seven of fourteen; the
claim types get a bare list. So the label is the whole specification, and arXiv
2610.02586 is the limiting case of that: where a short option name sits beside a
written definition, the name drives the decision, and a confidence threshold does
not catch it.

That matters here because `claim_type` is not decoration:

* it is hashed into the claim node id (`gate.py`), so a different type is a
  different node, and every edge to it moves with it;
* two shipped deterministic findings fire on it alone — `logical_gap` at
  confidence 0.9 and `unsupported_assumption` at 0.95.

§3y measured the two halves of a claim: `raw_span` is a *selection* into the
document and reproducible, `canonical_content` is a *generation* and the unstable
half. The type is also a generation, and nothing had ever measured it.

This script measures it from dossiers already paid for, at no further cost. It
reads stored packets, groups repeats of the same document, and reports:

1. whether the multiset of claim types is identical across repeats;
2. which of the flipping types are trigger inputs of a deterministic finding —
   taken from `checks.LOGICAL_GAP_TYPES` and `checks.UNSUPPORTED_ASSUMPTION_TYPE`
   rather than restated here, so the two cannot drift apart;
3. whether `confidence` separates the unstable cases from the stable ones, which
   is the detection claim in 2610.02586 and the mitigation someone would reach
   for first.

**What this cannot say.** Two defensible labels for one sentence is not a model
error. For "Nicht alle Schulen erhalten den Zuschlag." both `fact` and `scope` are
reasonable, and with no definitions there is no fact of the matter about which is
right. The finding is therefore not "the extractor is unstable" but "the
vocabulary has no truth conditions, and a 0.95-confidence finding stands on it."

Usage:
    claim_type_stability.py DIR            # dossiers named <group>-<repeat>.json
    claim_type_stability.py DIR --json OUT
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from budget_review.checks import (  # noqa: E402
    LOGICAL_GAP_TYPES,
    TRIGGER_RESTS_ON,
    UNSUPPORTED_ASSUMPTION_TYPE,
)

# A repeat of the same document: everything before a trailing -1, -2, -3.
REPEAT = re.compile(r"^(?P<group>.+)-(?P<repeat>\d+)$")

GAP_TYPES = {claim_type.value for claim_type in LOGICAL_GAP_TYPES}
ASSUMPTION_TYPE = UNSUPPORTED_ASSUMPTION_TYPE.value

# Findings whose trigger rests on the undefined label, named by the one table.
LABEL_KEYED = sorted(
    key for key, rests_on in TRIGGER_RESTS_ON.items() if "claim_type" in rests_on
)


def load(directory: Path) -> dict[str, list[dict]]:
    """Stored packets, grouped by the document they repeat."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(directory.glob("*.json")):
        matched = REPEAT.match(path.stem)
        if matched is None:
            continue
        packet = json.loads(path.read_text(encoding="utf-8"))
        if "claims" not in packet:
            continue
        groups[matched.group("group")].append(packet)
    return {group: runs for group, runs in groups.items() if len(runs) > 1}


def types_of(packet: dict) -> tuple[str, ...]:
    return tuple(sorted(claim["claim_type"] for claim in packet["claims"]))


def triggers_of(packet: dict) -> dict[str, bool]:
    """Whether each label-keyed rule's *type precondition* is met.

    Only the type half. `logical_gap` also requires the claim to be unsupported
    and `unsupported_assumption` an ASSUMPTION_FOR edge, so a flip here is a
    necessary and not a sufficient condition for the finding to move. Reporting
    the type half alone keeps this script from restating rule logic that lives in
    `checks.py` and would drift.
    """
    present = {claim["claim_type"] for claim in packet["claims"]}
    return {
        "logical_gap": bool(present & GAP_TYPES),
        "unsupported_assumption": ASSUMPTION_TYPE in present,
    }


def measure(groups: dict[str, list[dict]]) -> dict:
    unstable: list[dict] = []
    flipping_triggers: dict[str, list[str]] = defaultdict(list)
    confidence_unstable: list[float] = []
    confidence_stable: list[float] = []
    all_confidence: Counter[float] = Counter()

    for group, runs in sorted(groups.items()):
        per_run = [types_of(packet) for packet in runs]
        changed = len(set(per_run)) > 1
        if changed:
            unstable.append({"group": group, "types_per_run": [list(t) for t in per_run]})
        for rule in ("logical_gap", "unsupported_assumption"):
            states = [triggers_of(packet)[rule] for packet in runs]
            if len(set(states)) > 1:
                flipping_triggers[rule].append(group)
        for packet in runs:
            for claim in packet["claims"]:
                value = float(claim["confidence"])
                all_confidence[value] += 1
                (confidence_unstable if changed else confidence_stable).append(value)

    return {
        "groups": len(groups),
        "unstable": unstable,
        "flipping_triggers": dict(flipping_triggers),
        "confidence": {
            "unstable_mean": statistics.mean(confidence_unstable) if confidence_unstable else None,
            "stable_mean": statistics.mean(confidence_stable) if confidence_stable else None,
            "distribution": dict(sorted(all_confidence.items())),
            "claims": sum(all_confidence.values()),
        },
    }


def report(result: dict) -> None:
    total = result["groups"]
    unstable = result["unstable"]
    print(f"Dokumente mit mehr als einem Lauf: {total}")
    print(f"davon mit **wechselnder Typmenge**: {len(unstable)}")
    for entry in unstable:
        runs = "  |  ".join(",".join(types) for types in entry["types_per_run"])
        print(f"  {entry['group']:14} {runs}")

    print(f"\nRegeln, deren Auslöser am Label hängt: {', '.join(LABEL_KEYED)}")
    for rule in LABEL_KEYED:
        groups = result["flipping_triggers"].get(rule, [])
        print(f"  {rule:24} Typ-Vorbedingung wechselt in {len(groups)} von {total}", end="")
        print(f": {', '.join(groups)}" if groups else "")

    confidence = result["confidence"]
    print(f"\nKonfidenz über {confidence['claims']} Claims:")
    if confidence["unstable_mean"] is not None and confidence["stable_mean"] is not None:
        print(f"  in Fällen mit wechselndem Typ: {confidence['unstable_mean']:.3f}")
        print(f"  in Fällen mit stabilem Typ   : {confidence['stable_mean']:.3f}")
    print(f"  Verteilung: {confidence['distribution']}")
    distinct = len(confidence["distribution"])
    if distinct <= 5:
        print(
            f"  Das Feld nimmt {distinct} Werte an. Auf Konfidenz zu filtern war "
            "hier nie eine Option."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="stored dossiers, <group>-<repeat>.json")
    parser.add_argument("--json", type=Path, default=None, help="also write the result as JSON")
    args = parser.parse_args()

    groups = load(args.directory)
    if not groups:
        print(f"no document in {args.directory} has more than one stored run", file=sys.stderr)
        return 1
    result = measure(groups)
    report(result)
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
