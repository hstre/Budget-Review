"""Minimal DeepSeek API adapter with local validation and secret-safe errors."""

from __future__ import annotations

import http.client
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, replace
from typing import Any

from .gate import sha256_text
from .models import (
    ClaimProposal,
    Rejection,
    RelationProposal,
    SchemaError,
    SemanticPacket,
)
from .prompts import extraction_prompt
from .settings import effective_api_key


class ProviderError(RuntimeError):
    """Transport or contract failure. Never carries headers, bodies or the API key."""


class _FatalProviderError(ProviderError):
    """A failure an identical retry cannot resolve, so it must not be paid for twice."""


# Everything else (auth, malformed request, unknown model) stays failed on retry.
_RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


def _transport_reason(error: Exception | None) -> str:
    """Name the failure precisely without revealing headers, bodies or the key."""
    if isinstance(error, urllib.error.HTTPError):
        return f"HTTP {error.code}"
    if isinstance(error, ProviderError):
        return str(error)
    return type(error).__name__


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
                    # Same request at temperature 0: a retry ends the same way.
                    raise _FatalProviderError("DeepSeek output was truncated; raise max_tokens")
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
            except _FatalProviderError:
                raise
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in _RETRYABLE_STATUS:
                    raise ProviderError(
                        f"DeepSeek request failed: HTTP {exc.code}"
                    ) from exc
                if attempt >= self.retries:
                    break
                time.sleep(0.5 * (2**attempt))
            except (
                urllib.error.URLError,
                TimeoutError,
                # The body can end early or the peer can reset after urlopen has
                # already returned. Those escape URLError, and unlike a token
                # limit they are transient, so they belong in the retry.
                http.client.HTTPException,
                ConnectionError,
                json.JSONDecodeError,
                KeyError,
                ProviderError,
            ) as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                time.sleep(0.5 * (2**attempt))
        # Never include headers, request bodies or secrets in the exception.
        raise ProviderError(f"DeepSeek request failed: {_transport_reason(last_error)}") from (
            last_error
        )

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
                recovered = _reject_invalid_proposals(packet_data)
                if recovered is not None:
                    return recovered
                raise ProviderError(
                    f"DeepSeek extraction failed local schema validation: {exc}"
                ) from exc

        raise AssertionError("unreachable")


def _reject_invalid_proposals(packet_data: dict[str, Any]) -> SemanticPacket | None:
    """Fail closed per malformed proposal while preserving an auditable rejection.

    One bad label used to cost the whole extraction. A court decision reaches
    for claim_type "conclusion", which the closed vocabulary does not carry, and
    the regeneration round talked the model out of it in one run of three — so
    the packet was lost, after two paid calls, over a single field. Dropping the
    offending proposal and keeping the rest is what the gate already does for
    edges, and it is the same bargain: the run survives, and the loss is written
    into the audit rather than hidden.

    A relation left pointing at a dropped claim needs no handling here. The gate
    admits an edge only when both endpoints were admitted, so it becomes an
    ordinary unresolved-endpoint rejection there.

    Returns None when nothing was dropped, so a packet that fails for some other
    reason still surfaces its original error rather than a silent recovery.
    """
    claims, claim_rejections = _partition(
        packet_data.get("claims"), ClaimProposal, "claim", "C"
    )
    relations, relation_rejections = _partition(
        packet_data.get("relations", []), RelationProposal, "relation", "R"
    )
    if claims is None or relations is None:
        return None
    if not claim_rejections and not relation_rejections:
        return None

    sanitized = dict(packet_data)
    sanitized["claims"] = claims
    sanitized["relations"] = relations
    try:
        packet = SemanticPacket.from_dict(sanitized)
    except SchemaError:
        # Everything worth keeping is gone, or the packet is broken elsewhere.
        # Recovering here would mean returning a graph nobody proposed.
        return None
    return replace(
        packet,
        relation_rejections=tuple(relation_rejections),
        claim_rejections=tuple(claim_rejections),
    )


def _partition(
    raw: Any, model: type, kind: str, prefix: str
) -> tuple[list[dict[str, Any]] | None, list[Rejection]]:
    """Split proposals into the ones the closed schema accepts and the rest."""
    if not isinstance(raw, list):
        return None, []
    kept: list[dict[str, Any]] = []
    rejections: list[Rejection] = []
    for index, item in enumerate(raw, start=1):
        try:
            if not isinstance(item, dict):
                raise SchemaError(f"{kind} must be object")
            model.from_dict(item)
        except SchemaError as exc:
            rejections.append(
                Rejection(kind, f"{prefix}{index:03d}", f"closed_schema_rejection: {exc}")
            )
        else:
            kept.append(item)
    return kept, rejections


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
