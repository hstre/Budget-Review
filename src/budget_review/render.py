"""Simple human report; JSON remains the complete machine-readable audit."""

from __future__ import annotations

from html import escape

from .consolidate import (
    CATEGORY_LABELS,
    REVIEWER_LABELS,
    SEVERITY_LABELS,
    ConsolidatedIssue,
    consolidate_findings,
)
from .models import ClaimType, FindingCategory, GovernedClaim, ReviewDossier
from .profiles import authority_note, get_profile


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(dossier: ReviewDossier, language: str = "de") -> str:
    language = language if language in _TEXT else "de"
    t = _TEXT[language]
    profile = get_profile(dossier.profile)
    issues = consolidate_findings(dossier.findings)
    lines = [
        f"# {profile.display_name} — {t['md_dossier']}",
        "",
        f"**{t['md_document']}:** `{dossier.semantic.document_id}`  ",
        f"**{t['md_to_review']}:** {len(issues)} {t['md_points']}  ",
        f"**{t['md_basis']}:** {len(dossier.semantic.claims)} {t['md_basis_claims']}, "
        f"{len(dossier.semantic.relations)} {t['md_basis_relations']}, "
        f"{len(dossier.findings)} {t['md_basis_findings']}",
        "",
        f"> {authority_note(profile, language)}",
        "",
    ]
    if profile.name == "general":
        lines.extend(_markdown_argument_map(dossier, language))
    if not issues:
        lines.extend([f"## {t['no_findings']}", "", t["no_positive"]])
    for issue in issues:
        lines.extend(_markdown_issue(dossier, issue, language))
    lines.extend(
        [
            "",
            f"## {t['md_audit']}",
            "",
            f"- {t['document_hash']}: `{dossier.semantic.document_hash}`",
            f"- {t['extraction']}: `{dossier.semantic.provenance.provider}/"
            f"{dossier.semantic.provenance.model_id}`",
            f"- {t['md_semantic_rejections']}: {len(dossier.semantic.rejections)}",
            f"- {t['md_review_rejections']}: {len(dossier.review_rejections)}",
            f"- {t['md_full_audit']}: `dossier.json`",
        ]
    )
    return "\n".join(lines) + "\n"


def _markdown_issue(
    dossier: ReviewDossier, issue: ConsolidatedIssue, language: str = "de"
) -> list[str]:
    t = _TEXT[language]
    claims = {claim.proposal_id: claim for claim in dossier.semantic.claims}
    severity = _severity_label(issue.severity, language)
    category = _category_label(issue.category, language)
    reviewers = ", ".join(_reviewer_label(item, language) for item in issue.reviewer_ids)
    lines = [
        f"## {issue.issue_id} · {severity}: {category}",
        "",
        f"**{issue.title}**",
        "",
        issue.explanation,
        "",
        f"**{t['review_question']}:** {issue.question}",
        "",
        f"**{t['md_detected_by']}:** {reviewers}",
        "",
        f"**{t['md_claims']}:**",
        "",
    ]
    for claim_id in issue.claim_ids:
        claim = claims.get(claim_id)
        if claim is not None:
            opening, closing = t["md_quote"]
            lines.append(
                f"- `{claim_id}` {_cell(claim.canonical_content)} — "
                f"{opening}{_cell(claim.raw_span)}{closing}"
            )
    lines.append("")
    return lines


