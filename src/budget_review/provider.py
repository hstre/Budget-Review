"""Minimal DeepSeek API adapter with local validation and secret-safe errors."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any

from .gate import sha256_text
from .models import SchemaError, SemanticPacket
from .prompts import extraction_prompt


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelConfig:
    model_id: str
    thinking: bool = False
    reasoning_effort: str = "high"


class DeepSeekProvider:
    """OpenAI-compatible DeepSeek client using only the Python standard library."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
        retries: int = 2,
    ) -> None:
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if not self.api_key:
            raise ProviderError("DEEPSEEK_API_KEY is not configured")
        self.base_url = (
            base_url or os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"
        ).rstrip("/")
        self.timeout = timeout
        self.retries = retries

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        config: ModelConfig,
        max_tokens: int = 8192,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        payload: dict[str, Any] = {
            "model": config.model_id,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": max_tokens,
            "temperature": 0.0,
            "stream": False,
            "thinking": {"type": "enabled" if config.thinking else "disabled"},
        }
        if config.thinking:
            payload["reasoning_effort"] = config.reasoning_effort
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "budget-review/0.1-alpha",
            },
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    envelope = json.loads(response.read().decode("utf-8"))
                choice = envelope["choices"][0]
                if choice.get("finish_reason") == "length":
                    raise ProviderError("DeepSeek output was truncated; raise max_tokens")
                content = choice["message"].get("content")
                if not isinstance(content, str) or not content.strip():
                    raise ProviderError("DeepSeek returned empty JSON content")
                parsed = json.loads(_strip_fence(content))
                if not isinstance(parsed, dict):
                    raise ProviderError("DeepSeek JSON root must be an object")
                usage = envelope.get("usage") or {}
                metadata = {
                    "model": envelope.get("model", config.model_id),
                    "system_fingerprint": envelope.get("system_fingerprint", ""),
                    "usage": usage,
                    "output_hash": sha256_text(content),
                }
                return parsed, metadata
            except (
                urllib.error.URLError,
                TimeoutError,
                json.JSONDecodeError,
                KeyError,
                ProviderError,
            ) as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                time.sleep(0.5 * (2**attempt))
        # Never include headers, request bodies or secrets in the exception.
        raise ProviderError(f"DeepSeek request failed: {type(last_error).__name__}") from last_error

    def extract(
        self, document_id: str, document: str, model: str = "deepseek-v4-flash"
    ) -> SemanticPacket:
        system, user = extraction_prompt(document_id, document)
        response, metadata = self.complete_json(
            system=system,
            user=user,
            config=ModelConfig(model_id=model, thinking=False),
            max_tokens=16384,
        )
        packet_data = {
            "schema_version": "budget-review.semantic-packet/0.1",
            "document_id": document_id,
            "provenance": {
                "provider": "deepseek",
                "model_id": str(metadata["model"]),
                "run_id": str(uuid.uuid4()),
                "prompt_hash": sha256_text(system + "\n" + user),
                "output_hash": str(metadata["output_hash"]),
                "temperature": 0.0,
            },
            "claims": response.get("claims"),
            "relations": response.get("relations", []),
        }
        try:
            return SemanticPacket.from_dict(packet_data)
        except SchemaError as exc:
            raise ProviderError(
                f"DeepSeek extraction failed local schema validation: {exc}"
            ) from exc


def _strip_fence(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


__all__ = ["DeepSeekProvider", "ModelConfig", "ProviderError"]
