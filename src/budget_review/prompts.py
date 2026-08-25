"""Prompts are sensors: narrow output contracts and no decision authority."""

from __future__ import annotations

import json

from .models import SemanticDossier

CLAIM_TYPES = (
    "scope, target, capacity, resource, baseline, forecast, delivery, assumption, "
    "budget, method, causal, evidence, limitation, definition, other"
)
RELATION_TYPES = (
    "SUPPORTS, CONTRADICTS, DEPENDS_ON, ASSUMPTION_FOR, CONSTRAINS, QUANTIFIES, "
    "BASELINE_FOR, PART_OF, EVIDENCED_BY, SCOPE_TENSION"
)


def extraction_prompt(document_id: str, document: str) -> tuple[str, str]:
    system = f"""You are a non-authoritative semantic extraction sensor.
Return JSON only. Never judge whether a claim is true or whether funding should be granted.
Decompose polished prose aggressively: an elegant sentence may contain several claims.
Each raw_span must be copied verbatim and exactly from the document.
Allowed claim_type values: {CLAIM_TYPES}.
Allowed relation_type values: {RELATION_TYPES}.

Return exactly this JSON object, with no extra keys:
{{
  "claims": [{{
    "proposal_id": "C01",
    "claim_type": "target",
    "canonical_content": "One atomic proposition.",
    "raw_span": "Exact substring from the document.",
    "confidence": 0.0,
    "source_ref": "{document_id}"
  }}],
  "relations": [{{
    "source_id": "C01",
    "relation_type": "DEPENDS_ON",
    "target_id": "C02",
    "confidence": 0.0,
    "rationale": "Short structural reason, not a verdict."
  }}]
}}"""
    user = f"DOCUMENT ID: {document_id}\n\nDOCUMENT:\n{document}"
    return system, user


def reviewer_prompt(dossier: SemanticDossier, role: str) -> tuple[str, str]:
    graph = {
        "claims": [
            {
                "id": claim.proposal_id,
                "type": claim.claim_type.value,
                "claim": claim.canonical_content,
            }
            for claim in dossier.claims
        ],
        "relations": [
            {
                "source": _proposal_id(dossier, relation.source_claim_node_id),
                "type": relation.relation_type.value,
                "target": _proposal_id(dossier, relation.target_claim_node_id),
            }
            for relation in dossier.relations
        ],
    }
    system = f"""You are one independent Anti-Delphi reviewer: {role}.
Review only the governed ClaimGraph. Do not repair the application, vote on funding, or
declare claims true/false. Find tensions that a human examiner should inspect. Cite only
existing claim IDs. Return JSON only, exactly as:
{{"findings": [{{
  "finding_id": "F01",
  "category": "review_question",
  "severity": "low|medium|high|critical",
  "summary": "Short neutral label",
  "claim_ids": ["C01"],
  "explanation": "Why these claims require inspection",
  "question_for_reviewer": "A concrete question for the human examiner",
  "confidence": 0.0
}}]}}
Allowed categories: arithmetic_mismatch, budget_mismatch, capacity_mismatch,
resource_mismatch, unsupported_assumption, evidence_gap, causal_overclaim,
scope_tension, internal_contradiction, review_question.
Empty findings are allowed. Agreement is not truth."""
    return system, "GOVERNED CLAIMGRAPH:\n" + json.dumps(graph, ensure_ascii=False, indent=2)


def _proposal_id(dossier: SemanticDossier, node_id: str) -> str:
    for claim in dossier.claims:
        if claim.claim_node_id == node_id:
            return claim.proposal_id
    raise KeyError(node_id)


__all__ = ["extraction_prompt", "reviewer_prompt"]
