"""The arms' spread over a frozen graph, pinned where the measurement could cheat.

Three ways this could report stability that is not there: counting the
deterministic half, whose findings are identical by construction; treating a run
in which an arm never answered as a run that agreed; and measuring over a graph
that itself moved, which would report the extractor as the reviewer.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "reviewer_variance", ROOT / "scripts" / "reviewer_variance.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


variance = _module()


def _finding(category: str, claim_ids: list[str], **overrides) -> dict:
    base = {
        "category": category,
        "claim_ids": claim_ids,
        "reviewer_id": "evidence-arm",
        "reviewer_kind": "llm",
        "summary": "One wording",
    }
    return {**base, **overrides}


def test_the_same_claims_for_the_same_reason_are_the_same_finding() -> None:
    first = _finding("evidence_gap", ["C07", "C02"], summary="Baseline unclear")
    second = _finding("evidence_gap", ["C02", "C07"], summary="No source for the baseline")

    assert variance.finding_key(first) == variance.finding_key(second)


def test_a_different_reason_on_the_same_claims_is_a_different_finding() -> None:
    assert variance.finding_key(_finding("evidence_gap", ["C07"])) != variance.finding_key(
        _finding("causal_overclaim", ["C07"])
    )


def test_the_deterministic_half_is_not_counted_as_the_arms() -> None:
    dossier = {
        "findings": [
            _finding("evidence_gap", ["C07"]),
            _finding("arithmetic_mismatch", ["C01"], reviewer_kind="deterministic"),
        ]
    }

    assert [f["category"] for f in variance.arm_findings(dossier)] == ["evidence_gap"]


def test_a_key_missing_from_one_run_is_not_in_the_stable_core() -> None:
    runs = [{"a", "b"}, {"a", "b"}, {"a"}]

    always, flipping = variance.stability(runs)

    assert always == ["a"]
    assert flipping == [("b", 2)]


def test_a_run_without_an_answer_empties_the_stable_core() -> None:
    """An arm that dies once in five is exactly what a single run cannot see."""
    always, flipping = variance.stability([{"a"}, {"a"}, set()])

    assert always == []
    assert flipping == [("a", 2)]


def test_the_share_is_the_core_against_what_a_run_reports() -> None:
    runs = [{"a", "b"}, {"a", "b"}, {"a", "b", "c"}]
    always, _ = variance.stability(runs)

    assert variance.always_share(always, runs) == pytest.approx(2 / (7 / 3))
    assert variance.always_share([], []) == 0.0
    assert variance.always_share([], [set(), set()]) == 0.0


def test_a_graph_that_moved_is_a_different_signature() -> None:
    base = {"semantic": {"document_hash": "h", "claims": [{"proposal_id": "C01"}]}}
    grown = {
        "semantic": {
            "document_hash": "h",
            "claims": [{"proposal_id": "C01"}, {"proposal_id": "C02"}],
        }
    }

    assert variance.graph_signature(base) != variance.graph_signature(grown)


class _StubProvider:
    """Two arms per run; the second run's evidence gap names a different claim."""

    def __init__(self) -> None:
        self.calls = 0

    def complete_json(self, *, system, user, config, max_tokens=8192):  # noqa: ANN001
        self.calls += 1
        claim = "C01" if self.calls <= 2 else "C02"
        payload = {
            "findings": [
                {
                    "finding_id": "F01",
                    "category": "evidence_gap",
                    "severity": "medium",
                    "summary": "No source named",
                    "claim_ids": [claim],
                    "explanation": "The graph carries a figure and no evidence claim.",
                    "question_for_reviewer": "Which source supports it?",
                    "confidence": 0.7,
                }
            ]
        }
        return payload, {"model": config.model_id, "usage": {}, "output_hash": "0" * 16}


def test_two_runs_over_the_frozen_packet_report_their_spread(monkeypatch, tmp_path, capsys) -> None:
    """The call site: the arms must actually be run live over the frozen graph."""
    import sys

    stub = _StubProvider()
    monkeypatch.setattr(variance, "DeepSeekProvider", lambda *a, **k: stub)
    monkeypatch.setattr(
        sys, "argv", ["reviewer_variance.py", str(tmp_path), "--runs", "2", "--profile", "budget"]
    )

    assert variance.main() == 0
    assert stub.calls == 4, "two arms per run, both live"

    report = capsys.readouterr().out
    assert "In allen 2 Läufen: 0" in report, "the one arm finding moved between runs"
    # Both arms name the same claims for the same reason, so two findings are one
    # key. Reporting only the key count next to a findings count reads as an
    # arithmetic mistake, so the run line has to say both.
    assert "2 Arm-Befunde (1 verschieden)" in report
    assert "Verschiedene Befunde je Lauf: [1, 1]" in report
    written = json.loads((tmp_path / "reviewer-run-1.json").read_text(encoding="utf-8"))
    assert any(f["reviewer_kind"] == "llm" for f in written["findings"])


def test_a_failed_run_is_not_dropped_from_the_comparison() -> None:
    """Dropping it would report the surviving runs' agreement as the arms'."""
    runs = [{"a"}, set(), {"a"}]

    always, flipping = variance.stability(runs)

    assert always == [], "three runs, two hits: not stable"
    assert flipping == [("a", 2)]


def test_a_graph_that_moved_between_runs_stops_the_measurement(
    monkeypatch, tmp_path, capsys
) -> None:
    """Otherwise the extractor's spread is reported as the reviewer's."""
    import sys

    monkeypatch.setattr(variance, "DeepSeekProvider", lambda *a, **k: _StubProvider())
    signatures = iter([("h", ("C01",)), ("h", ("C01", "C02"))])
    monkeypatch.setattr(variance, "graph_signature", lambda dossier: next(signatures))
    monkeypatch.setattr(
        sys, "argv", ["reviewer_variance.py", str(tmp_path), "--runs", "2", "--profile", "budget"]
    )

    assert variance.main() == 1
    assert "sagt nichts über die Arme" in capsys.readouterr().out
