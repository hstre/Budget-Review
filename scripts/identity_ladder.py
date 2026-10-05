"""How much of the run-to-run difference is the same proposition, differently worded.

The gate's claim node id hashes the document id, the claim type, the model's
canonical_content and the quoted raw_span. Both wordings are therefore part of
the identity, and a relation id hashes both endpoints' node ids, so a reworded
claim changes every edge touching it. Working Paper 2 §10.2 specifies the
opposite — CIK = hash(subject_id, relation_id, object_id, scope), with the score
and the surface text attached as evidence rather than identity.

Whether that would buy stability is measurable on packets already paid for. This
re-keys finished runs at four rungs and reports, per rung, how many distinct
claims a run holds, how many survive in every run, and how many claims a rung
merges inside a single run — the price of a looser key.

The rungs:

    exact        (claim_type, canonical_content, raw_span) — today's identity
    span_ws      (claim_type, casefolded, whitespace-collapsed raw_span)
    span_norm    (claim_type, the same with punctuation stripped as well)
    content      (claim_type, normalised canonical_content)
    proposition  (claim_type, sorted token multiset of canonical_content)

The two span rungs are separated because punctuation can carry meaning and an
identity that ignores it is a stronger claim than one that only ignores
typesetting. Which of the two is load-bearing is a measurement, not a taste.
`proposition` keeps function words on purpose: dropping them would be a knob to
tune, and keeping them makes the rung collapse less, so an effect found under it
is not an artefact of a stopword list. What it cannot do is collapse synonyms —
a real CIK needs entity resolution, which does not exist here. This therefore
bounds the effect from one side only, and the bound is conservative on wording
and absent on vocabulary.

Usage:
    identity_ladder.py <label> <packet.json> [<packet.json> ...]
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from itertools import combinations
from pathlib import Path

PUNCTUATION = re.compile(r"[^\w\s]+", re.UNICODE)
RUNGS = ("exact", "span_ws", "span_norm", "content", "proposition")


def whitespace_folded(text: str) -> str:
    return " ".join(text.casefold().split())


def normalised(text: str) -> str:
    return " ".join(PUNCTUATION.sub(" ", text).casefold().split())


def tokens(text: str) -> tuple[str, ...]:
    return tuple(sorted(normalised(text).split()))


def key(claim: dict, rung: str) -> tuple:
    claim_type = str(claim["claim_type"])
    if rung == "exact":
        return (claim_type, claim["canonical_content"], claim["raw_span"])
    if rung == "span_ws":
        return (claim_type, whitespace_folded(claim["raw_span"]))
    if rung == "span_norm":
        return (claim_type, normalised(claim["raw_span"]))
    if rung == "content":
        return (claim_type, normalised(claim["canonical_content"]))
    if rung == "proposition":
        return (claim_type, tokens(claim["canonical_content"]))
    raise ValueError(f"unknown rung: {rung}")


def merges(claims: list[dict], rung: str) -> int:
    """Claims a rung folds together inside one run: the price of the looser key.

    Counted against the exact key, so two proposals that are already identical
    today are not charged to the rung.
    """
    exact = {key(claim, "exact") for claim in claims}
    loose = {key(claim, rung) for claim in claims}
    return len(exact) - len(loose)


def stable_core(runs: list[set]) -> int:
    if not runs:
        return 0
    core = set(runs[0])
    for keys in runs[1:]:
        core &= keys
    return len(core)


def mean_jaccard(runs: list[set]) -> float:
    pairs = list(combinations(runs, 2))
    if not pairs:
        return 0.0
    scores = []
    for left, right in pairs:
        union = left | right
        scores.append(len(left & right) / len(union) if union else 0.0)
    return sum(scores) / len(scores)


def core_keys(runs: list[dict]) -> set:
    """Keys every run holds, as keys rather than a count."""
    if not runs:
        return set()
    core = set(runs[0])
    for keyed in runs[1:]:
        core &= set(keyed)
    return core


def content_agreement(packets: list[list[dict]], rung: str) -> list[float]:
    """How much the propositions behind one shared key agree, per key.

    A span rung drops canonical_content from the identity, so it could merge two
    different assertions about the same passage across runs — which the merge
    counter cannot see, because it only looks inside one run. This looks: for
    each key in the core, the mean pairwise token overlap of the propositions the
    runs wrote under it. Low values mean the rung is over-merging.
    """
    keyed = [{key(claim, rung): claim for claim in claims} for claims in packets]
    scores = []
    for shared in core_keys(keyed):
        contents = [set(tokens(mapping[shared]["canonical_content"])) for mapping in keyed]
        pairs = [
            len(left & right) / len(left | right)
            for left, right in combinations(contents, 2)
            if left | right
        ]
        if pairs:
            scores.append(sum(pairs) / len(pairs))
    return scores


def report(label: str, packets: list[list[dict]]) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for rung in RUNGS:
        keyed = [{key(claim, rung) for claim in claims} for claims in packets]
        rows[rung] = {
            "mean_keys": sum(len(k) for k in keyed) / max(1, len(keyed)),
            "core": stable_core(keyed),
            "jaccard": mean_jaccard(keyed),
            "merges": sum(merges(claims, rung) for claims in packets),
            "claims": sum(len(claims) for claims in packets),
        }
    print(f"\n{label}: {len(packets)} Läufe, {rows['exact']['claims']} Claims insgesamt")
    print(f"{'Stufe':14}{'Keys/Lauf':>11}{'in allen':>10}{'Jaccard':>9}{'verschmolzen':>14}")
    for rung in RUNGS:
        row = rows[rung]
        print(
            f"{rung:14}{row['mean_keys']:11.1f}{row['core']:10}{row['jaccard']:9.2f}"
            f"{row['merges']:14}"
        )
    base = rows["exact"]["core"]
    for rung in RUNGS[1:]:
        grown = rows[rung]["core"]
        growth = (grown - base) / base if base else float("inf")
        share = rows[rung]["merges"] / max(1, rows[rung]["claims"])
        print(f"Kern exact → {rung}: {base} → {grown} ({growth:+.0%}), verschmolzen {share:.1%}")
    for rung in ("span_ws", "span_norm"):
        scores = content_agreement(packets, rung)
        if not scores:
            continue
        below = sum(1 for score in scores if score < 0.5)
        print(
            f"Propositionen innerhalb eines {rung}-Keys: Median "
            f"{statistics.median(scores):.2f}, Minimum {min(scores):.2f}, "
            f"unter 0,5: {below}/{len(scores)}"
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label")
    parser.add_argument("packets", nargs="+", type=Path)
    args = parser.parse_args()

    packets = []
    for path in args.packets:
        data = json.loads(path.read_text(encoding="utf-8"))
        claims = data["claims"] if "claims" in data else data["semantic"]["claims"]
        packets.append(claims)
    if len(packets) < 2:
        print("at least two runs are needed to compare", file=sys.stderr)
        return 1
    report(args.label, packets)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
