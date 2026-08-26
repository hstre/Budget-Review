from __future__ import annotations

import json

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
