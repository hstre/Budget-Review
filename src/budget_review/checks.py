"""Deterministic checks over admitted claims and relations.

These checks deliberately operate after semantic extraction. They do not try to
understand polished prose; they test explicit numeric and dependency structures.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable

from .models import ClaimType, Finding, FindingCategory, RelationType, SemanticDossier
from .profiles import ReviewProfile, get_profile

_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "twelve": 12,
}


_MONEY = r"(?:EUR|€)\s*([0-9][0-9,.]*)"
_SERVE = r"serve\s+([0-9,.]+)\s+participants"
_COHORTS_OF = r"([a-z]+|[0-9]+)\s+cohorts?\s+of\s+([0-9,.]+)"
_PERCENT = r"([0-9,.]+)\s*percent"


def _number(value: str) -> float | None:
    """Read one number, or None. An unreadable word is not a number and never a zero."""
    lowered = value.lower()
    if lowered in _WORDS:
        return float(_WORDS[lowered])
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def _first(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, re.IGNORECASE)
    return _number(match.group(1)) if match else None


def _money(text: str) -> float | None:
    return _first(_MONEY, text)


def _find_number(
    texts: dict[str, str],
    pattern: str,
    where: Callable[[str], bool] | None = None,
) -> tuple[str, float] | None:
    """First claim that carries a readable number for this pattern.

    A claim that satisfies the keyword filter but holds no readable number is
    skipped rather than consumed: it must not mask a later claim that matches.
    """
    for claim_id, text in texts.items():
        if where is not None and not where(text):
            continue
        value = _first(pattern, text)
        if value is not None:
            return claim_id, value
    return None


def _find_pair(
    texts: dict[str, str],
    pattern: str,
    where: Callable[[str], bool] | None = None,
) -> tuple[str, float, float] | None:
    """Same skip-don't-consume contract as _find_number for a two-number pattern."""
    for claim_id, text in texts.items():
        if where is not None and not where(text):
            continue
        match = re.search(pattern, text, re.IGNORECASE)
        if match is None:
            continue
        first, second = _number(match.group(1)), _number(match.group(2))
        if first is not None and second is not None:
            return claim_id, first, second
    return None


def _find_claim(texts: dict[str, str], where: Callable[[str], bool]) -> str | None:
    return next((claim_id for claim_id, text in texts.items() if where(text)), None)


def _texts(dossier: SemanticDossier) -> dict[str, str]:
    return {
        claim.proposal_id: f"{claim.canonical_content} {claim.raw_span}".lower()
        for claim in dossier.claims
    }


class _Builder:
    def __init__(self, profile: str) -> None:
        self.profile = profile
        self.findings: list[Finding] = []

    def add(
        self,
        category: FindingCategory,
        severity: str,
        summary: str,
        claims: Iterable[str],
        explanation: str,
        question: str,
        confidence: float = 0.99,
    ) -> None:
        claim_ids = tuple(dict.fromkeys(claims))
        self.findings.append(
            Finding(
                finding_id=f"D{len(self.findings) + 1:02d}",
                reviewer_id="deterministic-checks",
                reviewer_kind="deterministic",
                model_id=f"content-rules/{self.profile}/0.2",
                category=category,
                severity=severity,
                summary=summary,
                claim_ids=claim_ids,
                explanation=explanation,
                question_for_reviewer=question,
                confidence=confidence,
            )
        )


def deterministic_checks(
    dossier: SemanticDossier,
    profile: str | ReviewProfile = "general",
    tolerance: float = 0.01,
) -> tuple[Finding, ...]:
    """Run profile-specific checks; every finding still requires human judgment."""
    selected = get_profile(profile)
    texts = _texts(dossier)
    builder = _Builder(selected.name)
    if selected.name == "general":
        _check_general_structure(dossier, builder)
        return tuple(builder.findings)
    _check_capacity(texts, builder, tolerance)
    _check_resource_capacity(texts, builder, tolerance)
    _check_completion_rate(texts, builder, tolerance)
    _check_halving(texts, builder, tolerance)
    _check_assumption_dependencies(dossier, texts, builder)
    _check_fte_budget(texts, builder, tolerance)
    _check_budget_sum(dossier, texts, builder, tolerance)
    _check_causal_design(texts, builder)
    return tuple(builder.findings)