def render_html(
    dossier: ReviewDossier,
    language: str = "de",
    navigation: bool = False,
) -> str:
    language = language if language in _TEXT else "de"
    t = _TEXT[language]
    profile = get_profile(dossier.profile)
    issues = consolidate_findings(dossier.findings)
    urgent = tuple(issue for issue in issues if issue.severity in {"critical", "high"})
    further = tuple(issue for issue in issues if issue.severity not in {"critical", "high"})
    rejection_count = len(dossier.semantic.rejections) + len(dossier.review_rejections)
    empty = (
        f'<section class="empty"><h2>{t["no_findings"]}</h2><p>{t["no_positive"]}</p></section>'
        if not issues
        else ""
    )
    urgent_section = _issue_section(dossier, t["first"], t["high_priority"], urgent, language)
    further_section = _issue_section(dossier, t["then"], t["more_findings"], further, language)
    argument_map = _argument_map_html(dossier, language) if profile.name == "general" else ""
    navigation_html = (
        f'<nav class="result-nav"><a href="/">{t["new_review"]}</a>'
        f'<a href="/settings">{t["settings"]}</a></nav>'
        if navigation
        else ""
    )
    return f"""<!doctype html>
<html lang="{language}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(profile.display_name)} · {escape(dossier.semantic.document_id)}</title>
  <style>{_CSS}</style>
</head>
<body>
  <main>
    {navigation_html}
    <header class="hero">
      <div>
        <p class="eyebrow">{escape(profile.display_name)} · Alpha</p>
        <h1>{t["dossier"]}</h1>
        <p class="document">{escape(dossier.semantic.document_id)}</p>
      </div>
      {_decision_note(profile.name, language)}
    </header>
    <section class="summary" aria-label="{t["summary"]}">
      <div><strong>{len(issues)}</strong><span>{t["review_points"]}</span></div>
      <div><strong>{len(urgent)}</strong><span>{t["high_priority"]}</span></div>
      <div><strong>{len(dossier.semantic.claims)}</strong><span>{t["original_claims"]}</span></div>
      <div><strong>{rejection_count}</strong><span>{t["rejected"]}</span></div>
    </section>
    {_intro_html(profile.name, language)}
    {argument_map}
    {empty}
    {urgent_section}
    {further_section}
    {_audit_html(dossier, language)}
    <footer>{t["human_decides"]}</footer>
  </main>
</body>
</html>
"""


def _issue_section(
    dossier: ReviewDossier,
    eyebrow: str,
    title: str,
    issues: tuple[ConsolidatedIssue, ...],
    language: str,
) -> str:
    if not issues:
        return ""
    cards = "".join(_issue_html(dossier, issue, language) for issue in issues)
    return (
        f'<section><div class="section-heading"><p>{escape(eyebrow)}</p>'
        f"<h2>{escape(title)}</h2></div>"
        f'<div class="issue-list">{cards}</div></section>'
    )


def _argument_groups(
    dossier: ReviewDossier,
) -> tuple[tuple[str, tuple[GovernedClaim, ...]], ...]:
    definitions = (
        (
            "Kernthesen",
            {ClaimType.THESIS},
        ),
        (
            "Schlüsse und Empfehlungen",
            {
                ClaimType.INFERENCE,
                ClaimType.RECOMMENDATION,
                ClaimType.CAUSAL,
                ClaimType.FORECAST,
            },
        ),
        (
            "Fakten, Belege und Beispiele",
            {ClaimType.FACT, ClaimType.EVIDENCE, ClaimType.EXAMPLE, ClaimType.BASELINE},
        ),
        (
            "Annahmen und Begrenzungen",
            {
                ClaimType.ASSUMPTION,
                ClaimType.LIMITATION,
                ClaimType.SCOPE,
                ClaimType.DEFINITION,
                ClaimType.VALUE_JUDGMENT,
            },
        ),
    )
    assigned = set().union(*(types for _, types in definitions))
    groups = [
        (label, tuple(claim for claim in dossier.semantic.claims if claim.claim_type in types))
        for label, types in definitions
    ]
    remaining = tuple(
        claim for claim in dossier.semantic.claims if claim.claim_type not in assigned
    )
    if remaining:
        groups.append(("Weitere Aussagen", remaining))
    return tuple((label, claims) for label, claims in groups if claims)


def _markdown_argument_map(dossier: ReviewDossier, language: str = "de") -> list[str]:
    lines = [f"## {_TEXT[language]['content_map']}", ""]
    for label, claims in _argument_groups(dossier):
        lines.extend((f"**{_argument_group_label(label, language)}**", ""))
        lines.extend(
            f"- `{claim.proposal_id}` {_cell(claim.canonical_content)}" for claim in claims
        )
        lines.append("")
    return lines


def _argument_map_html(dossier: ReviewDossier, language: str) -> str:
    t = _TEXT[language]
    groups = "".join(
        (
            '<div class="argument-group">'
            f"<h3>{escape(_argument_group_label(label, language))}</h3><ul>"
            + "".join(
                f"<li><code>{escape(claim.proposal_id)}</code> "
                f"{escape(claim.canonical_content)}</li>"
                for claim in claims
            )
            + "</ul></div>"
        )
        for label, claims in _argument_groups(dossier)
    )
    return (
        '<section class="argument-map"><div class="section-heading">'
        f"<p>{t['understand_first']}</p><h2>{t['content_map']}</h2></div>"
        f'<div class="argument-grid">{groups}</div></section>'
    )


