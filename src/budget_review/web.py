"""Small local, bilingual web interface for Content Review."""

# ruff: noqa: E501 - translations, embedded HTML and CSS remain readable as complete fragments.

from __future__ import annotations

import html
import re
import secrets
import sys
import threading
import traceback
import webbrowser
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .ingest import SourceBundle
from .pipeline import ReviewPipeline
from .provider import DeepSeekProvider, ProviderError
from .render import render_html
from .settings import (
    LANGUAGES,
    api_key_source,
    effective_api_key,
    load_settings,
    save_settings,
)

MAX_BODY_BYTES = 2_000_000
# Redirects only ever return to a page this app actually serves.
REDIRECT_TARGETS = ("/", "/settings")

TEXT = {
    "de": {
        "app": "Content Review",
        "review": "Prüfen",
        "settings": "Einstellungen",
        "headline": "Inhalt prüfen, nicht Oberfläche",
        "lead": "Der Text wird zuerst in Claims und Relationen zerlegt. Erst danach prüfen unabhängige Perspektiven die inhaltliche Tragfähigkeit.",
        "document_id": "Dokumentname",
        "text": "Text",
        "text_placeholder": "Text hier einfügen …",
        "profile": "Prüfprofil",
        "general": "Allgemeiner Inhalt",
        "budget": "Antrag und Budget",
        "reviewers": "Zwei Anti-Delphi-Prüfer verwenden",
        "start": "Prüfung starten",
        "key_missing": "Für eine Live-Prüfung muss zuerst ein DeepSeek API-Key hinterlegt werden.",
        "settings_headline": "API und Sprache",
        "settings_lead": "Der Schlüssel bleibt auf diesem Rechner und wird weder im Dossier noch in Logs ausgegeben.",
        "key": "DeepSeek API-Key",
        "key_saved": "Ein API-Key ist hinterlegt",
        "key_environment": "Ein API-Key kommt aus der Serverumgebung",
        "key_none": "Noch kein API-Key hinterlegt",
        "key_hint": "Leer lassen, um den vorhandenen Schlüssel beizubehalten.",
        "clear": "Gespeicherten Schlüssel entfernen",
        "language": "Sprache der Oberfläche",
        "save": "Einstellungen speichern",
        "saved": "Einstellungen gespeichert.",
        "security": "Lokale Alpha: Die Einstellungsdatei ist nur für den angemeldeten Benutzer lesbar. Der Server bindet standardmäßig ausschließlich an 127.0.0.1.",
        "working": "Die Prüfung kann einige Minuten dauern.",
        "error": "Die Prüfung konnte nicht abgeschlossen werden",
        "back": "Zurück zur Prüfung",
    },
    "en": {
        "app": "Content Review",
        "review": "Review",
        "settings": "Settings",
        "headline": "Review content, not polish",
        "lead": "The text is first decomposed into claims and relations. Only then do independent perspectives inspect its internal support.",
        "document_id": "Document name",
        "text": "Text",
        "text_placeholder": "Paste text here …",
        "profile": "Review profile",
        "general": "General content",
        "budget": "Proposal and budget",
        "reviewers": "Use both Anti-Delphi reviewers",
        "start": "Start review",
        "key_missing": "Add a DeepSeek API key before starting a live review.",
        "settings_headline": "API and language",
        "settings_lead": "The key stays on this machine and is never written to dossiers or logs.",
        "key": "DeepSeek API key",
        "key_saved": "An API key is stored",
        "key_environment": "An API key is provided by the server environment",
        "key_none": "No API key has been added",
        "key_hint": "Leave blank to keep the existing key.",
        "clear": "Remove stored key",
        "language": "Interface language",
        "save": "Save settings",
        "saved": "Settings saved.",
        "security": "Local alpha: the settings file is readable only by the signed-in operating-system user. By default the server binds only to 127.0.0.1.",
        "working": "The review may take a few minutes.",
        "error": "The review could not be completed",
        "back": "Back to review",
    },
}


def _safe_document_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-")
    return cleaned[:80] or "document"


def _layout(language: str, title: str, body: str, token: str, path: str = "/") -> str:
    t = TEXT[language]
    other = "en" if language == "de" else "de"
    switch = "English" if other == "en" else "Deutsch"
    back = path if path in REDIRECT_TARGETS else "/"
    return f"""<!doctype html>
<html lang="{language}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · Content Review</title><style>{_CSS}</style></head>
<body><main><nav><a class="brand" href="/">{t["app"]}</a><div>
<a href="/">{t["review"]}</a><a href="/settings">{t["settings"]}</a>
<form class="lang" method="post" action="/language">
<input type="hidden" name="token" value="{token}">
<input type="hidden" name="value" value="{other}">
<input type="hidden" name="next" value="{back}">
<button type="submit">{switch}</button></form></div></nav>{body}
<footer>Alpha · ClaimGraph + Layer 9 · Human merge authority</footer></main>
<script>document.querySelectorAll('form:not(.lang)').forEach(f=>f.addEventListener('submit',()=>{{
const b=f.querySelector('button[type=submit]');if(b){{b.disabled=true;b.textContent='…';}}
}}));</script></body></html>"""


