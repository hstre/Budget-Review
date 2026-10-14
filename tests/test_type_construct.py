"""Whether two runs mean the same thing by a type name, and what can be concluded.

The question comes from outside (arXiv 2610.12841): when two builders use one
label, is the disagreement a boundary in a different place or a different
construct? Three of that paper's four cases need a score per item and a claim type
is a bare category, so what is left is the structure of the disagreement — a
consistent renaming, or no consistent mapping at all.

These tests pin that structure, and two things about the conclusions it permits:
a collapse of two types into one is not a renaming, and a comparison between two
packets says which effect it contains only if their prompt hashes are read.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "type_construct", ROOT / "scripts" / "type_construct.py"
)
type_construct = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(type_construct)


def _packet(types: dict[str, str], prompt_hash: str = "a" * 64) -> dict:
    return {
        "provenance": {"prompt_hash": prompt_hash, "model_id": "m"},
        "claims": [
            {"proposal_id": f"C{n}", "raw_span": span, "claim_type": claim_type}
            for n, (span, claim_type) in enumerate(types.items())
        ],
    }


def test_a_span_one_run_proposed_twice_is_dropped_rather_than_guessed() -> None:
    # Two types for one span have no single answer, and picking either would
    # invent agreement or disagreement that is not in the data.
    packet = {
        "claims": [
            {"raw_span": "alpha", "claim_type": "fact"},
            {"raw_span": "alpha", "claim_type": "method"},
            {"raw_span": "beta", "claim_type": "fact"},
        ]
    }
    assert type_construct.typed_spans(packet) == {"beta": "fact"}
    assert type_construct.repeated_spans(packet) == 1


def test_only_spans_both_runs_produced_are_compared() -> None:
    left = _packet({"alpha": "fact", "beta": "method"})
    right = _packet({"beta": "method", "gamma": "scope"})

    result = type_construct.compare(left, right)

    assert result["shared_spans"] == 1
    assert result["agreed"] == 1


def test_two_runs_with_no_span_in_common_compare_nothing() -> None:
    result = type_construct.compare(_packet({"alpha": "fact"}), _packet({"beta": "fact"}))
    assert result["shared_spans"] == 0
    assert result["identical"] is False
    assert result["is_consistent_renaming"] is False


def test_identical_typing_is_reported_as_identical_not_as_a_renaming() -> None:
    left = _packet({"alpha": "fact", "beta": "method"})

    result = type_construct.compare(left, left)

    assert result["identical"] is True
    assert result["is_consistent_renaming"] is False, "nothing was renamed"
    assert result["disagreed"] == 0


def test_a_wholesale_rename_is_recognised_as_one() -> None:
    left = _packet({"alpha": "fact", "beta": "fact", "gamma": "method"})
    right = _packet({"alpha": "datum", "beta": "datum", "gamma": "procedure"})

    result = type_construct.compare(left, right)

    assert result["is_consistent_renaming"] is True
    assert result["disagreed"] == 3


def test_two_types_collapsing_into_one_is_not_a_renaming() -> None:
    """The asymmetry that matters, and the reason both directions are checked.

    `fact` and `method` both becoming `fact` is a function one way, so a
    forward-only check would call it a rename and licence a merge. It is a loss
    of a distinction: nothing recovers which of the two a claim had been.
    """
    left = _packet({"alpha": "fact", "beta": "method"})
    right = _packet({"alpha": "fact", "beta": "fact"})

    result = type_construct.compare(left, right)

    assert result["is_consistent_renaming"] is False
    assert result["forward"] == {"fact": ["fact"], "method": ["fact"]}
    assert result["backward"] == {"fact": ["fact", "method"]}


def test_one_type_going_two_ways_is_named_as_the_ambiguous_source() -> None:
    left = _packet({"alpha": "fact", "beta": "fact"})
    right = _packet({"alpha": "fact", "beta": "method"})

    result = type_construct.compare(left, right)

    assert result["is_consistent_renaming"] is False
    assert result["ambiguous_sources"] == ["fact"]


def test_the_disagreements_are_counted_by_direction() -> None:
    left = _packet({"alpha": "fact", "beta": "method", "gamma": "method"})
    right = _packet({"alpha": "method", "beta": "fact", "gamma": "fact"})

    result = type_construct.compare(left, right)

    assert dict(result["disagreements"]) == {"fact -> method": 1, "method -> fact": 2}


@pytest.mark.parametrize(
    ("left_hash", "right_hash", "expected"),
    [
        ("a" * 64, "a" * 64, "Sampling allein"),
        ("a" * 64, "b" * 64, "Prompt und Sampling"),
        ("", "a" * 64, "unbekannt"),
        ("a" * 64, "", "unbekannt"),
    ],
)
def test_the_comparison_says_which_effect_it_contains(
    left_hash: str, right_hash: str, expected: str
) -> None:
    # Two packets alone cannot separate a prompt effect from sampling, and the
    # prompt hash is the only thing that says which of the two is in front of
    # you. A comparison that did not say so would invite reading one as the other.
    result = type_construct.compare(
        _packet({"alpha": "fact"}, left_hash), _packet({"alpha": "fact"}, right_hash)
    )
    assert expected in type_construct.kind_of(result)


def _write_repeats(directory: Path, cases: dict[str, list[tuple[dict, str]]]) -> None:
    for case, runs in cases.items():
        for index, (types, prompt_hash) in enumerate(runs, start=1):
            path = directory / f"{case}-{index}.json"
            path.write_text(json.dumps(_packet(types, prompt_hash)), encoding="utf-8")


def test_the_baseline_aggregates_the_repeats_of_each_case(tmp_path: Path) -> None:
    _write_repeats(
        tmp_path,
        {
            "one": [({"alpha": "fact"}, "h1"), ({"alpha": "fact"}, "h1")],
            "two": [({"beta": "fact"}, "h2"), ({"beta": "method"}, "h2")],
        },
    )

    result = type_construct.baseline(tmp_path)

    assert result["cases_compared"] == ["one", "two"]
    assert (result["shared_spans"], result["agreed"]) == (2, 1)
    assert dict(result["disagreements"]) == {"fact -> method": 1}


def test_a_case_whose_repeats_do_not_share_a_prompt_hash_is_refused(tmp_path: Path) -> None:
    """The guard, and why it refuses rather than averages.

    Pooling repeats that were not asked the same thing reports a configuration
    difference as sampling spread — the exact mistake the extraction's prompt
    hash was recorded to prevent, and one it has already caught once.
    """
    _write_repeats(
        tmp_path,
        {
            "mixed": [({"alpha": "fact"}, "h1"), ({"alpha": "method"}, "h2")],
            "clean": [({"beta": "fact"}, "h3"), ({"beta": "fact"}, "h3")],
        },
    )

    result = type_construct.baseline(tmp_path)

    assert result["cases_refused"] == ["mixed"]
    assert result["cases_compared"] == ["clean"]
    assert result["shared_spans"] == 1


def test_a_case_with_no_recorded_prompt_hash_is_refused_too(tmp_path: Path) -> None:
    _write_repeats(tmp_path, {"bare": [({"alpha": "fact"}, ""), ({"alpha": "fact"}, "")]})

    result = type_construct.baseline(tmp_path)

    assert result["cases_refused"] == ["bare"]
    assert result["shared_spans"] == 0


def test_a_single_run_of_a_case_is_not_a_comparison(tmp_path: Path) -> None:
    _write_repeats(tmp_path, {"lonely": [({"alpha": "fact"}, "h1")]})
    assert type_construct.baseline(tmp_path)["cases_compared"] == []


def test_a_governed_dossier_is_read_as_well_as_a_packet(tmp_path: Path) -> None:
    # The stored artefacts are a mix: some runs saved the proposal packet, others
    # only the governed dossier, which nests the same fields under "semantic".
    path = tmp_path / "case-1.json"
    path.write_text(json.dumps({"semantic": _packet({"alpha": "fact"}, "h")}), encoding="utf-8")
    (tmp_path / "case-2.json").write_text(
        json.dumps({"semantic": _packet({"alpha": "fact"}, "h")}), encoding="utf-8"
    )

    assert type_construct.baseline(tmp_path)["shared_spans"] == 1
