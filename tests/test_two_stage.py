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
    assert (
        two_stage.claims_only_prompt("d", DOCUMENT)[1]
        == extraction_prompt("d", DOCUMENT, "general")[1]
    )


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


def _schema_claims() -> list[dict]:
    """Stage one's claims as the closed schema wants them."""
    return [
        {
            "proposal_id": "C01",
            "claim_type": "fact",
            "canonical_content": "One proposition.",
            "raw_span": "A short document.",
            "confidence": 0.9,
            "source_ref": "d",
        },
        {
            "proposal_id": "C02",
            "claim_type": "fact",
            "canonical_content": "Another proposition.",
            "raw_span": "A short document.",
            "confidence": 0.9,
            "source_ref": "d",
        },
    ]


class _RelationOnlyProvider:
    """What stage two is asked for: edges, and the empty claim list it was told to send."""

    calls = 0
    claims_in_answer: list[dict] = []

    def complete_json(self, system, user, config, max_tokens):  # noqa: ANN001, D102
        type(self).calls += 1
        response = {
            "claims": list(type(self).claims_in_answer),
            "relations": [
                {
                    "source_id": "C01",
                    "relation_type": "SUPPORTS",
                    "target_id": "C02",
                    "confidence": 0.8,
                    "rationale": "x",
                }
            ],
        }
        return response, {"model": "deepseek-flash", "output_hash": "o" * 64}


def test_a_relation_only_answer_is_validated_against_stage_ones_claims(monkeypatch) -> None:
    """The failure that killed the first paid run of this pass, pinned.

    Stage two answers with no claims because that is what it is told to do, and
    the closed schema requires at least one. Validating that answer as a packet
    of its own therefore cannot succeed — it failed twice per document, after
    stage one had already produced its claims and been paid for.
    """
    _RelationOnlyProvider.calls = 0
    _RelationOnlyProvider.claims_in_answer = []
    monkeypatch.setattr(two_stage.variant, "DeepSeekProvider", _RelationOnlyProvider)

    packet = two_stage.variant.extract_packet("d", "system", "user", 128, claims=_schema_claims())

    assert _RelationOnlyProvider.calls == 1, "no repair round should be needed"
    assert [c["proposal_id"] for c in packet["claims"]] == ["C01", "C02"]
    assert packet["relations"][0]["relation_type"] == "SUPPORTS"


def test_without_the_claim_list_a_relation_only_answer_still_fails(monkeypatch) -> None:
    _RelationOnlyProvider.calls = 0
    _RelationOnlyProvider.claims_in_answer = []
    monkeypatch.setattr(two_stage.variant, "DeepSeekProvider", _RelationOnlyProvider)

    with pytest.raises(SystemExit) as failure:
        two_stage.variant.extract_packet("d", "system", "user", 128)

    assert "at least one claim" in str(failure.value)


def test_claims_stage_two_proposes_anyway_are_discarded(monkeypatch, capsys) -> None:
    """The ban on stage-two claims is code, not only prompt wording.

    Discarded silently it would be indistinguishable from a stage that obeyed,
    so the count is reported.
    """
    _RelationOnlyProvider.calls = 0
    _RelationOnlyProvider.claims_in_answer = [
        {
            "proposal_id": "C99",
            "claim_type": "fact",
            "canonical_content": "Smuggled.",
            "raw_span": "A short document.",
            "confidence": 0.9,
            "source_ref": "d",
        }
    ]
    monkeypatch.setattr(two_stage.variant, "DeepSeekProvider", _RelationOnlyProvider)

    packet = two_stage.variant.extract_packet("d", "system", "user", 128, claims=_schema_claims())

    assert [c["proposal_id"] for c in packet["claims"]] == ["C01", "C02"]
    assert "1 Claims trotz Verbot vorgeschlagen" in capsys.readouterr().err


class _TwoStageProvider:
    """Stage one answers claims, stage two answers edges and no claims."""

    seen: list[str] = []

    def complete_json(self, system, user, config, max_tokens):  # noqa: ANN001, D102
        stage = "two" if "The claim list is final" in system else "one"
        type(self).seen.append(stage)
        if stage == "one":
            response = {"claims": _schema_claims(), "relations": []}
        else:
            response = {
                "claims": [],
                "relations": [
                    {
                        "source_id": "C01",
                        "relation_type": "SUPPORTS",
                        "target_id": "C02",
                        "confidence": 0.8,
                        "rationale": "x",
                    },
                    {
                        "source_id": "C01",
                        "relation_type": "SUPPORTS",
                        "target_id": "C99",
                        "confidence": 0.8,
                        "rationale": "invented endpoint",
                    },
                ],
            }
        return response, {"model": "deepseek-flash", "output_hash": "o" * 64}


def test_both_stages_run_end_to_end_and_the_packet_is_written(monkeypatch, tmp_path) -> None:
    """The call site, which is where the first paid run of this pass died.

    Both halves were tested on their own and the run still failed twice per
    document, because nothing exercised main: stage two was validated without
    stage one's claims. A mutation that stops passing them has to fail here.
    """
    import json
    import sys

    _TwoStageProvider.seen = []
    monkeypatch.setattr(two_stage.variant, "DeepSeekProvider", _TwoStageProvider)
    document = tmp_path / "doc.txt"
    document.write_text(DOCUMENT, encoding="utf-8")
    out = tmp_path / "packet.json"
    monkeypatch.setattr(sys, "argv", ["two_stage_extract.py", str(document), "d", str(out)])

    assert two_stage.main() == 0
    assert _TwoStageProvider.seen == ["one", "two"]

    packet = json.loads(out.read_text(encoding="utf-8"))
    assert [c["proposal_id"] for c in packet["claims"]] == ["C01", "C02"]
    assert [(r["source_id"], r["target_id"]) for r in packet["relations"]] == [("C01", "C02")]