def _decision_note(profile: str, language: str) -> str:
    t = _TEXT[language]
    if profile == "budget":
        return (
            f'<div class="decision-note">{t["decision_support"]}<br>'
            f"<strong>{t['no_funding_verdict']}</strong></div>"
        )
    return (
        f'<div class="decision-note">{t["content_only"]}<br>'
        f"<strong>{t['no_style_verdict']}</strong></div>"
    )


def _intro_html(profile: str, language: str) -> str:
    t = _TEXT[language]
    if profile == "general":
        return f'<p class="intro">{t["general_intro"]}</p>'
    return f'<p class="intro">{t["budget_intro"]}</p>'


def _issue_html(dossier: ReviewDossier, issue: ConsolidatedIssue, language: str) -> str:
    t = _TEXT[language]
    claims = {claim.proposal_id: claim for claim in dossier.semantic.claims}
    shown_claims = [claim_id for claim_id in issue.claim_ids if claim_id in claims]
    claim_rows = "".join(
        (
            f"<li><code>{escape(claim_id)}</code><div><strong>"
            f"{escape(claims[claim_id].canonical_content)}</strong><blockquote>"
            f"{escape(claims[claim_id].raw_span)}</blockquote></div></li>"
        )
        for claim_id in shown_claims
    )
    voices = "".join(
        f"<li><strong>{escape(_reviewer_label(finding.reviewer_id, language))}"
        f"</strong>: {escape(finding.explanation)}</li>"
        for finding in issue.findings
    )
    sources = " · ".join(
        escape(_reviewer_label(reviewer_id, language)) for reviewer_id in issue.reviewer_ids
    )
    severity = _severity_label(issue.severity, language)
    category = _category_label(issue.category, language)
    return f"""
<article class="issue {escape(issue.severity)}">
  <div class="issue-topline">
    <span class="badge">{escape(severity)}</span>
    <span>{escape(issue.issue_id)} · {escape(category)}</span>
  </div>
  <h3>{escape(issue.title)}</h3>
  <p class="explanation">{escape(issue.explanation)}</p>
  <div class="question"><span>{t["review_question"]}</span>
    <strong>{escape(issue.question)}</strong></div>
  <p class="sources">{sources}</p>
  <details>
    <summary>{t["show_claims"]} ({len(shown_claims)})</summary>
    <ul class="claims">{claim_rows}</ul>
  </details>
  <details>
    <summary>{t["show_paths"]} ({len(issue.findings)})</summary>
    <ul class="voices">{voices}</ul>
  </details>
</article>"""


def _audit_html(dossier: ReviewDossier, language: str) -> str:
    t = _TEXT[language]
    claim_count = len(dossier.semantic.claims)
    relation_count = len(dossier.semantic.relations)
    rejection_count = len(dossier.semantic.rejections) + len(dossier.review_rejections)
    return f"""
<details class="audit">
  <summary>{t["show_audit"]}</summary>
  <dl>
    <div><dt>{t["document_hash"]}</dt><dd><code>{escape(dossier.semantic.document_hash)}</code></dd></div>
    <div><dt>{t["extraction"]}</dt><dd>{escape(dossier.semantic.provenance.provider)}/{escape(dossier.semantic.provenance.model_id)}</dd></div>
    <div><dt>{t["profile"]}</dt><dd>{escape(dossier.profile)}</dd></div>
    <div><dt>ClaimGraph</dt><dd>{claim_count} Claims · {relation_count} {t["relations"]}</dd></div>
    <div><dt>{t["raw_findings"]}</dt><dd>{len(dossier.findings)}</dd></div>
    <div><dt>Rejections</dt><dd>{rejection_count}</dd></div>
  </dl>
  <p>{t["full_audit"]} <code>dossier.json</code>.</p>
</details>"""


