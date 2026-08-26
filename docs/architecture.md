# Architektur und Autoritätsgrenzen

## 1. Problem

Form und Inhalt sind bei LLM-überarbeiteten Texten leicht zu verwechseln.
Sprachliche Glätte kann logische Lücken verdecken; umgekehrt kann ein rau
formulierter Text eine tragfähige Argumentation enthalten. Ein Inhaltsprüfer
darf deshalb weder Stilmerkmale noch vermutete KI-Autorenschaft als Signal für
inhaltliche Qualität verwenden.

Content Review trennt die Aufgaben strikt:

1. Inhalt in eine prüfbare Struktur überführen;
2. diese Struktur auf definierte Spannungen prüfen;
3. dem Menschen Originalstellen und konkrete Prüffragen vorlegen.

## 2. Semantic Packet

Der Extraktor liefert atomare Claim-Vorschläge mit:

- geschlossenem `claim_type`;
- normalisiertem, atomarem `canonical_content`;
- exaktem `raw_span` aus dem eingelesenen Dokument;
- `source_ref` und Konfidenz;
- vorgeschlagenen, geschlossen typisierten Relationen;
- lokal erzeugter Provenienz mit Prompt- und Output-Hash.

Allgemeine Claim-Typen umfassen `thesis`, `fact`, `inference`,
`value_judgment`, `recommendation`, `example`, `assumption`, `causal`,
`evidence`, `limitation`, `definition` und `scope`. Das Budgetprofil ergänzt
unter anderem `target`, `capacity`, `resource`, `delivery` und `budget`.

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

Inhaltsadressierung heißt: Zwei Vorschläge mit gleichem Typ, gleichem
`canonical_content` und gleichem `raw_span` bezeichnen denselben Knoten. Der
zweite wird als `duplicate_claim_node` abgewiesen, seine Kanten bleiben aber
erhalten und zeigen auf den zugelassenen Knoten. Relationen werden deshalb über
die aufgelösten Knoten-IDs dedupliziert, nicht über Proposal-IDs; eine doppelt
vorgeschlagene Kante erscheint als `duplicate_relation` im Audit. Claim- und
Relations-IDs sind im Dossier damit eindeutig.

Mehrdeutige Spans oder Konfidenzen unter 0,75 bleiben zugelassen, werden aber
als `human_review_required` markiert. Das Gate schließt keine inhaltliche Lücke
und kennt keinen Wahrheitszustand.

## 4. ClaimGraph

Kernrelationen sind `SUPPORTS`, `CONTRADICTS`, `DEPENDS_ON`,
`ASSUMPTION_FOR`, `EVIDENCED_BY`, `QUALIFIES`, `GENERALIZES`, `EXAMPLE_OF`,
`ENTAILS` und `SCOPE_TENSION`. Budget- und Zahlenstrukturen verwenden außerdem
`QUANTIFIES`, `BASELINE_FOR` und `PART_OF`.

Relationen sind Vorschläge über die Argumentstruktur des Textes, nicht über die
Wahrheit der verbundenen Aussagen.

## 5. Profile

Ein Profil verändert nur drei kontrollierte Komponenten:

- Extraktionsfokus;
- deterministische Regeln;
- unabhängige Reviewer-Rollen.

Der semantische Vertrag, das Gate, die Konsolidierung und die menschliche
Merge-Autorität bleiben identisch. `general` ist das Standardprofil. `budget`
ist der erste Domänenadapter und bewahrt die bisherige Budgetfunktion.

## 6. Anti-Delphi

Die Reviewer arbeiten unabhängig und sehen den gegateten Graphen statt des
glatten Ausgangstexts. Im allgemeinen Profil prüft ein Arm Evidenzbezüge; der
Thinking-Arm verfolgt Prämissen, Schlussfolgerungen, Verallgemeinerungen,
Widersprüche sowie Scope- und Begriffswechsel. Das Budgetprofil ersetzt den
zweiten Schwerpunkt durch Ziel–Ressourcen–Methoden–Budget-Abhängigkeiten.

Beide Arme verwenden DeepSeek V4 Flash, einmal ohne und einmal mit Thinking.
Sie sehen ihre gegenseitigen Antworten nicht. Findings müssen auf vorhandene
Claim-IDs verweisen und passieren ein zweites geschlossenes Gate. Das System
berechnet kein Mehrheitsurteil.

## 7. Deterministische Prüfungen

Im allgemeinen Profil werden nur explizite Graphstrukturen geprüft:

- `CONTRADICTS` → möglicher innerer Widerspruch;
- `GENERALIZES` → zu prüfende Verallgemeinerung;
- `SCOPE_TENSION` → wechselnder Geltungsbereich;
- zentrale Aussagen ohne zugelassene Stützverbindung → logische Lücke;
- wirksame Annahmen ohne Evidenzverbindung → unbelegte Annahme.

Das Budgetprofil verwendet zusätzlich konservative Rechenregeln für Kapazität,
Ressourcen, Prozentangaben, FTE und Summen.

## 8. Konsolidierung und Dossier

Findings mit stark überlappenden Claim-Mengen werden für die menschliche Ansicht
zu einem Prüfpunkt verbunden. Schweregrad, betroffene Claims und alle Prüfwege
bleiben erhalten. Das ist reine Darstellung: Jeder Einzelbefund bleibt im
JSON-Audit sichtbar.

Dossier und Befunde erscheinen auf Deutsch oder Englisch. Die Sprache wählt der
Aufrufer; sie steuert die Bezeichnungen, die Texte der deterministischen Regeln
und die Sprachvorgabe an die Reviewer-Arme. Sie verändert keine strukturellen
Felder: Kategorie, Schweregrad, Claim-IDs, Konfidenz und Provenienz sind
sprachunabhängig, und zitierte Originalstellen bleiben unverändert.

Die HTML-Seite trennt hohe Prioritäten von weiteren Hinweisen und zeigt pro
Prüfpunkt eine Erklärung und eine konkrete Frage. Originalaussagen, einzelne
Prüfwege und technische Daten sind einklappbar. Markdown bietet denselben Inhalt
als portablen Export.

## 9. Bewusste Grenze

Content Review bewertet interne inhaltliche Tragfähigkeit. Externe Faktenprüfung
ist nicht stillschweigend eingebaut, weil sie Quellenwahl, Aktualität und einen
eigenen Provenienzvertrag benötigt. Sie kann später als getrennte Schicht an den
zugelassenen ClaimGraph angeschlossen werden.
