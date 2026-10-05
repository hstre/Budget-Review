"""Sorting the labels the extractor reached for, pinned where the cases blur.

The four cases call for different answers — a prompt fix, a family-first ask, a
vocabulary extension, or nothing — so a classifier that collapses two of them
would argue for extending the vocabulary on the strength of a field confusion.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "relation_reach", ROOT / "scripts" / "relation_reach.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reach = _module()
CLAIM_TYPES = reach.our_claim_types()


def test_one_of_our_own_claim_types_is_a_field_confusion_not_a_missing_relation() -> None:
    """LIMITATION and CAUSAL are claim types of ours; the model crossed fields."""
    assert reach.classify("LIMITATION", CLAIM_TYPES)[0] == "claim_type_leak"
    assert reach.classify("CAUSAL", CLAIM_TYPES)[0] == "claim_type_leak"


def test_a_label_from_a_family_we_cover_is_the_wrong_word_not_a_gap() -> None:
    case, family = reach.classify("DEFINES", CLAIM_TYPES)

    assert (case, family) == ("family_member_exists", "ONTIC")


def test_a_label_from_a_family_we_have_no_member_of_is_a_gap() -> None:
    assert reach.classify("DIFFERENTIATES", CLAIM_TYPES) == (
        "family_member_missing",
        "STATISTICAL",
    )
    assert reach.classify("REQUIRES", CLAIM_TYPES) == ("family_member_missing", "NORMATIVE")


def test_a_label_in_no_family_is_not_quietly_assigned_one() -> None:
    assert reach.classify("FROBNICATES", CLAIM_TYPES) == ("unmapped", "-")


def test_our_vocabulary_covers_four_of_the_six_families() -> None:
    """The gap this measurement was built to find, stated as an invariant."""
    assert set(reach.PAPER_FAMILIES) - reach.COVERED_FAMILIES == {"STATISTICAL", "NORMATIVE"}


def test_labels_are_read_from_a_packets_rejection_reasons(tmp_path) -> None:
    packet = tmp_path / "packet.json"
    packet.write_text(
        json.dumps(
            {
                "relation_rejections": [
                    {"reason": "closed_schema_rejection: unknown relation_type: CAUSAL"}
                ],
                "claim_rejections": [
                    {"reason": "closed_schema_rejection: unknown claim_type: claim"}
                ],
            }
        ),
        encoding="utf-8",
    )

    relations, claims = reach.labels_in(packet)

    assert relations == {"CAUSAL": 1}
    assert claims == {"claim": 1}


def test_the_discarded_attempt_in_a_log_is_counted_too(tmp_path) -> None:
    """A packet records only what survived; the retry it cost is in the log."""
    log = tmp_path / "extraction.log"
    log.write_text(
        "  Schema-Ablehnung in Versuch 1: unknown relation_type: DEFINES\n"
        "  Schema-Ablehnung in Versuch 2: unknown relation_type: CAUSES\n"
        "111 Claims, 29 Relationen -> packet.json\n",
        encoding="utf-8",
    )

    relations, _ = reach.labels_in(log)

    assert relations == {"DEFINES": 1, "CAUSES": 1}


def test_a_json_file_is_not_scanned_as_raw_text(tmp_path) -> None:
    """Otherwise an admitted relation's rationale could be read as a rejection."""
    packet = tmp_path / "packet.json"
    packet.write_text(
        json.dumps(
            {
                "relations": [{"rationale": "not an unknown relation_type: SMUGGLED, just prose"}],
                "relation_rejections": [],
            }
        ),
        encoding="utf-8",
    )

    relations, _ = reach.labels_in(packet)

    assert relations == {}
