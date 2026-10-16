"""A forbidden reading has to be caught wherever the run put it.

The first paid run of the reading-identity set passed 48 of 48 while producing
23 forbidden resolutions — one sentence over from the span, where the scorer
judged only claims anchored on the span. Ten of those are caught by the repaired
scorer, and two of the ten arrived typed `fact`, asserting as fact an inference
the document does not make.

These tests hold the repair and the line it has to walk: an inferred resolution
is caught anywhere in the dossier, and a verbatim quote of another sentence is
not, because quoting the source correctly is the job.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "semantic_score", ROOT / "scripts" / "semantic_score.py"
)
semantic_score = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(semantic_score)

DOCUMENT = (
    "Das Amt hält fest, dass die Standorte den Mittelabruf nicht gemeldet haben, "
    "und prüft die Unterlagen; zwei der fünf Meldungen liegen inzwischen vor."
)
SPAN = "dass die Standorte den Mittelabruf nicht gemeldet haben"

CASE = {
    "case_id": "t-01",
    "document": DOCUMENT,
    "span": SPAN,
    "language": "de",
    "requires_all_groups": [["Standorte"], ["nicht"]],
    "min_claims_on_span": 1,
    "forbids": [],
    "forbidden_anywhere": ["\\bnoch nicht vor\\b"],
}


def _claim(text: str, claim_type: str = "fact", *, on_span: bool = True) -> dict:
    start = DOCUMENT.index(SPAN)
    if on_span:
        anchor = (start, start + len(SPAN))
    else:
        tail = DOCUMENT.index("zwei der fünf")
        anchor = (tail, len(DOCUMENT))
    return {
        "canonical_content": text,
        "claim_type": claim_type,
        "raw_span": DOCUMENT[anchor[0] : anchor[1]],
        "anchor_start": anchor[0],
        "anchor_end": anchor[1],
        "anchor_normalised": False,
    }


def test_a_clean_run_passes() -> None:
    row = semantic_score.score(
        CASE, [_claim("Die Standorte haben den Mittelabruf nicht gemeldet.")]
    )
    assert row["meaning_preserved"] is True
    assert row["distortions"] == []


def test_a_forbidden_resolution_off_the_span_fails_the_case() -> None:
    """The error the first run produced 23 times and the old scorer never saw."""
    row = semantic_score.score(
        CASE,
        [
            _claim("Die Standorte haben den Mittelabruf nicht gemeldet."),
            _claim(
                "Drei der fünf Meldungen liegen dem Amt noch nicht vor.",
                "inference",
                on_span=False,
            ),
        ],
    )

    assert row["meaning_preserved"] is False
    assert len(row["distortions_off_span"]) == 1


def test_a_verbatim_quote_of_another_sentence_is_not_punished() -> None:
    # Quoting the source correctly is the job. A pattern that caught this would
    # fail a run for doing what it is for, and the validator refuses such a
    # pattern besides.
    row = semantic_score.score(
        CASE,
        [
            _claim("Die Standorte haben den Mittelabruf nicht gemeldet."),
            _claim("Zwei der fünf Meldungen liegen inzwischen vor.", "fact", on_span=False),
        ],
    )

    assert row["meaning_preserved"] is True
    assert row["distortions"] == []


def test_an_inference_arriving_as_a_fact_is_recorded_as_such() -> None:
    """Three of the first run's ten caught claims were typed this way.

    An inference the document does not make, asserted as a fact, is a different
    error from one the run itself labels an inference — it is the invented
    commitment this product exists to catch.
    """
    row = semantic_score.score(
        CASE,
        [
            _claim("Die Standorte haben den Mittelabruf nicht gemeldet."),
            _claim(
                "Drei der fünf Meldungen liegen dem Amt noch nicht vor.",
                "fact",
                on_span=False,
            ),
        ],
    )

    assert len(row["inferences_typed_as_fact"]) == 1
    assert row["inferences_typed_as_fact"][0]["claim_type"] == "fact"


def test_an_inference_labelled_as_one_still_fails_but_is_not_a_fact_claim() -> None:
    row = semantic_score.score(
        CASE,
        [
            _claim("Die Standorte haben den Mittelabruf nicht gemeldet."),
            _claim(
                "Drei der fünf Meldungen liegen dem Amt noch nicht vor.",
                "inference",
                on_span=False,
            ),
        ],
    )

    assert row["meaning_preserved"] is False
    assert row["inferences_typed_as_fact"] == []


def test_a_forbidden_resolution_on_the_span_is_caught_too() -> None:
    # The patterns are not an off-span-only check: anywhere means anywhere.
    row = semantic_score.score(
        CASE, [_claim("Drei der fünf Meldungen liegen dem Amt noch nicht vor.")]
    )

    assert row["meaning_preserved"] is False
    assert row["distortions"]
    assert row["distortions_off_span"] == []


def test_a_case_without_the_new_field_behaves_as_before() -> None:
    """The first meaning set has no such field, and its 69 of 72 must not move."""
    without = {k: v for k, v in CASE.items() if k != "forbidden_anywhere"}
    row = semantic_score.score(
        without,
        [
            _claim("Die Standorte haben den Mittelabruf nicht gemeldet."),
            _claim(
                "Drei der fünf Meldungen liegen dem Amt noch nicht vor.",
                "fact",
                on_span=False,
            ),
        ],
    )

    assert row["meaning_preserved"] is True
    assert row["distortions"] == []
