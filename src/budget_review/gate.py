"""Deterministic Layer-9-style admission gate for the semantic machine."""

from __future__ import annotations

import hashlib

from .models import (
    GovernedClaim,
    GovernedRelation,
    Rejection,
    SemanticDossier,
    SemanticPacket,
)

CONFIDENCE_FLOOR = 0.5


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _all_offsets(document: str, span: str) -> list[int]:
    offsets: list[int] = []
    start = 0
    while True:
        found = document.find(span, start)
        if found < 0:
            return offsets
        offsets.append(found)
        start = found + 1


def govern_packet(document: str, packet: SemanticPacket) -> SemanticDossier:
    """Admit anchored claims and then relations between admitted endpoints.

    The gate checks only structure, provenance, anchoring, confidence and graph
    integrity. It deliberately has no operation that can mark a claim true.
    """
    claims: list[GovernedClaim] = []
    relations: list[GovernedRelation] = []
    rejections: list[Rejection] = list(packet.relation_rejections)
    admitted: dict[str, GovernedClaim] = {}
    by_node: dict[str, GovernedClaim] = {}
    seen_ids: set[str] = set()

    for proposal in packet.claims:
        if proposal.proposal_id in seen_ids:
            rejections.append(Rejection("claim", proposal.proposal_id, "duplicate_proposal_id"))
            continue
        seen_ids.add(proposal.proposal_id)
        offsets = _all_offsets(document, proposal.raw_span)
        if not offsets:
            rejections.append(Rejection("claim", proposal.proposal_id, "source_span_not_found"))
            continue
        if proposal.confidence < CONFIDENCE_FLOOR:
            rejections.append(Rejection("claim", proposal.proposal_id, "confidence_below_floor"))
            continue
        node_id = (
            "claim_"
            + sha256_text(
                "\x00".join(
                    (
                        packet.document_id,
                        proposal.claim_type.value,
                        proposal.canonical_content,
                        proposal.raw_span,
                    )
                )
            )[:20]
        )
        duplicate = by_node.get(node_id)
        if duplicate is not None:
            # Same content address: one node, not two. The edge still resolves.
            rejections.append(Rejection("claim", proposal.proposal_id, "duplicate_claim_node"))
            admitted[proposal.proposal_id] = duplicate
            continue
        state = (
            "human_review_required"
            if len(offsets) > 1 or proposal.confidence < 0.75
            else "proposed"
        )
        governed = GovernedClaim(
            claim_node_id=node_id,
            proposal_id=proposal.proposal_id,
            claim_type=proposal.claim_type,
            canonical_content=proposal.canonical_content,
            raw_span=proposal.raw_span,
            anchor_start=offsets[0],
            anchor_end=offsets[0] + len(proposal.raw_span),
            anchor_ambiguous=len(offsets) > 1,
            confidence=proposal.confidence,
            source_ref=proposal.source_ref,
            semantic_state=state,
        )
        claims.append(governed)
        admitted[proposal.proposal_id] = governed
        by_node[node_id] = governed

    seen_relations: set[str] = set()
    for index, proposal in enumerate(packet.relations, start=1):
        item_id = f"R{index:03d}"
        source = admitted.get(proposal.source_id)
        target = admitted.get(proposal.target_id)
        if source is None or target is None:
            rejections.append(Rejection("relation", item_id, "relation_endpoint_not_admitted"))
            continue
        if source.claim_node_id == target.claim_node_id:
            rejections.append(Rejection("relation", item_id, "self_relation"))
            continue
        if proposal.confidence < CONFIDENCE_FLOOR:
            rejections.append(Rejection("relation", item_id, "confidence_below_floor"))
            continue
        relation_id = (
            "rel_"
            + sha256_text(
                "\x00".join(
                    (source.claim_node_id, proposal.relation_type.value, target.claim_node_id)
                )
            )[:20]
        )
        if relation_id in seen_relations:
            # Dedup on the resolved edge, not on proposal ids: two proposals may
            # address the same pair of claim nodes.
            rejections.append(Rejection("relation", item_id, "duplicate_relation"))
            continue
        seen_relations.add(relation_id)
        relations.append(
            GovernedRelation(
                relation_id=relation_id,
                source_claim_node_id=source.claim_node_id,
                relation_type=proposal.relation_type,
                target_claim_node_id=target.claim_node_id,
                confidence=proposal.confidence,
                rationale=proposal.rationale,
                semantic_state=(
                    "human_review_required" if proposal.confidence < 0.75 else "proposed"
                ),
            )
        )

    return SemanticDossier(
        schema_version="content-review.semantic-dossier/0.2",
        document_id=packet.document_id,
        document_hash=sha256_text(document),
        provenance=packet.provenance,
        claims=tuple(claims),
        relations=tuple(relations),
        rejections=tuple(rejections),
    )


__all__ = ["CONFIDENCE_FLOOR", "govern_packet", "sha256_text"]
