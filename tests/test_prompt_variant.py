"""The prompt variants, pinned so an experiment cannot quietly test nothing.

Both edits together moved recall on one court decision from 16 of 24 to 20.
Which half did the work is a separate question, and it can only be answered if
each edit really is applied alone — a variant that silently degraded to the
production prompt would answer it wrongly and look plausible doing so.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from budget_review.prompts import extraction_prompt

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "variant", ROOT / "scripts" / "prompt_variant_extract.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


variant = _module()
DOCUMENT = "A short document."


def _production() -> str:
    return extraction_prompt("d", DOCUMENT, "general")[0]


@pytest.mark.parametrize("edits", [("decompose",), ("vocabulary",), variant.EDITS])
def test_every_variant_changes_the_production_prompt(edits) -> None:
    assert variant.variant_prompt("d", DOCUMENT, edits)[0] != _production()


def test_the_user_message_is_never_touched() -> None:
    """Only the instruction may vary, or the comparison has two variables."""
    _, produced = variant.variant_prompt("d", DOCUMENT)
    _, expected = extraction_prompt("d", DOCUMENT, "general")

    assert produced == expected


def test_decompose_alone_replaces_only_the_decomposition_sentence() -> None:
    system = variant.variant_prompt("d", DOCUMENT, ("decompose",))[0]

    assert variant.ORIGINAL_DECOMPOSE not in system
    assert variant.NEUTRAL_DECOMPOSE in system
    assert variant.TYPES_NOTE not in system


def test_vocabulary_alone_adds_only_the_label_note() -> None:
    system = variant.variant_prompt("d", DOCUMENT, ("vocabulary",))[0]

    assert variant.TYPES_NOTE in system
    assert variant.ORIGINAL_DECOMPOSE in system
    assert variant.NEUTRAL_DECOMPOSE not in system


def test_the_bundle_is_exactly_both_single_edits() -> None:
    both = variant.variant_prompt("d", DOCUMENT, variant.EDITS)[0]

    assert variant.NEUTRAL_DECOMPOSE in both
    assert variant.TYPES_NOTE in both
    assert variant.ORIGINAL_DECOMPOSE not in both


def test_a_prompt_that_moved_on_fails_the_run_instead_of_testing_nothing(monkeypatch) -> None:
    monkeypatch.setattr(variant, "ORIGINAL_DECOMPOSE", "a sentence the prompt does not contain")

    with pytest.raises(SystemExit):
        variant.variant_prompt("d", DOCUMENT, ("decompose",))
