"""Merging two extraction runs, checked without touching the network.

The merge is where a double run can quietly go wrong: colliding proposal ids
would make one run overwrite the other, and a relation joined across runs would
be an edge nobody proposed. Both are pinned here.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "double", ROOT / "scripts" / "double_run_extract.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


double = _module()


def _packet(claims, relations=()):
    return {
        "provenance": {
            "model_id": "deepseek-v4-flash",
            "prompt_hash": "p" * 64,
            "output_hash": "o" * 64,
        },
        "claims": [
            {
                "proposal_id": identifier,
                "claim_type": "fact",
                "canonical_content": content,
                "raw_span": content,
                "confidence": 0.9,
                "source_ref": "doc",
            }
            for identifier, content in claims
        ],
        "relations": [
            {
                "source_id": source,
                "relation_type": "SUPPORTS",
                "target_id": target,
                "confidence": 0.9,
                "rationale": "x",
            }
            for source, target in relations
        ],
    }


def test_both_runs_survive_a_shared_proposal_id() -> None:
    """Both runs number from C01, so a merge without prefixes loses one of them."""
    packets = {
        "P": _packet([("C01", "alpha")]),
        "N": _packet([("C01", "beta")]),
    }

    merged = double.merge(packets, "doc")

    assert len(merged["claims"]) == 2
    assert {claim["proposal_id"] for claim in merged["claims"]} == {"P-C01", "N-C01"}
    assert {claim["canonical_content"] for claim in merged["claims"]} == {"alpha", "beta"}


def test_a_relation_keeps_pointing_inside_its_own_run() -> None:
    packets = {
        "P": _packet([("C01", "a"), ("C02", "b")], [("C01", "C02")]),
        "N": _packet([("C01", "c"), ("C02", "d")], [("C02", "C01")]),
    }

    merged = double.merge(packets, "doc")

    pairs = {(r["source_id"], r["target_id"]) for r in merged["relations"]}
    assert pairs == {("P-C01", "P-C02"), ("N-C02", "N-C01")}


def test_no_relation_is_invented_between_the_runs() -> None:
    packets = {
        "P": _packet([("C01", "a")], [("C01", "C99")]),
        "N": _packet([("C99", "b")]),
    }

    merged = double.merge(packets, "doc")

    # C99 exists, but in the other run. Joining them would propose an edge no
    # extraction returned.
    assert merged["relations"] == []


def test_wording_that_matches_exactly_is_what_the_gate_can_collapse() -> None:
    packets = {"P": _packet([("C01", "same")]), "N": _packet([("C01", "same")])}

    merged = double.merge(packets, "doc")
    addresses = {
        (c["claim_type"], c["canonical_content"], c["raw_span"]) for c in merged["claims"]
    }

    assert len(merged["claims"]) == 2
    assert len(addresses) == 1


def test_provenance_moves_when_either_run_moves() -> None:
    base = {"P": _packet([("C01", "a")]), "N": _packet([("C01", "b")])}
    other = {"P": _packet([("C01", "a")]), "N": _packet([("C01", "b")])}
    other["N"]["provenance"] = {**other["N"]["provenance"], "output_hash": "z" * 64}

    assert (
        double.merge(base, "doc")["provenance"]["output_hash"]
        != double.merge(other, "doc")["provenance"]["output_hash"]
    )