_TEXT = {
    "de": {
        "dossier": "Prüferdossier",
        "summary": "Zusammenfassung",
        "review_points": "Prüfpunkte",
        "high_priority": "hohe Priorität",
        "original_claims": "Originalaussagen",
        "rejected": "nicht zugelassen",
        "no_findings": "Keine maschinellen Prüfhinweise",
        "no_positive": (
            "Das ist kein positives Urteil. Der Text muss weiterhin inhaltlich geprüft werden."
        ),
        "first": "Zuerst",
        "then": "Danach",
        "more_findings": "Weitere Hinweise",
        "understand_first": "Zuerst verstehen",
        "content_map": "Inhaltsgerüst",
        "decision_support": "Entscheidungshilfe",
        "no_funding_verdict": "Kein Fördervotum",
        "content_only": "Nur Inhalt",
        "no_style_verdict": "Kein Stil- oder Autorenurteil",
        "general_intro": (
            "Sehen Sie zuerst das Inhaltsgerüst an. Prüfen Sie danach die markierten "
            "Verbindungen und bei Bedarf den Originalwortlaut."
        ),
        "budget_intro": (
            "Beginnen Sie mit den Punkten hoher Priorität. Öffnen Sie die "
            "Originalaussagen erst, wenn Sie den Wortlaut prüfen möchten."
        ),
        "review_question": "Prüffrage",
        "show_claims": "Originalaussagen ansehen",
        "show_paths": "Einzelne Prüfwege",
        "show_audit": "Technischen Audit anzeigen",
        "document_hash": "Dokument-Hash",
        "extraction": "Extraktion",
        "profile": "Prüfprofil",
        "raw_findings": "Rohe Findings",
        "relations": "Relationen",
        "full_audit": "Der vollständige maschinenlesbare Audit steht in",
        "human_decides": "Die letzte Entscheidung trifft immer ein Mensch.",
        "new_review": "Neue Prüfung",
        "settings": "Einstellungen",
        "md_dossier": "Prüferdossier",
        "md_document": "Dokument",
        "md_to_review": "Zu prüfen",
        "md_points": "konsolidierte Punkte",
        "md_basis": "Grundlage",
        "md_basis_claims": "Originalaussagen",
        "md_basis_relations": "Relationen",
        "md_basis_findings": "rohe Prüfhinweise",
        "md_detected_by": "Erkannt durch",
        "md_claims": "Originalaussagen",
        "md_audit": "Technischer Audit",
        "md_semantic_rejections": "Layer-9-Rejections",
        "md_review_rejections": "Reviewer-Rejections",
        "md_full_audit": "Vollständige Einzelbefunde und Provenienz",
        "md_quote": ("\u201e", "\u201c"),
    },
    "en": {
        "dossier": "Reviewer dossier",
        "summary": "Summary",
        "review_points": "review points",
        "high_priority": "high priority",
        "original_claims": "original claims",
        "rejected": "not admitted",
        "no_findings": "No machine-generated review findings",
        "no_positive": "This is not a positive verdict. The content still requires human review.",
        "first": "First",
        "then": "Then",
        "more_findings": "Further findings",
        "understand_first": "Understand first",
        "content_map": "Content map",
        "decision_support": "Decision support",
        "no_funding_verdict": "No funding verdict",
        "content_only": "Content only",
        "no_style_verdict": "No style or authorship verdict",
        "general_intro": (
            "Start with the content map. Then inspect the marked connections and open the "
            "original wording where needed."
        ),
        "budget_intro": (
            "Start with high-priority points. Open the original claims when you need to "
            "verify the wording."
        ),
        "review_question": "Review question",
        "show_claims": "Show original claims",
        "show_paths": "Individual review paths",
        "show_audit": "Show technical audit",
        "document_hash": "Document hash",
        "extraction": "Extraction",
        "profile": "Review profile",
        "raw_findings": "Raw findings",
        "relations": "relations",
        "full_audit": "The complete machine-readable audit is available in",
        "human_decides": "The final decision always remains with a human.",
        "new_review": "New review",
        "settings": "Settings",
        "md_dossier": "Reviewer dossier",
        "md_document": "Document",
        "md_to_review": "To review",
        "md_points": "consolidated points",
        "md_basis": "Basis",
        "md_basis_claims": "original claims",
        "md_basis_relations": "relations",
        "md_basis_findings": "raw findings",
        "md_detected_by": "Detected by",
        "md_claims": "Original claims",
        "md_audit": "Technical audit",
        "md_semantic_rejections": "Layer 9 rejections",
        "md_review_rejections": "Reviewer rejections",
        "md_full_audit": "Complete individual findings and provenance",
        "md_quote": ("\u201c", "\u201d"),
    },
}

