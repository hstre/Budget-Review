from __future__ import annotations

import copy

import pytest

from budget_review.models import SchemaError, SemanticPacket


def _data(controlled_packet):
    return controlled_packet.to_dict()


def test_round_trip_packet(controlled_packet) -> None:
    assert SemanticPacket.from_dict(controlled_packet.to_dict()) == controlled_packet


@pytest.mark.parametrize("field", ["claims", "provenance", "document_id"])
def test_required_top_level_fields(controlled_packet, field: str) -> None:
    data = _data(controlled_packet)
    del data[field]
    with pytest.raises(SchemaError):
        SemanticPacket.from_dict(data)


def test_closed_top_level_schema(controlled_packet) -> None:
    data = _data(controlled_packet)
    data["verdict"] = "approved"
    with pytest.raises(SchemaError, match="unexpected fields"):
        SemanticPacket.from_dict(data)


def test_unknown_claim_type_is_rejected(controlled_packet) -> None:
    data = _data(controlled_packet)
    data["claims"][0]["claim_type"] = "sounds_plausible"
    with pytest.raises(SchemaError, match="unknown claim_type"):
        SemanticPacket.from_dict(data)


def test_unknown_relation_type_is_rejected(controlled_packet) -> None:
    data = _data(controlled_packet)
    data["relations"][0]["relation_type"] = "IMPLIES_TRUTH"
    with pytest.raises(SchemaError, match="unknown relation_type"):
        SemanticPacket.from_dict(data)


def test_confidence_range_is_closed(controlled_packet) -> None:
    data = copy.deepcopy(_data(controlled_packet))
    data["claims"][0]["confidence"] = 1.2
    with pytest.raises(SchemaError, match="between 0 and 1"):
        SemanticPacket.from_dict(data)
