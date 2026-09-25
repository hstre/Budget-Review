"""The admission rule a coverage-repair second pass would need, before it exists.

The measured problem is narrow: on one court decision three gold spans are
anchored at 0, 19 and 20 per cent — passages the extraction did not work. A
second LLM call over exactly those passages, with the existing graph as
negative context, is the obvious repair, and the obvious way to get it wrong is
to let it re-say what the first call already said. Our own double run showed the
size of that failure: 186 claims and 141 without a gold match, for two extra
gold spans.

So the rule comes first, deterministic and testable, and the paid pass second.
Four cases, in the order they are decided:

  1. An anchor outside the passages the pass was asked about. The second call
     was given specific gaps; a claim from somewhere else is the pass writing a
     second opinion on text that already has one. Rejected — and rejected
     rather than clipped, because a claim is admitted with the span it quotes.
  2. An anchor that adds no uncovered characters. This is the near-duplicate
     the double run produced in bulk: the same passage said again in slightly
     different words, which the gate cannot collapse because its content address
     covers the wording. Rejected below a minimum share of new characters.
  3. Content already admitted, anchored somewhere new. This one is admitted,
     and it is the interesting case rather than the embarrassing one: "the
     Government contended X" and the Court's later restatement of the same X are
     two speech acts, not one claim with two anchors. It is flagged so the
     dossier can show the pair instead of looking duplicated.
  4. Anything else: a new claim in a requested gap, which is what the pass is
     for.

Nothing here adds a claim, and nothing marks one true. The rule only decides
admission, which is what the gate already does — and, like the gate, it records
why on every rejection.
"""

from __future__ import annotations

MINIMUM_NEW_SHARE = 0.5


def _covered(span: tuple[int, int], union: list[tuple[int, int]]) -> int:
    start, end = span
    return sum(max(0, min(end, u_end) - max(start, u_start)) for u_start, u_end in union)


def verdict(
    span: tuple[int, int],
    canonical_content: str,
    requested_gaps: list[tuple[int, int]],
    admitted_union: list[tuple[int, int]],
    admitted_contents: set[str],
    minimum_new_share: float = MINIMUM_NEW_SHARE,
) -> tuple[str, str]:
    """Admit, admit-and-flag, or reject one proposal from the repair pass.

    Returns the verdict and the reason, so a rejection can be written into the
    audit in the shape the gate already uses.
    """
    length = max(1, span[1] - span[0])
    if _covered(span, requested_gaps) == 0:
        return ("reject", "outside_requested_gap")
    new_share = (length - _covered(span, admitted_union)) / length
    if new_share < minimum_new_share:
        return ("reject", "adds_no_uncovered_text")
    if canonical_content in admitted_contents:
        return ("admit", "duplicate_content_other_anchor")
    return ("admit", "new_claim")
