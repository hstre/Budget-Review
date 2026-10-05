"""What a whitespace-tolerant gate would have scored, pinned where it could flatter itself.

Two ways this measurement could look like a win without being one: amending the
baseline as well, so the tolerance is compared against itself, and admitting a
paraphrase — which would buy recall by quoting text the document does not carry.
"""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# A line break inside the sentence, which is what hard-wrapped sources do.
DOCUMENT = "The regional budget rises by four per cent.\nThe schools receive the larger share."
WRAPPED = "The regional budget rises by four per cent. The schools receive the larger share."


def _module():
    spec = importlib.util.spec_from_file_location(
        "gate_counterfactual", ROOT / "scripts" / "gate_counterfactual.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


counterfactual = _module()


def _packet(span: str) -> dict:
    return {
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
                "canonical_content": "The budget rises and the schools receive more.",
                "raw_span": span,
                "confidence": 0.9,
                "source_ref": "d",
            }
        ],
        "relations": [],
    }


def _gold() -> dict:
    return {"claims": [{"proposal_id": "G01", "raw_span": DOCUMENT}]}


def test_a_span_that_differs_only_in_a_line_break_takes_the_documents_text() -> None:
    tolerant, replaced = counterfactual.amended(_packet(WRAPPED), DOCUMENT)

    assert replaced == 1
    assert tolerant["claims"][0]["raw_span"] == DOCUMENT
    assert tolerant["claims"][0]["raw_span"] in DOCUMENT, "never the model's wording"


def test_the_baseline_packet_is_not_amended_with_it() -> None:
    """An amendment that moved both arms would compare the tolerance to itself."""
    packet = _packet(WRAPPED)
    before = copy.deepcopy(packet)

    counterfactual.amended(packet, DOCUMENT)

    assert packet == before


def test_a_paraphrase_is_left_alone() -> None:
    paraphrase = "The regional budget grows by four per cent and schools get more."
    tolerant, replaced = counterfactual.amended(_packet(paraphrase), DOCUMENT)

    assert replaced == 0
    assert tolerant["claims"][0]["raw_span"] == paraphrase


def test_the_tolerance_turns_a_refused_claim_into_a_reached_gold_span() -> None:
    """Through the real gate, not a stand-in for it."""
    gold = counterfactual.recall.gold_spans(_gold(), DOCUMENT)
    assert len(gold) == 1

    packet = _packet(WRAPPED)
    assert counterfactual.scored(packet, DOCUMENT, gold) == (0, 1, 0)

    tolerant, _ = counterfactual.amended(packet, DOCUMENT)
    assert counterfactual.scored(tolerant, DOCUMENT, gold) == (1, 0, 1)


def test_only_anchoring_failures_are_counted_as_anchoring_failures() -> None:
    """A rejection the tolerance cannot touch must not be reported as one it could.

    Two proposals quoting the same passage collapse into one content address, so
    the second is refused as a duplicate. Counting every claim rejection would
    read that as an anchor the tolerance failed to rescue.
    """
    gold = counterfactual.recall.gold_spans(_gold(), DOCUMENT)
    packet = _packet(WRAPPED)
    packet["claims"].append(dict(packet["claims"][0], proposal_id="C02"))

    assert counterfactual.scored(packet, DOCUMENT, gold) == (0, 2, 0)

    tolerant, replaced = counterfactual.amended(packet, DOCUMENT)
    assert replaced == 2
    assert counterfactual.scored(tolerant, DOCUMENT, gold) == (1, 0, 1)
