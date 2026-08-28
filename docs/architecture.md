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
vergleichbar und über verschiedene Verträge hinweg bedeutungslos. Die
Lückenliste ist der belastbarere Teil der Messung, aber ebenfalls nicht
längenunabhängig: Bei den rund 1700 Zeichen langen AbstRCT-Abstracts deckt sie
98 % des unverankerten Textes ab und ist damit eine Zerlegung der Rate. Auf den
Argumentationsteilen von EGMR-Entscheidungen (10.000 bis 40.000 Zeichen) sind
es im Median 72 %, mit 77 % unterhalb von 15.000 und 63 % oberhalb von 30.000
Zeichen. Der Grund ist mechanisch: 94 % der Zwischenräume zwischen Ankern
liegen unter der 120-Zeichen-Schwelle, und ihre Summe wächst mit der
Dokumentlänge. Auf langen Dokumenten benennt die Liste also die größten Lücken,
nicht mehr alle.

Ein erster Live-Lauf stützt das. Die Messung hatte im eingefrorenen
Budget-Packet zwei Passagen als unverankert benannt; eine unabhängige
Live-Extraktion desselben Dokuments, die von der Messung nichts wusste,
extrahierte Claims aus genau diesen beiden Passagen und erreichte dabei alle 25
Gold-Claims. Die Lückenliste zeigt also auf verwertbare Stellen und nicht nur
auf unverankerte. Das ist ein kurzes, konstruiertes Dokument und kein
Benchmark; es zeigt aber auch, dass ein handgebautes Packet gegenüber dem
Extraktor unterannotiert sein kann.

## 3b. Recall und Dokumentlänge

Das 25-von-25-Ergebnis war eine Eigenschaft des kurzen Dokuments, nicht des
Extraktors. Gemessen an den Argumentspannen des EGMR-Korpus (Habernal u. a.,
Artificial Intelligence and Law 2023; Apache-2.0, zur Laufzeit geklont, nicht
ins Repo übernommen) bricht der Recall mit der Länge ein:

| Dokument | Zeichen | Gold-Spannen | Recall bei 80 % Überlappung |
|---|---:|---:|---|
| Budget-Fixture | 1.707 | 25 | 25/25 |
| EGMR 001-141170 | 10.308 | 24 | 16/24 |
| EGMR 001-110144 | 26.715 | 49 | Lauf bricht ab |

Der mittlere Fall ist der gefährliche, weil er wie ein Erfolg aussieht: 43
Claims, 27 Relationen, 13 Befunde, kein Fehler. Das einzige Signal war die
Abdeckung mit 0,68 gegenüber 0,95 für die Gold-Antwort auf demselben Dokument
— die Messung aus Abschnitt 3a hat also genau das getan, wofür sie gebaut
wurde. Die acht verfehlten Spannen sind nicht die längsten (gefundene und
verfehlte haben dieselbe Medianlänge von rund 300 Zeichen), sondern
überwiegend Subsumtionsschritte des Gerichts und dessen Schlussfolgerung. Bei
24 Spannen ist das ein Hinweis, keine belegte Systematik.

Ab etwa 27.000 Zeichen scheitert die Extraktion mit „output was truncated":
Zu jedem Claim muss die wörtliche Textstelle zurückkommen, und die Antwort
übersteigt das Ausgabebudget von 16.384 Token. Der Abbruch ist der bessere der
beiden Fehler und der Grund, warum eine abgeschnittene Antwort seit 0.2.0a3
sofort als endgültig gilt: ein Wiederholungsversuch würde dasselbe Ergebnis
bezahlen.

## 3c. Zerteilen behebt es nicht

Naheliegende Erklärung: zu viel Text je Aufruf. Sie trägt nicht. Dieselbe
Entscheidung, in fünf Segmenten von je rund 2.000 Zeichen extrahiert — also in
Fixture-Größe, die der Extraktor vollständig zerlegt —, ergibt:

| | Claims | Recall 80 % | Recall 50 % | Abdeckung | Aufrufe |
|---|---:|---:|---:|---:|---:|
| ein Aufruf | 43 | 16/24 | 18/24 | 0,68 | 1 |
| fünf Segmente | 52 | **17/24** | **21/24** | 0,75 | 5 |

Vorab festgelegt war ein Erfolgsmaß von 20/24 bei 80 %. Es wurde verfehlt. Der
Zuwachs bei 80 % liegt bei einer einzigen Spanne und ist bei n = 24 nicht von
Rauschen zu unterscheiden; der Zuwachs bei 50 % (18 auf 21) ist deutlicher und
heißt: Mit weniger Text je Aufruf berührt der Extraktor mehr Passagen, deckt
sie aber nicht gründlicher ab.

