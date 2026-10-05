"""Run the extraction twice with different prompts and merge the two packets.

Comparing which gold spans each prompt reaches showed that they trade rather
than accumulate: on the longer court decision the neutral prompt gains three
spans and loses two, so the union of the two runs reaches 39 of 49 where the
better single run reaches 37. That figure is arithmetic over two span sets. It
is not the same claim as "a merged run produces a better graph", and this
script is what turns the first into the second.

Two things the arithmetic cannot show, and this can.

The gate collapses claims by content address, which needs the claim type, the
canonical content and the raw span to match exactly. Two runs under different
prompts will agree on a span far more often than they agree on its wording, so
most of the overlap arrives as separate claims rather than as one deduplicated
node. The merged graph is therefore larger than either input and carries pairs
that say nearly the same thing — which is fine for recall, since that measures
anchored characters, and possibly not fine for the dossier a human reads.

Relations are kept only where both endpoints come from the same run. A relation
across runs would have to be invented here, and this script proposes nothing.

Usage:
    double_run_extract.py <document> <document-id> <output-packet.json> [--max-tokens N]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "variant", Path(__file__).resolve().parent / "prompt_variant_extract.py"
)
variant = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(variant)


def merge(packets: dict[str, dict], document_id: str) -> dict:
    """One packet from several, with per-run proposal ids so nothing collides."""
    claims: list[dict] = []
    relations: list[dict] = []
    for tag, packet in packets.items():
        renamed = {}
        for claim in packet["claims"]:
            new_id = f"{tag}-{claim['proposal_id']}"
            renamed[claim["proposal_id"]] = new_id
            claims.append({**claim, "proposal_id": new_id, "source_ref": document_id})
        for relation in packet.get("relations", []):
            if relation["source_id"] in renamed and relation["target_id"] in renamed:
                relations.append(
                    {
                        **relation,
                        "source_id": renamed[relation["source_id"]],
                        "target_id": renamed[relation["target_id"]],
                    }
                )

    first = next(iter(packets.values()))
    joined_prompts = "|".join(p["provenance"]["prompt_hash"] for p in packets.values())
    joined_outputs = "|".join(p["provenance"]["output_hash"] for p in packets.values())
    return {
        "schema_version": "content-review.semantic-packet/0.2",
        "document_id": document_id,
        "provenance": {
            "provider": "deepseek",
            "model_id": first["provenance"]["model_id"],
            # One pair of hashes over both calls: replay-stable, but a real
            # implementation wants the schema to carry an entry per call.
            "run_id": variant.sha256_text(joined_outputs)[:32],
            "prompt_hash": variant.sha256_text(joined_prompts),
            "output_hash": variant.sha256_text(joined_outputs),
            "temperature": 0.0,
        },
        "claims": claims,
        "relations": relations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("document_id")
    parser.add_argument("out_path", type=Path)
    parser.add_argument("--max-tokens", type=int, default=16384)
    args = parser.parse_args()

    document = args.document.read_text(encoding="utf-8")
    packets = {}
    for tag in ("P", "N"):
        if tag == "N":
            system, user = variant.variant_prompt(args.document_id, document)
        else:
            system, user = variant.extraction_prompt(args.document_id, document, "general")
        packet = variant.extract_packet(args.document_id, system, user, args.max_tokens)
        packets[tag] = packet
        label = "neutrale Prompt" if tag == "N" else "Produktionsprompt"
        print(f"  {label}: {len(packet['claims'])} Claims, {len(packet['relations'])} Relationen")

    merged = merge(packets, args.document_id)
    # The merged packet must clear the same closed schema as a single one.
    variant.SemanticPacket.from_dict(merged)
    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    args.out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")

    exact = len(merged["claims"]) - len(
        {(c["claim_type"], c["canonical_content"], c["raw_span"]) for c in merged["claims"]}
    )
    print(
        f"\nZusammengeführt: {len(merged['claims'])} Claims, "
        f"{len(merged['relations'])} Relationen -> {args.out_path}"
    )
    print(f"davon wortgleich in beiden Läufen: {exact} (nur diese fallen im Gate zusammen)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