_CATEGORY_LABELS_EN = {
    FindingCategory.ARITHMETIC_MISMATCH: "Arithmetic mismatch",
    FindingCategory.BUDGET_MISMATCH: "Budget mismatch",
    FindingCategory.CAPACITY_MISMATCH: "Capacity mismatch",
    FindingCategory.RESOURCE_MISMATCH: "Resource mismatch",
    FindingCategory.UNSUPPORTED_ASSUMPTION: "Unsupported assumption",
    FindingCategory.EVIDENCE_GAP: "Evidence gap",
    FindingCategory.CAUSAL_OVERCLAIM: "Causal overclaim",
    FindingCategory.SCOPE_TENSION: "Scope tension",
    FindingCategory.INTERNAL_CONTRADICTION: "Internal contradiction",
    FindingCategory.LOGICAL_GAP: "Logical gap",
    FindingCategory.OVERGENERALIZATION: "Overgeneralization",
    FindingCategory.DEFINITION_SHIFT: "Definition shift",
    FindingCategory.RELEVANCE_GAP: "Relevance gap",
    FindingCategory.REVIEW_QUESTION: "Open review question",
}

_REVIEWER_LABELS_EN = {
    "deterministic-checks": "Deterministic structure and arithmetic checks",
    "flash-evidence-skeptic": "Evidence review (Flash)",
    "flash-thinking-dependency-skeptic": "Dependency review (Flash + Thinking)",
    "flash-thinking-argument-skeptic": "Argument review (Flash + Thinking)",
}


def _category_label(category: FindingCategory, language: str) -> str:
    if language == "en":
        return _CATEGORY_LABELS_EN.get(category, category.value)
    return CATEGORY_LABELS[category]


def _severity_label(severity: str, language: str) -> str:
    if language == "en":
        return {
            "critical": "Critical",
            "high": "High",
            "medium": "Medium",
            "low": "Low",
        }.get(severity, severity)
    return SEVERITY_LABELS.get(severity, severity)


def _reviewer_label(reviewer_id: str, language: str) -> str:
    if language == "en":
        return _REVIEWER_LABELS_EN.get(reviewer_id, reviewer_id)
    return REVIEWER_LABELS.get(reviewer_id, reviewer_id)


def _argument_group_label(label: str, language: str) -> str:
    if language == "de":
        return label
    return {
        "Kernthesen": "Core theses",
        "Schlüsse und Empfehlungen": "Inferences and recommendations",
        "Fakten, Belege und Beispiele": "Facts, evidence and examples",
        "Annahmen und Begrenzungen": "Assumptions and limitations",
        "Weitere Aussagen": "Further claims",
    }.get(label, label)


