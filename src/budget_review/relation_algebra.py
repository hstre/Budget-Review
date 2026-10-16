"""What swapping a relation's two endpoints is allowed to produce.

The relation vocabulary is fourteen closed labels and the extraction contract
glosses the direction of seven of them. Nothing anywhere says which labels are
*symmetric* — true of a pair in either order — and nothing names any label's
inverse. Without that, a structural consistency check on relations is not
expressible: there is no statement that swapping the endpoints could violate.

arXiv 2610.14442 supplies the check. A relation is determined twice, for (A,B)
and for (B,A); a symmetric relation must come back as itself, an asymmetric one
as its defined inverse, and anything else is a structural failure rather than a
confidence problem. Its own caveat applies here with force — it tested three
lexical families from a word net, so that the construction carries to `SUPPORTS`
or `CONTRADICTS` is an assumption — but the construction is what transfers, not
the result.

Applying it needs this table, and writing the table is where the vocabulary's
shape becomes visible: **of the fourteen labels, two are symmetric, one pair are
each other's inverse, and the remaining ten have no inverse in the vocabulary at
all.** For those ten the invariant has only its negative half: the same label
with the endpoints swapped is wrong, and the contract's own instruction — omit
rather than invent a label — is the correct behaviour. A tenth of the vocabulary
being expressible in both directions is a finding about the vocabulary, not a gap
in this module.
"""

from __future__ import annotations

from enum import Enum


class Reversal(Enum):
    """What the vocabulary permits when a relation's endpoints are swapped."""

    SYMMETRIC = "symmetric"
    """The same label is required of the swapped pair."""

    INVERTIBLE = "invertible"
    """A different label in the vocabulary is required of the swapped pair."""

    ONE_WAY = "one_way"
    """No label in the vocabulary expresses the swapped pair; omission is correct."""


# The one judgement in this file, and it is a reading of the contract's own
# direction glosses rather than a new decision. `DEPENDS_ON` and `ASSUMPTION_FOR`
# are each other's inverse: a claim that depends on another is one the other is an
# assumption for. That pair was found in the stored runs before it was written
# down here — two relations emitted in both directions, each carrying the other's
# label.
INVERSES: dict[str, str] = {
    "DEPENDS_ON": "ASSUMPTION_FOR",
    "ASSUMPTION_FOR": "DEPENDS_ON",
}

SYMMETRIC: frozenset[str] = frozenset({"CONTRADICTS", "SCOPE_TENSION"})

ONE_WAY: frozenset[str] = frozenset(
    {
        "SUPPORTS",
        "CONSTRAINS",
        "QUANTIFIES",
        "BASELINE_FOR",
        "PART_OF",
        "EVIDENCED_BY",
        "QUALIFIES",
        "GENERALIZES",
        "EXAMPLE_OF",
        "ENTAILS",
    }
)


def reversal_of(relation_type: str) -> Reversal:
    """How the vocabulary treats this label under a swap of the endpoints."""
    if relation_type in SYMMETRIC:
        return Reversal.SYMMETRIC
    if relation_type in INVERSES:
        return Reversal.INVERTIBLE
    if relation_type in ONE_WAY:
        return Reversal.ONE_WAY
    raise KeyError(f"relation type not classified: {relation_type}")


def permitted_reverse(relation_type: str) -> str | None:
    """The only label the swapped pair may carry, or None when it may carry none."""
    kind = reversal_of(relation_type)
    if kind is Reversal.SYMMETRIC:
        return relation_type
    if kind is Reversal.INVERTIBLE:
        return INVERSES[relation_type]
    return None


def inconsistent_pairs(relations: list[tuple[str, str, str]]) -> list[tuple[str, str, str, str]]:
    """Relations whose two directions cannot both be right.

    Takes (source, target, relation_type) triples and returns, for each ordered
    pair emitted in both directions, the ones whose reverse label is not the one
    the vocabulary permits. A relation emitted in one direction only is silent
    here: nothing about it is inconsistent, which is also why this check is
    nearly idle on observed data — across 1,041 stored relations both directions
    were emitted four times.
    """
    by_pair = {(source, target): kind for source, target, kind in relations}
    found: list[tuple[str, str, str, str]] = []
    for (source, target), kind in sorted(by_pair.items()):
        if source == target:
            # Its own swapped pair, so it would always compare against itself and
            # report a violation. The gate refuses a self-relation before this,
            # and inventing a structural finding for one would be worse than
            # saying nothing.
            continue
        reverse = by_pair.get((target, source))
        if reverse is None:
            continue
        if (source, target) > (target, source):
            continue  # each unordered pair is judged once
        if reverse != permitted_reverse(kind):
            found.append((source, target, kind, reverse))
    return found
