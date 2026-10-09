"""Reconstructing a stored dossier, and comparing the real findings across runs."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "finding_warrant.py"


def _module():
    spec = importlib.util.spec_from_file_location("finding_warrant", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _module()

DOCUMENT = "Die Daten endeten im Juni. Die Maßnahme wirkt nicht auf die Quote."
FIRST = "Die Daten endeten im Juni."
SECOND = "Die Maßnahme wirkt nicht auf die Quote."

PROVENANCE = {
    "provider": "deepseek",
    "model_id": "deepseek-flash",
    "run_id": "run-1",
    "prompt_hash": "a" * 16,
    "output_hash": "b" * 16,
}


def _dossier(relations: list[dict]) -> dict:
    """A stored dossier in the shape `SemanticDossier.to_dict` writes."""
    claims = [
        {
            "claim_node_id": "claim_aaa",
            "proposal_id": "C01",
            "claim_type": "evidence",
            "canonical_content": FIRST,
            "raw_span": FIRST,
            "anchor_start": 0,
            "anchor_end": len(FIRST),
            "anchor_ambiguous": False,
            "confidence": 0.9,
            "source_ref": "synthetic",
            "semantic_state": "proposed",
        },
        {
            "claim_node_id": "claim_bbb",
            "proposal_id": "C02",
            "claim_type": "inference",
            "canonical_content": SECOND,
            "raw_span": SECOND,
            "anchor_start": DOCUMENT.index(SECOND),
            "anchor_end": DOCUMENT.index(SECOND) + len(SECOND),
            "anchor_ambiguous": False,
            "confidence": 0.9,
            "source_ref": "synthetic",
            "semantic_state": "proposed",
        },
    ]
    return {
        "schema_version": "content-review.semantic-dossier/0.3",
        "document_id": "synthetic",
        "document_hash": "c" * 16,
        "provenance": PROVENANCE,
        "claims": claims,
        "relations": relations,
    }


def _edge(source: str, relation_type: str, target: str) -> dict:
    return {
        "relation_id": f"{source}-{relation_type}-{target}",
        "source_claim_node_id": source,
        "relation_type": relation_type,
        "target_claim_node_id": target,
        "confidence": 0.9,
        "rationale": "structural",
        "semantic_state": "proposed",
    }


EVIDENCED = _edge("claim_bbb", "EVIDENCED_BY", "claim_aaa")
DEPENDS = _edge("claim_bbb", "DEPENDS_ON", "claim_aaa")


def test_the_packet_is_rebuilt_with_relations_back_on_proposal_ids() -> None:
    packet = MODULE.as_packet(_dossier([EVIDENCED]))

    assert [claim.proposal_id for claim in packet.claims] == ["C01", "C02"]
    assert len(packet.relations) == 1
    assert packet.relations[0].source_id == "C02"
    assert packet.relations[0].target_id == "C01"


def test_a_relation_pointing_outside_the_claim_set_is_dropped_not_crashed() -> None:
    # A rejected claim leaves its edges dangling in a stored dossier.
    packet = MODULE.as_packet(_dossier([_edge("claim_bbb", "SUPPORTS", "claim_gone")]))
    assert packet.relations == ()


def test_the_real_rule_decides_and_an_edge_label_moves_it() -> None:
    # The whole point: the only difference is what the edge is called.
    assert MODULE.fired(_dossier([EVIDENCED]), DOCUMENT)["logical_gap"] == 0
    assert MODULE.fired(_dossier([DEPENDS]), DOCUMENT)["logical_gap"] == 1


def _write(directory: Path, name: str, payload: dict) -> None:
    (directory / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")


def _cases() -> dict:
    return {"cases": [{"case_id": "syn-01-de", "document": DOCUMENT}]}


def test_repeats_are_grouped_and_a_lone_run_is_not_evidence(tmp_path) -> None:
    _write(tmp_path, "syn-01-de-1", _dossier([EVIDENCED]))
    _write(tmp_path, "syn-01-de-2", _dossier([DEPENDS]))
    _write(tmp_path, "other-1", _dossier([DEPENDS]))

    grouped = MODULE.group(tmp_path)

    assert set(grouped) == {"syn-01-de"}
    assert len(grouped["syn-01-de"]) == 2


def test_a_file_that_is_not_a_dossier_is_skipped(tmp_path) -> None:
    _write(tmp_path, "summary-1", {"claims": []})
    _write(tmp_path, "summary-2", {"claims": []})
    assert MODULE.group(tmp_path) == {}


def test_a_finding_that_appears_in_one_run_only_is_reported_per_run(tmp_path) -> None:
    _write(tmp_path, "syn-01-de-1", _dossier([EVIDENCED]))
    _write(tmp_path, "syn-01-de-2", _dossier([DEPENDS]))
    _write(tmp_path, "syn-01-de-3", _dossier([DEPENDS]))

    result = MODULE.measure(_cases(), tmp_path)

    assert result["documents"] == 1
    assert result["stable"] == 0
    assert result["unstable"][0]["case_id"] == "syn-01-de"
    assert result["unstable"][0]["moved"]["logical_gap"] == [0, 1, 1]


def test_an_identical_finding_set_counts_as_stable(tmp_path) -> None:
    _write(tmp_path, "syn-01-de-1", _dossier([DEPENDS]))
    _write(tmp_path, "syn-01-de-2", _dossier([DEPENDS]))

    result = MODULE.measure(_cases(), tmp_path)

    assert result["stable"] == 1
    assert result["unstable"] == []


def test_a_dossier_with_no_matching_case_document_is_skipped(tmp_path) -> None:
    # Re-gating needs the document; guessing one would anchor against the wrong
    # text and invent rejections.
    _write(tmp_path, "unknown-1", _dossier([DEPENDS]))
    _write(tmp_path, "unknown-2", _dossier([DEPENDS]))

    assert MODULE.measure(_cases(), tmp_path)["documents"] == 0


def test_the_rules_it_reports_on_come_from_the_product() -> None:
    assert MODULE.LABEL_KEYED == ["logical_gap", "unsupported_assumption"]


@pytest.mark.parametrize("count", [1, 2])
def test_a_repeated_category_is_counted_not_flattened(tmp_path, count) -> None:
    # Two contradictions in one run and one in the next is a difference, and a
    # set of category names would hide it.
    first = _dossier([_edge("claim_aaa", "CONTRADICTS", "claim_bbb")])
    second = _dossier(
        [_edge("claim_aaa", "CONTRADICTS", "claim_bbb")] * count
        + [_edge("claim_bbb", "CONTRADICTS", "claim_aaa")]
    )
    _write(tmp_path, "syn-01-de-1", first)
    _write(tmp_path, "syn-01-de-2", second)

    moved = MODULE.measure(_cases(), tmp_path)["unstable"][0]["moved"]

    assert moved["internal_contradiction"][0] < moved["internal_contradiction"][1]


# --- the explicit-runs mode, for a corpus that is never vendored ---


def _as_pre_gate_packet(relations: list[dict], prompt_hash: str = "d" * 64) -> dict:
    """A stored run from before the gate: relations name their ends by proposal."""
    return {
        "schema_version": "content-review.semantic-packet/0.2",
        "document_id": "synthetic",
        "provenance": dict(PROVENANCE, prompt_hash=prompt_hash),
        "claims": [
            {
                "proposal_id": "C01",
                "claim_type": "evidence",
                "canonical_content": FIRST,
                "raw_span": FIRST,
                "confidence": 0.9,
                "source_ref": "synthetic",
            },
            {
                "proposal_id": "C02",
                "claim_type": "inference",
                "canonical_content": SECOND,
                "raw_span": SECOND,
                "confidence": 0.9,
                "source_ref": "synthetic",
            },
        ],
        "relations": relations,
    }


def _proposal_edge(source: str, relation_type: str, target: str) -> dict:
    return {
        "source_id": source,
        "relation_type": relation_type,
        "target_id": target,
        "confidence": 0.9,
        "rationale": "structural",
    }


def test_a_pre_gate_packet_is_recognised_and_passed_through() -> None:
    stored = _as_pre_gate_packet([_proposal_edge("C02", "EVIDENCED_BY", "C01")])

    assert not MODULE.is_governed(stored)
    packet = MODULE.as_packet(stored)
    assert packet.relations[0].source_id == "C02"


def test_a_gated_dossier_is_recognised_as_such() -> None:
    assert MODULE.is_governed(_dossier([EVIDENCED]))


def test_an_empty_claim_list_is_not_mistaken_for_a_dossier() -> None:
    assert not MODULE.is_governed({"claims": []})


def test_explicit_runs_report_what_moved_and_what_held() -> None:
    runs = [
        _as_pre_gate_packet([_proposal_edge("C02", "EVIDENCED_BY", "C01")]),
        _as_pre_gate_packet([_proposal_edge("C02", "DEPENDS_ON", "C01")]),
        _as_pre_gate_packet([_proposal_edge("C02", "DEPENDS_ON", "C01")]),
    ]

    result = MODULE.measure_runs(DOCUMENT, runs)

    assert result["runs"] == 3
    assert result["moved"]["logical_gap"] == [0, 1, 1]
    assert "logical_gap" not in result["held"]


def test_a_category_present_and_equal_in_every_run_is_held_not_moved() -> None:
    runs = [_as_pre_gate_packet([_proposal_edge("C01", "CONTRADICTS", "C02")])] * 3

    result = MODULE.measure_runs(DOCUMENT, runs)

    assert result["held"]["internal_contradiction"] == 1
    assert result["moved"] == {}


def test_a_category_absent_from_every_run_is_neither_held_nor_moved() -> None:
    # A rule that never had a chance to fire held nothing, so it must not pad the
    # stable count. This holds because a category is only collected by appearing
    # in some run — an earlier version guarded it again inside `held`, where the
    # guard was unreachable, and a mutation of it survived.
    runs = [_as_pre_gate_packet([])] * 2

    result = MODULE.measure_runs(DOCUMENT, runs)

    assert "internal_contradiction" not in result["held"]
    assert "internal_contradiction" not in result["moved"]
    # `logical_gap` does hold at 1 here, because with no edges the inference
    # claim is unsupported in both runs. That is the rule working, not padding.
    assert result["held"] == {"logical_gap": 1}


def test_a_category_counted_in_some_runs_only_is_moved_never_held() -> None:
    # The case the unreachable guard was aimed at: nought in the first run and
    # one later. It belongs in `moved`, and `held` must not also claim it.
    runs = [
        _as_pre_gate_packet([]),
        _as_pre_gate_packet([_proposal_edge("C01", "CONTRADICTS", "C02")]),
    ]

    result = MODULE.measure_runs(DOCUMENT, runs)

    assert result["moved"]["internal_contradiction"] == [0, 1]
    assert "internal_contradiction" not in result["held"]


def test_runs_of_one_configuration_share_a_prompt_hash() -> None:
    same = [_as_pre_gate_packet([]), _as_pre_gate_packet([])]
    assert len(MODULE.prompt_hashes(same)) == 1


def test_runs_of_different_configurations_are_detectable() -> None:
    # The guard this exists for: comparing two configurations would report their
    # difference as run-to-run instability. It caught a real set of runs that the
    # research log describes as three runs of one arm.
    mixed = [_as_pre_gate_packet([]), _as_pre_gate_packet([], prompt_hash="e" * 64)]
    assert len(MODULE.prompt_hashes(mixed)) == 2
