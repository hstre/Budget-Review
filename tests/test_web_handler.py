from __future__ import annotations

import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

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
