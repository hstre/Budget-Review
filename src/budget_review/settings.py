"""Per-user settings for the local web interface."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

LANGUAGES = {"de", "en"}


@dataclass(frozen=True)
class AppSettings:
    language: str = "de"
    api_key: str = ""

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    @property
    def masked_api_key(self) -> str:
        if not self.api_key:
            return ""
        return "••••" + self.api_key[-4:]


def _restrict_descriptor(descriptor: int) -> None:
    """Owner-only permissions where the platform has them.

    os.chmod accepts a descriptor only where fchmod exists; on Windows it does
    not, and there is no POSIX-mode equivalent to fall back to.
    """
    if os.chmod in os.supports_fd:
        os.chmod(descriptor, 0o600)


def _restrict_path(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError:
        pass


def settings_path() -> Path:
    configured = os.environ.get("CONTENT_REVIEW_CONFIG_DIR")
    root = Path(configured).expanduser() if configured else Path.home() / ".config"
    return root / "content-review" / "settings.json"


def load_settings(path: Path | None = None) -> AppSettings:
    target = path or settings_path()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    language = payload.get("language", "de")
    api_key = payload.get("api_key", "")
    return AppSettings(
        language=language if language in LANGUAGES else "de",
        api_key=api_key.strip() if isinstance(api_key, str) else "",
    )


def effective_api_key(path: Path | None = None) -> str:
    stored = load_settings(path).api_key
    return stored or os.environ.get("DEEPSEEK_API_KEY", "").strip()


def api_key_source(path: Path | None = None) -> str:
    if load_settings(path).api_key:
        return "settings"
    if os.environ.get("DEEPSEEK_API_KEY", "").strip():
        return "environment"
    return "missing"


def save_settings(
    *,
    language: str | None = None,
    api_key: str | None = None,
    clear_api_key: bool = False,
    path: Path | None = None,
) -> AppSettings:
    target = path or settings_path()
    current = load_settings(target)
    updated = current
    if language is not None:
        if language not in LANGUAGES:
            raise ValueError("language must be de or en")
        updated = replace(updated, language=language)
    if clear_api_key:
        updated = replace(updated, api_key="")
    elif api_key is not None and api_key.strip():
        updated = replace(updated, api_key=api_key.strip())

    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = json.dumps(
        {"language": updated.language, "api_key": updated.api_key},
        ensure_ascii=False,
        indent=2,
    )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".settings-", suffix=".json", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        _restrict_descriptor(descriptor)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
        temporary.replace(target)
        _restrict_path(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return updated


__all__ = [
    "AppSettings",
    "LANGUAGES",
    "api_key_source",
    "effective_api_key",
    "load_settings",
    "save_settings",
    "settings_path",
]
