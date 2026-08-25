from __future__ import annotations

from budget_review.gate import govern_packet
from budget_review.models import SemanticPacket


def test_controlled_graph_is_fully_admitted(controlled_semantic) -> None:
    assert len(controlled_semantic.claims) == 25
    assert len(controlled_semantic.relations) == 15
    assert controlled_semantic.rejections == ()
    assert all(claim.anchor_end > claim.anchor_start for claim in controlled_semantic.claims)


def test_gate_replays_deterministically(controlled_source, controlled_packet) -> None:
    first = govern_packet(controlled_source.text, controlled_packet)
    second = govern_packet(controlled_source.text, controlled_packet)
    assert first == second


def test_unanchored_claim_and_relation_are_rejected(controlled_source, controlled_packet) -> None:
    data = controlled_packet.to_dict()
    data["claims"][0]["raw_span"] = "This sentence is invented."
    dossier = govern_packet(controlled_source.text, SemanticPacket.from_dict(data))
    reasons = [rejection.reason for rejection in dossier.rejections]
    assert "source_span_not_found" in reasons


def test_low_confidence_claim_is_not_admitted(controlled_source, controlled_packet) -> None:
    data = controlled_packet.to_dict()
    data["claims"][0]["confidence"] = 0.49
    dossier = govern_packet(controlled_source.text, SemanticPacket.from_dict(data))
    assert "confidence_below_floor" in {item.reason for item in dossier.rejections}


def test_duplicate_claim_id_is_rejected(controlled_source, controlled_packet) -> None:
    data = controlled_packet.to_dict()
    data["claims"].append(data["claims"][0])
    dossier = govern_packet(controlled_source.text, SemanticPacket.from_dict(data))
    assert "duplicate_proposal_id" in {item.reason for item in dossier.rejections}


def test_self_relation_is_rejected(controlled_source, controlled_packet) -> None:
    data = controlled_packet.to_dict()
    data["relations"][0]["target_id"] = data["relations"][0]["source_id"]
    dossier = govern_packet(controlled_source.text, SemanticPacket.from_dict(data))
    assert "self_relation" in {item.reason for item in dossier.rejections}


def test_gate_has_no_truth_state(controlled_semantic) -> None:
    serialized = controlled_semantic.to_dict()
    states = {claim["semantic_state"] for claim in serialized["claims"]}
    assert states <= {"proposed", "human_review_required"}
    assert all("truth" not in claim and "verdict" not in claim for claim in serialized["claims"])
