from __future__ import annotations

import http.client
import io
import json
import urllib.error

import pytest

from budget_review.provider import DeepSeekProvider, ModelConfig, ProviderError


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def test_json_completion_uses_current_model_contract(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data)
        return _Response(
            {
                "model": "deepseek-v4-flash",
                "system_fingerprint": "fp",
                "choices": [{"finish_reason": "stop", "message": {"content": '{"findings": []}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3},
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = DeepSeekProvider(api_key="test-secret", retries=0)
    result, metadata = provider.complete_json(
        system="Return json.",
        user="Review.",
        config=ModelConfig("deepseek-v4-flash", thinking=False),
    )
    assert result == {"findings": []}
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert captured["body"]["thinking"] == {"type": "disabled"}
    assert metadata["model"] == "deepseek-v4-flash"


def test_missing_key_fails_without_network(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="not configured"):
        DeepSeekProvider()


def test_extraction_receives_general_profile_contract(monkeypatch) -> None:
    captured = {}
    provider = DeepSeekProvider(api_key="test-secret", retries=0)

    def fake_complete_json(**kwargs):
        captured["system"] = kwargs["system"]
        return (
            {
                "claims": [
                    {
                        "proposal_id": "C01",
                        "claim_type": "thesis",
                        "canonical_content": "A claim.",
                        "raw_span": "A claim.",
                        "confidence": 0.9,
                        "source_ref": "example",
                    }
                ],
                "relations": [],
            },
            {"model": "deepseek-v4-flash", "output_hash": "1234567890abcdef"},
        )

    monkeypatch.setattr(provider, "complete_json", fake_complete_json)
    packet = provider.extract("example", "A claim.", profile="general")

    assert packet.schema_version == "content-review.semantic-packet/0.2"
    assert "Ignore prose quality" in captured["system"]
    assert "human-written or AI-written" in captured["system"]


def test_extraction_repairs_one_schema_violation(monkeypatch) -> None:
    calls = []
    provider = DeepSeekProvider(api_key="test-secret", retries=0)

    def fake_complete_json(**kwargs):
        calls.append(kwargs)
        relation_type = "METHOD" if len(calls) == 1 else "SUPPORTS"
        return (
            {
                "claims": [
                    {
                        "proposal_id": "C01",
                        "claim_type": "method",
                        "canonical_content": "A method is used.",
                        "raw_span": "A method is used.",
                        "confidence": 0.9,
                        "source_ref": "example",
                    },
                    {
                        "proposal_id": "C02",
                        "claim_type": "thesis",
                        "canonical_content": "A result follows.",
                        "raw_span": "A result follows.",
                        "confidence": 0.9,
                        "source_ref": "example",
                    },
                ],
                "relations": [
                    {
                        "source_id": "C01",
                        "relation_type": relation_type,
                        "target_id": "C02",
                        "confidence": 0.8,
                        "rationale": "Method supports result.",
                    }
                ],
            },
            {"model": "deepseek-v4-flash", "output_hash": "1234567890abcdef"},
        )

    monkeypatch.setattr(provider, "complete_json", fake_complete_json)
    packet = provider.extract(
        "example", "A method is used. A result follows.", profile="general"
    )

    assert len(calls) == 2
    assert "unknown relation_type: METHOD" in calls[1]["system"]
    assert packet.relations[0].relation_type.value == "SUPPORTS"


def test_extraction_rejects_bad_relation_after_repair_attempt(monkeypatch) -> None:
    provider = DeepSeekProvider(api_key="test-secret", retries=0)

    def fake_complete_json(**kwargs):
        return (
            {
                "claims": [
                    {
                        "proposal_id": "C01",
                        "claim_type": "method",
                        "canonical_content": "A method is used.",
                        "raw_span": "A method is used.",
                        "confidence": 0.9,
                        "source_ref": "example",
                    }
                ],
                "relations": [
                    {
                        "source_id": "C01",
                        "relation_type": "CAUSAL",
                        "target_id": "C01",
                        "confidence": 0.8,
                        "rationale": "Invalid model label.",
                    }
                ],
            },
            {"model": "deepseek-v4-flash", "output_hash": "1234567890abcdef"},
        )

    monkeypatch.setattr(provider, "complete_json", fake_complete_json)
    packet = provider.extract("example", "A method is used.", profile="general")

    assert packet.relations == ()
    assert packet.relation_rejections[0].item_id == "R001"
    assert "unknown relation_type: CAUSAL" in packet.relation_rejections[0].reason


def test_secret_is_not_exposed_in_transport_error(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise TimeoutError("transport failed")

    monkeypatch.setattr("urllib.request.urlopen", fail)
    secret = "do-not-print-this-secret"
    provider = DeepSeekProvider(api_key=secret, retries=0)
    with pytest.raises(ProviderError) as captured:
        provider.complete_json(
            system="Return json.",
            user="Review.",
            config=ModelConfig("deepseek-v4-flash"),
        )
    assert secret not in str(captured.value)


def _raise_http(code: int, calls: list[int]):
    def fail(request, timeout=None):
        calls.append(code)
        raise urllib.error.HTTPError(request.full_url, code, "reason", {}, io.BytesIO(b"{}"))

    return fail


def _truncated(calls: list[int]):
    class _Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def respond(request, timeout=None):
        calls.append(0)
        envelope = {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}
        return _Response(json.dumps(envelope).encode("utf-8"))

    return respond


@pytest.fixture
def instant_sleep(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)


def _complete(monkeypatch, opener):
    monkeypatch.setattr("urllib.request.urlopen", opener)
    provider = DeepSeekProvider(api_key="secret-key", retries=2)
    with pytest.raises(ProviderError) as captured:
        provider.complete_json(system="s", user="u", config=ModelConfig("deepseek-v4-flash"))
    return str(captured.value)


def test_truncated_output_is_not_paid_for_twice(monkeypatch, instant_sleep) -> None:
    """Identical request at temperature 0: a retry cannot end differently."""
    calls: list[int] = []

    message = _complete(monkeypatch, _truncated(calls))

    assert len(calls) == 1
    assert "max_tokens" in message


def test_client_error_is_not_retried_and_names_the_status(monkeypatch, instant_sleep) -> None:
    calls: list[int] = []

    message = _complete(monkeypatch, _raise_http(401, calls))

    assert len(calls) == 1
    assert "HTTP 401" in message
    assert "secret-key" not in message


def test_rate_limit_and_upstream_errors_are_retried(monkeypatch, instant_sleep) -> None:
    for code in (429, 503):
        calls: list[int] = []

        message = _complete(monkeypatch, _raise_http(code, calls))

        assert len(calls) == 3, f"HTTP {code} should be retried"
        assert f"HTTP {code}" in message


def _drops_connection(calls: list[int]):
    """A response whose body ends early — the real failure seen against DeepSeek."""

    class _Response:
        def read(self):
            raise http.client.IncompleteRead(b"partial")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def respond(request, timeout=None):
        calls.append(0)
        return _Response()

    return respond


def test_a_connection_dropped_mid_response_is_retried(monkeypatch, instant_sleep) -> None:
    """The body arrives incomplete, which a retry can fix — unlike a token limit.

    Before this was handled the exception escaped the retry loop as a traceback
    and killed the run, so a transient drop looked like a crash.
    """
    calls: list[int] = []

    message = _complete(monkeypatch, _drops_connection(calls))

    assert len(calls) == 3
    assert "IncompleteRead" in message
    assert "secret-key" not in message
