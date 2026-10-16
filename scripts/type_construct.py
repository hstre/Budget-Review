"""Do two runs that use the same type name mean the same thing by it?

Twenty-one claim types, no definitions anywhere in the extraction contract. §4.13
measured that the label is the whole specification and that two shipped findings
fire on it; §4.14 measured that the label moves across byte-identical runs. What
neither asked is the question arXiv 2610.12841 puts: when two builders use the
same name, is the disagreement a boundary drawn in a different place, or are they
projecting different constructs?

That paper separates four cases — a base-rate difference, an affine shift of
scale, a monotone but non-linear mapping, and a divergent ordering, which is the
only one that means the constructs differ. **Three of the four are not available
here, and saying so is the point.** All four rest on a score per item, and a claim
type is a bare category: there is no ordering to preserve or to lose, and §4.13
measured that the confidence float does not separate the stable cases from the
unstable ones, so it cannot stand in for one.

What does transfer is the structure of the disagreement, which needs no ordering:

* **a consistent renaming** — every claim one run calls X, the other calls Y.
  One construct, two names, and a merge is safe once the mapping is applied;
* **no consistent mapping** — X goes sometimes to X and sometimes to Y. The label
  then does not determine the other run's label, and a merge across the two
  cannot be rescued by a rename.

The comparison is made on claims whose `raw_span` is byte-identical, and that is a
condition rather than a detail (§4.19): claims only one run produced are excluded,
so this measures the agreement where both runs looked at the same characters and
says nothing about where they looked differently.

Finally, the script reports the prompt hash of each packet, because what the
numbers mean depends on it: equal hashes make the comparison a sampling baseline —
how much the label moves under no change at all — and different hashes fold the
prompt effect into the sampling one. The two are not separable from a single pair,
and a reader has to see which they are looking at.

A second mode supplies the baseline the first one needs. `--repeats DIR` groups
dossiers named `<case>-<repeat>.json`, **refuses any case whose repeats do not
share a prompt hash**, and aggregates the pairwise comparisons. Without that
figure, an agreement rate between two prompts says nothing: it has to be read
against how much the label moves when nothing changes at all, which is §4.2's
lesson one layer down.

Usage:
    type_construct.py PACKET PACKET [PACKET ...]
    type_construct.py --repeats DIR
    type_construct.py ... --json OUT
"""

from __future__ import annotations

import argparse
import collections
import itertools
import json
from pathlib import Path


def typed_spans(packet: dict) -> dict[str, str]:
    """The claim type each byte-identical span was given, for spans given once.

    A span one run proposed twice has no single type, and picking either would
    invent agreement or disagreement that is not in the data, so it is dropped
    and counted.
    """
    seen: dict[str, list[str]] = collections.defaultdict(list)
    for claim in packet.get("claims", []):
        seen[claim["raw_span"]].append(str(claim["claim_type"]))
    return {span: types[0] for span, types in seen.items() if len(types) == 1}


def repeated_spans(packet: dict) -> int:
    counts = collections.Counter(claim["raw_span"] for claim in packet.get("claims", []))
    return sum(1 for count in counts.values() if count > 1)


def mapping_of(left: dict[str, str], right: dict[str, str]) -> dict[str, list[str]]:
    """For each type on the left, every type the right gave the same spans."""
    targets: dict[str, set[str]] = collections.defaultdict(set)
    for span in set(left) & set(right):
        targets[left[span]].add(right[span])
    return {source: sorted(values) for source, values in sorted(targets.items())}


def compare(left: dict, right: dict) -> dict:
    left_types, right_types = typed_spans(left), typed_spans(right)
    shared = sorted(set(left_types) & set(right_types))
    pairs = [(left_types[span], right_types[span]) for span in shared]
    agreed = sum(1 for a, b in pairs if a == b)
    forward = mapping_of(left_types, right_types)
    backward = mapping_of(right_types, left_types)
    # A renaming is a mapping that is a function in both directions: each type on
    # one side goes to exactly one on the other. One-directional is not enough —
    # two types collapsing into one is a loss, not a rename.
    ambiguous = {s: t for s, t in forward.items() if len(t) > 1}
    renaming = not ambiguous and all(len(t) == 1 for t in backward.values())
    return {
        "shared_spans": len(shared),
        "agreed": agreed,
        "disagreed": len(shared) - agreed,
        "forward": forward,
        "backward": backward,
        "ambiguous_sources": sorted(ambiguous),
        "is_consistent_renaming": renaming and agreed < len(shared),
        # Both require something to have been compared. With no span in common,
        # `agreed == len(shared)` holds at zero and would report two runs that
        # overlap nowhere as agreeing everywhere.
        "identical": bool(shared) and agreed == len(shared),
        "disagreements": collections.Counter(f"{a} -> {b}" for a, b in pairs if a != b),
        "prompt_hash_left": str(left.get("provenance", {}).get("prompt_hash", ""))[:16],
        "prompt_hash_right": str(right.get("provenance", {}).get("prompt_hash", ""))[:16],
    }


