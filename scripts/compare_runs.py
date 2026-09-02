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

THRESHOLD = 0.8


def found_spans(dossier_path: Path, gold: list[tuple[str, tuple[int, int], str]]) -> set[str]:
    data = json.loads(dossier_path.read_text(encoding="utf-8"))
    semantic = data["semantic"] if "semantic" in data else data
    union = recall.merged(
        [(claim["anchor_start"], claim["anchor_end"]) for claim in semantic["claims"]]
    )
    return {
        proposal_id
        for proposal_id, span, _ in gold
        if recall.covered_characters(span, union) / max(1, span[1] - span[0]) >= THRESHOLD
    }


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

    runs = {}
    for argument in sys.argv[3:]:
        path = Path(argument)
        runs[path.stem] = found_spans(path, gold)

    total = len(gold)
    print(f"Gold-Spannen: {total}   Schwelle: {THRESHOLD:.0%} Span-Überlappung\n")
    for name, found in runs.items():
        print(f"  {name:34} {len(found):>3}/{total} = {len(found) / total:.0%}")
    print()

    for (left, found_left), (right, found_right) in combinations(runs.items(), 2):
        only_left = found_left - found_right
        only_right = found_right - found_left
        verdict = (
            "strikte Verbesserung"
            if not only_left and only_right
            else "strikte Verschlechterung"
            if only_left and not only_right
            else "Tausch"
            if only_left and only_right
            else "identisch"
        )
        print(f"  {left}  gegen  {right}: {verdict}")
        print(f"    nur {left}: {len(only_left)} {sorted(only_left)}")
        print(f"    nur {right}: {len(only_right)} {sorted(only_right)}")
        print(f"    Vereinigung: {len(found_left | found_right)}/{total}")
        print()

    if len(runs) > 2:
        union = set().union(*runs.values())
        print(
            f"  Vereinigung aller {len(runs)} Läufe: "
            f"{len(union)}/{total} = {len(union) / total:.0%}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
