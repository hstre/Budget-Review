"""Deterministic checks over admitted claims and relations.

These checks deliberately operate after semantic extraction. They do not try to
understand polished prose; they test explicit numeric and dependency structures.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

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


def _number(value: str) -> float:
    lowered = value.lower()
    if lowered in _WORDS:
        return float(_WORDS[lowered])
    return float(value.replace(",", ""))


def _first(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, re.IGNORECASE)
    return _number(match.group(1)) if match else None


def _money(text: str) -> float | None:
    match = re.search(r"(?:EUR|€)\s*([0-9][0-9,.]*)", text, re.IGNORECASE)
    return _number(match.group(1)) if match else None


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
    target = next(
        (
            (claim_id, _first(r"serve\s+([0-9,.]+)\s+participants", text))
            for claim_id, text in texts.items()
            if "serve" in text
        ),
        None,
    )
    capacity = next(
        (
            (claim_id, match)
            for claim_id, text in texts.items()
            if (match := re.search(r"([a-z]+|[0-9]+)\s+cohorts?\s+of\s+([0-9,.]+)", text))
        ),
        None,
    )
    if not target or target[1] is None or not capacity:
        return
    cohorts = _number(capacity[1].group(1))
    cohort_size = _number(capacity[1].group(2))
    available = cohorts * cohort_size
    if abs(available - target[1]) > tolerance:
        builder.add(
            FindingCategory.CAPACITY_MISMATCH,
            "high",
            "Die Kohortenkapazität reicht nicht für das Teilnehmerziel",
            (target[0], capacity[0]),
            f"{cohorts:g} Kohorten × {cohort_size:g} Plätze = {available:g}, nicht {target[1]:g}.",
            "Welche zusätzliche Kapazität macht das Teilnehmerziel erreichbar?",
        )


def _check_resource_capacity(texts: dict[str, str], builder: _Builder, tolerance: float) -> None:
    purchase = next(
        (
            (claim_id, _first(r"purchase\s+([0-9,.]+)\s+laptops?", text))
            for claim_id, text in texts.items()
            if "purchase" in text and "laptop" in text
        ),
        None,
    )
    parallel = next(
        (
            (claim_id, _first(r"([a-z]+|[0-9]+)\s+cohorts?", text))
            for claim_id, text in texts.items()
            if "parallel" in text
        ),
        None,
    )
    cohort = next(
        (
            (claim_id, _number(match.group(1)), _number(match.group(2)))
            for claim_id, text in texts.items()
            if (match := re.search(r"([a-z]+|[0-9]+)\s+cohorts?\s+of\s+([0-9,.]+)", text))
        ),
        None,
    )
    one_to_one = next(
        (claim_id for claim_id, text in texts.items() if "one-to-one" in text and "laptop" in text),
        None,
    )
    if (
        not purchase
        or purchase[1] is None
        or not parallel
        or parallel[1] is None
        or not cohort
        or not one_to_one
    ):
        return
    simultaneous = min(parallel[1], cohort[1]) * cohort[2]
    if purchase[1] + tolerance < simultaneous:
        builder.add(
            FindingCategory.RESOURCE_MISMATCH,
            "high",
            "Die zugesagte Einzelausstattung übersteigt die verfügbaren Laptops",
            (parallel[0], one_to_one, purchase[0], cohort[0]),
            (
                f"Die parallele Durchführung erfordert {simultaneous:g} gleichzeitige "
                f"Plätze, gekauft werden aber nur {purchase[1]:g} Laptops."
            ),
            "Wie wird der persönliche Laptopzugang organisatorisch oder materiell gesichert?",
        )


def _check_completion_rate(texts: dict[str, str], builder: _Builder, tolerance: float) -> None:
    enrolled = next(
        (
            (claim_id, _first(r"serve\s+([0-9,.]+)\s+participants", text))
            for claim_id, text in texts.items()
            if "serve" in text
        ),
        None,
    )
    rate = next(
        (
            (claim_id, _first(r"([0-9,.]+)\s*percent", text))
            for claim_id, text in texts.items()
            if "completion" in text and ("expect" in text or "raise" in text)
        ),
        None,
    )
    graduates = next(
        (
            (claim_id, _first(r"(?:graduate|graduates?)\D{0,20}([0-9,.]+)", text))
            for claim_id, text in texts.items()
            if "graduat" in text
        ),
        None,
    )
    if (
        not enrolled
        or enrolled[1] is None
        or not rate
        or rate[1] is None
        or not graduates
        or graduates[1] is None
    ):
        return
    implied = enrolled[1] * rate[1] / 100.0
    if abs(implied - graduates[1]) > tolerance:
        builder.add(
            FindingCategory.ARITHMETIC_MISMATCH,
            "high",
            "Abschlussquote und Absolventenziel passen nicht zusammen",
            (enrolled[0], rate[0], graduates[0]),
            f"{rate[1]:g} % von {enrolled[1]:g} sind {implied:g}, nicht {graduates[1]:g}.",
            "Welche Zahl ist für das operative Ziel maßgeblich?",
        )


def _check_halving(texts: dict[str, str], builder: _Builder, tolerance: float) -> None:
    baseline = next(
        (
            (claim_id, _first(r"([0-9,.]+)\s*percent", text))
            for claim_id, text in texts.items()
            if "current attrition" in text
        ),
        None,
    )
    halve = next(
        (claim_id for claim_id, text in texts.items() if "halve" in text and "attrition" in text),
        None,
    )
    result = next(
        (
            (claim_id, _first(r"([0-9,.]+)\s*percent", text))
            for claim_id, text in texts.items()
            if "dropout rate" in text
        ),
        None,
    )
    if not baseline or baseline[1] is None or not halve or not result or result[1] is None:
        return
    implied = baseline[1] / 2.0
    if abs(implied - result[1]) > tolerance:
        builder.add(
            FindingCategory.ARITHMETIC_MISMATCH,
            "high",
            "Die halbierte Abbruchquote stimmt nicht mit dem Zielwert überein",
            (baseline[0], halve, result[0]),
            f"Die Hälfte von {baseline[1]:g} % ist {implied:g} %, nicht {result[1]:g} %.",
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
    fte = next(
        (
            (claim_id, _first(r"([0-9.]+)\s*FTE", text), _first(r"([0-9,.]+)\s+months?", text))
            for claim_id, text in texts.items()
            if "fte" in text
        ),
        None,
    )
    salary = next(
        (
            (claim_id, _money(text))
            for claim_id, text in texts.items()
            if "annual" in text and "salary" in text
        ),
        None,
    )
    allocated = next(
        (
            (claim_id, _money(text))
            for claim_id, text in texts.items()
            if "allocated" in text and "coordinator" in text
        ),
        None,
    )
    if (
        not fte
        or fte[1] is None
        or not salary
        or salary[1] is None
        or not allocated
        or allocated[1] is None
    ):
        return
    months = fte[2] or 12.0
    implied = fte[1] * salary[1] * months / 12.0
    if abs(implied - allocated[1]) > tolerance:
        builder.add(
            FindingCategory.BUDGET_MISMATCH,
            "high",
            "Der Koordinationsposten folgt nicht aus der FTE-Berechnung",
            (fte[0], salary[0], allocated[0]),
            (
                f"{fte[1]:g} FTE × {salary[1]:,.0f} EUR × {months:g}/12 = "
                f"{implied:,.0f} EUR, nicht {allocated[1]:,.0f} EUR."
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
    before_after = next(
        (claim_id for claim_id, text in texts.items() if "before-and-after" in text), None
    )
    no_control = next(
        (
            claim_id
            for claim_id, text in texts.items()
            if "control group" in text and ("unnecessary" in text or "no " in text)
        ),
        None,
    )
    causal = next(
        (claim_id for claim_id, text in texts.items() if "caused" in text or "causal" in text), None
    )
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