def kind_of(result: dict) -> str:
    """What a comparison of these two packets can and cannot separate."""
    if not result["prompt_hash_left"] or not result["prompt_hash_right"]:
        return "unbekannt: mindestens ein Paket zeichnet keinen Prompt-Hash auf"
    if result["prompt_hash_left"] == result["prompt_hash_right"]:
        return "Sampling allein: gleicher Prompt-Hash, also Streuung ohne Änderung"
    return "Prompt und Sampling gemeinsam: verschiedene Prompt-Hashes, nicht trennbar"


def report(name: str, result: dict) -> None:
    shared = result["shared_spans"]
    print(f"{name}")
    print(f"  {kind_of(result)}")
    print(f"  Prompt-Hashes: {result['prompt_hash_left']} / {result['prompt_hash_right']}")
    if not shared:
        print("  Keine byte-identische Spanne gemeinsam. Nichts vergleichbar.")
        return
    print(f"  gemeinsame Spannen: {shared}   gleich getypt: {result['agreed']} "
          f"({result['agreed'] / shared:.0%})")
    if result["identical"]:
        print("  → Jede gemeinsame Spanne trägt denselben Typ.")
        return
    for change, count in result["disagreements"].most_common():
        print(f"    {count:>3}  {change}")
    if result["is_consistent_renaming"]:
        print("  → **Konsistente Umbenennung.** Jeder Typ der einen Seite geht auf")
        print("    genau einen der anderen, in beiden Richtungen. Ein Merge ist")
        print("    möglich, sobald die Abbildung angewandt wird.")
    else:
        print("  → **Keine konsistente Abbildung.** Diese Typen gehen auf mehrere:")
        for source in result["ambiguous_sources"]:
            print(f"      {source} -> {', '.join(result['forward'][source])}")
        print("    Der Typ der einen Seite bestimmt den der anderen nicht, ein")
        print("    Rename rettet den Merge also nicht.")


def _claims_of(stored: dict) -> dict:
    """A packet or a governed dossier, reduced to what this script reads."""
    return stored.get("semantic", stored)


def repeat_groups(directory: Path) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = collections.defaultdict(list)
    for path in sorted(directory.glob("*.json")):
        case, _, repeat = path.stem.rpartition("-")
        if not repeat.isdigit() or not case:
            continue
        stored = _claims_of(json.loads(path.read_text(encoding="utf-8")))
        if "claims" in stored:
            groups[case].append(stored)
    return {case: runs for case, runs in groups.items() if len(runs) > 1}


def baseline(directory: Path) -> dict:
    """Type agreement across repeats of one prompt, aggregated over cases.

    A case whose repeats do not share a prompt hash is refused rather than
    averaged in: pooling them would report a configuration difference as
    sampling spread, which is the mistake the extraction's prompt hash was
    recorded to prevent.
    """
    shared = agreed = 0
    changes: collections.Counter[str] = collections.Counter()
    refused, compared = [], []
    for case, runs in sorted(repeat_groups(directory).items()):
        hashes = {str(run.get("provenance", {}).get("prompt_hash", "")) for run in runs}
        if len(hashes) != 1 or "" in hashes:
            refused.append(case)
            continue
        compared.append(case)
        for left, right in itertools.combinations(runs, 2):
            result = compare(left, right)
            shared += result["shared_spans"]
            agreed += result["agreed"]
            changes.update(result["disagreements"])
    return {
        "cases_compared": compared,
        "cases_refused": refused,
        "shared_spans": shared,
        "agreed": agreed,
        "disagreements": changes,
    }


def report_baseline(result: dict) -> None:
    shared = result["shared_spans"]
    print(f"Grundlinie: gleicher Prompt, Wiederholungen, {len(result['cases_compared'])} Fälle")
    if result["cases_refused"]:
        print(f"  abgelehnt, weil Prompt-Hashes abweichen: {result['cases_refused']}")
    if not shared:
        print("  Keine gemeinsame Spanne. Nichts vergleichbar.")
        return
    print(f"  Paarvergleiche über gemeinsame Spannen: {shared}, "
          f"gleich getypt {result['agreed']} ({result['agreed'] / shared:.0%})")
    for change, count in result["disagreements"].most_common(8):
        print(f"    {count:>3}  {change}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packets", type=Path, nargs="*")
    parser.add_argument("--repeats", type=Path, default=None)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    if args.repeats:
        result = baseline(args.repeats)
        report_baseline(result)
        if args.json:
            payload = dict(result)
            payload["disagreements"] = dict(result["disagreements"])
            args.json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            print(f"\n{args.json} geschrieben")
        return 0 if result["shared_spans"] else 1

    if len(args.packets) < 2:
        print("mindestens zwei Pakete nötig, oder --repeats DIR", flush=True)
        return 2

    loaded = {
        path.stem: _claims_of(json.loads(path.read_text(encoding="utf-8")))
        for path in args.packets
    }
    for name, packet in loaded.items():
        dropped = repeated_spans(packet)
        if dropped:
            print(f"{name}: {dropped} Spanne(n) mehrfach vorgeschlagen, ausgelassen")

    results = {}
    for (left_name, left), (right_name, right) in itertools.combinations(loaded.items(), 2):
        key = f"{left_name} gegen {right_name}"
        results[key] = compare(left, right)
        print()
        report(key, results[key])

    if args.json:
        payload = {
            key: {k: (dict(v) if isinstance(v, collections.Counter) else v)
                  for k, v in result.items()}
            for key, result in results.items()
        }
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(f"\n{args.json} geschrieben")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