def _check_general_structure(dossier: SemanticDossier, builder: _Builder) -> None:
    """Expose explicit graph tensions without rereading style or guessing authorship."""
    node_to_claim = {claim.claim_node_id: claim for claim in dossier.claims}
    supported: set[str] = set()
    evidenced: set[str] = set()
    assumption_sources: set[str] = set()

    for relation in dossier.relations:
        source = node_to_claim[relation.source_claim_node_id]
        target = node_to_claim[relation.target_claim_node_id]
        claim_ids = (source.proposal_id, target.proposal_id)
        if relation.relation_type in {RelationType.SUPPORTS, RelationType.ENTAILS}:
            supported.add(target.proposal_id)
        elif relation.relation_type == RelationType.EVIDENCED_BY:
            evidenced.add(source.proposal_id)
        elif relation.relation_type == RelationType.ASSUMPTION_FOR:
            assumption_sources.add(source.proposal_id)

        if relation.relation_type == RelationType.CONTRADICTS:
            builder.add(
                FindingCategory.INTERNAL_CONTRADICTION,
                "high",
                "Zwei Aussagen stehen in einem ausdrücklichen Widerspruch",
                claim_ids,
                "Der zugelassene ClaimGraph verbindet diese Aussagen als widersprüchlich.",
                (
                    "Ist der Widerspruch beabsichtigt, auflösbar oder muss eine Aussage "
                    "korrigiert werden?"
                ),
            )
        elif relation.relation_type == RelationType.SCOPE_TENSION:
            builder.add(
                FindingCategory.SCOPE_TENSION,
                "medium",
                "Der Geltungsbereich verschiebt sich zwischen zwei Aussagen",
                claim_ids,
                "Der ClaimGraph markiert unterschiedliche Reichweiten oder Bezugsgruppen.",
                "Für welchen genauen Geltungsbereich soll die Schlussfolgerung gelten?",
            )
        elif relation.relation_type == RelationType.GENERALIZES:
            supported.add(source.proposal_id)
            builder.add(
                FindingCategory.OVERGENERALIZATION,
                "medium",
                "Eine Aussage verallgemeinert eine engere Grundlage",
                claim_ids,
                "Die Schlussfolgerung reicht weiter als die Aussage, aus der sie abgeleitet wird.",
                "Welche zusätzliche Grundlage rechtfertigt diese Verallgemeinerung?",
            )

    for claim in dossier.claims:
        claim_id = claim.proposal_id
        if (
            claim.claim_type
            in {
                ClaimType.THESIS,
                ClaimType.INFERENCE,
                ClaimType.RECOMMENDATION,
            }
            and claim_id not in supported | evidenced
        ):
            builder.add(
                FindingCategory.LOGICAL_GAP,
                "medium",
                "Die zentrale Aussage hat keine zugelassene Stützverbindung",
                (claim_id,),
                "Im ClaimGraph führt keine SUPPORTS-, ENTAILS- oder EVIDENCED_BY-Verbindung "
                "zu dieser Aussage.",
                "Welche Prämisse oder welcher Beleg trägt diese Aussage?",
                0.9,
            )
        if (
            claim.claim_type == ClaimType.ASSUMPTION
            and claim_id in assumption_sources
            and claim_id not in evidenced
        ):
            builder.add(
                FindingCategory.UNSUPPORTED_ASSUMPTION,
                "medium",
                "Eine wirksame Annahme bleibt unbelegt",
                (claim_id,),
                (
                    "Andere Aussagen hängen von dieser Annahme ab, ohne dass der Graph "
                    "einen Beleg nennt."
                ),
                "Wie wird diese Annahme begründet oder gegen ihr Scheitern abgesichert?",
                0.95,
            )


def _check_capacity(texts: dict[str, str], builder: _Builder, tolerance: float) -> None:
    target = _find_number(texts, _SERVE)
    capacity = _find_pair(texts, _COHORTS_OF)
    if target is None or capacity is None:
        return
    target_id, participants = target
    capacity_id, cohorts, cohort_size = capacity
    available = cohorts * cohort_size
    if abs(available - participants) > tolerance:
        builder.add(
            FindingCategory.CAPACITY_MISMATCH,
            "high",
            "Die Kohortenkapazität reicht nicht für das Teilnehmerziel",
            (target_id, capacity_id),
            f"{cohorts:g} Kohorten × {cohort_size:g} Plätze = {available:g}, "
            f"nicht {participants:g}.",
            "Welche zusätzliche Kapazität macht das Teilnehmerziel erreichbar?",
        )


