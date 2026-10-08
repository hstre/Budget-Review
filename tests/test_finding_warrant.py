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
