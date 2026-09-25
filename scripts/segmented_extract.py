"""Experiment: does extracting a long document in pieces restore recall?

A 10k-character document scored 16 of 24 gold spans while filling only about
40 per cent of the output budget, so the extractor was not running out of room
— it was summarising instead of decomposing. The same extractor takes all 25
gold claims out of a 1700-character document. This script tests the obvious
consequence: show it less text per call and the decomposition should come back.

It is an experiment, not the production path, and it is deliberately narrow:

  - Claims only. Relations are kept when both endpoints sit in one segment and
    dropped otherwise, so cross-segment structure is lost here. A real
    implementation needs a second pass that proposes relations over the whole
    claim list; this script measures recall, which does not depend on it.
  - Provenance is collapsed into one pair of hashes over all segment prompts
    and replies. It stays replay-stable, but a production version needs the
    schema to carry one entry per call.

Segmentation is deterministic: paragraphs are accumulated until the budget is
reached, and a paragraph is never cut. A paragraph longer than the budget is
emitted alone rather than split mid-sentence, because a claim whose span
straddles a cut cannot be anchored afterwards.

Usage:
    segmented_extract.py <document> <document-id> <output-packet.json> [budget]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from budget_review.gate import sha256_text  # noqa: E402
from budget_review.provider import DeepSeekProvider  # noqa: E402

DEFAULT_BUDGET = 2500


def blocks(text: str) -> list[str]:
    """Indivisible pieces of the document, in order and covering it exactly.

    Prose separates paragraphs by a blank line, but plenty of real documents —
    court decisions among them — put one numbered paragraph on one long line.
    Splitting on blank lines there yields a single block and no segmentation at
    all, so the separator is chosen from the document: blank lines when it has
    them, single line breaks otherwise.
    """
    separator = "\n\n" if "\n\n" in text else "\n"
    parts = text.split(separator)
    return [part + separator for part in parts[:-1]] + parts[-1:]


def segments(text: str, budget: int = DEFAULT_BUDGET) -> list[tuple[int, str]]:
    """Block-aligned pieces, each with its offset in the original text.

    A block is never cut, even when it alone exceeds the budget: a claim whose
    span straddles a cut is unanchorable afterwards, and losing it would be the
    very failure this is meant to remove.
    """
    out: list[tuple[int, str]] = []
    start = 0
    position = 0
    for block in blocks(text):
        if position > start and (position - start) + len(block) > budget:
            out.append((start, text[start:position]))
            start = position
        position += len(block)
    if position > start:
        out.append((start, text[start:position]))
    return out


def main() -> int:
    if len(sys.argv) not in (4, 5):
        print(__doc__, file=sys.stderr)
        return 2
    document = Path(sys.argv[1]).read_text(encoding="utf-8")
    document_id = sys.argv[2]
    out_path = Path(sys.argv[3])
    budget = int(sys.argv[4]) if len(sys.argv) == 5 else DEFAULT_BUDGET

    pieces = segments(document, budget)
    print(f"{len(document)} Zeichen -> {len(pieces)} Segmente (Budget {budget})")
    for offset, piece in pieces:
        print(f"  [{offset:>6}:{offset + len(piece):>6}] {len(piece):>5} Zeichen")

    provider = DeepSeekProvider()
    claims: list[dict] = []
    relations: list[dict] = []
    prompt_hashes: list[str] = []
    output_hashes: list[str] = []
    model_id = ""

    for index, (offset, piece) in enumerate(pieces, start=1):
        packet = provider.extract(f"{document_id}-s{index:02d}", piece, profile="general")
        prompt_hashes.append(packet.provenance.prompt_hash)
        output_hashes.append(packet.provenance.output_hash)
        model_id = packet.provenance.model_id

        renamed: dict[str, str] = {}
        kept = 0
        for claim in packet.claims:
            # A span the segment does not contain cannot be anchored later, and
            # would otherwise be searched for across the whole document.
            if claim.raw_span not in piece:
                continue
            new_id = f"S{index:02d}{claim.proposal_id}"
            renamed[claim.proposal_id] = new_id
            claims.append(
                {
                    "proposal_id": new_id,
                    "claim_type": claim.claim_type,
                    "canonical_content": claim.canonical_content,
                    "raw_span": claim.raw_span,
                    "confidence": claim.confidence,
                    "source_ref": document_id,
                }
            )
            kept += 1
        for relation in packet.relations:
            if relation.source_id in renamed and relation.target_id in renamed:
                relations.append(
                    {
                        "source_id": renamed[relation.source_id],
                        "relation_type": relation.relation_type,
                        "target_id": renamed[relation.target_id],
                        "confidence": relation.confidence,
                        "rationale": relation.rationale,
                    }
                )
        print(
            f"  Segment {index}: {len(packet.claims)} Claims vorgeschlagen, "
            f"{kept} mit Span im Segment, {offset=}"
        )

    merged = {
        "schema_version": "content-review.semantic-packet/0.2",
        "document_id": document_id,
        "provenance": {
            "provider": "deepseek",
            "model_id": model_id,
            "run_id": sha256_text("|".join(output_hashes))[:32],
            "prompt_hash": sha256_text("|".join(prompt_hashes)),
            "output_hash": sha256_text("|".join(output_hashes)),
            "temperature": 0.0,
        },
        "claims": claims,
        "relations": relations,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nZusammengeführt: {len(claims)} Claims, {len(relations)} Relationen -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
