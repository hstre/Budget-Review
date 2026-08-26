"""Closed alpha contracts. Model output is always a proposal, never authority."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum, StrEnum
from typing import Any


class SchemaError(ValueError):
    """Raised when an untrusted packet does not satisfy the closed contract."""


class ClaimType(StrEnum):
    THESIS = "thesis"
    FACT = "fact"
    INFERENCE = "inference"
    VALUE_JUDGMENT = "value_judgment"
    RECOMMENDATION = "recommendation"
    EXAMPLE = "example"
    SCOPE = "scope"
    TARGET = "target"
    CAPACITY = "capacity"
    RESOURCE = "resource"
    BASELINE = "baseline"
    FORECAST = "forecast"
    DELIVERY = "delivery"
    ASSUMPTION = "assumption"
    BUDGET = "budget"
    METHOD = "method"
    CAUSAL = "causal"
    EVIDENCE = "evidence"
    LIMITATION = "limitation"
    DEFINITION = "definition"
    OTHER = "other"


class RelationType(StrEnum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    DEPENDS_ON = "DEPENDS_ON"
    ASSUMPTION_FOR = "ASSUMPTION_FOR"
    CONSTRAINS = "CONSTRAINS"
    QUANTIFIES = "QUANTIFIES"
    BASELINE_FOR = "BASELINE_FOR"
    PART_OF = "PART_OF"
    EVIDENCED_BY = "EVIDENCED_BY"
    SCOPE_TENSION = "SCOPE_TENSION"
    QUALIFIES = "QUALIFIES"
    GENERALIZES = "GENERALIZES"
    EXAMPLE_OF = "EXAMPLE_OF"
    ENTAILS = "ENTAILS"


class FindingCategory(StrEnum):
    ARITHMETIC_MISMATCH = "arithmetic_mismatch"
    BUDGET_MISMATCH = "budget_mismatch"
    CAPACITY_MISMATCH = "capacity_mismatch"
    RESOURCE_MISMATCH = "resource_mismatch"
    UNSUPPORTED_ASSUMPTION = "unsupported_assumption"
    EVIDENCE_GAP = "evidence_gap"
    CAUSAL_OVERCLAIM = "causal_overclaim"
    SCOPE_TENSION = "scope_tension"
    INTERNAL_CONTRADICTION = "internal_contradiction"
    LOGICAL_GAP = "logical_gap"
    OVERGENERALIZATION = "overgeneralization"
    DEFINITION_SHIFT = "definition_shift"
    RELEVANCE_GAP = "relevance_gap"
    REVIEW_QUESTION = "review_question"


def _required(data: dict[str, Any], key: str, expected: type) -> Any:
    value = data.get(key)
    if not isinstance(value, expected):
        raise SchemaError(f"{key} must be {expected.__name__}")
    return value


def _closed(data: dict[str, Any], allowed: set[str], where: str) -> None:
    extras = set(data) - allowed
    if extras:
        raise SchemaError(f"unexpected fields in {where}: {', '.join(sorted(extras))}")


def _confidence(value: Any, where: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise SchemaError(f"{where} confidence must be numeric")
    result = float(value)
    if not 0.0 <= result <= 1.0:
        raise SchemaError(f"{where} confidence must be between 0 and 1")
    return result


@dataclass(frozen=True)
class Provenance:
    provider: str
    model_id: str
    run_id: str
    prompt_hash: str
    output_hash: str
    temperature: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Provenance:
        _closed(
            data,
            {"provider", "model_id", "run_id", "prompt_hash", "output_hash", "temperature"},
            "provenance",
        )
        prompt_hash = _required(data, "prompt_hash", str)
        output_hash = _required(data, "output_hash", str)
        if len(prompt_hash) < 8 or len(output_hash) < 8:
            raise SchemaError("provenance hashes are too short")
        temperature = data.get("temperature", 0.0)
        if not isinstance(temperature, int | float):
            raise SchemaError("temperature must be numeric")
        return cls(
            provider=_required(data, "provider", str),
            model_id=_required(data, "model_id", str),
            run_id=_required(data, "run_id", str),
            prompt_hash=prompt_hash,
            output_hash=output_hash,
            temperature=float(temperature),
        )


@dataclass(frozen=True)
class ClaimProposal:
    proposal_id: str
    claim_type: ClaimType
    canonical_content: str
    raw_span: str
    confidence: float
    source_ref: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClaimProposal:
        _closed(
            data,
            {
                "proposal_id",
                "claim_type",
                "canonical_content",
                "raw_span",
                "confidence",
                "source_ref",
            },
            "claim",
        )
        proposal_id = _required(data, "proposal_id", str)
        if not proposal_id or len(proposal_id) > 64 or not proposal_id[0].isalpha():
            raise SchemaError("invalid proposal_id")
        try:
            claim_type = ClaimType(_required(data, "claim_type", str))
        except ValueError as exc:
            raise SchemaError(f"unknown claim_type: {data.get('claim_type')}") from exc
        canonical = _required(data, "canonical_content", str).strip()
        raw_span = _required(data, "raw_span", str)
        source_ref = _required(data, "source_ref", str).strip()
        if not canonical or not raw_span or not source_ref:
            raise SchemaError("claim strings must not be empty")
        return cls(
            proposal_id=proposal_id,
            claim_type=claim_type,
            canonical_content=canonical,
            raw_span=raw_span,
            confidence=_confidence(data.get("confidence"), proposal_id),
            source_ref=source_ref,
        )


@dataclass(frozen=True)
class RelationProposal:
    source_id: str
    relation_type: RelationType
    target_id: str
    confidence: float
    rationale: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RelationProposal:
        _closed(
            data,
            {"source_id", "relation_type", "target_id", "confidence", "rationale"},
            "relation",
        )
        try:
            relation_type = RelationType(_required(data, "relation_type", str))
        except ValueError as exc:
            raise SchemaError(f"unknown relation_type: {data.get('relation_type')}") from exc
        return cls(
            source_id=_required(data, "source_id", str),
            relation_type=relation_type,
            target_id=_required(data, "target_id", str),
            confidence=_confidence(data.get("confidence", 0.5), "relation"),
            rationale=str(data.get("rationale", "")),
        )


@dataclass(frozen=True)
class SemanticPacket:
    schema_version: str
    document_id: str
    provenance: Provenance
    claims: tuple[ClaimProposal, ...]
    relations: tuple[RelationProposal, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticPacket:
        _closed(
            data,
            {"schema_version", "document_id", "provenance", "claims", "relations"},
            "semantic packet",
        )
        if data.get("schema_version") not in {
            "budget-review.semantic-packet/0.1",
            "content-review.semantic-packet/0.2",
        }:
            raise SchemaError("unsupported semantic packet schema_version")
        raw_claims = _required(data, "claims", list)
        raw_relations = data.get("relations", [])
        if not isinstance(raw_relations, list):
            raise SchemaError("relations must be a list")
        if not raw_claims:
            raise SchemaError("semantic packet must contain at least one claim")
        return cls(
            schema_version=data["schema_version"],
            document_id=_required(data, "document_id", str),
            provenance=Provenance.from_dict(_required(data, "provenance", dict)),
            claims=tuple(ClaimProposal.from_dict(item) for item in raw_claims),
            relations=tuple(RelationProposal.from_dict(item) for item in raw_relations),
        )

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class GovernedClaim:
    claim_node_id: str
    proposal_id: str
    claim_type: ClaimType
    canonical_content: str
    raw_span: str
    anchor_start: int
    anchor_end: int
    anchor_ambiguous: bool
    confidence: float
    source_ref: str
    semantic_state: str


@dataclass(frozen=True)
class GovernedRelation:
    relation_id: str
    source_claim_node_id: str
    relation_type: RelationType
    target_claim_node_id: str
    confidence: float
    rationale: str
    semantic_state: str


@dataclass(frozen=True)
class Rejection:
    item_kind: str
    item_id: str
    reason: str


@dataclass(frozen=True)
class SemanticDossier:
    schema_version: str
    document_id: str
    document_hash: str
    provenance: Provenance
    claims: tuple[GovernedClaim, ...]
    relations: tuple[GovernedRelation, ...]
    rejections: tuple[Rejection, ...]
    authority_note: str = "Semantic structure only. No claim has been judged true or false."

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class Finding:
    finding_id: str
    reviewer_id: str
    reviewer_kind: str
    model_id: str
    category: FindingCategory
    severity: str
    summary: str
    claim_ids: tuple[str, ...]
    explanation: str
    question_for_reviewer: str
    confidence: float
    state: str = "human_review_required"


@dataclass(frozen=True)
class ReviewRejection:
    reviewer_id: str
    item_id: str
    reason: str


@dataclass(frozen=True)
class ReviewDossier:
    schema_version: str
    semantic: SemanticDossier
    findings: tuple[Finding, ...]
    review_rejections: tuple[ReviewRejection, ...]
    profile: str = "general"
    reviewer_runs: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    authority_note: str = (
        "Decision support only. Agreement between reviewers is not evidence of truth; "
        "the human reviewer remains the merge authority."
    )

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    return value


__all__ = [
    "ClaimProposal",
    "ClaimType",
    "Finding",
    "FindingCategory",
    "GovernedClaim",
    "GovernedRelation",
    "Provenance",
    "RelationProposal",
    "RelationType",
    "Rejection",
    "ReviewDossier",
    "ReviewRejection",
    "SchemaError",
    "SemanticDossier",
    "SemanticPacket",
]
