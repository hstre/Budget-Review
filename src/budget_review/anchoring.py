"""Locating a proposed span in the document it claims to quote.

The gate admits a claim only if the document carries the quoted passage. That is
what makes a dossier auditable: every claim points at characters a reader can
check. Exactness is the right default and stays the first test.

What it cannot be is exactness about typesetting. A hard-wrapped source has line
breaks inside its sentences — the court decision measured here runs 28 lines over
10,308 characters, a median line of 323 — and a proposal quoting such a passage
writes it as flowing prose, so the newline becomes a space or disappears. The
exact lookup then fails on a passage the document plainly contains.

Measured over four runs on one paper: 412 of 465 proposals anchored verbatim, 42
more differ from the document only in whitespace, and 11 are genuine paraphrase.
Refusing those 42 cost between nine and sixty-eight gold spans per run.

So a span that fails the exact test is tried again on a whitespace-collapsed copy
of the document, and what comes back is its position in the **original** text.
The claim then quotes the document's own characters, never the model's wording,
and a span the document does not carry apart from whitespace is still refused:
this tolerates typesetting, not paraphrase.

Case is not folded and punctuation is not stripped. On the same data casefolding
anchors nothing further and adds nothing to a claim's identity — the stable core
is 75 and 30 claims either way — so the weaker rule is the one that holds.
"""

from __future__ import annotations


def folded(text: str) -> str:
    """Whitespace runs squeezed to one space, and nothing else changed."""
    return " ".join(text.split())


def _collapsed(text: str) -> tuple[str, list[int]]:
    """The text with whitespace runs squeezed to one space, and an index map.

    The map carries, per character of the copy, its offset in the original, so a
    match on the copy can be reported as a position in the document.
    """
    out: list[str] = []
    origin: list[int] = []
    previous_space = False
    for index, character in enumerate(text):
        if character.isspace():
            if not previous_space:
                out.append(" ")
                origin.append(index)
            previous_space = True
            continue
        out.append(character)
        origin.append(index)
        previous_space = False
    return "".join(out), origin


def _occurrences(document: str, span: str) -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    start = 0
    while True:
        position = document.find(span, start)
        if position < 0:
            return found
        found.append((position, position + len(span)))
        start = position + 1


def anchor_spans(document: str, span: str) -> tuple[list[tuple[int, int]], bool]:
    """Every position the document carries this span, and whether whitespace was ignored.

    Exact occurrences win outright. A proposal that quoted correctly therefore
    anchors exactly as it did before this tolerance existed, and the tolerance
    can only ever add anchors for a span that had none — never move one.
    """
    if not span:
        return [], False
    exact = _occurrences(document, span)
    if exact:
        return exact, False
    needle = folded(span)
    if not needle:
        return [], False
    haystack, origin = _collapsed(document)
    found: list[tuple[int, int]] = []
    start = 0
    while True:
        position = haystack.find(needle, start)
        if position < 0:
            break
        found.append((origin[position], origin[position + len(needle) - 1] + 1))
        start = position + 1
    return found, bool(found)


__all__ = ["anchor_spans", "folded"]
