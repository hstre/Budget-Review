"""The claim-type stability measurement, and the two ways it could lie."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "claim_type_stability.py"


def _module():
    spec = importlib.util.spec_from_file_location("claim_type_stability", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _module()


def _packet(types: list[str], confidence: float = 0.9) -> dict:
    return {
        "claims": [
            {"claim_type": claim_type, "confidence": confidence} for claim_type in types
        ]
    }


def _write(directory: Path, name: str, packet: dict) -> None:
    (directory / f"{name}.json").write_text(json.dumps(packet), encoding="utf-8")


def test_repeats_of_one_document_are_grouped(tmp_path) -> None:
    _write(tmp_path, "neg-01-de-1", _packet(["fact"]))
    _write(tmp_path, "neg-01-de-2", _packet(["fact"]))
    _write(tmp_path, "mod-01-en-1", _packet(["forecast"]))
    _write(tmp_path, "mod-01-en-2", _packet(["forecast"]))

    groups = MODULE.load(tmp_path)

    assert set(groups) == {"neg-01-de", "mod-01-en"}
    assert all(len(runs) == 2 for runs in groups.values())


def test_a_document_with_a_single_run_says_nothing_about_stability(tmp_path) -> None:
    _write(tmp_path, "only-1", _packet(["fact"]))
    assert MODULE.load(tmp_path) == {}


def test_a_file_that_is_not_a_packet_is_skipped(tmp_path) -> None:
    _write(tmp_path, "score-1", {"summary": "not a packet"})
    _write(tmp_path, "score-2", {"summary": "not a packet"})
    assert MODULE.load(tmp_path) == {}


def test_a_changed_type_is_reported_with_every_run(tmp_path) -> None:
    _write(tmp_path, "neg-02-de-1", _packet(["fact", "forecast"]))
    _write(tmp_path, "neg-02-de-2", _packet(["fact", "forecast"]))
    _write(tmp_path, "neg-02-de-3", _packet(["forecast", "scope"]))

    result = MODULE.measure(MODULE.load(tmp_path))

    assert result["groups"] == 1
    assert [entry["group"] for entry in result["unstable"]] == ["neg-02-de"]
    assert result["unstable"][0]["types_per_run"] == [
        ["fact", "forecast"],
        ["fact", "forecast"],
        ["forecast", "scope"],
    ]


def test_an_unchanged_type_multiset_is_not_reported_as_unstable(tmp_path) -> None:
    # Order must not count: the same types in another order is the same dossier.
    _write(tmp_path, "stable-1", _packet(["fact", "forecast"]))
    _write(tmp_path, "stable-2", _packet(["forecast", "fact"]))

    assert MODULE.measure(MODULE.load(tmp_path))["unstable"] == []


def test_a_repeated_type_is_not_collapsed(tmp_path) -> None:
    # Two facts is a different dossier from one, and the two runs here have the
    # same *set* of types — so only a multiset sees the difference. An earlier
    # version of this test used fact,fact,fact,other against fact,fact,fact,fact,
    # which a set catches too, and the mutation that collapses to a set survived.
    _write(tmp_path, "mul-1", _packet(["fact", "fact"]))
    _write(tmp_path, "mul-2", _packet(["fact"]))

    assert [e["group"] for e in MODULE.measure(MODULE.load(tmp_path))["unstable"]] == ["mul"]


@pytest.mark.parametrize(
    ("rule", "types"),
    [
        ("unsupported_assumption", ["assumption"]),
        ("logical_gap", ["recommendation"]),
    ],
)
def test_a_flipping_trigger_precondition_is_named_per_rule(tmp_path, rule, types) -> None:
    _write(tmp_path, "case-1", _packet(types))
    _write(tmp_path, "case-2", _packet(["fact"]))

    flipping = MODULE.measure(MODULE.load(tmp_path))["flipping_triggers"]

    assert flipping.get(rule) == ["case"]


def test_a_type_no_rule_keys_on_moves_no_trigger(tmp_path) -> None:
    _write(tmp_path, "case-1", _packet(["fact"]))
    _write(tmp_path, "case-2", _packet(["forecast"]))

    result = MODULE.measure(MODULE.load(tmp_path))

    assert result["unstable"]
    assert result["flipping_triggers"] == {}


def test_the_rules_it_checks_come_from_the_product_not_from_here() -> None:
    # If `checks.py` stopped keying on the label, this script must stop claiming
    # it does. Restating the rule names here is what would drift.
    assert MODULE.LABEL_KEYED == ["logical_gap", "unsupported_assumption"]
    assert MODULE.ASSUMPTION_TYPE == "assumption"
    assert MODULE.GAP_TYPES == {"thesis", "inference", "recommendation"}


def test_confidence_is_reported_for_both_populations(tmp_path) -> None:
    _write(tmp_path, "flip-1", _packet(["fact"], confidence=0.95))
    _write(tmp_path, "flip-2", _packet(["scope"], confidence=0.95))
    _write(tmp_path, "firm-1", _packet(["fact"], confidence=0.8))
    _write(tmp_path, "firm-2", _packet(["fact"], confidence=0.8))

    confidence = MODULE.measure(MODULE.load(tmp_path))["confidence"]

    assert confidence["unstable_mean"] == pytest.approx(0.95)
    assert confidence["stable_mean"] == pytest.approx(0.8)
    assert confidence["distribution"] == {0.8: 2, 0.95: 2}
    assert confidence["claims"] == 4
