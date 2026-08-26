"""Minimal DeepSeek API adapter with local validation and secret-safe errors."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, replace
from typing import Any

from .gate import sha256_text
from .models import Rejection, RelationProposal, SchemaError, SemanticPacket
from .prompts import extraction_prompt
from .settings import effective_api_key


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
        self.api_key = api_key or effective_api_key()
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
                "User-Agent": "content-review/0.2-alpha",
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
        self,
        document_id: str,
        document: str,
        model: str = "deepseek-v4-flash",
        profile: str = "general",
    ) -> SemanticPacket:
        system, user = extraction_prompt(document_id, document, profile)
        validation_error: SchemaError | None = None
        for validation_attempt in range(2):
            active_system = system
            if validation_error is not None:
                active_system += (
                    "\n\nYour previous JSON was rejected by the local closed-schema gate: "
                    f"{validation_error}. Regenerate the complete JSON object. Correct the "
                    "schema violation; do not add new fields. Omit any uncertain relation."
                )
            response, metadata = self.complete_json(
                system=active_system,
                user=user,
                config=ModelConfig(model_id=model, thinking=False),
                max_tokens=16384,
            )
            packet_data = {
                "schema_version": "content-review.semantic-packet/0.2",
                "document_id": document_id,
                "provenance": {
                    "provider": "deepseek",
                    "model_id": str(metadata["model"]),
                    "run_id": str(uuid.uuid4()),
                    "prompt_hash": sha256_text(active_system + "\n" + user),
                    "output_hash": str(metadata["output_hash"]),
                    "temperature": 0.0,
                },
                "claims": response.get("claims"),
                "relations": response.get("relations", []),
            }
            try:
                return SemanticPacket.from_dict(packet_data)
            except SchemaError as exc:
                validation_error = exc
                if validation_attempt == 0:
                    continue
                recovered = _reject_invalid_relations(packet_data)
                if recovered is not None:
                    return recovered
                raise ProviderError(
                    f"DeepSeek extraction failed local schema validation: {exc}"
                ) from exc

        raise AssertionError("unreachable")


def _reject_invalid_relations(packet_data: dict[str, Any]) -> SemanticPacket | None:
    """Fail closed per malformed edge while preserving an auditable rejection."""
    raw_relations = packet_data.get("relations")
    if not isinstance(raw_relations, list):
        return None
    valid_relations: list[dict[str, Any]] = []
    rejections: list[Rejection] = []
    for index, item in enumerate(raw_relations, start=1):
        try:
            if not isinstance(item, dict):
                raise SchemaError("relation must be object")
            RelationProposal.from_dict(item)
        except SchemaError as exc:
            rejections.append(
                Rejection("relation", f"R{index:03d}", f"closed_schema_rejection: {exc}")
            )
        else:
            valid_relations.append(item)
    if not rejections:
        return None
    sanitized = dict(packet_data)
    sanitized["relations"] = valid_relations
    try:
        packet = SemanticPacket.from_dict(sanitized)
    except SchemaError:
        return None
    return replace(packet, relation_rejections=tuple(rejections))


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
