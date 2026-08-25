from __future__ import annotations

import json
from pathlib import Path

import pytest

from budget_review.gate import govern_packet
from budget_review.ingest import ingest
from budget_review.pipeline import load_packet


@pytest.fixture(scope="session")
def fixture_dir() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "src"
        / "budget_review"
        / "fixtures"
        / "coherence_theatre"
    )


@pytest.fixture(scope="session")
def controlled_source(fixture_dir: Path):
    return ingest([fixture_dir / "proposal.md"], document_id="regional-skills-bridge")


@pytest.fixture(scope="session")
def controlled_packet(fixture_dir: Path):
    return load_packet(fixture_dir / "semantic_packet.json")


@pytest.fixture(scope="session")
def controlled_semantic(controlled_source, controlled_packet):
    return govern_packet(controlled_source.text, controlled_packet)


@pytest.fixture(scope="session")
def expected_findings(fixture_dir: Path):
    return json.loads((fixture_dir / "expected_findings.json").read_text(encoding="utf-8"))[
        "known_findings"
    ]
