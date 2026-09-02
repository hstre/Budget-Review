"""Ask for claims and for relations in separate calls, not in the same one.

One call currently has to atomise, type, anchor and relate at once. Two effects
of that are measured rather than assumed: the segmented run loses every relation
that crosses a segment boundary, because relations are only ever proposed inside
the call that saw both endpoints; and a court decision fills its output budget
with claim text long before it runs out of things to relate.

Splitting the two is therefore worth measuring, and the split is what this
builds. Stage one asks the production contract minus its relation half. Stage
two receives the admitted claims — id, type, proposition and quoted span — and
proposes edges between them, over the whole document rather than inside a
segment.

The prompt surgery asserts the passages it removes are present, so a production
prompt that has since changed fails the run instead of quietly testing the same
thing twice. Stage two may not invent claims: an edge naming an id that stage
one did not produce is dropped with a reason before the packet is assembled,
which is the same bargain the gate makes for unresolved endpoints.

Nothing here is the production path. It exists to be measured against it.

Usage:
    two_stage_extract.py <document> <document-id> <output-packet.json>
                         [--max-tokens N]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


variant = _load("prompt_variant_extract")

from budget_review.gate import sha256_text  # noqa: E402
from budget_review.models import SemanticPacket  # noqa: E402
from budget_review.prompts import RELATION_TYPES  # noqa: E402

RELATION_VALUES = f"Allowed relation_type values: {RELATION_TYPES}.\n"
RELATION_RULES = (
    "The relation_type field must contain one of those UPPERCASE relation values only. Never put\n"
    "a claim_type such as method, evidence or assumption into relation_type. If no allowed "
    "relation\nfits with high confidence, omit that relation instead of inventing a label.\n"
)
RELATION_DIRECTION = (
    "Relation direction is semantic: source SUPPORTS target; source claim EVIDENCED_BY target\n"
)
RELATION_TEMPLATE = """  "relations": [{
    "source_id": "C01",
    "relation_type": "DEPENDS_ON",
    "target_id": "C02",
    "confidence": 0.0,
    "rationale": "Short structural reason, not a verdict."
  }]"""
CLAIMS_ONLY_TEMPLATE = '  "relations": []'
CLAIMS_ONLY_NOTE = (
    '\nThis pass proposes claims only. Return "relations": [] — the relations are asked for\n'
    "separately, over the finished claim list, so nothing is lost by leaving them out here.\n"
)


def claims_only_prompt(document_id: str, document: str) -> tuple[str, str]:
    """The production prompt with its relation half removed and nothing else."""
    system, user = variant.extraction_prompt(document_id, document, "general")
    for passage in (RELATION_VALUES, RELATION_RULES, RELATION_DIRECTION, RELATION_TEMPLATE):
        if system.count(passage) != 1:
            raise SystemExit("production prompt no longer contains a relation passage")
    system = system.replace(RELATION_VALUES, "")
    system = system.replace(RELATION_RULES, "")
    system = system.replace(RELATION_DIRECTION, "")
    system = system.replace(RELATION_TEMPLATE, CLAIMS_ONLY_TEMPLATE)
    return system + CLAIMS_ONLY_NOTE, user


def relation_prompt(document_id: str, document: str, claims: list[dict]) -> tuple[str, str]:
    """Stage two: edges over a claim list that is already fixed."""
    system = f"""You are a non-authoritative semantic relation sensor.
Return JSON only. Never judge whether a claim is true, good, human-written or AI-written.
The claim list is final: propose no new claims and change none of the given ones.
Allowed relation_type values: {RELATION_TYPES}.
The relation_type field must contain one of those UPPERCASE relation values only. If no
allowed relation fits with high confidence, omit that relation instead of inventing a label.
Relation direction is semantic: source SUPPORTS target; source claim EVIDENCED_BY target
evidence; source broader claim GENERALIZES target narrower basis; source QUALIFIES target;
source premise ENTAILS target conclusion; source example EXAMPLE_OF target general claim;
source part PART_OF target whole.
Use only the given proposal_id values as source_id and target_id.

Return exactly this JSON object, with no extra keys:
{{
  "claims": [],
  "relations": [{{
    "source_id": "C01",
    "relation_type": "DEPENDS_ON",
    "target_id": "C02",
    "confidence": 0.0,
    "rationale": "Short structural reason, not a verdict."
  }}]
}}"""
    listed = "\n".join(
        f"{claim['proposal_id']} [{claim['claim_type']}] {claim['canonical_content']}\n"
        f"    Quoted: {' '.join(claim['raw_span'].split())[:200]}"
        for claim in claims
    )
    user = (
        f"DOCUMENT ID: {document_id}\n\nDOCUMENT:\n{document}\n\nCLAIMS ({len(claims)}):\n{listed}"
    )
    return system, user


def resolved(relations: list[dict], claims: list[dict]) -> tuple[list[dict], list[str]]:
    """Edges whose endpoints stage one actually produced, and the dropped ids.

    Stage two sees a list rather than the packet, so an id it invents would
    otherwise arrive as a relation nobody can resolve. The gate would reject it,
    but rejecting it here keeps the reason attached to the pass that caused it.
    """
    known = {claim["proposal_id"] for claim in claims}
    kept, dropped = [], []
    for relation in relations:
        if relation.get("source_id") in known and relation.get("target_id") in known:
            kept.append(relation)
        else:
            dropped.append(f"{relation.get('source_id')}->{relation.get('target_id')}")
    return kept, dropped


def assemble(claims_packet: dict, relations: list[dict], prompts: list[str], outputs: list[str]):
    """One packet from two calls, with provenance over both."""
    packet = dict(claims_packet)
    packet["relations"] = relations
    provenance = dict(claims_packet["provenance"])
    provenance["run_id"] = str(uuid.uuid4())
    provenance["prompt_hash"] = sha256_text("\n".join(prompts))
    provenance["output_hash"] = sha256_text("\n".join(outputs))
    packet["provenance"] = provenance
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("document_id")
    parser.add_argument("out_path", type=Path)
    parser.add_argument("--max-tokens", type=int, default=16384)
    args = parser.parse_args()

    document = args.document.read_text(encoding="utf-8")
    system, user = claims_only_prompt(args.document_id, document)
    first = variant.extract_packet(args.document_id, system, user, args.max_tokens)
    print(f"Stufe 1: {len(first['claims'])} Claims, 0 Relationen angefordert", flush=True)

    relation_system, relation_user = relation_prompt(args.document_id, document, first["claims"])
    second = variant.extract_packet(
        args.document_id, relation_system, relation_user, args.max_tokens
    )
    kept, dropped = resolved(second.get("relations", []), first["claims"])
    print(f"Stufe 2: {len(second.get('relations', []))} Relationen, {len(kept)} auflösbar")
    for edge in dropped[:5]:
        print(f"  verworfen (unbekannte Endpunkte): {edge}")

    packet = assemble(
        first,
        kept,
        [system, relation_system],
        [first["provenance"]["output_hash"], second["provenance"]["output_hash"]],
    )
    SemanticPacket.from_dict(packet)
    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    args.out_path.write_text(json.dumps(packet, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"{len(packet['claims'])} Claims, {len(packet['relations'])} Relationen -> {args.out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