def render_home(language: str, token: str, message: str = "") -> str:
    t = TEXT[language]
    notice = f'<p class="notice">{html.escape(message)}</p>' if message else ""
    body = f"""<section class="hero"><p class="eyebrow">Content Review · Alpha</p>
<h1>{t["headline"]}</h1><p>{t["lead"]}</p></section>{notice}
<form method="post" action="/review"><input type="hidden" name="token" value="{token}">
<label>{t["document_id"]}<input name="document_id" value="document" maxlength="80"></label>
<label>{t["text"]}<textarea name="text" required placeholder="{t["text_placeholder"]}"></textarea></label>
<div class="row"><label>{t["profile"]}<select name="profile"><option value="general">{t["general"]}</option>
<option value="budget">{t["budget"]}</option></select></label>
<label class="check"><input type="checkbox" name="live_review" value="yes" checked> {t["reviewers"]}</label></div>
<button type="submit">{t["start"]}</button><p class="hint">{t["working"]}</p></form>"""
    return _layout(language, t["review"], body, token, "/")


def render_settings(language: str, token: str, message: str = "") -> str:
    t = TEXT[language]
    settings = load_settings()
    source = api_key_source()
    status_key = {
        "settings": "key_saved",
        "environment": "key_environment",
        "missing": "key_none",
    }[source]
    masked = f" · {html.escape(settings.masked_api_key)}" if settings.masked_api_key else ""
    notice = f'<p class="notice success">{html.escape(message)}</p>' if message else ""
    checked_de = " selected" if language == "de" else ""
    checked_en = " selected" if language == "en" else ""
    body = f"""<section class="hero"><p class="eyebrow">{t["settings"]}</p>
<h1>{t["settings_headline"]}</h1><p>{t["settings_lead"]}</p></section>{notice}
<form method="post" action="/settings"><input type="hidden" name="token" value="{token}">
<div class="status"><strong>{t[status_key]}{masked}</strong></div>
<label>{t["key"]}<input type="password" name="api_key" autocomplete="new-password" spellcheck="false"></label>
<p class="hint">{t["key_hint"]}</p>
<label class="check"><input type="checkbox" name="clear_api_key" value="yes"> {t["clear"]}</label>
<label>{t["language"]}<select name="language"><option value="de"{checked_de}>Deutsch</option>
<option value="en"{checked_en}>English</option></select></label>
<button type="submit">{t["save"]}</button><p class="security">{t["security"]}</p></form>"""
    return _layout(language, t["settings"], body, token, "/settings")


