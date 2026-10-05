"""The Sci-Arg reference builder, pinned where a wrong gold answer would be silent.

A reference is the one thing in a measurement nobody checks afterwards: if it
carries text the document does not contain, or offsets that point somewhere
else, every recall figure computed against it is wrong and looks fine. So the
invariant is the same as for the legal corpus — a re-based span must quote the
same characters — and everything the corpus cannot deliver is dropped and
counted rather than repaired.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "sciarg_gold", ROOT / "scripts" / "sciarg_gold.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sciarg = _module()
TEXT = "Front matter here. The method is fast. Results improve. Bibliography follows."


def _corpus(tmp_path: Path, annotations: str, text: str = TEXT) -> Path:
    corpus = tmp_path / "compiled_corpus"
    corpus.mkdir()
    (corpus / "A01.txt").write_text(text, encoding="utf-8")
    (corpus / "A01.ann").write_text(annotations, encoding="utf-8")
    return corpus


def _line(identifier: str, label: str, start: int, end: int, text: str) -> str:
    return f"{identifier}\t{label} {start} {end}\t{text}\n"


def test_the_region_runs_from_the_first_to_the_last_component(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        _line("T1", "background_claim", 19, 37, "The method is fast")
        + _line("T2", "own_claim", 39, 55, "Results improve."),
    )

    sciarg.build(corpus, "A01", tmp_path / "out")

    assert (tmp_path / "out" / "A01.txt").read_text(encoding="utf-8") == (
        "The method is fast. Results improve."
    )


def test_every_rebased_span_quotes_the_same_characters(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        _line("T1", "background_claim", 19, 37, "The method is fast")
        + _line("T2", "own_claim", 39, 55, "Results improve."),
    )

    sciarg.build(corpus, "A01", tmp_path / "out")
    region = (tmp_path / "out" / "A01.txt").read_text(encoding="utf-8")
    gold = json.loads((tmp_path / "out" / "A01.gold.json").read_text(encoding="utf-8"))

    for claim in gold["claims"]:
        assert region[claim["begin"] : claim["end"]] == claim["raw_span"]


def test_a_discontinuous_annotation_is_dropped_not_guessed(tmp_path, capsys) -> None:
    corpus = _corpus(
        tmp_path,
        _line("T1", "background_claim", 19, 37, "The method is fast")
        + "T2\town_claim 39 46;47 55\tResults improve.\n"
        + _line("T3", "own_claim", 39, 55, "Results improve."),
    )

    sciarg.build(corpus, "A01", tmp_path / "out")
    gold = json.loads((tmp_path / "out" / "A01.gold.json").read_text(encoding="utf-8"))

    assert len(gold["claims"]) == 2
    assert "1 unbrauchbare" in capsys.readouterr().out


def test_an_annotation_whose_offsets_disagree_with_its_text_is_dropped(tmp_path) -> None:
    """The one error that would poison every later recall figure silently."""
    corpus = _corpus(
        tmp_path,
        _line("T1", "background_claim", 19, 37, "The method is fast")
        + _line("T2", "own_claim", 0, 10, "Results improve."),
    )

    sciarg.build(corpus, "A01", tmp_path / "out")
    gold = json.loads((tmp_path / "out" / "A01.gold.json").read_text(encoding="utf-8"))

    assert [claim["raw_span"] for claim in gold["claims"]] == ["The method is fast"]


def test_labels_outside_the_three_components_are_not_gold(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        _line("T1", "background_claim", 19, 37, "The method is fast")
        + _line("T2", "token", 39, 55, "Results improve."),
    )

    _, spans, _ = sciarg.read_paper(corpus / "A01.txt")

    assert [label for _, _, label in spans] == ["background_claim"]


def test_a_non_bmp_character_stops_the_build(tmp_path) -> None:
    """Offsets would line up here, but the legal corpus taught the cost of assuming."""
    corpus = _corpus(
        tmp_path,
        _line("T1", "background_claim", 19, 37, "The method is fast"),
        text=TEXT + " 😀",
    )

    with pytest.raises(ValueError):
        sciarg.read_paper(corpus / "A01.txt")
