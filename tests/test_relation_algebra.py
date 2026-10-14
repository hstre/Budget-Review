"""What the vocabulary permits when a relation's endpoints are swapped.

The table exists so that a structural check on relations is expressible at all:
until it was written, nothing said which labels are symmetric or what any
label's inverse is, so there was no statement a swap could violate.

The tests that matter most here are the two that tie the table to the vocabulary
it describes. A table that silently stopped covering a label would make the check
raise, and one that classified a label the contract no longer offers would look
like coverage it does not have.
"""

from __future__ import annotations

import pytest

from budget_review.prompts import RELATION_TYPES
from budget_review.relation_algebra import (
    INVERSES,
    ONE_WAY,
    SYMMETRIC,
    Reversal,
    inconsistent_pairs,
    permitted_reverse,
    reversal_of,
)

VOCABULARY = frozenset(label.strip() for label in RELATION_TYPES.replace("\n", " ").split(","))


def test_every_label_the_contract_offers_is_classified() -> None:
    classified = set(SYMMETRIC) | set(INVERSES) | set(ONE_WAY)
    assert VOCABULARY - classified == set(), "a relation type the contract offers is unclassified"


def test_the_table_classifies_nothing_the_contract_does_not_offer() -> None:
    # A label here that the extraction cannot emit would be coverage on paper
    # only, and would hide that the real vocabulary had moved.
    classified = set(SYMMETRIC) | set(INVERSES) | set(ONE_WAY)
    assert classified - VOCABULARY == set()


def test_no_label_is_in_two_classes() -> None:
    assert not SYMMETRIC & set(INVERSES)
    assert not SYMMETRIC & ONE_WAY
    assert not set(INVERSES) & ONE_WAY


def test_an_unclassified_label_raises_rather_than_being_guessed() -> None:
    # Silently treating an unknown label as one-way would report a structural
    # violation as correct behaviour.
    with pytest.raises(KeyError):
        reversal_of("INVENTED_BY_THE_MODEL")


def test_the_inverse_table_is_its_own_mirror() -> None:
    """A one-sided inverse would licence a swap that cannot be swapped back."""
    for source, target in INVERSES.items():
        assert INVERSES[target] == source, (source, target)


def test_a_symmetric_relation_must_come_back_as_itself() -> None:
    assert reversal_of("CONTRADICTS") is Reversal.SYMMETRIC
    assert permitted_reverse("CONTRADICTS") == "CONTRADICTS"


def test_an_invertible_relation_must_come_back_as_its_inverse() -> None:
    assert reversal_of("DEPENDS_ON") is Reversal.INVERTIBLE
    assert permitted_reverse("DEPENDS_ON") == "ASSUMPTION_FOR"
    assert permitted_reverse("ASSUMPTION_FOR") == "DEPENDS_ON"


def test_a_one_way_relation_permits_no_reverse_at_all() -> None:
    # Ten of the fourteen labels are here, and that is the finding: for them the
    # invariant has only its negative half, and omission is the correct output.
    assert reversal_of("SUPPORTS") is Reversal.ONE_WAY
    assert permitted_reverse("SUPPORTS") is None


def test_most_of_the_vocabulary_cannot_be_expressed_in_both_directions() -> None:
    # Stated as a test so that adding an inverse pair has to come past it: the
    # claim in the module docstring is a measurement of the vocabulary.
    assert len(ONE_WAY) > len(SYMMETRIC) + len(INVERSES)


def test_a_relation_emitted_one_way_only_is_not_inconsistent() -> None:
    assert inconsistent_pairs([("a", "b", "SUPPORTS")]) == []


def test_a_symmetric_relation_in_both_directions_is_consistent() -> None:
    assert inconsistent_pairs([("a", "b", "CONTRADICTS"), ("b", "a", "CONTRADICTS")]) == []


def test_the_inverse_pair_in_both_directions_is_consistent() -> None:
    # This is the shape the stored runs actually produced, twice.
    assert inconsistent_pairs([("a", "b", "DEPENDS_ON"), ("b", "a", "ASSUMPTION_FOR")]) == []


def test_a_one_way_relation_asserted_in_both_directions_is_flagged() -> None:
    found = inconsistent_pairs([("a", "b", "SUPPORTS"), ("b", "a", "SUPPORTS")])
    assert found == [("a", "b", "SUPPORTS", "SUPPORTS")]


def test_a_symmetric_relation_answered_with_another_label_is_flagged() -> None:
    found = inconsistent_pairs([("a", "b", "CONTRADICTS"), ("b", "a", "SUPPORTS")])
    assert found == [("a", "b", "CONTRADICTS", "SUPPORTS")]


def test_an_invertible_relation_answered_with_itself_is_flagged() -> None:
    found = inconsistent_pairs([("a", "b", "DEPENDS_ON"), ("b", "a", "DEPENDS_ON")])
    assert found == [("a", "b", "DEPENDS_ON", "DEPENDS_ON")]


def test_each_unordered_pair_is_judged_once() -> None:
    """Otherwise one inconsistency is reported twice and a count doubles."""
    found = inconsistent_pairs([("a", "b", "SUPPORTS"), ("b", "a", "SUPPORTS")])
    assert len(found) == 1


def test_a_self_relation_pair_does_not_report_itself_as_a_swap() -> None:
    # The gate refuses a self-relation, so this should not arise; if it does,
    # treating (a,a) as its own swapped pair would invent a violation.
    assert inconsistent_pairs([("a", "a", "SUPPORTS")]) == []
