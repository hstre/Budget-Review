from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from budget_review.models import SemanticPacket
from budget_review.provider import ProviderError
from budget_review.settings import load_settings
from budget_review.web import ContentReviewHandler

TOKEN = "test-csrf-token"
FORM = "application/x-www-form-urlencoded"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTENT_REVIEW_CONFIG_DIR", str(tmp_path))
    handler = type("ConfiguredHandler", (ContentReviewHandler,), {"csrf_token": TOKEN})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _call(base, path, body=None, content_type=FORM, follow=True):
    headers = {"Content-Type": content_type} if body is not None else {}
    request = urllib.request.Request(
        base + path, data=body, headers=headers, method="POST" if body is not None else "GET"
    )
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request) as response:
            return response.status, response.headers
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers


def test_language_is_not_changed_by_a_get(server) -> None:
    """A cross-site <img> must not be able to write settings."""
    status, _ = _call(server, "/language?value=en")

    assert status == 404
    assert load_settings().language == "de"


def test_language_switch_requires_the_csrf_token(server) -> None:
    status, _ = _call(server, "/language", b"value=en")

    assert status == 403
    assert load_settings().language == "de"


def test_language_switch_accepts_a_token_carrying_post(server) -> None:
    status, headers = _call(
        server, "/language", b"token=" + TOKEN.encode() + b"&value=en&next=/settings", follow=False
    )

    assert status == 303
    assert headers.get("Location") == "/settings"
    assert load_settings().language == "en"


def test_redirect_never_leaves_the_application(server) -> None:
    _, headers = _call(
        server,
        "/language",
        b"token=" + TOKEN.encode() + b"&value=en&next=//evil.example/x",
        follow=False,
    )

    assert headers.get("Location") == "/"


@pytest.mark.parametrize(
    ("body", "content_type", "expected"),
    [
        (b"", FORM, 400),
        (b"token=" + TOKEN.encode() + b"&text=\xff\xfe", FORM, 400),
        (b"token=" + TOKEN.encode(), "text/plain", 415),
    ],
)
def test_malformed_bodies_are_refused_cleanly(server, body, content_type, expected) -> None:
    status, _ = _call(server, "/settings", body, content_type=content_type)

    assert status == expected
    assert _call(server, "/")[0] == 200, "the server must still be serving"


def test_unknown_language_keeps_the_current_one(server) -> None:
    status, _ = _call(server, "/settings", b"token=" + TOKEN.encode() + b"&language=fr")

    assert status == 200
    assert load_settings().language == "de"


def test_post_routing_ignores_the_query_string(server) -> None:
    status, _ = _call(server, "/settings?anything=1", b"token=" + TOKEN.encode() + b"&language=en")

    assert status == 200
    assert load_settings().language == "en"


def test_responses_carry_the_hardening_headers(server) -> None:
    _, headers = _call(server, "/")

    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]


REVIEW_TEXT = "Remote work raises output. The survey measured impressions only."


def _packet(document_id: str) -> SemanticPacket:
    def claim(proposal_id: str, claim_type: str, span: str) -> dict:
        return {
            "proposal_id": proposal_id,
            "claim_type": claim_type,
            "canonical_content": span,
            "raw_span": span,
            "confidence": 0.9,
            "source_ref": document_id,
        }

    return SemanticPacket.from_dict(
        {
            "schema_version": "content-review.semantic-packet/0.2",
            "document_id": document_id,
            "provenance": {
                "provider": "deepseek",
                "model_id": "deepseek-v4-flash",
                "run_id": "run-1",
                "prompt_hash": "a" * 16,
                "output_hash": "b" * 16,
            },
            "claims": [
                claim("C01", "thesis", "Remote work raises output."),
                claim("C02", "fact", "The survey measured impressions only."),
            ],
            "relations": [
                {
                    "source_id": "C02",
                    "relation_type": "CONTRADICTS",
                    "target_id": "C01",
                    "confidence": 0.9,
                    "rationale": "The measurement contradicts the thesis.",
                }
            ],
        }
    )


