"""Deterministic measurement of how much source text the admitted claims touch.

The gate can reject a claim but never add one, so everything downstream is
bounded by what the extractor produced. A claim that was never proposed is
invisible to the deterministic checks and to both reviewer arms alike, and the
dossier it produces looks clean. This module makes that blind spot measurable
from data the gate already records: every admitted claim carries the exact
offsets of its source span.

It counts characters and names gaps. It never decides that a gap is a defect:
an uncovered passage may be a heading, a transition, or genuinely claim-free
prose. That judgment belongs to the human examiner, so the finding this feeds
is phrased as a question.

The ratio is a descriptive statistic, not a score, and it must not be read as
one. It moves with how broadly claims are defined, not only with how well they
were extracted: on AbstRCT the same documents measure a median ratio of 0.48
when every annotated argument component counts and 0.14 when only conclusions
do. A ratio is therefore comparable across runs of one extraction contract and
meaningless across different ones.
"""

from __future__ import annotations

from collections.abc import Iterable

from .models import Coverage, CoverageGap, GovernedClaim

# A gap shorter than this is connective tissue between two anchored spans, not
# a passage the extractor plausibly skipped. Calibrated against AbstRCT (Mayer
# et al., ECAI 2020), 293 clinical abstracts with expert-annotated argument
# spans: between thresholds of 60 and 300 the reported gaps per document only
# move from 1.31 to 1.01, so the exact value is not a sensitive knob. The
# reported gaps account for 98% of the unanchored text on average, which is
# what makes the list a decomposition of the ratio rather than a sample of it.
# That last property is scale-dependent: on the 10k-to-40k-character
# argumentation of ECHR court decisions the gaps cover a median 72% instead,
# since 94% of the stretches between anchors fall under the threshold and their
# total mass grows with the document.
MIN_GAP_CHARACTERS = 120
EXCERPT_CHARACTERS = 160


def _merged_spans(claims: Iterable[GovernedClaim]) -> list[list[int]]:
    """Anchored ranges, overlaps collapsed, so a character counts once."""
    merged: list[list[int]] = []
    for start, end in sorted([claim.anchor_start, claim.anchor_end] for claim in claims):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _ink(text: str) -> int:
    """Characters that carry text. Whitespace would flatter the ratio."""
    return sum(1 for character in text if not character.isspace())


def _excerpt(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= EXCERPT_CHARACTERS:
        return collapsed
    return collapsed[:EXCERPT_CHARACTERS].rstrip() + "…"


def measure_coverage(
    document: str,
    claims: Iterable[GovernedClaim],
    minimum_gap: int = MIN_GAP_CHARACTERS,
) -> Coverage:
    """Report anchored share and the passages no admitted claim reaches."""
    spans = _merged_spans(claims)
    total = _ink(document)
    anchored = sum(_ink(document[start:end]) for start, end in spans)

    gaps: list[CoverageGap] = []
    position = 0
    for start, end in [*spans, [len(document), len(document)]]:
        if start > position:
            raw = document[position:start]
            stripped = raw.strip()
            if len(stripped) >= minimum_gap:
                offset = position + (len(raw) - len(raw.lstrip()))
                gaps.append(CoverageGap(offset, offset + len(stripped), _excerpt(stripped)))
        position = max(position, end)

    return Coverage(
        document_characters=total,
        anchored_characters=anchored,
        # Rounded so the audit stays byte-identical on replay.
        ratio=round(anchored / total, 4) if total else 0.0,
        gaps=tuple(gaps),
    )


__all__ = ["EXCERPT_CHARACTERS", "MIN_GAP_CHARACTERS", "measure_coverage"]
