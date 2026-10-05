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


def _duplicate_of(claim: dict, proposal_id: str) -> dict:
    """Same content, different proposal id: one claim node addressed twice."""
    return {**claim, "proposal_id": proposal_id}


def test_claims_with_identical_content_collapse_to_one_node(
    controlled_source, controlled_packet
) -> None:
    data = controlled_packet.to_dict()
    original = len(data["claims"])
    data["claims"].append(_duplicate_of(data["claims"][0], "CDUP"))
    dossier = govern_packet(controlled_source.text, SemanticPacket.from_dict(data))

    node_ids = [claim.claim_node_id for claim in dossier.claims]
    assert len(node_ids) == len(set(node_ids))
    assert len(dossier.claims) == original
    assert "duplicate_claim_node" in {item.reason for item in dossier.rejections}


def test_duplicate_claim_keeps_its_edge_on_the_canonical_node(
    controlled_source, controlled_packet
) -> None:
    data = controlled_packet.to_dict()
    edge = data["relations"][0]
    source_claim = next(
        claim for claim in data["claims"] if claim["proposal_id"] == edge["source_id"]
    )
    data["claims"].append(_duplicate_of(source_claim, "CDUP"))
    data["relations"].append({**edge, "source_id": "CDUP"})
    dossier = govern_packet(controlled_source.text, SemanticPacket.from_dict(data))

    relation_ids = [relation.relation_id for relation in dossier.relations]
    assert len(relation_ids) == len(set(relation_ids))
    assert len(dossier.relations) == len(controlled_packet.relations)
    assert "duplicate_relation" in {item.reason for item in dossier.rejections}
    assert "relation_endpoint_not_admitted" not in {item.reason for item in dossier.rejections}


def test_distinct_proposals_addressing_one_edge_are_deduplicated(
    controlled_source, controlled_packet
) -> None:
    """Dedup keys on resolved claim nodes, not on proposal ids."""
    data = controlled_packet.to_dict()
    edge = data["relations"][0]
    target_claim = next(
        claim for claim in data["claims"] if claim["proposal_id"] == edge["target_id"]
    )
    data["claims"].append(_duplicate_of(target_claim, "CDUP"))
    data["relations"].append({**edge, "target_id": "CDUP"})
    dossier = govern_packet(controlled_source.text, SemanticPacket.from_dict(data))

    assert len(dossier.relations) == len(controlled_packet.relations)
    assert [item.reason for item in dossier.rejections].count("duplicate_relation") == 1


def test_a_claim_dropped_before_the_gate_still_appears_in_the_audit(
    controlled_source, controlled_packet
) -> None:
    """A proposal the provider had to drop must not vanish from the record.

    That is the whole bargain of rejecting one claim instead of the packet: the
    run survives and the loss stays visible.
    """
    data = controlled_packet.to_dict()
    data["claim_rejections"] = [
        {
            "item_kind": "claim",
            "item_id": "C042",
            "reason": "closed_schema_rejection: unknown claim_type: conclusion",
        }
    ]

    dossier = govern_packet(controlled_source.text, SemanticPacket.from_dict(data))

    recorded = [item for item in dossier.rejections if item.item_id == "C042"]
    assert len(recorded) == 1
    assert "unknown claim_type: conclusion" in recorded[0].reason