class ContentReviewHandler(BaseHTTPRequestHandler):
    server_version = "ContentReview/0.2-alpha"
    csrf_token = ""

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        try:
            self._handle_get(urlparse(self.path).path)
        except Exception:
            self._fail()

    def do_POST(self) -> None:
        try:
            self._handle_post(urlparse(self.path).path)
        except Exception:
            self._fail()

    def _handle_get(self, path: str) -> None:
        language = load_settings().language
        if path == "/":
            self._html(render_home(language, self.csrf_token))
        elif path == "/settings":
            self._html(render_settings(language, self.csrf_token))
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def _handle_post(self, path: str) -> None:
        data = self._form_data()
        if data is None:
            return
        if not secrets.compare_digest(data.get("token", [""])[0], self.csrf_token):
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if path == "/settings":
            self._save_settings(data)
        elif path == "/language":
            self._switch_language(data)
        elif path == "/review":
            self._run_review(data, load_settings().language)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def _switch_language(self, data: dict[str, list[str]]) -> None:
        requested = data.get("value", [""])[0]
        if requested in LANGUAGES:
            save_settings(language=requested)
        self._redirect(data.get("next", ["/"])[0])

    def _save_settings(self, data: dict[str, list[str]]) -> None:
        current = load_settings().language
        requested = data.get("language", [current])[0]
        saved = save_settings(
            language=requested if requested in LANGUAGES else current,
            api_key=data.get("api_key", [""])[0],
            clear_api_key=data.get("clear_api_key", [""])[0] == "yes",
        )
        self._html(render_settings(saved.language, self.csrf_token, TEXT[saved.language]["saved"]))

    def _fail(self) -> None:
        """One malformed request must not take the handler thread down with it."""
        traceback.print_exc(file=sys.stderr)
        try:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)
        except OSError:
            pass

    def _run_review(self, data: dict[str, list[str]], language: str) -> None:
        t = TEXT[language]
        if not effective_api_key():
            self._html(
                render_settings(language, self.csrf_token, t["key_missing"]), HTTPStatus.BAD_REQUEST
            )
            return
        text = data.get("text", [""])[0].strip()
        if not text:
            self._html(render_home(language, self.csrf_token, t["text"]), HTTPStatus.BAD_REQUEST)
            return
        document_id = _safe_document_id(data.get("document_id", ["document"])[0])
        profile = data.get("profile", ["general"])[0]
        if profile not in {"general", "budget"}:
            profile = "general"
        source = SourceBundle(document_id, text, ("web-input",))
        try:
            provider = DeepSeekProvider(api_key=effective_api_key())
            dossier = ReviewPipeline(provider, profile=profile, language=language).run(
                source,
                live_review=data.get("live_review", [""])[0] == "yes",
            )
            timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            output = Path("review-output") / "web" / f"{document_id}-{timestamp}"
            ReviewPipeline.write(dossier, output, language)
            self._html(render_html(dossier, language=language, navigation=True))
        except (ProviderError, ValueError, OSError) as exc:
            body = (
                f'<section class="hero"><h1>{t["error"]}</h1>'
                f'<p class="notice">{html.escape(str(exc))}</p>'
                f'<p><a href="/">{t["back"]}</a></p></section>'
            )
            self._html(_layout(language, t["error"], body, self.csrf_token), HTTPStatus.BAD_GATEWAY)

    def _form_data(self) -> dict[str, list[str]] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST)
            return None
        if length <= 0:
            self.send_error(HTTPStatus.BAD_REQUEST)
            return None
        if length > MAX_BODY_BYTES:
            self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return None
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("application/x-www-form-urlencoded"):
            self.send_error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            return None
        try:
            body = self.rfile.read(length).decode("utf-8")
        except UnicodeDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST)
            return None
        return parse_qs(body, keep_blank_values=True)

    def _html(self, value: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = value.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(payload)

    def _redirect(self, target: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", target if target in REDIRECT_TARGETS else "/")
        self.send_header("Content-Length", "0")
        self.end_headers()


def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    token = secrets.token_urlsafe(32)
    handler = type("ConfiguredContentReviewHandler", (ContentReviewHandler,), {"csrf_token": token})
    server = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{server.server_port}/"
    print(f"Content Review: {url}")
    print("Stop with Ctrl+C")
    if open_browser:
        threading.Timer(0.4, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


_CSS = """
:root{color-scheme:light;--ink:#18202a;--muted:#69727d;--line:#dfe3e8;--paper:#fff;--ground:#f4f5f7;--accent:#2457d6}
*{box-sizing:border-box}body{margin:0;background:var(--ground);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{width:min(880px,calc(100% - 32px));margin:0 auto 64px}nav{display:flex;justify-content:space-between;align-items:center;padding:22px 0}nav div{display:flex;gap:18px;align-items:center}
form.lang{display:inline;background:none;border:0;border-radius:0;padding:0;margin:0;box-shadow:none;gap:0}
form.lang button{background:none;color:var(--accent);padding:0;font:inherit;font-weight:400}a{color:var(--accent);text-decoration:none}.brand{color:var(--ink);font-weight:800}
.hero{padding:52px 0 26px;max-width:720px}.eyebrow{color:var(--accent);font-size:.78rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase}h1{font-size:clamp(2.2rem,7vw,4.4rem);line-height:1;letter-spacing:-.05em;margin:8px 0 18px}.hero p{color:var(--muted);font-size:1.05rem}
form{display:grid;gap:18px;background:var(--paper);border:1px solid var(--line);border-radius:18px;padding:26px;box-shadow:0 4px 20px rgba(16,24,40,.04)}label{display:grid;gap:7px;font-weight:700}input,textarea,select{width:100%;font:inherit;border:1px solid #cbd1d8;border-radius:10px;padding:11px 12px;background:#fff}textarea{min-height:320px;resize:vertical}.row{display:grid;grid-template-columns:1fr 1fr;gap:18px}.check{display:flex;align-items:center;align-self:end;font-weight:500;padding:11px 0}.check input{width:auto}button{border:0;border-radius:10px;background:var(--accent);color:#fff;padding:13px 18px;font:inherit;font-weight:800;cursor:pointer}button:disabled{opacity:.55}.hint,.security{margin:-8px 0 0;color:var(--muted);font-size:.84rem}.notice,.status{padding:13px 15px;border-radius:10px;background:#fff4e5;border:1px solid #fedf89}.success{background:#ecfdf3;border-color:#abefc6}.status{background:#f7f9fc;border-color:var(--line)}footer{color:var(--muted);font-size:.8rem;text-align:center;margin-top:34px}@media(max-width:650px){.row{grid-template-columns:1fr}nav div{gap:10px}.hero{padding-top:30px}form{padding:18px}}
"""


__all__ = ["ContentReviewHandler", "render_home", "render_settings", "serve"]
