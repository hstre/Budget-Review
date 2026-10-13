"""Deterministic Layer-9-style admission gate for the semantic machine."""

from __future__ import annotations

import hashlib

from .anchoring import anchor_spans
from .coverage import measure_coverage
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


def prompt_fingerprint(system: str, user: str) -> str:
    """One hash for the pair of prompts a call was made with.

    The extraction has recorded this since it existed, as its own expression at
    the call site. The reviewer arms recorded no prompt hash at all, so a
    comparison across reviewer runs could not be guarded the way a comparison
    across extraction runs can — and that guard has already earned itself once,
    catching two artifacts the log described as one arm's three runs while only
    two shared a hash.

    Naming the convention once is the point. Writing the same expression a second
    time in the reviewer path would let the two drift, and two hashes that mean
    slightly different things are worse than one missing hash: they compare as
    unequal and the comparison then reports a difference that is not there.
    """
    return sha256_text(system + "\n" + user)


def govern_packet(document: str, packet: SemanticPacket) -> SemanticDossier:
    """Admit anchored claims and then relations between admitted endpoints.

    The gate checks only structure, provenance, anchoring, confidence and graph
    integrity. It deliberately has no operation that can mark a claim true.
    """
    claims: list[GovernedClaim] = []
    relations: list[GovernedRelation] = []
    # Rejections the provider already recorded travel with the packet, so a
    # proposal dropped before the gate is still visible in the audit.
    rejections: list[Rejection] = [
        *packet.claim_rejections,
        *packet.relation_rejections,
    ]
    admitted: dict[str, GovernedClaim] = {}
    by_node: dict[str, GovernedClaim] = {}
    seen_ids: set[str] = set()

    for proposal in packet.claims:
        if proposal.proposal_id in seen_ids:
            rejections.append(Rejection("claim", proposal.proposal_id, "duplicate_proposal_id"))
            continue
        seen_ids.add(proposal.proposal_id)
        spans, normalised = anchor_spans(document, proposal.raw_span)
        if not spans:
            rejections.append(Rejection("claim", proposal.proposal_id, "source_span_not_found"))
            continue
        start, end = spans[0]
        # The document's characters, not the model's. A claim's quote has to be
        # something a reader can check against the source.
        quoted = document[start:end]
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
                        # The document's passage rather than the model's
                        # transcription of it, so a quote that differs only in
                        # typesetting is the same node. canonical_content stays:
                        # one passage can carry several assertions, and two
                        # readings of it are a conflict for a human, never an
                        # automatic duplicate.
                        quoted,
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
        # A normalised anchor does not raise the state. The passage is the
        # document's own, and typesetting is not something a human has to
        # adjudicate; what a reader needs is the record that it happened.
        state = (
            "human_review_required" if len(spans) > 1 or proposal.confidence < 0.75 else "proposed"
        )
        governed = GovernedClaim(
            claim_node_id=node_id,
            proposal_id=proposal.proposal_id,
            claim_type=proposal.claim_type,
            canonical_content=proposal.canonical_content,
            raw_span=quoted,
            anchor_start=start,
            anchor_end=end,
            anchor_ambiguous=len(spans) > 1,
            confidence=proposal.confidence,
            source_ref=proposal.source_ref,
            semantic_state=state,
            anchor_normalised=normalised,
            proposed_span=None if quoted == proposal.raw_span else proposal.raw_span,
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
        schema_version="content-review.semantic-dossier/0.3",
        document_id=packet.document_id,
        document_hash=sha256_text(document),
        provenance=packet.provenance,
        claims=tuple(claims),
        relations=tuple(relations),
        rejections=tuple(rejections),
        coverage=measure_coverage(document, claims),
    )


__all__ = ["CONFIDENCE_FLOOR", "govern_packet", "sha256_text"]
