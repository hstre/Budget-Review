from __future__ import annotations

import stat

from budget_review.cli import main
from budget_review.pipeline import ReviewPipeline
from budget_review.render import render_html
from budget_review.settings import (
    api_key_source,
    effective_api_key,
    load_settings,
    save_settings,
)
from budget_review.web import render_home, render_settings


def test_settings_round_trip_and_private_permissions(tmp_path) -> None:
    path = tmp_path / "settings.json"
    saved = save_settings(language="en", api_key="ds-secret-1234", path=path)

    assert saved.language == "en"
    assert load_settings(path).api_key == "ds-secret-1234"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_stored_key_overrides_environment_and_can_be_cleared(tmp_path, monkeypatch) -> None:
    path = tmp_path / "settings.json"
    monkeypatch.setenv("DEEPSEEK_API_KEY", "environment-key")
    assert effective_api_key(path) == "environment-key"
    assert api_key_source(path) == "environment"

    save_settings(api_key="stored-key", path=path)
    assert effective_api_key(path) == "stored-key"
    assert api_key_source(path) == "settings"

    save_settings(clear_api_key=True, path=path)
    assert effective_api_key(path) == "environment-key"


def test_bilingual_pages_and_key_is_never_rendered(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CONTENT_REVIEW_CONFIG_DIR", str(tmp_path))
    save_settings(language="en", api_key="never-render-this-9876")

    home = render_home("en", "csrf")
    settings = render_settings("en", "csrf")
    assert "Review content, not polish" in home
    assert "API and language" in settings
    assert "never-render-this" not in settings
    assert "••••9876" in settings


def test_english_dossier_chrome(controlled_source, controlled_packet) -> None:
    dossier = ReviewPipeline(profile="budget").run(controlled_source, packet=controlled_packet)
    rendered = render_html(dossier, language="en", navigation=True)

    assert '<html lang="en">' in rendered
    assert "Reviewer dossier" in rendered
    assert "Review question" in rendered
    assert "New review" in rendered


def test_cli_refuses_network_binding_without_explicit_flag(capsys) -> None:
    assert main(["web", "--host", "0.0.0.0", "--no-browser"]) == 2
    assert "requires --allow-network" in capsys.readouterr().err
