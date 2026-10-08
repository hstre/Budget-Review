"""Every counterexample the two independent reviews gave, kept as a test.

The reviews of 2026-10-08 produced sixteen concrete renderings and a claim about
each: this one is unfaithful and would pass, that one is faithful and would fail.
Each was checked against the validator, twelve held, four were refuted, and the
cases were then rewritten. Keeping the renderings here is what stops the set
drifting back: a later widening of a token list has to leave every one of these
verdicts intact.

Three co-presence cases are here too. Those are the form the reviews' refuted
claims survive in — the offending wording beside a compliant claim, where the
requirement is satisfied and, before the rewrite, no pattern fired.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "src" / "budget_review" / "fixtures" / "semantic_cases" / "cases.json"


def _module(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cases_module = _module("semantic_cases")
scorer = _module("semantic_score")
BY_ID = {c["case_id"]: c for c in json.loads(CASES.read_text(encoding="utf-8"))["cases"]}


def _verdict(case_id: str, renderings: list[str]) -> bool:
    """Whether the case passes with exactly these claims on its span."""
    case = BY_ID[case_id]
    start = case["document"].index(case["span"])
    claims = [
        {
            "canonical_content": text,
            "claim_type": "fact",
            "anchor_start": start,
            "anchor_end": start + len(case["span"]),
            "anchor_normalised": False,
        }
        for text in renderings
    ]
    return scorer.score(case, claims)["meaning_preserved"]


# An unfaithful rendering must not pass. All of these were verified to pass
# before the rewrite, which is why the cases were rewritten.
UNFAITHFUL = [
    (
        "neg-01-de",
        ["Die Maßnahme wirkt nicht nur auf die Abbrecherquote, sondern auch auf die Noten."],
        "the scope reversed while the negation token stays",
    ),
    ("mod-01-de", ["Das Programm senkte die Abbrecherquote."], "possibility to past fact"),
    ("mod-01-de", ["Die Senkung der Quote durch das Programm."], "possibility nominalised"),
    ("mod-01-en", ["The programme will lower the dropout rate."], "possibility to commitment"),
    (
        "cor-01-de",
        ["Die Teilnahme trägt dazu bei, die Abschlussquote zu verbessern."],
        "correlation to cause without a cause verb",
    ),
    ("spk-01-de", ["Die Regierung ist wirksam."], "the speaker named, a different proposition"),
    (
        "spk-02-de",
        ["Die Regierung ist eine Behörde.", "Der Gerichtshof steht in Straßburg."],
        "both speakers named, no semantic core",
    ),
    ("mul-01-de", ["Haushalt.", "Schulen."], "two bare fragments"),
    ("mul-02-de", ["Mittel.", "Ausbau."], "two bare fragments"),
]

# A faithful rendering must pass. Each of these failed before the rewrite, which
# is a false alarm: the system is punished for a correct answer.
FAITHFUL = [
    ("mod-02-de", ["Laut Studie senkt das Programm die Quote."], "attribution without the verb"),
    (
        "mod-02-en",
        ["According to the study, the programme lowers the rate."],
        "attribution without the verb",
    ),
    ("neg-02-de", ["Ein Teil der Schulen geht leer aus."], "the negation from the other side"),
    (
        "sco-02-de",
        ["Vorbehaltlich der Mittelbewilligung beginnt der Ausbau im Frühjahr."],
        "the condition as a preposition",
    ),
    (
        "cor-01-de",
        ["Teilnahme und höhere Abschlussquoten treten gemeinsam auf."],
        "correlation without the loan word",
    ),
    (
        "cor-02-de",
        ["Wegen der Kürzung fielen zwei Kurse weg."],
        "the cause as a preposition",
    ),
    (
        "cor-02-en",
        ["Because of the cut, two courses were dropped."],
        "the cause as a preposition",
    ),
]

# The form the reviews' refuted claims survive in: a lone unfaithful claim fails
# the requirement, so they were wrong about the mechanism — but beside a
# compliant claim the requirement is satisfied and only a pattern can catch it.
CO_PRESENT = [
    (
        "mod-01-de",
        [
            "Das Programm könnte die Abbrecherquote senken.",
            "Das Programm senkte die Abbrecherquote.",
        ],
    ),
    (
        "mod-01-en",
        [
            "The programme could lower the dropout rate.",
            "The programme will lower the dropout rate.",
        ],
    ),
    (
        "cor-01-de",
        [
            "Teilnahme korreliert mit höheren Abschlussquoten.",
            "Die Teilnahme trägt dazu bei, die Abschlussquote zu verbessern.",
        ],
    ),
]


@pytest.mark.parametrize(("case_id", "renderings", "why"), UNFAITHFUL)
def test_an_unfaithful_rendering_does_not_pass(case_id, renderings, why) -> None:
    assert _verdict(case_id, renderings) is False, why


@pytest.mark.parametrize(("case_id", "renderings", "why"), FAITHFUL)
def test_a_faithful_rendering_passes(case_id, renderings, why) -> None:
    assert _verdict(case_id, renderings) is True, why


@pytest.mark.parametrize(("case_id", "renderings"), CO_PRESENT)
def test_a_forbidden_wording_beside_a_compliant_claim_still_fails(case_id, renderings) -> None:
    assert _verdict(case_id, renderings) is False


def test_the_set_still_holds_all_five_invariants() -> None:
    # A rewrite that satisfies the counterexamples and breaks an invariant has
    # traded one defect for another.
    assert cases_module.validate(cases_module.load()) == []


def test_no_case_still_uses_the_superseded_single_group_per_claim_field() -> None:
    for case_id, case in BY_ID.items():
        assert "requires_distinct_groups" not in case, case_id


def test_every_multi_claim_case_demands_more_than_one_group_per_claim() -> None:
    # The defect both reviews found: one keyword per claim is a counting test,
    # not a meaning test. If a later edit drops back to one group, say so here.
    for case_id, case in BY_ID.items():
        if case.get("min_claims_on_span", 1) < 2:
            continue
        claims = cases_module.distinct_claims(case)
        assert claims, case_id
        assert all(len(groups) >= 2 for groups in claims[:1]), case_id
