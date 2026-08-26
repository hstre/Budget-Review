"""Prompts are sensors: narrow output contracts and no decision authority."""

from __future__ import annotations

import json

from .models import SemanticDossier
from .profiles import ReviewProfile, get_profile

CLAIM_TYPES = (
    "thesis, fact, inference, value_judgment, recommendation, example, scope, target, "
    "capacity, resource, baseline, forecast, delivery, assumption, budget, method, "
    "causal, evidence, limitation, definition, other"
)
RELATION_TYPES = (
    "SUPPORTS, CONTRADICTS, DEPENDS_ON, ASSUMPTION_FOR, CONSTRAINS, QUANTIFIES, "
    "BASELINE_FOR, PART_OF, EVIDENCED_BY, SCOPE_TENSION, QUALIFIES, GENERALIZES, "
    "EXAMPLE_OF, ENTAILS"
)


def extraction_prompt(
    document_id: str,
    document: str,
    profile: str | ReviewProfile = "general",
) -> tuple[str, str]:
    selected = get_profile(profile)
    system = f"""You are a non-authoritative semantic extraction sensor.
Review profile: {selected.name}.
{selected.extraction_guidance}
Return JSON only. Never judge whether a claim is true, good, human-written or AI-written.
Decompose polished prose aggressively: an elegant sentence may contain several claims.
Each raw_span must be copied verbatim and exactly from the document.
Allowed claim_type values: {CLAIM_TYPES}.
Allowed relation_type values: {RELATION_TYPES}.
The relation_type field must contain one of those UPPERCASE relation values only. Never put
a claim_type such as method, evidence or assumption into relation_type. If no allowed relation
fits with high confidence, omit that relation instead of inventing a label.
Relation direction is semantic: source SUPPORTS target; source claim EVIDENCED_BY target
evidence; source broader claim GENERALIZES target narrower basis; source QUALIFIES target;
source premise ENTAILS target conclusion; source example EXAMPLE_OF target general claim;
source part PART_OF target whole.

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


_REVIEWER_LANGUAGE = {"de": "clear German", "en": "clear English"}


def reviewer_prompt(
    dossier: SemanticDossier,
    role: str,
    profile: str | ReviewProfile = "general",
    language: str = "de",
) -> tuple[str, str]:
    selected = get_profile(profile)
    prose = _REVIEWER_LANGUAGE.get(language, _REVIEWER_LANGUAGE["de"])
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
    system = f"""You are one independent Anti-Delphi reviewer for the {selected.name} profile:
{role}
Review only the governed ClaimGraph. Ignore fluency, formatting and suspected AI authorship.
Do not repair the text, give an overall quality verdict, or declare claims true/false. Find
content tensions that a human examiner should inspect. Cite only existing claim IDs. Write
summary, explanation and question_for_reviewer in {prose}.
Return JSON only, exactly as:
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
scope_tension, internal_contradiction, logical_gap, overgeneralization,
definition_shift, relevance_gap, review_question.
Empty findings are allowed. Agreement is not truth."""
    return system, "GOVERNED CLAIMGRAPH:\n" + json.dumps(graph, ensure_ascii=False, indent=2)


def _proposal_id(dossier: SemanticDossier, node_id: str) -> str:
    for claim in dossier.claims:
        if claim.claim_node_id == node_id:
            return claim.proposal_id
    raise KeyError(node_id)


__all__ = ["extraction_prompt", "reviewer_prompt"]
