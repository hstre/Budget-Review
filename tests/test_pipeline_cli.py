from __future__ import annotations

import json

from budget_review.cli import main
from budget_review.pipeline import ReviewPipeline


def test_offline_pipeline(controlled_source, controlled_packet) -> None:
    dossier = ReviewPipeline(profile="budget").run(controlled_source, packet=controlled_packet)
    assert len(dossier.semantic.claims) == 25
    assert len(dossier.semantic.relations) == 15
    assert len(dossier.findings) == 10


def test_write_all_audit_formats(tmp_path, controlled_source, controlled_packet) -> None:
    dossier = ReviewPipeline(profile="budget").run(controlled_source, packet=controlled_packet)
    json_path, markdown_path, html_path = ReviewPipeline.write(dossier, tmp_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "content-review.dossier/0.2"
    assert payload["profile"] == "budget"
    assert "10 konsolidierte Punkte" in markdown_path.read_text(encoding="utf-8")
    html = html_path.read_text(encoding="utf-8")
    assert "<strong>10</strong><span>Prüfpunkte</span>" in html
    assert "Originalaussagen ansehen" in html


def test_demo_cli(tmp_path, capsys) -> None:
    exit_code = main(["demo", "--json", "--output", str(tmp_path)])
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["profile"] == "general"
    assert output["claims"] == 5
    assert output["relations"] == 5
    assert output["findings"] == 3


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
