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

## 3a. Abdeckungsmessung

Das Gate kann eine Aussage abweisen, aber keine ergänzen. Alles Nachfolgende —
deterministische Regeln wie Reviewer-Arme — ist deshalb durch das begrenzt, was
der Extraktor vorgeschlagen hat. Ein nie vorgeschlagener Claim ist für das
gesamte System unsichtbar, und das Dossier sieht dann sauber aus.

Weil jeder zugelassene Claim seine exakten Quellpositionen mitführt, ist dieser
blinde Fleck messbar: Das Gate berechnet den verankerten Anteil des Textes und
benennt zusammenhängende Passagen ohne Anker. Whitespace zählt nicht mit, und
überlappende Anker zählen ein Zeichen einmal. Die Messung ist deterministisch
und replay-stabil; sie steht als `coverage` im Audit.

Sie ist ausdrücklich kein Urteil. Eine nicht erfasste Passage kann eine
Überschrift, eine Überleitung oder tatsächlich aussagefreier Text sein. Der
daraus erzeugte Befund `coverage_gap` trägt deshalb keine Claim-IDs, hat die
niedrigste Dringlichkeit und formuliert eine Frage an den Prüfer statt einer
Feststellung.

Der Zahlenwert selbst ist eine beschreibende Größe, keine Note. Er hängt davon
ab, wie weit der Extraktionsvertrag „Claim" fasst, nicht nur davon, wie gut
extrahiert wurde. Gemessen an AbstRCT (Mayer u. a., ECAI 2020; 293 medizinische
Abstracts mit annotierten Argumentkomponenten) liegt derselbe Text bei einer
Rate von 0,48, wenn alle Komponenten zählen, und bei 0,14, wenn nur
Schlussfolgerungen zählen. Raten sind damit über Läufe desselben Vertrags
vergleichbar und über verschiedene Verträge hinweg bedeutungslos. Der belastbare
Teil der Messung ist die Liste der Lücken: sie deckt im Mittel 98 % des
unverankerten Textes ab, ist also eine Zerlegung der Rate und keine Stichprobe
daraus.

Ein erster Live-Lauf stützt das. Die Messung hatte im eingefrorenen
Budget-Packet zwei Passagen als unverankert benannt; eine unabhängige
Live-Extraktion desselben Dokuments, die von der Messung nichts wusste,
extrahierte Claims aus genau diesen beiden Passagen und erreichte dabei alle 25
Gold-Claims. Die Lückenliste zeigt also auf verwertbare Stellen und nicht nur
auf unverankerte. Das ist ein kurzes, konstruiertes Dokument und kein
Benchmark; es zeigt aber auch, dass ein handgebautes Packet gegenüber dem
Extraktor unterannotiert sein kann.

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

Profilunabhängig kommt die Abdeckungsprüfung aus Abschnitt 3a hinzu.

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
