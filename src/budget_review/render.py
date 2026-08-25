"""Simple human report; JSON remains the complete machine-readable audit."""

from __future__ import annotations

from html import escape

from .consolidate import REVIEWER_LABELS, ConsolidatedIssue, consolidate_findings
from .models import ReviewDossier


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(dossier: ReviewDossier) -> str:
    issues = consolidate_findings(dossier.findings)
    lines = [
        "# Budget Review — Prüferdossier",
        "",
        f"**Dokument:** `{dossier.semantic.document_id}`  ",
        f"**Zu prüfen:** {len(issues)} konsolidierte Punkte  ",
        f"**Grundlage:** {len(dossier.semantic.claims)} Originalaussagen, "
        f"{len(dossier.semantic.relations)} Relationen, "
        f"{len(dossier.findings)} rohe Prüfhinweise",
        "",
        "> Entscheidungshilfe, kein Fördervotum. Die letzte Entscheidung liegt beim Menschen.",
        "",
    ]
    if not issues:
        lines.extend(
            [
                "## Keine maschinellen Prüfhinweise",
                "",
                "Das ist kein positives Urteil. Der Antrag muss weiterhin fachlich geprüft werden.",
            ]
        )
    for issue in issues:
        lines.extend(_markdown_issue(dossier, issue))
    lines.extend(
        [
            "",
            "## Technischer Audit",
            "",
            f"- Dokument-Hash: `{dossier.semantic.document_hash}`",
            f"- Extraktion: `{dossier.semantic.provenance.provider}/"
            f"{dossier.semantic.provenance.model_id}`",
            f"- Layer-9-Rejections: {len(dossier.semantic.rejections)}",
            f"- Reviewer-Rejections: {len(dossier.review_rejections)}",
            "- Vollständige Einzelbefunde und Provenienz: `dossier.json`",
        ]
    )
    return "\n".join(lines) + "\n"


def _markdown_issue(dossier: ReviewDossier, issue: ConsolidatedIssue) -> list[str]:
    claims = {claim.proposal_id: claim for claim in dossier.semantic.claims}
    lines = [
        f"## {issue.issue_id} · {issue.severity_label}: {issue.category_label}",
        "",
        f"**{issue.title}**",
        "",
        issue.explanation,
        "",
        f"**Prüffrage:** {issue.question}",
        "",
        f"**Erkannt durch:** {', '.join(issue.reviewer_labels)}",
        "",
        "**Originalaussagen:**",
        "",
    ]
    for claim_id in issue.claim_ids:
        claim = claims.get(claim_id)
        if claim is not None:
            lines.append(
                f"- `{claim_id}` {_cell(claim.canonical_content)} — „{_cell(claim.raw_span)}“"
            )
    lines.append("")
    return lines


def render_html(dossier: ReviewDossier) -> str:
    issues = consolidate_findings(dossier.findings)
    urgent = tuple(issue for issue in issues if issue.severity in {"critical", "high"})
    further = tuple(issue for issue in issues if issue.severity not in {"critical", "high"})
    rejection_count = len(dossier.semantic.rejections) + len(dossier.review_rejections)
    empty = (
        '<section class="empty"><h2>Keine maschinellen Prüfhinweise</h2>'
        "<p>Das ist kein positives Urteil. Der Antrag muss weiterhin fachlich geprüft werden.</p>"
        "</section>"
        if not issues
        else ""
    )
    urgent_section = _issue_section(dossier, "Zuerst", "Hohe Priorität", urgent)
    further_section = _issue_section(dossier, "Danach", "Weitere Hinweise", further)
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Budget Review · {escape(dossier.semantic.document_id)}</title>
  <style>{_CSS}</style>
</head>
<body>
  <main>
    <header class="hero">
      <div>
        <p class="eyebrow">Budget Review · Alpha</p>
        <h1>Prüferdossier</h1>
        <p class="document">{escape(dossier.semantic.document_id)}</p>
      </div>
      <div class="decision-note">Entscheidungshilfe<br><strong>Kein Fördervotum</strong></div>
    </header>
    <section class="summary" aria-label="Zusammenfassung">
      <div><strong>{len(issues)}</strong><span>Prüfpunkte</span></div>
      <div><strong>{len(urgent)}</strong><span>hohe Priorität</span></div>
      <div><strong>{len(dossier.semantic.claims)}</strong><span>Originalaussagen</span></div>
      <div><strong>{rejection_count}</strong><span>nicht zugelassen</span></div>
    </section>
    <p class="intro">Beginnen Sie mit den Punkten hoher Priorität. Öffnen Sie die
      Originalaussagen erst, wenn Sie den Wortlaut prüfen möchten.</p>
    {empty}
    {urgent_section}
    {further_section}
    {_audit_html(dossier)}
    <footer>Die letzte Entscheidung trifft immer ein Mensch.</footer>
  </main>
