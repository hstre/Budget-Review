"""Compare which gold spans two or more extractions reach, and what their union reaches.

A single recall number hides whether one variant is better than another or
merely different. The distinction decides what to do with it: a variant that
strictly improves replaces the old one, while a variant that trades some spans
for others is a second sensor, and two sensors that fail in different places
are worth more together than either is alone.

Both shapes occur. The domain-neutral prompt is a strict improvement on one
court decision — every span it misses, the production prompt missed too — and a
trade on another, where it gains three spans and loses two. Segmentation trades
as well. Where they trade, the union reaches more than the better of the two.

That is the Anti-Delphi argument moved one layer down, and it holds here for a
reason the coverage case lacked: the independence is measured rather than
assumed. Merging costs little, because the gate addresses claims by content, so
a claim both runs found collapses into one node and its edges survive.

**The verdict is not read off the spans alone.** Whether a run is a strict
improvement or a trade depends on which spans count as reached, and that is
decided by an overlap threshold this script used to fix at one value. On the
argument-annotated papers that choice decides nothing — every gold span is
anchored either not at all or in full. On a long court decision it decides half
of them, and a recall figure stated without it is stated incompletely
(arXiv 2610.13476). So the comparison now runs at every threshold in the sweep
and says whether the verdict survives it. A verdict that holds across the
condition space is a finding about the runs; one that does not is a finding
about the threshold.

Usage:
    compare_runs.py <gold-packet.json> <source-document> <dossier.json> <dossier.json> [...]
"""

from __future__ import annotations

import importlib.util
import json
import sys
from itertools import combinations
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "recall", Path(__file__).resolve().parent / "measure_recall.py"
)
recall = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recall)

# The condition space of this comparison, not a single setting. The two values
# the project publishes sit inside it, so a reader can place a published figure
# in the sweep rather than beside it.
SWEEP = (0.5, 0.8, 0.95)


def found_spans(
    dossier_path: Path,
    gold: list[tuple[str, tuple[int, int], str]],
    threshold: float,
) -> set[str]:
    data = json.loads(dossier_path.read_text(encoding="utf-8"))
    semantic = data["semantic"] if "semantic" in data else data
    union = recall.merged(
        [(claim["anchor_start"], claim["anchor_end"]) for claim in semantic["claims"]]
    )
    return {
        proposal_id
        for proposal_id, span, _ in gold
        if recall.covered_characters(span, union) / max(1, span[1] - span[0]) >= threshold
    }


def verdict_for(found_left: set[str], found_right: set[str]) -> str:
    only_left = found_left - found_right
    only_right = found_right - found_left
    if not only_left and only_right:
        return "strikte Verbesserung"
    if only_left and not only_right:
        return "strikte Verschlechterung"
    if only_left and only_right:
        return "Tausch"
    return "identisch"


def main() -> int:
    if len(sys.argv) < 5:
        print(__doc__, file=sys.stderr)
        return 2
    packet = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    document = Path(sys.argv[2]).read_text(encoding="utf-8")
    gold = recall.gold_spans(packet, document)
    if not gold:
        print("no gold spans located", file=sys.stderr)
        return 1

    paths = [Path(argument) for argument in sys.argv[3:]]
    per_threshold = {
        threshold: {path.stem: found_spans(path, gold, threshold) for path in paths}
        for threshold in SWEEP
    }

    total = len(gold)
    print(f"Gold-Spannen: {total}   Schwellen: "
          + ", ".join(f"{t:.0%}" for t in SWEEP) + " Span-Überlappung\n")
    names = [path.stem for path in paths]
    print(f"  {'Lauf':34} " + " ".join(f"{t:>7.0%}" for t in SWEEP))
    for name in names:
        print(f"  {name:34} "
              + " ".join(f"{len(per_threshold[t][name]):>7}" for t in SWEEP))
    print()

    for left, right in combinations(names, 2):
        verdicts = {
            threshold: verdict_for(per_threshold[threshold][left], per_threshold[threshold][right])
            for threshold in SWEEP
        }
        stable = len(set(verdicts.values())) == 1
        print(f"  {left}  gegen  {right}:")
        for threshold in SWEEP:
            found_left = per_threshold[threshold][left]
            found_right = per_threshold[threshold][right]
            only_left = found_left - found_right
            only_right = found_right - found_left
            print(f"    bei {threshold:>4.0%}: {verdicts[threshold]:<24} "
                  f"nur {left}: {len(only_left)}, nur {right}: {len(only_right)}, "
                  f"Vereinigung: {len(found_left | found_right)}/{total}")
        if stable:
            print(f"    → Urteil hält über die Schwellen: {verdicts[SWEEP[0]]}")
        else:
            print("    → **Das Urteil hängt an der Schwelle.** Es ist damit keine")
            print("      Aussage über die Läufe, sondern über die Zuordnungsregel.")
        print()

    if len(names) > 2:
        print(f"  {'Vereinigung aller Läufe':34} "
              + " ".join(
                  f"{len(set().union(*per_threshold[t].values())):>7}" for t in SWEEP
              ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