def _check_resource_capacity(texts: dict[str, str], builder: _Builder, tolerance: float) -> None:
    purchase = _find_number(texts, r"purchase\s+([0-9,.]+)\s+laptops?")
    parallel = _find_number(texts, r"([a-z]+|[0-9]+)\s+cohorts?", lambda text: "parallel" in text)
    cohort = _find_pair(texts, _COHORTS_OF)
    one_to_one = _find_claim(texts, lambda text: "one-to-one" in text and "laptop" in text)
    if purchase is None or parallel is None or cohort is None or one_to_one is None:
        return
    purchase_id, laptops = purchase
    parallel_id, parallel_cohorts = parallel
    cohort_id, cohorts, cohort_size = cohort
    simultaneous = min(parallel_cohorts, cohorts) * cohort_size
    if laptops + tolerance < simultaneous:
        builder.add(
            FindingCategory.RESOURCE_MISMATCH,
            "high",
            "Die zugesagte Einzelausstattung übersteigt die verfügbaren Laptops",
            (parallel_id, one_to_one, purchase_id, cohort_id),
            (
                f"Die parallele Durchführung erfordert {simultaneous:g} gleichzeitige "
                f"Plätze, gekauft werden aber nur {laptops:g} Laptops."
            ),
            "Wie wird der persönliche Laptopzugang organisatorisch oder materiell gesichert?",
        )


def _check_completion_rate(texts: dict[str, str], builder: _Builder, tolerance: float) -> None:
    enrolled = _find_number(texts, _SERVE)
    rate = _find_number(
        texts,
        _PERCENT,
        lambda text: "completion" in text and ("expect" in text or "raise" in text),
    )
    graduates = _find_number(
        texts, r"(?:graduate|graduates?)\D{0,20}([0-9,.]+)", lambda text: "graduat" in text
    )
    if enrolled is None or rate is None or graduates is None:
        return
    enrolled_id, participants = enrolled
    rate_id, percent = rate
    graduates_id, graduate_target = graduates
    implied = participants * percent / 100.0
    if abs(implied - graduate_target) > tolerance:
        builder.add(
            FindingCategory.ARITHMETIC_MISMATCH,
            "high",
            "Abschlussquote und Absolventenziel passen nicht zusammen",
            (enrolled_id, rate_id, graduates_id),
            f"{percent:g} % von {participants:g} sind {implied:g}, nicht {graduate_target:g}.",
            "Welche Zahl ist für das operative Ziel maßgeblich?",
        )


def _check_halving(texts: dict[str, str], builder: _Builder, tolerance: float) -> None:
    baseline = _find_number(texts, _PERCENT, lambda text: "current attrition" in text)
    halve = _find_claim(texts, lambda text: "halve" in text and "attrition" in text)
    result = _find_number(texts, _PERCENT, lambda text: "dropout rate" in text)
    if baseline is None or halve is None or result is None:
        return
    baseline_id, attrition = baseline
    result_id, dropout = result
    implied = attrition / 2.0
    if abs(implied - dropout) > tolerance:
        builder.add(
            FindingCategory.ARITHMETIC_MISMATCH,
            "high",
            "Die halbierte Abbruchquote stimmt nicht mit dem Zielwert überein",
            (baseline_id, halve, result_id),
            f"Die Hälfte von {attrition:g} % ist {implied:g} %, nicht {dropout:g} %.",
            "Ist die Reduktion relativ, absolut oder auf eine andere Basis bezogen?",
        )


