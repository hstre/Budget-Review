"""The run comparison, on cases whose answer is fixed in advance.

The verdict is what the tool is for: a variant that only adds spans replaces
the one before it, while a variant that also loses some is a second sensor and
belongs in a union rather than in a choice. Confusing the two would turn a
trade into a false claim of improvement, so each verdict is pinned here.

Each case is now checked at every threshold in the sweep rather than at one.
That is the point of the sweep: a verdict that holds only at 0.8 is a statement
about the matching rule and not about the runs, and these fixtures are built so
that the verdict should not depend on it.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "src" / "budget_review" / "fixtures" / "coherence_theatre"


def _module():
    spec = importlib.util.spec_from_file_location("compare", ROOT / "scripts" / "compare_runs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compare = _module()


@pytest.fixture(params=compare.SWEEP, ids=lambda t: f"{t:.0%}")
def threshold(request) -> float:
    """Every case runs at every threshold in the condition space."""
    return request.param


@pytest.fixture
def gold() -> list:
    packet = json.loads((FIXTURES / "semantic_packet.json").read_text(encoding="utf-8"))
    source = (FIXTURES / "proposal.md").read_text(encoding="utf-8")
    return compare.recall.gold_spans(packet, source)


def _dossier(spans, path: Path) -> Path:
    path.write_text(
        json.dumps(
            {"semantic": {"claims": [{"anchor_start": s[0], "anchor_end": s[1]} for s in spans]}}
        ),
        encoding="utf-8",
    )
    return path


def test_a_run_reproducing_every_gold_span_finds_them_all(gold, tmp_path, threshold) -> None:
    path = _dossier([span for _, span, _ in gold], tmp_path / "full.json")

    found = compare.found_spans(path, gold, threshold)

    assert found == {proposal_id for proposal_id, _, _ in gold}


def test_a_subset_run_finds_exactly_that_subset(gold, tmp_path, threshold) -> None:
    path = _dossier([span for _, span, _ in gold[:10]], tmp_path / "part.json")

    found = compare.found_spans(path, gold, threshold)

    assert found == {proposal_id for proposal_id, _, _ in gold[:10]}


def test_two_halves_that_overlap_are_a_trade_whose_union_is_whole(
    gold, tmp_path, threshold
) -> None:
    left = _dossier([span for _, span, _ in gold[:15]], tmp_path / "left.json")
    right = _dossier([span for _, span, _ in gold[10:]], tmp_path / "right.json")

    found_left = compare.found_spans(left, gold, threshold)
    found_right = compare.found_spans(right, gold, threshold)


    assert found_left - found_right, "left must hold spans right does not"
    assert found_right - found_left, "right must hold spans left does not"
    whole = {proposal_id for proposal_id, _, _ in gold}
    assert found_left | found_right == whole


def test_a_superset_run_is_a_strict_improvement_and_loses_nothing(
    gold, tmp_path, threshold
) -> None:
    small = _dossier([span for _, span, _ in gold[:10]], tmp_path / "small.json")
    large = _dossier([span for _, span, _ in gold[:18]], tmp_path / "large.json")

    found_small = compare.found_spans(small, gold, threshold)
    found_large = compare.found_spans(large, gold, threshold)

    assert found_small < found_large
    assert not found_small - found_large


def test_an_unanchored_run_finds_nothing(gold, tmp_path, threshold) -> None:
    path = _dossier([], tmp_path / "empty.json")

    assert compare.found_spans(path, gold, threshold) == set()
