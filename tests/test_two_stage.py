"""Splitting claim and relation extraction, pinned where the split could cheat.

The experiment is only worth running if stage one really loses its relation
half — a variant that quietly kept it would answer the question wrongly and look
plausible doing so — and if stage two cannot smuggle in claims or edges between
ids nobody proposed.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from budget_review.prompts import extraction_prompt

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = "A short document."


def _module():
    spec = importlib.util.spec_from_file_location(
        "two_stage", ROOT / "scripts" / "two_stage_extract.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


two_stage = _module()


def _claims() -> list[dict]:
    return [
        {
            "proposal_id": "C01",
            "claim_type": "fact",
            "canonical_content": "One proposition.",
            "raw_span": "A short document.",
        },
        {
            "proposal_id": "C02",
            "claim_type": "fact",
            "canonical_content": "Another proposition.",
            "raw_span": "A short document.",
        },
    ]


def test_stage_one_drops_the_relation_half_of_the_contract() -> None:
    system, _ = two_stage.claims_only_prompt("d", DOCUMENT)

    assert "Allowed relation_type values" not in system
    assert "Relation direction is semantic" not in system
    # The note at the end also says "relations": [], so the template has to be
    # checked by something only the template carries.
    assert '"relation_type": "DEPENDS_ON"' not in system
    assert '"relations": []' in system
    assert "Allowed claim_type values" in system, "the claim half must be untouched"


def test_stage_one_keeps_the_user_message_byte_identical() -> None:
    assert two_stage.claims_only_prompt("d", DOCUMENT)[1] == extraction_prompt(
        "d", DOCUMENT, "general"
    )[1]


def test_a_production_prompt_without_the_relation_half_fails_the_run(monkeypatch) -> None:
    """Otherwise the experiment would compare the production prompt with itself."""
    monkeypatch.setattr(
        two_stage.variant, "extraction_prompt", lambda *args, **kwargs: ("nothing here", "user")
    )

    with pytest.raises(SystemExit):
        two_stage.claims_only_prompt("d", DOCUMENT)


def test_stage_two_is_given_every_claim_with_its_id() -> None:
    _, user = two_stage.relation_prompt("d", DOCUMENT, _claims())

    assert "C01 [fact] One proposition." in user
    assert "C02 [fact] Another proposition." in user


def test_stage_two_may_not_propose_claims() -> None:
    system, _ = two_stage.relation_prompt("d", DOCUMENT, _claims())

    assert '"claims": []' in system
    assert "propose no new claims" in system


def test_an_edge_naming_an_unknown_id_is_dropped_with_its_pair() -> None:
    relations = [
        {"source_id": "C01", "target_id": "C02"},
        {"source_id": "C01", "target_id": "C99"},
    ]

    kept, dropped = two_stage.resolved(relations, _claims())

    assert kept == [{"source_id": "C01", "target_id": "C02"}]
    assert dropped == ["C01->C99"]


def test_assembling_keeps_the_claims_and_takes_the_new_relations() -> None:
    packet = {
        "claims": _claims(),
        "relations": [],
        "provenance": {"prompt_hash": "a" * 64, "output_hash": "b" * 64, "model_id": "m"},
    }

    assembled = two_stage.assemble(packet, [{"source_id": "C01"}], ["p1", "p2"], ["o1", "o2"])

    assert assembled["claims"] == _claims()
    assert assembled["relations"] == [{"source_id": "C01"}]
    assert assembled["provenance"]["prompt_hash"] != "a" * 64