_CSS = """
:root { color-scheme: light; --ink:#18202a; --muted:#69727d; --line:#dfe3e8;
  --paper:#fff; --ground:#f4f5f7; --accent:#2457d6; --critical:#b42318;
  --high:#b54708; --medium:#175cd3; --low:#667085; }
* { box-sizing:border-box; }
body { margin:0; background:var(--ground); color:var(--ink); font:16px/1.55
  -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
main { width:min(980px,calc(100% - 32px)); margin:40px auto 80px; }
.result-nav { display:flex; justify-content:flex-end; gap:18px; margin-bottom:28px; }
.result-nav a { color:var(--accent); text-decoration:none; font-weight:650; }
.hero { display:flex; justify-content:space-between; gap:24px; align-items:flex-end; }
.eyebrow,.section-heading p { margin:0 0 4px; color:var(--accent); font-size:.78rem;
  font-weight:750; letter-spacing:.08em; text-transform:uppercase; }
h1 { margin:0; font-size:clamp(2rem,6vw,3.6rem); letter-spacing:-.045em; line-height:1; }
.document { margin:12px 0 0; color:var(--muted); }
.decision-note { border:1px solid var(--line); border-radius:12px; background:var(--paper);
  padding:12px 16px; text-align:right; color:var(--muted); font-size:.88rem; }
.decision-note strong { color:var(--ink); }
.summary { display:grid; grid-template-columns:repeat(4,1fr); gap:1px; margin:32px 0 52px;
  overflow:hidden; border:1px solid var(--line); border-radius:16px; background:var(--line); }
.summary div { display:flex; flex-direction:column; background:var(--paper); padding:18px; }
.summary strong { font-size:1.7rem; letter-spacing:-.03em; }
.summary span { color:var(--muted); font-size:.84rem; }
.intro { max-width:650px; margin:-28px 0 44px; color:var(--muted); }
.argument-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
.argument-group { border:1px solid var(--line); border-radius:12px; background:var(--paper);
  padding:16px 18px; }
.argument-group h3 { margin:0 0 8px; font-size:.92rem; }
.argument-group ul { list-style:none; margin:0; padding:0; }
.argument-group li { padding:7px 0; border-top:1px solid #eef0f2; font-size:.88rem; }
.argument-group code { margin-right:4px; }
.section-heading { margin:42px 0 16px; }
.section-heading h2 { margin:0; font-size:1.5rem; letter-spacing:-.02em; }
.issue-list { display:grid; gap:14px; }
.issue { border:1px solid var(--line); border-left:5px solid var(--low); border-radius:14px;
  background:var(--paper); padding:22px 24px; box-shadow:0 1px 2px rgba(16,24,40,.04); }
.issue.critical { border-left-color:var(--critical); }
.issue.high { border-left-color:var(--high); }
.issue.medium { border-left-color:var(--medium); }
.issue-topline { display:flex; gap:10px; align-items:center; color:var(--muted);
  font-size:.78rem; font-weight:700; text-transform:uppercase; letter-spacing:.04em; }
.badge { border-radius:999px; background:#f2f4f7; color:var(--ink); padding:3px 8px; }
.critical .badge { color:var(--critical); background:#fef3f2; }
.high .badge { color:var(--high); background:#fffaeb; }
.medium .badge { color:var(--medium); background:#eff8ff; }
.issue h3 { margin:12px 0 8px; font-size:1.25rem; line-height:1.3; }
.explanation { margin:0 0 18px; }
.question { display:grid; gap:4px; border-radius:10px; background:#f7f9fc; padding:14px 16px; }
.question span { color:var(--accent); font-size:.75rem; font-weight:750; text-transform:uppercase; }
.sources { color:var(--muted); font-size:.78rem; margin:14px 0 6px; }
details { border-top:1px solid var(--line); margin-top:10px; padding-top:10px; }
summary { cursor:pointer; color:var(--accent); font-weight:650; }
.claims,.voices { list-style:none; padding:4px 0 0; margin:8px 0 0; }
.claims li { display:grid; grid-template-columns:52px 1fr; gap:8px; padding:10px 0;
  border-top:1px solid #eef0f2; }
blockquote { margin:5px 0 0; color:var(--muted); font-size:.88rem; }
.voices li { padding:8px 0; border-top:1px solid #eef0f2; font-size:.88rem; }
.audit { margin-top:42px; border:1px solid var(--line); border-radius:14px;
  background:var(--paper); padding:18px 22px; }
.audit dl div { display:grid; grid-template-columns:150px 1fr; gap:12px; margin:8px 0; }
.audit dt { color:var(--muted); } .audit dd { margin:0; overflow-wrap:anywhere; }
footer { color:var(--muted); text-align:center; margin-top:34px; font-size:.82rem; }
.empty { background:var(--paper); border:1px solid var(--line); border-radius:14px; padding:24px; }
@media (max-width:700px) { main { margin-top:24px; } .hero { align-items:flex-start;
  flex-direction:column; } .decision-note { text-align:left; }
  .summary { grid-template-columns:1fr 1fr; }
  .argument-grid { grid-template-columns:1fr; }
  .issue { padding:18px; } .audit dl div { grid-template-columns:1fr; gap:0; } }
@media print { body { background:#fff; } main { width:100%; margin:0; }
  .issue { break-inside:avoid; box-shadow:none; }
  details:not([open]) > *:not(summary) { display:block; }
  summary { color:var(--ink); } }
"""


__all__ = ["render_html", "render_markdown"]
