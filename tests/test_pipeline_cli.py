from __future__ import annotations

import json

from budget_review.cli import main
from budget_review.pipeline import ReviewPipeline


def test_offline_pipeline(controlled_source, controlled_packet) -> None:
    dossier = ReviewPipeline().run(controlled_source, packet=controlled_packet)
    assert len(dossier.semantic.claims) == 25
    assert len(dossier.semantic.relations) == 15
    assert len(dossier.findings) == 8


def test_write_both_audit_formats(tmp_path, controlled_source, controlled_packet) -> None:
    dossier = ReviewPipeline().run(controlled_source, packet=controlled_packet)
    json_path, markdown_path = ReviewPipeline.write(dossier, tmp_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "budget-review.dossier/0.1"
    assert "## ClaimGraph: Claims" in markdown_path.read_text(encoding="utf-8")


def test_demo_cli(tmp_path, capsys) -> None:
    exit_code = main(["demo", "--json", "--output", str(tmp_path)])
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["claims"] == 25
    assert output["relations"] == 15
    assert output["findings"] == 8


def test_offline_review_without_packet_fails(fixture_dir, tmp_path, capsys) -> None:
    exit_code = main(
        [
            "review",
            str(fixture_dir / "proposal.md"),
            "--provider",
            "offline",
            "--output",
            str(tmp_path),
        ]
    )
    assert exit_code == 2
    assert "offline mode requires --packet" in capsys.readouterr().err
