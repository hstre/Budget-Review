# Architektur und Autoritätsgrenzen

## 1. Problem

LLM-überarbeitete Anträge sind häufig sprachlich kohärenter als die darin
enthaltene Begründungsstruktur. Übergänge können logische Lücken verdecken.
Ein zweites LLM, das wieder nur den Fließtext liest, ist für dieselbe Glättung
anfällig. Budget Review trennt deshalb Formulierung und Prüfstruktur.

## 2. Semantic Packet

Der Extraktor liefert atomare Claim-Vorschläge mit:

- geschlossenem `claim_type`;
- normalisiertem, atomarem `canonical_content`;
- exaktem `raw_span` aus dem eingelesenen Dokument;
- `source_ref` und Konfidenz;
- vorgeschlagenen, geschlossen typisierten Relationen;
- lokal erzeugter Provenienz mit Prompt- und Output-Hash.

Der Anbieter darf keine Provenienzfelder selbst behaupten. Der Adapter setzt
sie erst nach dem API-Aufruf.

## 3. Layer-9-Gate

Das Gate ist deterministisch und replay-stabil. Es prüft:

1. eindeutige Proposal-IDs;
2. exaktes Vorkommen jedes Originalspans;
3. Mindestkonfidenz von 0,5;
4. stabile, inhaltsadressierte Claim-IDs;
5. geschlossene Relationstypen;
6. vorhandene Endpunkte, keine Selbstkanten und keine Duplikate.

Mehrdeutige Spans oder Konfidenzen unter 0,75 bleiben zugelassen, werden aber
als `human_review_required` markiert. Das Gate schließt keine inhaltliche Lücke
und kennt keinen Wahrheitszustand.

## 4. ClaimGraph

Claim-Typen:

`scope`, `target`, `capacity`, `resource`, `baseline`, `forecast`, `delivery`,
`assumption`, `budget`, `method`, `causal`, `evidence`, `limitation`,
`definition`, `other`.

Relationen:

`SUPPORTS`, `CONTRADICTS`, `DEPENDS_ON`, `ASSUMPTION_FOR`, `CONSTRAINS`,
`QUANTIFIES`, `BASELINE_FOR`, `PART_OF`, `EVIDENCED_BY`, `SCOPE_TENSION`.

Die Relationen sind Behauptungen über die Struktur des Antrags, nicht über die
Wahrheit der verbundenen Claims.

## 5. Anti-Delphi

Die Reviewer arbeiten unabhängig und sehen den gegateten Graphen statt des
glatten Ausgangstexts. Die Alpha besitzt drei verschiedenartige Kanäle:

| Kanal | Implementierung | Schwerpunkt |
|---|---|---|
| Rechenprüfer | deterministisch, offline | Arithmetik, Kapazität, FTE, Summen |
| Evidenzskeptiker | DeepSeek V4 Flash, Thinking aus | Annahmen, Baselines, Scope |
| Abhängigkeitsskeptiker | DeepSeek V4 Flash, Thinking an | Ziel–Ressourcen–Methoden-Ketten |

Reviewer sehen die Antworten der anderen Reviewer nicht. Ihre Findings müssen
auf vorhandene Claim-IDs verweisen und passieren ein zweites geschlossenes
Gate. Ungültige Findings werden als Rejection protokolliert. Das System
berechnet kein Mehrheitsurteil.

Beide LLM-Arme verwenden in der Alpha bewusst dasselbe Flash-Modell, weil es
im kontrollierten Live-Lauf mindestens gleich gute Hinweise mit deutlich
geringerem Tokenaufwand lieferte. Das ist Perspektivtrennung, keine behauptete
Modellvielfalt.

## 6. Dossier

Das Markdown-Dossier ist die Arbeitsansicht für den Menschen. JSON ist der
vollständige maschinenlesbare Audit mit:

- Dokument- und Provenienz-Hashes;
- Claims, Originalspans, Relationen und Gate-Zuständen;
- Findings samt Reviewer, Modell, Konfidenz und Prüferfrage;
- Rejections beider Gates;
- Reviewer-Läufen und Token-Nutzung, aber ohne Promptinhalte oder Secrets.

Die letzte Autorität liegt explizit beim Prüfer.
