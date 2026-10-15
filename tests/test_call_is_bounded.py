"""A paid call has to end, and a failure has to say what happened.

A run of 48 calls delivered one line in 45 minutes and then was cancelled. The
line read `DeepSeek request failed: KeyError` — no key name, no status, no sign
that the envelope had arrived carrying an error instead of a completion. Two
defects, both ours:

* `urlopen(timeout=...)` bounds each socket operation, not the response. A peer
  that sends a few bytes at a time resets that timer on every chunk, so the read
  ran far past the three attempts' six minutes.
* the message named the exception class and nothing else, so the log could not
  distinguish an exhausted balance from a server fault from a contract change.

These tests hold the bound and the message. The bound is the one that costs
money when it is missing.
"""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import pytest

from budget_review.provider import (
    DeepSeekProvider,
    ModelConfig,
    ProviderError,
    _envelope_complaint,
    _read_within,
    _transport_reason,
)

CONFIG = ModelConfig(model_id="deepseek-v4-flash")


class _Trickle:
    """A body that never ends, one byte at a time — the shape that cost 45 minutes."""

    def __init__(self, delay: float = 0.01) -> None:
        self.delay = delay
        self.reads = 0

    def read(self, size: int = -1) -> bytes:
        self.reads += 1
        time.sleep(self.delay)
        return b"x"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


class _Envelope:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.done = False

    def read(self, size: int = -1) -> bytes:
        if self.done:
            return b""
        self.done = True
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


def test_a_body_that_never_ends_is_cut_off_by_the_clock() -> None:
    body = _Trickle()
    deadline = time.monotonic() + 0.2

    with pytest.raises(ProviderError) as caught:
        _read_within(body, deadline, 0.2)

    assert "did not complete" in str(caught.value)
    assert body.reads > 0, "it should have tried to read"


def test_a_body_that_ends_is_returned_whole() -> None:
    body = _Envelope({"hello": "world"})
    assert json.loads(_read_within(body, time.monotonic() + 10, 10)) == {"hello": "world"}


def test_a_call_whose_budget_is_spent_does_not_start_another_attempt(monkeypatch) -> None:
    """The bound that makes 48 calls finishable, asserted on the retry path.

    Without it, three attempts at the socket timeout are six minutes only if
    every attempt returns; a trickling peer makes each one unbounded, and the
    retries then multiply an unbounded wait.
    """
    attempts = []

    def opener(request, timeout):
        attempts.append(1)
        return _Trickle(delay=0.05)

    monkeypatch.setattr("urllib.request.urlopen", opener)
    provider = DeepSeekProvider(api_key="k", timeout=5.0, retries=5, budget=0.2)

    with pytest.raises(ProviderError):
        provider.complete_json(system="s", user="u", config=CONFIG)

    # Not all six attempts: the budget stops it well before the retry count.
    assert len(attempts) < 6, attempts


def test_an_envelope_without_choices_says_what_it_carried_instead(monkeypatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: _Envelope({"error": {"type": "insufficient_balance",
                                                      "message": "no funds"}}),
    )
    provider = DeepSeekProvider(api_key="k", retries=0, budget=5.0)

    with pytest.raises(ProviderError) as caught:
        provider.complete_json(system="s", user="u", config=CONFIG)

    message = str(caught.value)
    assert "insufficient_balance" in message
    assert "no funds" in message
    assert "KeyError" not in message, "the old message said only this"


def test_an_envelope_with_neither_choices_nor_an_error_names_its_keys() -> None:
    complaint = _envelope_complaint({"id": "x", "object": "chat.completion"})
    assert "no choices" in complaint
    assert "id" in complaint and "object" in complaint


def test_the_complaint_truncates_a_long_provider_message() -> None:
    # A provider message is the provider's own diagnostic text, not a header and
    # not our request, so it is safe to log — but not at unbounded length.
    complaint = _envelope_complaint({"error": {"type": "t", "message": "x" * 500}})
    assert len(complaint) < 260


def test_the_complaint_never_carries_the_request_or_a_header() -> None:
    complaint = _envelope_complaint(
        {"error": {"type": "t", "message": "m"}, "request": "SECRET", "headers": "SECRET"}
    )
    assert "SECRET" not in complaint


def test_a_missing_key_is_named_rather_than_left_as_a_class() -> None:
    assert _transport_reason(KeyError("choices")) == "KeyError 'choices'"
    assert _transport_reason(KeyError()) == "KeyError"


def test_the_budget_is_longer_than_the_attempts_it_has_to_allow() -> None:
    # A budget below one socket timeout would cut off answers that are merely
    # slow, which is a different defect from the one being fixed.
    provider = DeepSeekProvider(api_key="k")
    assert provider.budget > provider.timeout


_score_spec = importlib.util.spec_from_file_location(
    "semantic_score", Path(__file__).resolve().parents[1] / "scripts" / "semantic_score.py"
)
semantic_score = importlib.util.module_from_spec(_score_spec)
_score_spec.loader.exec_module(semantic_score)


def test_a_run_whose_calls_keep_failing_stops_paying_for_more() -> None:
    breaker = semantic_score.Breaker(limit=3)
    assert breaker.record(succeeded=False) is False
    assert breaker.record(succeeded=False) is False
    assert breaker.record(succeeded=False) is True


def test_one_success_clears_the_row() -> None:
    """The reset, which a mutation removing it survived for want of any test.

    Without it, three failures scattered across 48 calls would stop a run that
    is working, and the breaker would cost more than it saves.
    """
    breaker = semantic_score.Breaker(limit=3)
    breaker.record(succeeded=False)
    breaker.record(succeeded=False)
    assert breaker.record(succeeded=True) is False
    assert breaker.consecutive == 0
    assert breaker.record(succeeded=False) is False


def test_a_run_that_never_fails_never_stops() -> None:
    breaker = semantic_score.Breaker(limit=3)
    assert not any(breaker.record(succeeded=True) for _ in range(48))


def test_the_limit_is_smaller_than_a_run() -> None:
    # A limit at or above the number of calls could never fire, which is the
    # near-vacuous shape this project has caught twice elsewhere.
    assert semantic_score.CONSECUTIVE_FAILURE_LIMIT < 16
