"""The recall harness measured against a run whose answer is known in advance.

A recall number is only worth as much as the matching behind it, so the two
controls here are a run that must score 100% and a run that must not.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from budget_review.pipeline import ReviewPipeline, load_packet

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "src" / "budget_review" / "fixtures" / "coherence_theatre"
DOCUMENT_ID = "regional-skills-bridge"


def _module():
    spec = importlib.util.spec_from_file_location("recall", ROOT / "scripts" / "measure_recall.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


recall = _module()


@pytest.fixture
def source() -> str:
    return (FIXTURES / "proposal.md").read_text(encoding="utf-8")


@pytest.fixture
def gold() -> dict:
    return json.loads((FIXTURES / "semantic_packet.json").read_text(encoding="utf-8"))


def _dossier(packet_data: dict, tmp_path: Path) -> dict:
    """Run the offline pipeline so the harness sees a real dossier, not a stub."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(packet_data), encoding="utf-8")
    from budget_review.ingest import ingest

    bundle = ingest([FIXTURES / "proposal.md"], document_id=DOCUMENT_ID)
    dossier = ReviewPipeline(profile="budget").run(bundle, packet=load_packet(packet_path))
    return dossier.to_dict()


def _score(dossier: dict, gold: dict, source: str, threshold: float) -> float:
    union = recall.merged(
        [(c["anchor_start"], c["anchor_end"]) for c in dossier["semantic"]["claims"]]
    )
    located = recall.gold_spans(gold, source)
    found = [
        pid
        for pid, span, _ in located
        if recall.covered_characters(span, union) / max(1, span[1] - span[0]) >= threshold
    ]
    return len(found) / len(located)


def test_an_extraction_that_reproduces_the_gold_scores_one(tmp_path, gold, source) -> None:
    dossier = _dossier(gold, tmp_path)

    assert _score(dossier, gold, source, 0.8) == 1.0
    assert _score(dossier, gold, source, 0.5) == 1.0


def test_a_partial_extraction_scores_below_one(tmp_path, gold, source) -> None:
    """Eight claims withheld must show up as eight misses, not as a rounding wobble."""
    reduced = dict(gold)
    reduced["claims"] = gold["claims"][:17]
    keep = {claim["proposal_id"] for claim in reduced["claims"]}
    reduced["relations"] = [
        relation
        for relation in gold["relations"]
        if relation["source_id"] in keep and relation["target_id"] in keep
    ]

    score = _score(_dossier(reduced, tmp_path), gold, source, 0.8)

    assert score == pytest.approx(17 / 25)


def test_dropping_claims_lowers_the_coverage_ratio_too(tmp_path, gold, source) -> None:
    """Coverage moves with recall, but far less sharply — it is a weak proxy."""
    reduced = dict(gold)
    reduced["claims"] = gold["claims"][:17]
    keep = {claim["proposal_id"] for claim in reduced["claims"]}
    reduced["relations"] = [
        relation
        for relation in gold["relations"]
        if relation["source_id"] in keep and relation["target_id"] in keep
    ]

    full = _dossier(gold, tmp_path)["semantic"]["coverage"]
    partial = _dossier(reduced, tmp_path / "b")["semantic"]["coverage"]

    assert partial["ratio"] < full["ratio"]
    assert len(partial["gaps"]) >= len(full["gaps"])


def test_a_gold_span_absent_from_the_source_is_reported_not_counted(source, capsys) -> None:
    broken = {"claims": [{"proposal_id": "C99", "raw_span": "this sentence is invented"}]}

    located = recall.gold_spans(broken, source)

    assert located == []
    assert "gold span not in source" in capsys.readouterr().err


def test_overlapping_live_claims_do_not_inflate_the_score() -> None:
    union = recall.merged([(0, 50), (0, 50), (10, 30)])

    assert union == [[0, 50]]
    assert recall.covered_characters((0, 50), union) == 50


def test_offsets_win_over_a_repeated_formula(capsys) -> None:
    """The motivation for carrying offsets: legal prose repeats whole sentences."""
    document = "The Court finds no violation. Other matter. The Court finds no violation."
    packet = {
        "claims": [
            {
                "proposal_id": "G01",
                "raw_span": "The Court finds no violation.",
                "begin": 44,
                "end": 73,
            }
        ]
    }

    located = recall.gold_spans(packet, document)

    assert located == [("G01", (44, 73), "The Court finds no violation.")]
    assert capsys.readouterr().err == ""


def test_offsets_that_quote_other_text_are_rejected_not_silently_searched(capsys) -> None:
    packet = {"claims": [{"proposal_id": "G01", "raw_span": "alpha", "begin": 0, "end": 5}]}

    located = recall.gold_spans(packet, "beta alpha")

    assert located == []
    assert "gold offsets do not quote the span" in capsys.readouterr().err


def test_a_packet_without_offsets_still_falls_back_to_searching(source, gold) -> None:
    stripped = {
        "claims": [
            {"proposal_id": c["proposal_id"], "raw_span": c["raw_span"]} for c in gold["claims"]
        ]
    }

    assert len(recall.gold_spans(stripped, source)) == len(gold["claims"])


def _gold(*spans: tuple[str, int, int]) -> list[tuple[str, tuple[int, int], str]]:
    return [(proposal_id, (start, end), "x") for proposal_id, start, end in spans]


def test_the_share_per_span_is_ranked_by_coverage_not_by_id() -> None:
    gold = _gold(("G01", 0, 100), ("G02", 200, 300))
    union = [[0, 50], [200, 290]]

    assert recall.shares(gold, union) == [("G02", 0.9, 100), ("G01", 0.5, 100)]


def test_a_span_no_anchor_reaches_has_a_share_of_zero() -> None:
    assert recall.shares(_gold(("G01", 0, 100)), [[500, 600]]) == [("G01", 0.0, 100)]


def test_the_border_band_includes_the_threshold_and_both_its_edges() -> None:
    """A span on the threshold is the most fragile there is, and 5 points is 5."""
    rows = [("G01", 0.80, 100), ("G02", 0.85, 100), ("G03", 0.75, 100)]

    assert recall.knife_edge(rows, 0.8) == [("G01", 0.80), ("G02", 0.85), ("G03", 0.75)]


def test_a_span_far_from_the_threshold_is_not_in_the_border_band() -> None:
    rows = [("G01", 0.99, 100), ("G02", 0.10, 100), ("G03", 0.86, 100)]

    assert recall.knife_edge(rows, 0.8) == []
