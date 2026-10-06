"""Finding a quoted passage in its source, pinned where the tolerance could overreach.

The tolerance exists for hard-wrapped sources, where a line break falls inside a
sentence. Two ways it could do harm: moving an anchor that was already exact, and
admitting a paraphrase rather than a typesetting difference.
"""

from __future__ import annotations

from budget_review.anchoring import anchor_spans, folded

DOCUMENT = "The regional budget rises by four per cent.\nThe schools receive the larger share."


def test_folding_touches_whitespace_and_nothing_else() -> None:
    assert folded("a\n b\t\tc ") == "a b c"
    assert folded("Case, and punctuation.") == "Case, and punctuation."


def test_an_exact_span_anchors_exactly_and_is_not_called_normalised() -> None:
    spans, normalised = anchor_spans(DOCUMENT, "The regional budget rises")

    assert spans == [(0, 25)]
    assert normalised is False
    assert DOCUMENT[0:25] == "The regional budget rises"


def test_a_line_break_written_as_a_space_still_anchors_on_the_document() -> None:
    quoted = "four per cent. The schools receive"
    spans, normalised = anchor_spans(DOCUMENT, quoted)

    assert normalised is True
    start, end = spans[0]
    assert DOCUMENT[start:end] == "four per cent.\nThe schools receive"
    assert DOCUMENT[start:end] != quoted, "the document's characters, not the model's"


def test_an_exact_match_wins_over_a_folded_one() -> None:
    """The tolerance may add anchors for a span that had none, never move one."""
    document = "alpha beta\nalpha beta"
    spans, normalised = anchor_spans(document, "alpha beta")

    assert spans == [(0, 10), (11, 21)]
    assert normalised is False


def test_a_passage_quoted_twice_is_found_twice_under_folding() -> None:
    document = "the same\nwords here and the same words here"
    spans, normalised = anchor_spans(document, "the  same words")

    assert normalised is True
    assert len(spans) == 2
    assert [document[a:b] for a, b in spans] == ["the same\nwords", "the same words"]


def test_a_paraphrase_is_still_refused() -> None:
    spans, normalised = anchor_spans(DOCUMENT, "The regional budget grows by four per cent")

    assert spans == []
    assert normalised is False


def test_an_empty_span_anchors_nowhere() -> None:
    """Otherwise it would match at every position in the document."""
    assert anchor_spans(DOCUMENT, "") == ([], False)
    assert anchor_spans(DOCUMENT, "   ") == ([], False)


def test_the_end_offset_comes_from_the_document_not_the_folded_needle() -> None:
    """A whitespace run collapses to one space, so the slice is longer than the needle.

    With a single newline the two lengths coincide and the arithmetic cannot be
    told apart; the papers measured here have spaced citation brackets and
    formula setting, where they do not.
    """
    document = "the value [  HK03  ] is cited"
    spans, normalised = anchor_spans(document, "the value [ HK03 ] is cited")

    assert normalised is True
    start, end = spans[0]
    assert document[start:end] == document, "the whole document, whitespace and all"
    assert end - start > len("the value [ HK03 ] is cited")