Damit ist die Längen-Hypothese weitgehend widerlegt. Segmente in Fixture-Größe
hätten sich wie die Fixture verhalten müssen (25/25) und tun es nicht. Der
Unterschied zwischen beiden Dokumenten ist nicht die Länge, sondern die
Textsorte. Fünf Aufrufe für eine zusätzliche Spanne sind zudem ein schlechtes
Geschäft.

Zwei Vorbehalte: ein Dokument, ein Modell, 24 Gold-Spannen. Und die vorab
genannte Obergrenze von 22/24 war falsch — sie unterstellte, eine Gold-Spanne
müsse von einem einzelnen Claim abgedeckt werden. Gemessen wird die Vereinigung
aller Anker, die eine Segmentgrenze überbrücken kann; G08 wurde genau so
gefunden. Die Obergrenze war 24/24.

## 3d. Es lag am Prompt

Bleibt die Frage, ob der Extraktor diese Textsorte nicht kann oder ob er nach
der falschen Sache gefragt wird. Zwei Stellen der Produktionsprompt sind an
Projektanträgen entstanden: Sieben der 21 Claim-Typen — target, capacity,
resource, baseline, forecast, delivery, budget — beschreiben einen Plan, kein
Argument. Und „decompose polished prose aggressively: an elegant sentence may
contain several claims" beschreibt Werbetext, nicht ein Gericht, das in langen
Gliedsätzen subsumiert.

Ein Lauf mit genau diesen zwei Stellen ersetzt, sonst unverändert, gleiches
Modell, gleiches Dokument, ein Aufruf:

| | Aufrufe | Claims | Recall 80 % | Recall 50 % | Abdeckung | Claims ohne Gold |
|---|---:|---:|---:|---:|---:|---:|
| Produktionsprompt | 1 | 43 | 16/24 | 18/24 | 0,68 | 30 |
| fünf Segmente | 5 | 52 | 17/24 | 21/24 | 0,75 | 40 |
| neutrale Prompt | 1 | **40** | **20/24** | 21/24 | 0,76 | **23** |

Vorab festgelegt war ≥ 20/24. Erreicht, genau auf der Schwelle.

Das Aufschlussreiche ist die Claim-Zahl: Die neutrale Fassung erzeugt **weniger**
Claims als die Produktionsfassung (40 gegen 43) und findet trotzdem vier
Gold-Spannen mehr, bei deutlich weniger Claims ohne Gold-Entsprechung (23 gegen
30). Es ging also nie um die Menge, sondern um das Ziel. Das erklärt auch,
warum die Segmentierung so wenig brachte: Sie erhöhte die Menge (52 Claims, 40
ohne Entsprechung), ohne die Treffsicherheit zu ändern.

Vorbehalte: ein Dokument, 24 Gold-Spannen, ein Lauf, und die Änderung ist ein
Bündel aus zwei Eingriffen — welcher davon wirkt, ist offen. Am
Abbruchverhalten oberhalb von 27.000 Zeichen ändert sie nichts.

Die Gegenprobe auf der eigenen Fixture ist gelaufen und fällt eindeutig aus:

| Fixture, 1.707 Zeichen, 25 Gold-Claims | Claims | Recall 80 % | Verankert | Lücken |
|---|---:|---:|---:|---:|
| Produktionsprompt | 29 | 25/25 | 0,93 | 0 |
| neutrale Prompt | 23 | 25/25 | **0,98** | 0 |

Dasselbe Muster wie auf der Gerichtsentscheidung: weniger Claims, gleiche
Trefferquote, höherer verankerter Anteil. Die Änderung gewinnt auf Rechtstexten,
ohne auf Anträgen zu verlieren.

Die eingefrorenen Offline-Kontrollen sagen dazu nichts — sie spielen
gespeicherte Packets ab und rufen den Extraktor nie. Nur ein Live-Lauf gegen das
eingefrorene Packet kann eine Prompt-Regression überhaupt sehen, und genau den
führt der Workflow ohne Entscheidungs-ID aus.

## 3e. Die deterministische Hälfte

Die deterministische Hälfte trägt die Länge dagegen problemlos. Speist man die
Gold-Spannen als Packet ein, lässt das Gate alle 24 beziehungsweise 49 Claims
ohne Rejection zu, und die Abdeckungsmessung liefert 0,946 und 0,977. Die
Begrenzung liegt allein bei der Extraktion, was den offenen Fahrplanpunkt
abschnittsweise Extraktion bestätigt.

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
