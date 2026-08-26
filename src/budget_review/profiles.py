"""Closed review profiles over one governed semantic core."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewerSpec:
    reviewer_id: str
    role: str
    thinking: bool


@dataclass(frozen=True)
class ReviewProfile:
    name: str
    display_name: str
    subject_name: str
    authority_note: str
    extraction_guidance: str
    reviewers: tuple[ReviewerSpec, ...]
    # The English rendering of authority_note. The German form stays the one
    # serialized into the JSON audit, so the governance record does not move.
    authority_note_en: str = ""


GENERAL = ReviewProfile(
    name="general",
    display_name="Content Review",
    subject_name="Text",
    authority_note=(
        "Inhaltliche Entscheidungshilfe, kein Wahrheits- oder Qualitätsurteil. "
        "Die letzte Entscheidung liegt beim Menschen."
    ),
    extraction_guidance=(
        "Ignore prose quality, formatting, fluency and suspected AI authorship. Extract the "
        "content structure: theses, factual claims, definitions, assumptions, evidence, "
        "inferences, causal claims, forecasts, value judgments, recommendations, examples, "
        "scope and limitations. Distinguish evidence from conclusions and examples from proof."
    ),
    reviewers=(
        ReviewerSpec(
            "flash-evidence-skeptic",
            "Evidence skeptic. Check whether factual claims and conclusions have the internal "
            "support the graph says they have. Distinguish examples from evidence. Do not perform "
            "external fact checking.",
            False,
        ),
        ReviewerSpec(
            "flash-thinking-argument-skeptic",
            "Argument skeptic. Trace premises to conclusions. Focus on missing inferential links, "
            "overgeneralization, contradictions, definition shifts and changes of scope.",
            True,
        ),
    ),
    authority_note_en=(
        "Decision support on content only, not a verdict on truth or quality. "
        "The final decision rests with a human."
    ),
)


BUDGET = ReviewProfile(
    name="budget",
    display_name="Budget Review",
    subject_name="Antrag",
    authority_note=(
        "Entscheidungshilfe, kein Fördervotum. Die letzte Entscheidung liegt beim Menschen."
    ),
    extraction_guidance=(
        "Focus on targets, capacity, resources, delivery, assumptions, budgets, methods, causal "
        "claims, evidence, scope and limitations. Preserve every number as an atomic claim."
    ),
    reviewers=(
        ReviewerSpec(
            "flash-evidence-skeptic",
            "Evidence skeptic. Focus on unsupported assumptions, missing baselines and "
            "scope shifts.",
            False,
        ),
        ReviewerSpec(
            "flash-thinking-dependency-skeptic",
            "Dependency skeptic. Trace whether targets follow from capacity, resources, methods "
            "and budget.",
            True,
        ),
    ),
    authority_note_en=(
        "Decision support, not a funding verdict. The final decision rests with a human."
    ),
)


PROFILES = {profile.name: profile for profile in (GENERAL, BUDGET)}


def authority_note(profile: ReviewProfile, language: str = "de") -> str:
    if language == "en" and profile.authority_note_en:
        return profile.authority_note_en
    return profile.authority_note


def get_profile(value: str | ReviewProfile) -> ReviewProfile:
    if isinstance(value, ReviewProfile):
        return value
    try:
        return PROFILES[value]
    except KeyError as exc:
        allowed = ", ".join(PROFILES)
        raise ValueError(f"unknown review profile {value!r}; choose one of: {allowed}") from exc


__all__ = [
    "BUDGET",
    "GENERAL",
    "PROFILES",
    "ReviewProfile",
    "ReviewerSpec",
    "authority_note",
    "get_profile",
]
