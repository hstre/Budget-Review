"""Human-facing Markdown projection; JSON remains the machine-readable audit."""

from __future__ import annotations

from collections import Counter

from .models import ReviewDossier


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(dossier: ReviewDossier) -> str:
    semantic = dossier.semantic
    claim_by_node = {claim.claim_node_id: claim for claim in semantic.claims}
    category_counts = Counter(finding.category.value for finding in dossier.findings)
    lines = [
        "# Budget Review — Prüferdossier",
        "",
        f"**Dokument:** `{semantic.document_id}`  ",
        f"**Dokument-Hash:** `{semantic.document_hash}`  ",
        f"**Extraktion:** `{semantic.provenance.provider}/{semantic.provenance.model_id}`  ",
        f"**ClaimGraph:** {len(semantic.claims)} Claims, {len(semantic.relations)} Relationen  ",
        f"**Prüfhinweise:** {len(dossier.findings)}",
        "",
        f"> {dossier.authority_note}",
        "",
        "## Prüfprioritäten",
        "",
    ]
    if not category_counts:
        lines.append("Keine maschinell zugelassenen Prüfhinweise. Das ist kein positives Urteil.")
    else:
        lines.extend(
            f"- **{category}**: {count}" for category, count in category_counts.most_common()
        )

    lines.extend(
        [
            "",
            "## Prüfhinweise",
            "",
            "| Schwere | Kategorie | Claims | Hinweis | Frage an den Prüfer | Quelle |",
            "|---|---|---|---|---|---|",
        ]
    )
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    for finding in sorted(
        dossier.findings,
        key=lambda item: (severity_order.get(item.severity, 9), item.finding_id),
    ):
        lines.append(
            f"| {finding.severity} | {finding.category.value} | "
            f"{', '.join(finding.claim_ids)} | {_cell(finding.explanation)} | "
            f"{_cell(finding.question_for_reviewer)} | `{finding.reviewer_id}` |"
        )

    lines.extend(
        [
            "",
            "## ClaimGraph: Claims",
            "",
            "| ID | Typ | Atomarer Claim | Originalspan | Zustand |",
            "|---|---|---|---|---|",
        ]
    )
    for claim in semantic.claims:
        lines.append(
            f"| {claim.proposal_id} | {claim.claim_type.value} | "
            f"{_cell(claim.canonical_content)} | {_cell(claim.raw_span)} | "
            f"{claim.semantic_state} |"
        )

    lines.extend(
        [
            "",
            "## ClaimGraph: Relationen",
            "",
            "| Quelle | Relation | Ziel | Begründung | Zustand |",
            "|---|---|---|---|---|",
        ]
    )
    for relation in semantic.relations:
        source = claim_by_node[relation.source_claim_node_id].proposal_id
        target = claim_by_node[relation.target_claim_node_id].proposal_id
        lines.append(
            f"| {source} | {relation.relation_type.value} | {target} | "
            f"{_cell(relation.rationale)} | {relation.semantic_state} |"
        )

    lines.extend(["", "## Layer-9-Rejections", ""])
    if not semantic.rejections and not dossier.review_rejections:
        lines.append("Keine.")
    for rejection in semantic.rejections:
        lines.append(f"- `semantic:{rejection.item_kind}:{rejection.item_id}` — {rejection.reason}")
    for rejection in dossier.review_rejections:
        lines.append(f"- `review:{rejection.reviewer_id}:{rejection.item_id}` — {rejection.reason}")

    lines.extend(
        [
            "",
            "## Reviewer-Läufe",
            "",
            "| Reviewer | Art | Modell | Status | Findings |",
            "|---|---|---|---|---|",
        ]
    )
    for run in dossier.reviewer_runs:
        lines.append(
            f"| {run.get('reviewer_id', '')} | {run.get('kind', '')} | "
            f"{run.get('model_id', '')} | {run.get('status', '')} | "
            f"{run.get('finding_count', 0)} |"
        )
    lines.extend(
        [
            "",
            "---",
            "",
            "Alpha-Hinweis: Das System bereitet eine Prüfung vor. Es erteilt keine "
            "Förderempfehlung und ersetzt weder Fachprüfung noch Originalbelege.",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = ["render_markdown"]
