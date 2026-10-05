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


def _wrapped_source() -> tuple[str, dict]:
    """A hard-wrapped document and a packet quoting across its line break."""
    document = "The budget rises by four per cent.\nThe schools receive the larger share."
    packet = {
        "schema_version": "content-review.semantic-packet/0.2",
        "document_id": "d",
        "provenance": {
            "provider": "deepseek",
            "model_id": "m",
            "run_id": "r",
            "prompt_hash": "a" * 64,
            "output_hash": "b" * 64,
            "temperature": 0.0,
        },
        "claims": [
            {
                "proposal_id": "C01",
                "claim_type": "fact",
                "canonical_content": "The budget rises and the schools get more.",
                # The document has a newline where this has a space.
                "raw_span": "four per cent. The schools receive",
                "confidence": 0.9,
                "source_ref": "d",
            }
        ],
        "relations": [],
    }
    return document, packet


def test_a_span_that_differs_only_in_a_line_break_is_admitted_quoting_the_document() -> None:
    """Fourteen of eighteen repair proposals died on this, and 42 of 465 on a paper."""
    document, packet = _wrapped_source()

    dossier = govern_packet(document, SemanticPacket.from_dict(packet))

    assert dossier.rejections == ()
    claim = dossier.claims[0]
    assert claim.raw_span == "four per cent.\nThe schools receive", "the document's characters"
    assert claim.proposed_span == "four per cent. The schools receive", "what the model sent"
    assert claim.anchor_normalised is True
    assert document[claim.anchor_start : claim.anchor_end] == claim.raw_span


def test_a_normalised_anchor_does_not_raise_the_state() -> None:
    """Typesetting is not something a human has to adjudicate."""
    document, packet = _wrapped_source()

    dossier = govern_packet(document, SemanticPacket.from_dict(packet))

    assert dossier.claims[0].semantic_state == "proposed"


def test_an_exactly_quoted_claim_records_no_substitution(
    controlled_semantic,
) -> None:
    assert all(not claim.anchor_normalised for claim in controlled_semantic.claims)
    assert all(claim.proposed_span is None for claim in controlled_semantic.claims)


def test_the_identity_ignores_the_models_wording(controlled_source, controlled_packet) -> None:
    """Re-keying four finished runs this way raised the stable core from 36 to 75."""
    data = controlled_packet.to_dict()
    reworded = {
        **data["claims"][0],
        "proposal_id": "CRE",
        "canonical_content": data["claims"][0]["canonical_content"] + " Put another way.",
    }
    data["claims"].append(reworded)

    dossier = govern_packet(controlled_source.text, SemanticPacket.from_dict(data))

    assert len(dossier.claims) == len(controlled_packet.claims), "one node, not two"
    assert "duplicate_claim_node" in {item.reason for item in dossier.rejections}


def test_the_identity_ignores_whitespace_in_the_quote() -> None:
    """The wrapped and the flowing quote of one passage are the same node."""
    document, packet = _wrapped_source()
    exact = {
        **packet,
        "claims": [{**packet["claims"][0], "raw_span": "four per cent.\nThe schools receive"}],
    }

    folded_run = govern_packet(document, SemanticPacket.from_dict(packet))
    exact_run = govern_packet(document, SemanticPacket.from_dict(exact))

    assert folded_run.claims[0].claim_node_id == exact_run.claims[0].claim_node_id


def test_the_identity_still_separates_two_claim_types_on_one_passage(
    controlled_source, controlled_packet
) -> None:
    data = controlled_packet.to_dict()
    retyped = dict(data["claims"][0], proposal_id="CTY")
    retyped["claim_type"] = "inference" if retyped["claim_type"] != "inference" else "fact"
    data["claims"].append(retyped)

    dossier = govern_packet(controlled_source.text, SemanticPacket.from_dict(data))

    assert len(dossier.claims) == len(controlled_packet.claims) + 1


def test_one_sentence_typeset_twice_is_one_node() -> None:
    """Folding in the identity is what makes it independent of the typesetting.

    Keyed on the document's slice alone, two spellings of one sentence would be
    two nodes; the repeated occurrence is already flagged by anchor_ambiguous,
    and treating it as two claims would double the graph on any source that
    repeats a formula.
    """
    document = "The budget\nrises today. Elsewhere: The budget  rises today. End."
    packet = {
        "schema_version": "content-review.semantic-packet/0.2",
        "document_id": "d",
        "provenance": {
            "provider": "deepseek",
            "model_id": "m",
            "run_id": "r",
            "prompt_hash": "a" * 64,
            "output_hash": "b" * 64,
            "temperature": 0.0,
        },
        "claims": [
            {
                "proposal_id": "C01",
                "claim_type": "fact",
                "canonical_content": "The budget rises today.",
                "raw_span": "The budget\nrises today.",
                "confidence": 0.9,
                "source_ref": "d",
            },
            {
                "proposal_id": "C02",
                "claim_type": "fact",
                "canonical_content": "The budget rises today, said elsewhere.",
                "raw_span": "The budget  rises today.",
                "confidence": 0.9,
                "source_ref": "d",
            },
        ],
        "relations": [],
    }

    dossier = govern_packet(document, SemanticPacket.from_dict(packet))

    assert [claim.raw_span for claim in dossier.claims] == ["The budget\nrises today."]
    assert "duplicate_claim_node" in {item.reason for item in dossier.rejections}
