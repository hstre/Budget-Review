"""What a reviewer run has to record before a comparison across runs means anything.

The extraction has recorded a prompt hash since it existed, and that guard already
earned itself once: the research log describes one experiment as three runs per
arm, and of the three stored artifacts only two shared a hash — pooling them would
have reported a configuration difference as run-to-run instability.

The reviewer arms recorded no prompt hash at all, so no reviewer comparison could
be guarded that way. These tests pin what is now recorded, and the two properties
that make it worth recording: the hash separates different prompts, and it is
present even when the arm does not answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from budget_review.anti_delphi import REVIEWER_MAX_TOKENS, review_claim_graph
from budget_review.gate import prompt_fingerprint
from budget_review.provider import ProviderError


@dataclass
class _Recorder:
    """A provider that answers nothing and remembers what it was asked."""

    calls: list[dict[str, Any]]
    fail: bool = False

    def complete_json(self, *, system, user, config, max_tokens):
        self.calls.append({"system": system, "user": user, "max_tokens": max_tokens})
        if self.fail:
            raise ProviderError("no answer")
        return {"findings": []}, {
            "model": config.model_id,
            "output_hash": "d" * 16,
            "usage": {},
        }


def _llm_runs(dossier):
    return [run for run in dossier.reviewer_runs if run.get("kind") == "llm"]


def test_a_completed_arm_records_the_prompt_it_was_sent(controlled_semantic) -> None:
    recorder = _Recorder(calls=[])

    dossier = review_claim_graph(controlled_semantic, provider=recorder, profile="budget")

    runs = _llm_runs(dossier)
    assert runs, "the budget profile has llm arms"
    for run, call in zip(runs, recorder.calls, strict=True):
        assert run["prompt_hash"] == prompt_fingerprint(call["system"], call["user"])


def test_an_arm_that_did_not_answer_records_it_too(controlled_semantic) -> None:
    # The case a later comparison most needs to identify: the arm was asked and
    # said nothing. The prompt and the budget are known regardless, because they
    # are what was sent.
    recorder = _Recorder(calls=[], fail=True)

    dossier = review_claim_graph(controlled_semantic, provider=recorder, profile="budget")

    runs = _llm_runs(dossier)
    assert runs
    for run in runs:
        assert run["status"] == "failed"
        assert len(run["prompt_hash"]) >= 16
        assert run["max_tokens"] == REVIEWER_MAX_TOKENS
    for run, call in zip(runs, recorder.calls, strict=True):
        assert run["prompt_hash"] == prompt_fingerprint(call["system"], call["user"])


def test_every_arm_records_the_budget_it_was_given(controlled_semantic) -> None:
    recorder = _Recorder(calls=[])

    dossier = review_claim_graph(controlled_semantic, provider=recorder, profile="budget")

    for run, call in zip(_llm_runs(dossier), recorder.calls, strict=True):
        assert run["max_tokens"] == call["max_tokens"] == REVIEWER_MAX_TOKENS


def test_the_two_arms_do_not_share_a_prompt_hash(controlled_semantic) -> None:
    # If both arms hashed equal, the field would say nothing about which role was
    # asked, and a comparison could pool two different questions.
    recorder = _Recorder(calls=[])

    dossier = review_claim_graph(controlled_semantic, provider=recorder, profile="budget")

    hashes = {run["prompt_hash"] for run in _llm_runs(dossier)}
    assert len(hashes) == len(_llm_runs(dossier))


def test_a_different_graph_gives_a_different_recorded_hash(controlled_semantic) -> None:
    """The property the whole guard rests on, and the one this test first missed.

    An earlier version compared the prompts the recorder saw and not the hashes
    that were recorded, so a fingerprint ignoring the user half — the graph —
    passed it. That mutation survived, which is how the gap was found. Two runs
    over different graphs must record different hashes, or a comparison can pool
    two documents as one condition.
    """
    first = _Recorder(calls=[])
    original = review_claim_graph(controlled_semantic, provider=first, profile="budget")

    trimmed = controlled_semantic.__class__(
        **{
            **controlled_semantic.__dict__,
            "claims": controlled_semantic.claims[:2],
            "relations": (),
        }
    )
    second = _Recorder(calls=[])
    reduced = review_claim_graph(trimmed, provider=second, profile="budget")

    # The role prompts are unchanged; only the graph differs.
    assert [c["system"] for c in first.calls] == [c["system"] for c in second.calls]
    assert [c["user"] for c in first.calls] != [c["user"] for c in second.calls]
    # And that difference has to reach the recorded hashes.
    before = [run["prompt_hash"] for run in _llm_runs(original)]
    after = [run["prompt_hash"] for run in _llm_runs(reduced)]
    assert before and len(before) == len(after)
    assert all(b != a for b, a in zip(before, after, strict=True))


def test_the_profiles_ask_different_questions(controlled_semantic) -> None:
    general = _Recorder(calls=[])
    review_claim_graph(controlled_semantic, provider=general, profile="general")
    budget = _Recorder(calls=[])
    review_claim_graph(controlled_semantic, provider=budget, profile="budget")

    assert {c["system"] for c in general.calls} != {c["system"] for c in budget.calls}


def test_the_fingerprint_is_one_expression_rather_than_two() -> None:
    # Two hashes that mean slightly different things are worse than one missing
    # hash: they compare as unequal and report a difference that is not there.
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "budget_review"
    for name in ("provider.py", "anti_delphi.py"):
        source = (root / name).read_text(encoding="utf-8")
        assert 'sha256_text(active_system + "\\n" + user)' not in source, name
        assert "prompt_fingerprint(" in source, name


def test_a_differently_split_prompt_pair_is_not_the_same_fingerprint() -> None:
    """The pair the separator exists for, which an earlier version of this test missed.

    It first compared ("a", "b") against ("a\nb", ""), and those two differ with
    the separator or without it — so a fingerprint that simply concatenated the
    halves passed, and the mutation survived. The pair that separates the two
    conventions is one where the halves are split at a different point: without a
    separator they both hash "abc" and the comparison calls two different
    conditions equal.
    """
    assert prompt_fingerprint("ab", "c") != prompt_fingerprint("a", "bc")


def test_the_separator_convention_is_not_injective_and_says_so() -> None:
    """What the separator does not buy, pinned so no later reading overstates it.

    A prompt may contain the separator itself, and then two different splits do
    collide: ("a", "b\nc") and ("a\nb", "c") are one hash. That is harmless here
    because the system half is a fixed role prompt from ``prompts.py`` and never
    a prefix of a graph serialisation — but it is a property of this repository,
    not of the hash, so it is asserted rather than assumed. A convention change
    that claimed injectivity would have to come past this test.
    """
    assert prompt_fingerprint("a", "b\nc") == prompt_fingerprint("a\nb", "c")
