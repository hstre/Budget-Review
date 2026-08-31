"""The repair pass's plumbing, checked where it could silently cheat.

Two ways this experiment could look successful without being it: by taking its
passages from the gold answer instead of the product's coverage measurement, or
by losing the first pass's claims in the merge so the second one only appears to
add. The first is a property of the caller and visible in the source; the second
is pinned here, together with the prompt actually carrying the passages and the
claims it must not repeat.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = "Alpha carries one claim. Beta is a gap nobody reached. Gamma ends it."


def _module():
    spec = importlib.util.spec_from_file_location(
        "repair_extract", ROOT / "scripts" / "repair_extract.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


repair = _module()


def _packet(claims: list[dict]) -> dict:
    return {
        "schema_version": "content-review.semantic-packet/0.2",
        "document_id": "d",
        "provenance": {
            "provider": "deepseek",
            "model_id": "m",
            "run_id": "r" * 16,
            "prompt_hash": "a" * 64,
            "output_hash": "b" * 64,
            "temperature": 0.0,
        },
        "claims": claims,
        "relations": [],
    }


def _claim(identifier: str, span: str) -> dict:
    return {
        "proposal_id": identifier,
        "claim_type": "fact",
        "canonical_content": span,
        "raw_span": span,
        "confidence": 0.9,
        "source_ref": "d",
    }


def test_the_prompt_carries_the_passages_and_the_claims_not_to_repeat() -> None:
    gap = DOCUMENT.index("Beta")
    system, user = repair.repair_prompt(
        "d", DOCUMENT, ["Alpha carries one claim."], [(gap, gap + 29)]
    )

    # The whole document is in the message anyway, so the passage has to be
    # checked where the pass is told to look: in the numbered list.
    assert "[1] Beta is a gap nobody reached." in user
    assert "- Alpha carries one claim." in user
    assert "repair pass" in system
    assert "Allowed claim_type values" in system, "the production contract must still apply"


def test_the_merge_keeps_the_first_pass_claims() -> None:
    """A merge that drops them would make any second pass look like a gain."""
    base = _packet([_claim("C01", "Alpha carries one claim.")])

    merged = repair.merge(base, [_claim("Q01", "Beta is a gap nobody reached.")], ["p"], ["o"])

    assert [claim["proposal_id"] for claim in merged["claims"]] == ["C01", "Q01"]


def test_the_merge_gives_the_run_its_own_provenance() -> None:
    base = _packet([_claim("C01", "Alpha carries one claim.")])

    merged = repair.merge(base, [], ["p1", "p2"], ["o1", "o2"])

    assert merged["provenance"]["prompt_hash"] != base["provenance"]["prompt_hash"]
    assert merged["provenance"]["output_hash"] != base["provenance"]["output_hash"]
    assert merged["provenance"]["model_id"] == "m"


def test_the_merge_does_not_invent_relations() -> None:
    base = _packet([_claim("C01", "Alpha carries one claim.")])

    assert repair.merge(base, [_claim("Q01", "Gamma ends it.")], ["p"], ["o"])["relations"] == []


def test_scoring_runs_the_merged_packet_through_the_real_gate() -> None:
    gold = [("G01", (0, 24), "Alpha carries one claim.")]
    packet = _packet([_claim("C01", "Alpha carries one claim.")])

    found, claims, shares = repair.scored(packet, DOCUMENT, gold)

    assert (found, claims) == (1, 1)
    assert shares["G01"] == 1.0


def test_a_span_the_gaps_do_not_name_is_reported_as_not_asked_about() -> None:
    """A pass driven by coverage gaps cannot repair what they never named."""
    gold = [("G01", (0, 100), "x"), ("G02", (200, 300), "y")]

    shares = repair.gap_share(gold, [(0, 100)])

    assert shares == {"G01": 1.0, "G02": 0.0}


def test_partial_coverage_is_reported_as_a_fraction_not_as_asked() -> None:
    gold = [("G01", (0, 100), "x")]

    assert repair.gap_share(gold, [(0, 20), (90, 100)]) == {"G01": 0.3}
