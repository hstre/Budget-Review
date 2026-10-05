"""Which relation labels the extractor reached for, and whether our vocabulary has them.

Every run on this branch that lost a proposal to `unknown relation_type: X` paid
for it: once as a dropped edge, and in the worst case as a schema repair round
or, on 001-77936, as a whole document. The labels are recorded — in a packet's
relation_rejections, and in the extraction log for the attempt that was thrown
away — so what the extractor keeps asking for can be counted rather than
guessed.

Each reached-for label is sorted into one of four cases, because they call for
different answers and lumping them together is how a vocabulary gets extended
for the wrong reason:

    claim_type_leak        the label is one of our own claim_type values, so the
                           model put a claim type in the relation field. Not a
                           missing relation: a field confusion.
    family_member_exists   the label belongs to a relation family our vocabulary
                           covers. The model had the right family and the wrong
                           word, which is what a family-first ask (Working Paper
                           2 §5.3) would catch.
    family_member_missing  the label belongs to a family our vocabulary has no
                           member of at all. Extending the vocabulary is then the
                           honest answer, not a better prompt.
    unmapped               fits no family in the paper's six.

The family assignment of the paper's vocabulary is the paper's (§5.1). The
assignment of OUR fourteen relation types to those families is a judgement call,
made here once and in the open, not a measurement.

Usage:
    relation_reach.py <path> [<path> ...]      # packets, dossiers, extraction logs
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

RELATION_PATTERN = re.compile(r"unknown relation_type:\s*([A-Za-z_][\w]*)")
CLAIM_PATTERN = re.compile(r"unknown claim_type:\s*([A-Za-z_][\w]*)")

# Working Paper 2 §5.1, verbatim.
PAPER_FAMILIES = {
    "ONTIC": ("has_property", "part_of", "located_in", "participates_in", "instance_of"),
    "DYNAMIC": (
        "affects",
        "increases",
        "decreases",
        "stabilizes",
        "causes",
        "enables",
        "inhibits",
        "triggers",
    ),
    "STATISTICAL": ("correlates_with", "covaries_with", "associates_with", "differs_from"),
    "EPISTEMIC": ("supports", "contradicts", "suggests", "refines", "extends", "qualifies"),
    "MODEL": ("predicts", "explains", "estimates", "simulates", "approximates"),
    "NORMATIVE": ("requires", "forbids", "recommends", "permits", "prioritizes"),
}

# Our own vocabulary against those families. A judgement, stated so it can be
# argued with: SCOPE_TENSION is the least comfortable of them.
OUR_FAMILY = {
    "SUPPORTS": "EPISTEMIC",
    "CONTRADICTS": "EPISTEMIC",
    "DEPENDS_ON": "DYNAMIC",
    "ASSUMPTION_FOR": "EPISTEMIC",
    "CONSTRAINS": "DYNAMIC",
    "QUANTIFIES": "MODEL",
    "BASELINE_FOR": "MODEL",
    "PART_OF": "ONTIC",
    "EVIDENCED_BY": "EPISTEMIC",
    "SCOPE_TENSION": "EPISTEMIC",
    "QUALIFIES": "EPISTEMIC",
    "GENERALIZES": "EPISTEMIC",
    "EXAMPLE_OF": "ONTIC",
    "ENTAILS": "EPISTEMIC",
}

# Reached-for labels mapped to a paper family by their lemma. Also a judgement.
LABEL_FAMILY = {
    "CAUSES": "DYNAMIC",
    "CAUSAL": "DYNAMIC",
    "CAUSED_BY": "DYNAMIC",
    "ENABLES": "DYNAMIC",
    "INHIBITS": "DYNAMIC",
    "INCREASES": "DYNAMIC",
    "DECREASES": "DYNAMIC",
    "AFFECTS": "DYNAMIC",
    "TRIGGERS": "DYNAMIC",
    "DIFFERENTIATES": "STATISTICAL",
    "DIFFERS_FROM": "STATISTICAL",
    "CORRELATES_WITH": "STATISTICAL",
    "ASSOCIATED_WITH": "STATISTICAL",
    "COMPARES": "STATISTICAL",
    "CONTRASTS": "STATISTICAL",
    "DEFINES": "ONTIC",
    "DEFINITION_OF": "ONTIC",
    "INSTANCE_OF": "ONTIC",
    "LOCATED_IN": "ONTIC",
    "HAS_PROPERTY": "ONTIC",
    "SUGGESTS": "EPISTEMIC",
    "REFINES": "EPISTEMIC",
    "EXTENDS": "EPISTEMIC",
    "ELABORATES": "EPISTEMIC",
    "EXPLAINS": "MODEL",
    "PREDICTS": "MODEL",
    "ESTIMATES": "MODEL",
    "MEASURES": "MODEL",
    "REQUIRES": "NORMATIVE",
    "FORBIDS": "NORMATIVE",
    "PROHIBITS": "NORMATIVE",
    "RECOMMENDS": "NORMATIVE",
    "PERMITS": "NORMATIVE",
    "OBLIGES": "NORMATIVE",
}

COVERED_FAMILIES = frozenset(OUR_FAMILY.values())


def our_claim_types() -> frozenset[str]:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[0].parent / "src"))
    from budget_review.models import ClaimType

    return frozenset(member.value.upper() for member in ClaimType)


def classify(label: str, claim_types: frozenset[str]) -> tuple[str, str]:
    """The case this label falls into, and the family it was read as."""
    upper = label.upper()
    if upper in claim_types:
        return ("claim_type_leak", "-")
    family = LABEL_FAMILY.get(upper)
    if family is None:
        return ("unmapped", "-")
    if family in COVERED_FAMILIES:
        return ("family_member_exists", family)
    return ("family_member_missing", family)


def labels_in(path: Path) -> tuple[Counter, Counter]:
    """Relation and claim labels this file records, with where they came from.

    A packet records only what survived into it; the extraction log also holds
    the attempt that was discarded, which is the one that cost a retry.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    relations: Counter = Counter()
    claims: Counter = Counter()
    if path.suffix == ".json":
        data = json.loads(text)
        pools = []
        for container in (data, data.get("semantic", {}) if isinstance(data, dict) else {}):
            if not isinstance(container, dict):
                continue
            for field in ("relation_rejections", "claim_rejections", "rejections"):
                pools.extend(container.get(field) or [])
        text = "\n".join(str(entry.get("reason", "")) for entry in pools)
    relations.update(RELATION_PATTERN.findall(text))
    claims.update(CLAIM_PATTERN.findall(text))
    return relations, claims


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    claim_types = our_claim_types()
    relations: Counter = Counter()
    claims: Counter = Counter()
    for path in args.paths:
        found_relations, found_claims = labels_in(path)
        relations.update(found_relations)
        claims.update(found_claims)

    print(f"{len(args.paths)} Dateien, {sum(relations.values())} Relations-Ablehnungen")
    print(f"\n{'Label':20}{'Treffer':>8}  {'Fall':22}{'Familie':14}")
    cases: Counter = Counter()
    for label, hits in relations.most_common():
        case, family = classify(label, claim_types)
        cases[case] += hits
        print(f"{label:20}{hits:8}  {case:22}{family:14}")
    print("\nnach Fall:")
    for case, hits in cases.most_common():
        print(f"  {case:22}{hits:5}")
    if claims:
        print(f"\nClaim-Typ-Ablehnungen: {dict(claims.most_common())}")

    uncovered = sorted(set(PAPER_FAMILIES) - COVERED_FAMILIES)
    print(f"\nFamilien ohne ein einziges Mitglied in unserem Vokabular: {uncovered or 'keine'}")
    for family in uncovered:
        print(f"  {family}: {', '.join(PAPER_FAMILIES[family])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
