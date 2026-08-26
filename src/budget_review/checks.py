"""Deterministic checks over admitted claims and relations.

These checks deliberately operate after semantic extraction. They do not try to
understand polished prose; they test explicit numeric and dependency structures.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable

from .models import ClaimType, Finding, FindingCategory, RelationType, SemanticDossier
from .profiles import ReviewProfile, get_profile
from .settings import LANGUAGES

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


# Provenance of the deterministic path. Bump whenever a rule changes which
# findings it produces, so two dossiers cannot claim one version for two results.
RULES_VERSION = "0.3"


def rules_model_id(profile_name: str) -> str:
    return f"content-rules/{profile_name}/{RULES_VERSION}"


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



# Deterministic finding prose, keyed by check. Structural fields (category,
# severity, claim_ids, confidence) stay language independent; only this text
# follows the dossier language.
_MESSAGES: dict[str, dict[str, tuple[str, str, str]]] = {
    "internal_contradiction": {
        "de": (
            "Zwei Aussagen stehen in einem ausdrücklichen Widerspruch",
            "Der zugelassene ClaimGraph verbindet diese Aussagen als widersprüchlich.",
            "Ist der Widerspruch beabsichtigt, auflösbar oder muss eine Aussage korrigiert werden?",
        ),
        "en": (
            "Two claims are explicitly contradictory",
            "The admitted ClaimGraph links these claims as contradicting each other.",
            "Is the contradiction intended, resolvable, or must one claim be corrected?",
        ),
    },
    "scope_tension": {
        "de": (
            "Der Geltungsbereich verschiebt sich zwischen zwei Aussagen",
            "Der ClaimGraph markiert unterschiedliche Reichweiten oder Bezugsgruppen.",
            "Für welchen genauen Geltungsbereich soll die Schlussfolgerung gelten?",
        ),
        "en": (
            "The scope shifts between two claims",
            "The ClaimGraph marks differing reach or reference groups.",
            "For exactly which scope is the conclusion meant to hold?",
        ),
    },
    "overgeneralization": {
        "de": (
            "Eine Aussage verallgemeinert eine engere Grundlage",
            "Die Schlussfolgerung reicht weiter als die Aussage, aus der sie abgeleitet wird.",
            "Welche zusätzliche Grundlage rechtfertigt diese Verallgemeinerung?",
        ),
        "en": (
            "A claim generalizes a narrower basis",
            "The conclusion reaches further than the claim it is drawn from.",
            "What additional basis justifies this generalization?",
        ),
    },
    "logical_gap": {
        "de": (
            "Die zentrale Aussage hat keine zugelassene Stützverbindung",
            "Im ClaimGraph führt keine SUPPORTS-, ENTAILS- oder EVIDENCED_BY-Verbindung "
            "zu dieser Aussage.",
            "Welche Prämisse oder welcher Beleg trägt diese Aussage?",
        ),
        "en": (
            "The central claim has no admitted supporting link",
            "No SUPPORTS, ENTAILS or EVIDENCED_BY edge in the ClaimGraph leads to this claim.",
            "Which premise or piece of evidence carries this claim?",
        ),
    },
    "unsupported_assumption": {
        "de": (
            "Eine wirksame Annahme bleibt unbelegt",
            "Andere Aussagen hängen von dieser Annahme ab, ohne dass der Graph einen Beleg nennt.",
            "Wie wird diese Annahme begründet oder gegen ihr Scheitern abgesichert?",
        ),
        "en": (
            "A load-bearing assumption remains unsupported",
            "Other claims depend on this assumption, but the graph names no evidence for it.",
            "How is this assumption justified, or hedged against its failure?",
        ),
    },
    "capacity_mismatch": {
        "de": (
            "Die Kohortenkapazität reicht nicht für das Teilnehmerziel",
            "{cohorts:g} Kohorten × {cohort_size:g} Plätze = {available:g}, "
            "nicht {participants:g}.",
            "Welche zusätzliche Kapazität macht das Teilnehmerziel erreichbar?",
        ),
        "en": (
            "Cohort capacity does not cover the participant target",
            "{cohorts:g} cohorts × {cohort_size:g} places = {available:g}, "
            "not {participants:g}.",
            "What additional capacity makes the participant target reachable?",
        ),
    },
    "resource_mismatch": {
        "de": (
            "Die zugesagte Einzelausstattung übersteigt die verfügbaren Laptops",
            "Die parallele Durchführung erfordert {simultaneous:g} gleichzeitige Plätze, "
            "gekauft werden aber nur {laptops:g} Laptops.",
            "Wie wird der persönliche Laptopzugang organisatorisch oder materiell gesichert?",
        ),
        "en": (
            "The promised one-to-one equipment exceeds the available laptops",
            "Running cohorts in parallel needs {simultaneous:g} simultaneous places, "
            "but only {laptops:g} laptops are purchased.",
            "How is personal laptop access secured, organizationally or materially?",
        ),
    },
    "completion_rate": {
        "de": (
            "Abschlussquote und Absolventenziel passen nicht zusammen",
            "{percent:g} % von {participants:g} sind {implied:g}, nicht {graduate_target:g}.",
            "Welche Zahl ist für das operative Ziel maßgeblich?",
        ),
        "en": (
            "Completion rate and graduate target do not match",
            "{percent:g} % of {participants:g} is {implied:g}, not {graduate_target:g}.",
            "Which figure governs the operational target?",
        ),
    },
    "halving": {
        "de": (
            "Die halbierte Abbruchquote stimmt nicht mit dem Zielwert überein",
            "Die Hälfte von {attrition:g} % ist {implied:g} %, nicht {dropout:g} %.",
            "Ist die Reduktion relativ, absolut oder auf eine andere Basis bezogen?",
        ),
        "en": (
            "The halved attrition rate does not match the stated target",
            "Half of {attrition:g} % is {implied:g} %, not {dropout:g} %.",
            "Is the reduction relative, absolute, or measured against another baseline?",
        ),
    },
    "assumption_dependency": {
        "de": (
            "Die Budgetaussage hängt von einer externen Zusage ab",
            "Der Graph weist eine Annahme als Voraussetzung aus, aber kein zugelassener "
            "Beleg sichert sie ab.",
            "Gibt es eine verbindliche Zusage, ein Ersatzbudget oder eine bezifferte Reserve?",
        ),
        "en": (
            "The budget claim depends on an external commitment",
            "The graph marks an assumption as a precondition, but no admitted evidence "
            "secures it.",
            "Is there a binding commitment, a fallback budget, or a quantified reserve?",
        ),
    },
    "fte_budget": {
        "de": (
            "Der Koordinationsposten folgt nicht aus der FTE-Berechnung",
            "{fte:g} FTE × {salary:,.0f} EUR × {months:g}/12 = {implied:,.0f} EUR, "
            "nicht {allocated:,.0f} EUR.",
            "Welche zusätzlichen Koordinationskosten erklären den Betrag?",
        ),
        "en": (
            "The coordination line does not follow from the FTE calculation",
            "{fte:g} FTE × {salary:,.0f} EUR × {months:g}/12 = {implied:,.0f} EUR, "
            "not {allocated:,.0f} EUR.",
            "Which additional coordination costs explain the amount?",
        ),
    },
    "budget_sum": {
        "de": (
            "Die Budgetpositionen ergeben nicht die beantragte Gesamtsumme",
            "Die zugelassenen Teilposten ergeben {part_sum:,.0f} EUR; als Gesamtsumme "
            "werden {total:,.0f} EUR genannt.",
            "Welche Einzelposition oder Gesamtsumme muss korrigiert werden?",
        ),
        "en": (
            "The budget lines do not add up to the requested total",
            "The admitted line items sum to {part_sum:,.0f} EUR; the stated total is "
            "{total:,.0f} EUR.",
            "Which line item or total needs to be corrected?",
        ),
    },
    "coverage_gap": {
        "de": (
            "Ein Abschnitt trägt keine zugelassene Aussage",
            "Zwischen Zeichen {start} und {end} ist kein zugelassener Claim verankert: "
            "„{excerpt}“",
            "Enthält dieser Abschnitt eine prüfbare Aussage, die im Graphen fehlt?",
        ),
        "en": (
            "A passage carries no admitted claim",
            "No admitted claim is anchored between characters {start} and {end}: "
            "“{excerpt}”",
            "Does this passage contain a checkable claim that is missing from the graph?",
        ),
    },
    "causal_design": {
        "de": (
            "Die kausale Schlussfolgerung geht über das Evaluationsdesign hinaus",
            "Ein Vorher-nachher-Vergleich ohne Vergleichsgruppe trennt den Programmeffekt "
            "nicht von anderen Veränderungen.",
            "Welches Design oder welcher Beleg identifiziert das Programm als Ursache?",
        ),
        "en": (
            "The causal conclusion reaches beyond the evaluation design",
            "A before-and-after comparison without a control group does not separate the "
            "programme effect from other changes.",
            "Which design or evidence identifies the programme as the cause?",
        ),
    },
}


class _Builder:
    def __init__(self, profile: str, language: str = "de") -> None:
        self.profile = profile
        self.language = language if language in LANGUAGES else "de"
        self.findings: list[Finding] = []

    def add(
        self,
        key: str,
        category: FindingCategory,
        severity: str,
        claims: Iterable[str],
        confidence: float = 0.99,
        **params: float | int | str,
    ) -> None:
        summary, explanation, question = _MESSAGES[key][self.language]
        claim_ids = tuple(dict.fromkeys(claims))
        self.findings.append(
            Finding(
                finding_id=f"D{len(self.findings) + 1:02d}",
                reviewer_id="deterministic-checks",
                reviewer_kind="deterministic",
                model_id=rules_model_id(self.profile),
                category=category,
                severity=severity,
                summary=summary,
                claim_ids=claim_ids,
                explanation=explanation.format(**params),
                question_for_reviewer=question,
                confidence=confidence,
            )
        )


def deterministic_checks(
    dossier: SemanticDossier,
    profile: str | ReviewProfile = "general",
    tolerance: float = 0.01,
    language: str = "de",
) -> tuple[Finding, ...]:
    """Run profile-specific checks; every finding still requires human judgment."""
    selected = get_profile(profile)
    texts = _texts(dossier)
    builder = _Builder(selected.name, language)
    # Profile independent: what the extractor never proposed is invisible to
    # every other check, so measure it before the profile branch.
    _check_coverage(dossier, builder)
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


def _check_coverage(dossier: SemanticDossier, builder: _Builder) -> None:
    """Name the passages no admitted claim reaches; the examiner decides why."""
    if dossier.coverage is None:
        return
    for gap in dossier.coverage.gaps:
        builder.add(
            "coverage_gap",
            FindingCategory.COVERAGE_GAP,
            "low",
            (),
            0.9,
            start=gap.start,
            end=gap.end,
            excerpt=gap.excerpt,
        )


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
                "internal_contradiction",
                FindingCategory.INTERNAL_CONTRADICTION,
                "high",
                claim_ids,
            )
        elif relation.relation_type == RelationType.SCOPE_TENSION:
            builder.add(
                "scope_tension",
                FindingCategory.SCOPE_TENSION,
                "medium",
                claim_ids,
            )
        elif relation.relation_type == RelationType.GENERALIZES:
            supported.add(source.proposal_id)
            builder.add(
                "overgeneralization",
                FindingCategory.OVERGENERALIZATION,
                "medium",
                claim_ids,
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
                "logical_gap",
                FindingCategory.LOGICAL_GAP,
                "medium",
                (claim_id,),
                0.9,
            )
        if (
            claim.claim_type == ClaimType.ASSUMPTION
            and claim_id in assumption_sources
            and claim_id not in evidenced
        ):
            builder.add(
                "unsupported_assumption",
                FindingCategory.UNSUPPORTED_ASSUMPTION,
                "medium",
                (claim_id,),
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
            "capacity_mismatch",
            FindingCategory.CAPACITY_MISMATCH,
            "high",
            (target_id, capacity_id),
            cohorts=cohorts,
            cohort_size=cohort_size,
            available=available,
            participants=participants,
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
            "resource_mismatch",
            FindingCategory.RESOURCE_MISMATCH,
            "high",
            (parallel_id, one_to_one, purchase_id, cohort_id),
            simultaneous=simultaneous,
            laptops=laptops,
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
            "completion_rate",
            FindingCategory.ARITHMETIC_MISMATCH,
            "high",
            (enrolled_id, rate_id, graduates_id),
            percent=percent,
            participants=participants,
            implied=implied,
            graduate_target=graduate_target,
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
            "halving",
            FindingCategory.ARITHMETIC_MISMATCH,
            "high",
            (baseline_id, halve, result_id),
            attrition=attrition,
            implied=implied,
            dropout=dropout,
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
                "assumption_dependency",
                FindingCategory.UNSUPPORTED_ASSUMPTION,
                "medium",
                (source, target),
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
            "fte_budget",
            FindingCategory.BUDGET_MISMATCH,
            "high",
            (fte_id, salary_id, allocated_id),
            fte=fte_value,
            salary=annual_salary,
            months=months,
            implied=implied,
            allocated=allocated_amount,
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
                "budget_sum",
                FindingCategory.BUDGET_MISMATCH,
                "critical",
                (*part_ids, total_id),
                part_sum=part_sum,
                total=total,
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
            "causal_design",
            FindingCategory.CAUSAL_OVERCLAIM,
            "high",
            (before_after, no_control, causal),
            0.98,
        )


__all__ = ["deterministic_checks"]