def _install_provider(monkeypatch, failure: ProviderError | None = None) -> list[str]:
    """Replace the handler's provider so a review runs without a key or network."""
    seen: list[str] = []

    class StubProvider:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def extract(self, document_id, document, model="", profile="general"):
            seen.append(document_id)
            if failure is not None:
                raise failure
            return _packet(document_id)

        def complete_json(self, **kwargs):
            return {"findings": []}, {
                "model": "deepseek-v4-flash",
                "usage": {},
                "output_hash": "c" * 16,
            }

    monkeypatch.setattr("budget_review.web.DeepSeekProvider", StubProvider)
    return seen


def _review_body(**fields: str) -> bytes:
    form = {"token": TOKEN, "text": REVIEW_TEXT, "document_id": "essay", **fields}
    return urllib.parse.urlencode(form).encode()


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    return tmp_path


def _written(workspace: Path) -> Path:
    directories = sorted((workspace / "review-output" / "web").iterdir())
    assert len(directories) == 1
    return directories[0]


def test_a_review_without_a_key_sends_the_user_to_settings(server, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    status, _ = _call(server, "/review", _review_body())

    assert status == 400


def test_a_review_without_text_is_refused(server, workspace, monkeypatch) -> None:
    _install_provider(monkeypatch)

    status, _ = _call(server, "/review", _review_body(text="   "))

    assert status == 400
    assert not (workspace / "review-output").exists()


def test_a_successful_review_renders_and_writes_the_dossier(
    server, workspace, monkeypatch
) -> None:
    _install_provider(monkeypatch)

    status, _ = _call(server, "/review", _review_body())

    assert status == 200
    written = _written(workspace)
    assert written.name.startswith("essay-")
    assert {path.name for path in written.iterdir()} == {
        "dossier.json",
        "dossier.md",
        "dossier.html",
    }
    audit = json.loads((written / "dossier.json").read_text(encoding="utf-8"))
    assert sorted(item["category"] for item in audit["findings"]) == [
        "internal_contradiction",
        "logical_gap",
    ]


def test_the_document_id_cannot_escape_the_output_directory(
    server, workspace, monkeypatch
) -> None:
    _install_provider(monkeypatch)

    _call(server, "/review", _review_body(document_id="../../etc/passwd"))

    written = _written(workspace)
    assert written.parent == workspace / "review-output" / "web"
    assert "/" not in written.name
    assert not (workspace / "etc").exists()


def test_a_provider_failure_becomes_an_error_page_not_a_traceback(
    server, workspace, monkeypatch
) -> None:
    _install_provider(monkeypatch, failure=ProviderError("DeepSeek request failed: HTTP 401"))

    status, _ = _call(server, "/review", _review_body())

    assert status == 502
    assert _call(server, "/")[0] == 200, "the server must still be serving"


def test_the_error_page_escapes_the_provider_message(server, workspace, monkeypatch) -> None:
    _install_provider(monkeypatch, failure=ProviderError("<script>alert('x')</script>"))

    request = urllib.request.Request(
        server + "/review", data=_review_body(), headers={"Content-Type": FORM}, method="POST"
    )
    try:
        urllib.request.urlopen(request)
        raise AssertionError("expected an error response")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")

    assert "<script>alert" not in body
    assert "&lt;script&gt;" in body


def test_an_unknown_profile_falls_back_to_general(server, workspace, monkeypatch) -> None:
    _install_provider(monkeypatch)

    _call(server, "/review", _review_body(profile="funding-decision"))

    audit = json.loads((_written(workspace) / "dossier.json").read_text(encoding="utf-8"))
    assert audit["profile"] == "general"


def test_the_interface_language_reaches_the_written_dossier(
    server, workspace, monkeypatch
) -> None:
    _install_provider(monkeypatch)
    _call(server, "/language", b"token=" + TOKEN.encode() + b"&value=en&next=/")

    _call(server, "/review", _review_body())

    written = _written(workspace)
    assert "Reviewer dossier" in (written / "dossier.md").read_text(encoding="utf-8")
    assert 'lang="en"' in (written / "dossier.html").read_text(encoding="utf-8")