</body>
</html>
"""


def _issue_section(
    dossier: ReviewDossier,
    eyebrow: str,
    title: str,
    issues: tuple[ConsolidatedIssue, ...],
) -> str:
    if not issues:
        return ""
    cards = "".join(_issue_html(dossier, issue) for issue in issues)
    return (
        f'<section><div class="section-heading"><p>{escape(eyebrow)}</p>'
        f"<h2>{escape(title)}</h2></div>"
        f'<div class="issue-list">{cards}</div></section>'
    )


def _issue_html(dossier: ReviewDossier, issue: ConsolidatedIssue) -> str:
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
        f"<li><strong>{escape(REVIEWER_LABELS.get(finding.reviewer_id, finding.reviewer_id))}"
        f"</strong>: {escape(finding.explanation)}</li>"
        for finding in issue.findings
    )
    sources = " · ".join(escape(label) for label in issue.reviewer_labels)
    return f"""
<article class="issue {escape(issue.severity)}">
  <div class="issue-topline">
    <span class="badge">{escape(issue.severity_label)}</span>
    <span>{escape(issue.issue_id)} · {escape(issue.category_label)}</span>
  </div>
  <h3>{escape(issue.title)}</h3>
  <p class="explanation">{escape(issue.explanation)}</p>
  <div class="question"><span>Prüffrage</span><strong>{escape(issue.question)}</strong></div>
  <p class="sources">{sources}</p>
  <details>
    <summary>Originalaussagen ansehen ({len(shown_claims)})</summary>
    <ul class="claims">{claim_rows}</ul>
  </details>
  <details>
    <summary>Einzelne Prüfwege ({len(issue.findings)})</summary>
    <ul class="voices">{voices}</ul>
  </details>
</article>"""


def _audit_html(dossier: ReviewDossier) -> str:
    claim_count = len(dossier.semantic.claims)
    relation_count = len(dossier.semantic.relations)
    rejection_count = len(dossier.semantic.rejections) + len(dossier.review_rejections)
    return f"""
<details class="audit">
  <summary>Technischen Audit anzeigen</summary>
  <dl>
    <div><dt>Dokument-Hash</dt><dd><code>{escape(dossier.semantic.document_hash)}</code></dd></div>
    <div><dt>Extraktion</dt><dd>{escape(dossier.semantic.provenance.provider)}/{escape(dossier.semantic.provenance.model_id)}</dd></div>
    <div><dt>ClaimGraph</dt><dd>{claim_count} Claims · {relation_count} Relationen</dd></div>
    <div><dt>Rohe Findings</dt><dd>{len(dossier.findings)}</dd></div>
    <div><dt>Rejections</dt><dd>{rejection_count}</dd></div>
  </dl>
  <p>Der vollständige maschinenlesbare Audit steht in <code>dossier.json</code>.</p>
</details>"""


_CSS = """
:root { color-scheme: light; --ink:#18202a; --muted:#69727d; --line:#dfe3e8;
  --paper:#fff; --ground:#f4f5f7; --accent:#2457d6; --critical:#b42318;
  --high:#b54708; --medium:#175cd3; --low:#667085; }
* { box-sizing:border-box; }
body { margin:0; background:var(--ground); color:var(--ink); font:16px/1.55
  -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
main { width:min(980px,calc(100% - 32px)); margin:40px auto 80px; }
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
  .issue { padding:18px; } .audit dl div { grid-template-columns:1fr; gap:0; } }
@media print { body { background:#fff; } main { width:100%; margin:0; }
  .issue { break-inside:avoid; box-shadow:none; }
  details:not([open]) > *:not(summary) { display:block; }
  summary { color:var(--ink); } }
"""


__all__ = ["render_html", "render_markdown"]
