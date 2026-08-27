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