def _check_assumption_dependencies(
    dossier: SemanticDossier, texts: dict[str, str], builder: _Builder
) -> None:
    nodes = {claim.claim_node_id: claim.proposal_id for claim in dossier.claims}
    for relation in dossier.relations:
        if relation.relation_type.value != "ASSUMPTION_FOR":
            continue
        source = nodes[relation.source_claim_node_id]
        target = nodes[relation.target_claim_node_id]
        joined = texts[source] + " " + texts[target]
        if any(word in joined for word in ("partner", "expected", "assume")):
            builder.add(
                FindingCategory.UNSUPPORTED_ASSUMPTION,
                "medium",
                "Die Budgetaussage hängt von einer externen Zusage ab",
                (source, target),
                (
                    "Der Graph weist eine Annahme als Voraussetzung aus, aber kein "
                    "zugelassener Beleg sichert sie ab."
                ),
                "Gibt es eine verbindliche Zusage, ein Ersatzbudget oder eine bezifferte Reserve?",
                0.95,
            )


def _check_fte_budget(texts: dict[str, str], builder: _Builder, tolerance: float) -> None:
    fte = _find_number(texts, r"([0-9.]+)\s*FTE", lambda text: "fte" in text)
    salary = _find_number(texts, _MONEY, lambda text: "annual" in text and "salary" in text)
    allocated = _find_number(
        texts, _MONEY, lambda text: "allocated" in text and "coordinator" in text
    )
    if fte is None or salary is None or allocated is None:
        return
    fte_id, fte_value = fte
    salary_id, annual_salary = salary
    allocated_id, allocated_amount = allocated
    months = _first(r"([0-9,.]+)\s+months?", texts[fte_id]) or 12.0
    implied = fte_value * annual_salary * months / 12.0
    if abs(implied - allocated_amount) > tolerance:
        builder.add(
            FindingCategory.BUDGET_MISMATCH,
            "high",
            "Der Koordinationsposten folgt nicht aus der FTE-Berechnung",
            (fte_id, salary_id, allocated_id),
            (
                f"{fte_value:g} FTE × {annual_salary:,.0f} EUR × {months:g}/12 = "
                f"{implied:,.0f} EUR, nicht {allocated_amount:,.0f} EUR."
            ),
            "Welche zusätzlichen Koordinationskosten erklären den Betrag?",
        )


def _check_budget_sum(
    dossier: SemanticDossier, texts: dict[str, str], builder: _Builder, tolerance: float
) -> None:
    nodes = {claim.claim_node_id: claim.proposal_id for claim in dossier.claims}
    grouped: dict[str, list[str]] = {}
    for relation in dossier.relations:
        if relation.relation_type.value == "PART_OF":
            grouped.setdefault(nodes[relation.target_claim_node_id], []).append(
                nodes[relation.source_claim_node_id]
            )
    for total_id, part_ids in grouped.items():
        total = _money(texts[total_id])
        parts = [(claim_id, _money(texts[claim_id])) for claim_id in part_ids]
        if total is None or any(value is None for _, value in parts):
            continue
        part_sum = sum(value for _, value in parts if value is not None)
        if abs(part_sum - total) > tolerance:
            builder.add(
                FindingCategory.BUDGET_MISMATCH,
                "critical",
                "Die Budgetpositionen ergeben nicht die beantragte Gesamtsumme",
                (*part_ids, total_id),
                (
                    f"Die zugelassenen Teilposten ergeben {part_sum:,.0f} EUR; als "
                    f"Gesamtsumme werden {total:,.0f} EUR genannt."
                ),
                "Welche Einzelposition oder Gesamtsumme muss korrigiert werden?",
            )


def _check_causal_design(texts: dict[str, str], builder: _Builder) -> None:
    before_after = _find_claim(texts, lambda text: "before-and-after" in text)
    no_control = _find_claim(
        texts,
        lambda text: "control group" in text and ("unnecessary" in text or "no " in text),
    )
    causal = _find_claim(texts, lambda text: "caused" in text or "causal" in text)
    if before_after and no_control and causal:
        builder.add(
            FindingCategory.CAUSAL_OVERCLAIM,
            "high",
            "Die kausale Schlussfolgerung geht über das Evaluationsdesign hinaus",
            (before_after, no_control, causal),
            (
                "Ein Vorher-nachher-Vergleich ohne Vergleichsgruppe trennt den "
                "Programmeffekt nicht von anderen Veränderungen."
            ),
            "Welches Design oder welcher Beleg identifiziert das Programm als Ursache?",
            0.98,
        )


__all__ = ["deterministic_checks"]
