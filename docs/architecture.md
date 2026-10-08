# Architektur und Autoritätsgrenzen

> Dieses Dokument ist die chronologische Aufzeichnung, Lauf für Lauf. Wer wissen
> will, **was daraus insgesamt folgt** — belegt, zurückgezogen, offen —, liest
> [`research-report.md`](research-report.md).

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

## 3d. Der Prompt wirkt, aber ungleichmäßig

> **Nachtrag, siehe Abschnitt 3h:** Der Befund dieses Abschnitts hält der
> Wiederholung nicht stand. Ein späterer Lauf derselben Konfiguration —
> Produktionsprompt, gleiches Dokument, gleiches Budget — liefert 20/24 statt
> der hier berichteten 16/24. Die Lauf-zu-Lauf-Streuung ist damit so groß wie
> der gemessene Effekt. Alle Zahlen dieses Abschnitts beruhen auf je einem
> Aufruf pro Arm und sind als eine Ziehung zu lesen, nicht als Messung.

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

Auf dem zweiten Dokument trägt das aber kaum. Mit erhöhtem Budget, sonst
identisch:

| 001-110144, Budget 65.536 | Claims | Recall 80 % | Recall 50 % | Verankert |
|---|---:|---:|---:|---:|
| Produktionsprompt | 108 | 36/49 (73 %) | 46/49 (94 %) | 0,82 |
| neutrale Prompt | 107 | 37/49 (76 %) | 47/49 (96 %) | 0,84 |

Vorab festgelegt war ≥ 42/49. Verfehlt. Aus +4 Spannen auf 001-141170 werden
hier +1 — aus 17 Prozentpunkten werden 2.

Damit ist der Prompt-Befund kein allgemeiner mehr. Er lautet jetzt: Die
Änderung hilft auf einem Dokument deutlich, auf einem zweiten kaum, und auf der
Fixture ist sie nicht nötig, weil dort ohnehin alles gefunden wird. Dass sie
nirgends schadet, ist gemessen; wie groß ihr Nutzen ist, hängt vom Dokument ab
und ist mit zwei Dokumenten nicht bestimmt.

**Welcher Eingriff wirkt?** Beide, und zwar jeder für sich. Gleiches Dokument,
gleiches Budget, ein Aufruf:

| Prompt | Claims | Recall 80 % | Recall 50 % | Verankert | Lücken |
|---|---:|---:|---:|---:|---:|
| Produktionsprompt | 43 | 16/24 | 18/24 | 0,68 | 8 |
| nur `decompose` | 45 | 20/24 | 21/24 | 0,76 | 5 |
| nur `vocabulary` | 40 | 20/24 | 21/24 | 0,76 | 5 |
| beide | 40 | 20/24 | 21/24 | 0,76 | 5 |

Die Eingriffe sind also **redundant**, nicht additiv: Keiner ist notwendig,
jeder allein genügt. Und die vier verfehlten Spannen sind in allen drei
Varianten dieselben — G03, G08, G09, G19 —, während die Produktionsfassung
genau diese vier plus vier weitere verfehlt. Was die Änderung bewirkt, ist
demnach nicht ein bisschen mehr Sorgfalt, sondern ein Schalter: Entweder der
Extraktor behandelt den Text als Antrag, oder er tut es nicht.

Eine Erklärung, ausdrücklich als Vermutung: Beide Sätze sagen dasselbe auf
verschiedenen Wegen — dass die antragsförmige Rahmung der Prompt die Extraktion
nicht begrenzen soll. Ein Signal davon reicht.

Praktisch heißt das: Der Vokabular-Hinweis allein genügt. Er ist der kleinere
Eingriff, weil er nur einen Satz *ergänzt*, statt eine bestehende Anweisung zu
*ersetzen* — und er behebt zusätzlich den `conclusion`-Abbruch aus Abschnitt 3e
an dessen Ursache.

Weitere Vorbehalte: je ein Lauf pro Arm, ein Dokument, 24 Spannen. Dass drei
verschiedene Prompts auf dieselben vier Verfehlungen und dieselbe Abdeckung
kommen, deutet darauf hin, dass die Lauf-zu-Lauf-Schwankung hier klein ist —
belegt ist das mit je einem Lauf aber nicht. Am Abbruchverhalten oberhalb
von 27.000 Zeichen ändert sie nichts.

Warum sich die Effekte nicht addieren, zeigt der Vergleich auf Spannenebene:

| Vergleich | A findet | B findet | nur B | nur A | Vereinigung |
|---|---:|---:|---:|---:|---:|
| Fall A: Produktionsprompt gegen neutral | 16 | 20 | 4 | 0 | 20/24 |
| Fall A: ein Aufruf gegen fünf Segmente | 16 | 17 | 3 | 2 | 19/24 |
| Fall B: Produktionsprompt gegen neutral | 36 | 37 | 3 | 2 | **39/49** |

Nur der erste Fall ist eine echte Verbesserung: Was die neutrale Prompt dort
verfehlt, verfehlt die Produktionsfassung auch. Die anderen beiden sind
**Tausch** — die Variante gewinnt Spannen und verliert andere. Deshalb
summieren sich Budget und Prompt nicht: Sie verschieben die Aufmerksamkeit des
Extraktors, statt sie zu vertiefen.

Daraus folgt ein Befund, den keine der Einzelmessungen hergibt: Auf Fall B
erreicht die **Vereinigung zweier Läufe 39 von 49**, gegenüber 37 beim besseren
einzelnen. Das ist das Anti-Delphi-Argument eine Schicht tiefer, und hier trägt
es aus einem Grund, der bei der Abdeckung fehlte — die Unabhängigkeit ist
gemessen, nicht unterstellt: Von den Verfehlungen sind zehn gemeinsam und fünf
exklusiv. Das Zusammenführen ist zudem billig, weil das Gate Claims über ihre
Inhaltsadresse führt: Was beide Läufe finden, fällt zu einem Knoten zusammen,
und die Kanten bleiben erhalten.

`scripts/compare_runs.py` rechnet das aus zwei Dossiers nach.

**Gefahren, nicht nur gerechnet.** Der Doppellauf durch die volle Pipeline —
zwei Extraktionen, zusammengeführt, dann Gate, Regeln, Abdeckung:

| 001-110144, Budget 65.536 | Claims | Recall 80 % | Recall 50 % | Verankert |
|---|---:|---:|---:|---:|
| Produktionsprompt | 108 | 36/49 | 46/49 | 0,82 |
| neutrale Prompt | 107 | 37/49 | 47/49 | 0,84 |
| **zusammengeführt** | **186** | **39/49** | 47/49 | 0,86 |

Vorab festgelegt war ≥ 39/49, und genau das kommt heraus: Die Arithmetik über
die Spannenmengen sagt den gemessenen Wert exakt voraus.

Der Preis steht in der Claim-Spalte. Aus 215 Vorschlägen werden 186
zugelassene Claims — das Gate verwirft 29 über die Inhaltsadresse —, und 141
davon haben keine Gold-Entsprechung. Für den Recall ist das gleichgültig, für
einen Menschen, der das Dossier liest, nicht: Der Graph ist fast doppelt so
groß wie der eines Einzellaufs und trägt Beinahe-Dubletten, weil zwei Prompts
sich viel eher auf eine Textstelle einigen als auf deren Formulierung. Wer den
Doppellauf einsetzt, kauft zehn Prozentpunkte Recall mit einem doppelten
Aufruf und einem deutlich unübersichtlicheren Dossier.

Die Claim-Partitionierung aus Abschnitt 3e hat sich dabei bewährt: Derselbe
Lauf war zuvor zweimal an `conclusion` gestorben, diesmal fiel der Vorschlag
weg und der Rest kam durch.

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

## 3e. Ein Label, das die Extraktion kosten kann

Auf der Gerichtsentscheidung greift das Modell zum Claim-Typ `conclusion`. Den
gibt es im geschlossenen 21-Werte-Katalog nicht, und der Katalog ist an
Projektanträgen entstanden: Für ein Urteil ist die Schlussfolgerung der
wichtigste Satzsorte überhaupt.

Entscheidend ist, was danach passiert. `provider.extract` erzeugt genau einmal
neu und spielt dem Modell den Schema-Fehler zurück. Gemessen:

| Lauf | Reparaturrunde | Ergebnis |
|---|---|---|
| 001-110144, Produktionsprompt | nein | `unknown claim_type: conclusion` |
| 001-110144, Produktionsprompt | ja | durchgelaufen, 36/49 |
| 001-110144, Doppellauf, Produktionsleg | ja | zweimal `conclusion`, Abbruch |
| 001-110144, Doppellauf, Wiederholung | ja | zweimal `conclusion`, Abbruch |

Gleicher Prompt, gleiches Dokument, gleiches Budget: **ein Durchlauf von
dreien**. Die Reparaturrunde hilft also manchmal und ist keine Absicherung. Bei
Temperatur 0 ist das kein Widerspruch: Determinismus sichert kein Anbieter zu. Damit ist meine frühere
Einordnung, das sei „ein Fehler des Experiments, nicht des Produkts", zu
zuversichtlich gewesen — der Produktionspfad hat dieselbe Schleife und kann
genauso scheitern, nach zwei bezahlten Aufrufen.

Verschärfend: Der Fallback `_reject_invalid_relations` fängt nur fehlerhafte
**Kanten** ab. Für einen fehlerhaften Claim-Typ gibt es keine Entsprechung, das
ganze Packet geht an einem einzigen Label verloren.

Praktische Folge: Der Doppellauf ist an dieser Stelle blockiert. Sein
Produktionsleg scheitert, bevor irgendetwas zusammengeführt werden kann, und
zwei bezahlte Versuche haben daran nichts geändert. Die 39 von 49 aus der
Spannenarithmetik bleiben damit gerechnet und ungefahren.

**Behoben, und zwar an der Wurzel.** Die Rettungsstufe des Providers
partitioniert jetzt auch die Claims: Der unbrauchbare Vorschlag fällt weg, der
Rest bleibt, und der Verlust steht als `claim_rejections` im Audit, das das Gate
in das Dossier durchreicht. Das entspricht der eigenen Linie — das Schlechte
verwerfen, den Rest behalten — und ist genau das, was für Kanten schon galt.

Drei Grenzen bleiben bewusst bestehen. Ohne tatsächliche Ablehnung greift die
Rettung nicht, damit ein aus anderem Grund fehlerhaftes Packet seinen eigenen
Fehler zeigt statt still repariert zurückzukommen. Ist *jeder* Claim
unbrauchbar, scheitert der Lauf weiterhin: Dort zu retten hieße, einen Graphen
zurückzugeben, den niemand vorgeschlagen hat. Und eine Relation, die auf einen
entfernten Claim zeigt, braucht keine Sonderbehandlung — das Gate lässt eine
Kante ohnehin nur zu, wenn beide Endpunkte zugelassen wurden.

Die zweite Abhilfe bleibt offen: Der Prompt könnte den Hinweis der neutralen
Variante übernehmen — „nimm den nächstliegenden Wert oder `other`" —, was
zugleich die Hälfte des Prompt-Bündels isoliert testbar machen würde. Sie
behebt allerdings nur diesen einen Fall, während die Partitionierung trägt,
egal welches Label das Modell als Nächstes erfindet.

## 3f. Das Ausgabebudget

Die 16.384 Token sind eine selbstgesetzte Grenze; deepseek-v4-flash lässt
384.000 zu. Der Einwand gegen eine Erhöhung war, sie tausche einen lauten
Fehler gegen einen leisen: Ein Dokument, das heute sichtbar abbricht, lieferte
dann ein Dossier, dessen Dünne niemand bemerkt.

Die Messung widerlegt das.

| Dokument | Budget | Claims | Recall 80 % | Recall 50 % | Verankert | Lücken |
|---|---:|---:|---:|---:|---:|---:|
| 001-141170, 10.308 Zeichen | 16.384 | 43 | 16/24 (67 %) | 18/24 | 0,68 | 8 |
| 001-110144, 26.715 Zeichen | 16.384 | — | Abbruch | — | — | — |
| 001-110144, 26.715 Zeichen | 65.536 | 108 | **36/49 (73 %)** | 46/49 (94 %) | 0,82 | 13 |

Der Lauf mit erhöhtem Budget ist nicht dünn: 108 Claims, 0,82 verankert, und
bei der strengen Schwelle ein *besserer* Recall als die kürzere Entscheidung
mit demselben Prompt erreicht. Die erwartete Verschlechterung tritt nicht ein.

Zwei Dinge bleiben trotzdem richtig. Die Abdeckungsmessung zeigt die Lücke
weiterhin an — 0,82 gegen 0,977 für die Gold-Antwort, mit 13 benannten Passagen
—, die Warnleuchte funktioniert also auch im erhöhten Budget. Und die Erhöhung
verschiebt die Abbruchgrenze nur proportional: 64k Token reichen grob bis
110.000 Zeichen, die längste Entscheidung im Korpus hat 447.000.

Was hier nicht gemessen ist: erhöhtes Budget zusammen mit der neutralen Prompt.
Der 73-Prozent-Lauf verwendet die Produktionsprompt, deren Passungsproblem
Abschnitt 3d beschreibt.

## 3g. Die deterministische Hälfte

Die deterministische Hälfte trägt die Länge dagegen problemlos. Speist man die
Gold-Spannen als Packet ein, lässt das Gate alle 24 beziehungsweise 49 Claims
ohne Rejection zu, und die Abdeckungsmessung liefert 0,946 und 0,977. Die
Begrenzung liegt allein bei der Extraktion, was den offenen Fahrplanpunkt
abschnittsweise Extraktion bestätigt.

## 3h. Fünf Entscheidungen: der Befund fällt

Die Prompt-Änderung war auf **einem** Dokument abgeleitet. Ist der Gewinn
juristik-typisch, wäre ein Vokabular-Satz pro Fachbereich eine tragfähige
Bauform; ist er es nicht, war die Optimierung auf 001-141170 eine Optimierung
auf dieses Dokument. Vorab festgelegt: **Gewinn ≥ 3 Spannen bei mindestens 3
von 5 Entscheidungen.** Gleiches Modell, Budget 16.384, ein Aufruf pro Arm,
beide Pakete durch das echte Gate.

| Entscheidung | Gold | Produktion | `vocabulary` | Differenz |
|---|---:|---:|---:|---:|
| 001-141170 | 24 | 20/24 | 20/24 | ±0 |
| 001-172073 | 21 | 18/21 | 17/21 | −1 |
| 001-61247 | 23 | 17/23 | 7/23 | **−10** |
| 001-60917 | 24 | — | — | Produktionslauf bei 16.384 abgeschnitten |
| 001-77936 | 23 | — | — | Fehler im Messskript, siehe unten |
| Summe (gemessen) | | 55 | 44 | **−11** |

Das Erfolgsmaß ist in die andere Richtung verfehlt. Der Vokabular-Hinweis ist
in der Summe schlechter und bricht auf einer Entscheidung ein. Er geht **nicht**
in die Produktion, und das fachbereichsweise Vokabular, das er begründen
sollte, hat keine Grundlage.

**Die wichtigere Zahl steht in der ersten Zeile.** Der Produktionsprompt
erreicht hier 20/24 auf 001-141170 — derselbe Prompt, dasselbe Modell, dasselbe
Dokument, dasselbe Budget, Temperatur 0 — und in Abschnitt 3d 16/24. Vier
Spannen Streuung zwischen zwei Läufen einer Konfiguration sind genau die Größe
des dort berichteten „Prompt-Effekts".

Daraus folgt nicht, dass die neutrale Prompt nichts bringt, und auch nicht,
dass sie etwas bringt. Es folgt, dass **ein Aufruf pro Arm den Effekt nicht von
der Eigenstreuung des Extraktors trennen kann**. Das betrifft jeden
Einzellauf-Vergleich der Abschnitte 3c bis 3f — Segmentierung (+1), Budget,
Bündel-Zerlegung, Doppellauf. Die Zahlen bleiben stehen, ihr Status ändert
sich: eine Ziehung, keine Messung. Zu entscheiden wäre das mit Wiederholungen
pro Arm; bezahlt hat sie bisher niemand. Bis dahin bleibt die Produktionsprompt
unverändert, weil eine ungemessene Änderung keine Verbesserung ist.

**Die letzte Tabellenzeile war unser eigener Fehler.** Das Experimentskript
brach bei `unknown relation_type: DIFFERENTIATES` ab, während die Produktion
genau diese eine Relation ablehnt und das Paket behält (Abschnitt 3e). Ein
Messinstrument, das strenger ist als der gemessene Pfad, meldet ein Dokument
als unmessbar, das das Produkt verarbeitet — und verschweigt dabei nicht
einmal etwas, es fehlt einfach eine Zeile. Das Skript nimmt jetzt denselben
Rückfallpfad. Der Abbruch bei 001-60917 ist dagegen echt: Bei 16.384 Tokens
reicht die Ausgabe nicht, was Abschnitt 3f beschreibt.

## 3i. Die Streuung eines einzelnen Laufs

Abschnitt 3h stellte zwei Läufe derselben Konfiguration nebeneinander, 16/24
und 20/24, und ließ offen, ob das Rauschen ist. Vorab festgelegt: Streuung ≥ 4
Spannen ⇒ Einzellauf-Vergleiche sind wertlos; Streuung ≤ 1 ⇒ Stichprobenrauschen
erklärt die Differenz nicht und die Ursache liegt woanders. Fünf Läufe,
001-141170, Produktionsprompt, 16.384 Tokens, Temperatur 0:

| Lauf | Recall 80 % | Claims |
|---|---:|---:|
| 1 | 20/24 | 40 |
| 2 | 20/24 | 40 |
| 3 | 20/24 | 38 |
| 4 | 19/24 | 41 |
| 5 | 20/24 | 40 |

**Streuung 1 Spanne** (Mittel 19,8; Claims 38–41), fünf von fünf Läufen
geglückt. — *Nachtrag, siehe Abschnitt 3j: Diese fünf Läufe liegen in einem
Fünf-Minuten-Fenster und unterschätzen die Streuung. Über Sitzungen hinweg sind
es vier Spannen, und der Schluss dieses Abschnitts ist damit zurückgenommen.* Der Extraktor ist auf dieser Konfiguration also nicht wackelig — die
bequeme Erklärung „alles Rauschen" ist widerlegt, und zwar gegen meine eigene
Vermutung.

Damit ist die Frage verschoben, nicht beantwortet: Die 16/24 mit 43 Claims
liegen außerhalb von allem, was fünf Wiederholungen zeigen. Was ich ausschließen
kann, steht im Code — `prompts.py` ist auf diesem Branch unverändert, die
Zulassungslogik des Gates ebenso, und `ingest` liest eine `.txt` unverändert
ein, sodass Anker und Gold-Offsets auf denselben Zeichen sitzen. Die beiden
Änderungen an `provider.py` (Retry-Klassifikation, Claim-Partitionierung)
greifen nur in Fehlerfällen. Bleiben zwei Möglichkeiten, die ich mit diesen
Daten **nicht** trennen kann: ein seltener Ausreißer jenseits von fünf
Ziehungen, oder eine Änderung auf Anbieterseite zwischen den Läufen. Wer
`deepseek-v4-flash` sagt, benennt einen Alias, keine Prüfsumme.

**Was das für den Prompt-Befund heißt.** Der Produktionsprompt verfehlt heute
genau G03, G08, G09 und G19 — dieselben vier Spannen, die in Abschnitt 3d alle
drei Prompt-Varianten verfehlten, während die Produktionsfassung dort diese vier
*plus vier weitere* verfehlte. Die Produktionsfassung verhält sich heute also
wie die „neutrale" Prompt von gestern. Der Vorteil der Prompt-Änderung ist
damit nicht widerlegt, sondern verschwunden: Es gibt nichts mehr, wogegen er
gemessen wäre. Zusammen mit Abschnitt 3h bleibt: keine Prompt-Änderung geht in
die Produktion.

**Der belastbare neue Befund ist das Verfehlungsmuster.** Vier Spannen werden
in *keinem* der fünf Läufe erreicht, eine einzige schwankt (G18, 4 von 5), 19
sind in jedem Lauf da. Die Vereinigung aller fünf Läufe ist wieder **20/24**.
Wiederholtes Ziehen kauft auf diesem Dokument also nichts — die Verfehlungen
sind systematisch, nicht zufällig. Das ist zugleich die Grenze des
Doppellauf-Arguments aus Abschnitt 3d: Es trägt dort, wo zwei *verschiedene*
Konfigurationen verschiedene Spannen treffen, und nicht bei bloßer Wiederholung.

Was die vier verbindet, ist überwiegend die Länge:

| Spanne | Zeichen | Längenrang | Akteur / Typ |
|---|---:|---:|---|
| G19 | 1.145 | 24/24 | EGMR, Subsumtion |
| G08 | 1.068 | 23/24 | EGMR, Subsumtion |
| G09 | 483 | 18/24 | EGMR, Subsumtion |
| G03 | 267 | 10/24 | Staat, frühere Rechtsprechung |

Median der gefundenen Spannen 309 Zeichen, der verfehlten 1.068. Bei einer
Schwelle von 80 Prozent Überlappung muss eine 1.145-Zeichen-Passage fast
vollständig zerlegt werden, damit sie als gefunden zählt; das ist zum Teil eine
Eigenschaft der Messung und nicht nur des Extraktors. Deterministisch ist die
Länge trotzdem nicht: Fünf Spannen über 450 Zeichen werden zuverlässig
gefunden, G03 mit 267 Zeichen nie. Der Akteur-Typ trennt nicht — sechs
EGMR-Subsumtionen werden gefunden, drei nicht.

Nebenbefund zur Kostenseite: In drei der fünf Läufe wurde der erste Versuch mit
`unknown claim_type: conclusion` abgelehnt und im zweiten korrigiert. Das Label
aus Abschnitt 3e kostet also in gut der Hälfte der Läufe einen zweiten
bezahlten Aufruf, ohne dass ein Paket verloren geht.

## 3j. Die Verteilung, und was sie über die Streuung von 3i sagt

Vier Spannen werden in fünf Läufen nie erreicht. Eine Trefferzahl sagt nicht,
ob der Extraktor diese Passagen nie berührt oder sie berührt und nicht
ausschöpft. Vorab festgelegt: 60–80 Prozent verankert ⇒ Schwellenfrage, die
Messung untertreibt; unter 30 ⇒ echte Extraktionslücke; dazwischen ⇒ angefasst,
nicht zerlegt. Ein Lauf über den Produktionspfad, 001-141170, 16.384 Tokens:

| Spanne | verankert | Zeichen | Lesart |
|---|---:|---:|---|
| G03 | **0 %** | 267 | nie berührt |
| G22 | 19 % | 325 | nie berührt |
| G09 | 20 % | 483 | nie berührt |
| G19 | 38 % | 1.145 | angefasst, nicht zerlegt |
| G18 | 66 % | 319 | angefasst, nicht zerlegt |
| G05 | 77 % | 461 | Grenzfall |
| G08 | 81 % | 1.068 | knapp gefunden |

Die übrigen 17 Spannen liegen bei 86 bis 100 Prozent, zehn davon bei 100. Die
Verteilung ist also **zweigipflig**: Der Extraktor trifft eine Spanne fast ganz
oder er verfehlt sie deutlich. Im Grenzband um 80 Prozent (±5 Punkte) liegen
**2 von 24**. Damit ist die Recall-Zahl belastbarer als befürchtet — sie kippt
nicht mit der Frage, wie der Extraktor einen Satz schneidet — und die
Verfehlungen sind überwiegend echte Lücken, keine Messartefakte. Die Länge
erklärt sie nur teilweise: G19 mit 1.145 Zeichen kommt auf 38 Prozent, G08 mit
1.068 auf 81.

G03 mit 0 Prozent ist der auffälligste Fall und vermutlich kein Loch, sondern
eine Verwechslung der Fundstelle: Der Graph enthält einen Claim zu genau diesem
Sachverhalt (`Lazzarini and Ghiacci`), verankert ihn aber an der späteren
Wiedergabe durch den Gerichtshof statt an der Einlassung der Regierung. Das ist
der Grund, warum `gold_spans` Gold-Spannen niemals per Textsuche lokalisiert:
Rechtsprosa wiederholt ganze Formulierungen, und die erste Fundstelle ist nicht
die annotierte. Als Vermutung notiert, nicht als Befund.

**Und ein Nachtrag zu Abschnitt 3i, der dessen Schluss zurücknimmt.** Dieser
Lauf liefert 47 Claims und 18/24 — außerhalb von beidem, was die fünf
Wiederholungen zeigten (38–41 Claims, 19–20/24). Alle Messungen derselben
Konfiguration, chronologisch:

| Zeitpunkt | Pfad | Claims | Recall 80 % |
|---|---|---:|---:|
| 28.08., vormittags | CLI | 43 | 16/24 |
| 28.08., 21:22 | Skript | — | 20/24 |
| 28.08., 22:09–22:14 (5 Läufe) | Skript | 38–41 | 19–20/24 |
| 29.08., 11:52 | CLI | 47 | 18/24 |

Beide Pfade schicken dieselbe Prompt, dasselbe Budget und dasselbe Modell; die
Anfragen sind identisch aufgebaut. Was die fünf Wiederholungen gemessen haben,
ist deshalb nicht die Lauf-zu-Lauf-Streuung, sondern die Streuung **innerhalb
eines Fünf-Minuten-Fensters** — und die unterschätzt sie. Über alle Sitzungen
hinweg liegt die Spannweite bei **16 bis 20 Spannen und 38 bis 47 Claims**,
also bei vier Spannen, genau der Größe des früher berichteten „Prompt-Effekts".

Damit gilt doch der erste vorab festgelegte Zweig aus 3i: Einzellauf-Vergleiche
dieser Art sind nicht aussagekräftig, und der Satz aus 3i, Stichprobenrauschen
erkläre die 16/24 nicht, ist zurückgenommen. Wer die Streuung eines Arms
bestimmen will, muss die Läufe über Sitzungen verteilen; fünf Aufrufe
hintereinander messen den Server, nicht das Modell.

## 3k. Entwurf: das Merge-Gate eines Reparaturlaufs

Noch nicht gebaut, aber entschieden — die Regel steht als geprüfte Funktion in
`scripts/repair_merge.py`, damit der bezahlte Lauf sie nicht nebenbei erfindet.

Der gemessene Anlass ist eng: Auf 001-141170 liegen drei Gold-Spannen bei 0, 19
und 20 Prozent Deckung (Abschnitt 3j). Ein zweiter LLM-Aufruf über genau diese
Passagen, mit dem vorhandenen Graphen als Negativkontext, ist der naheliegende
Reparaturweg. Wie er schiefgeht, ist ebenfalls gemessen: Der Doppellauf aus 3d
brachte zwei zusätzliche Gold-Spannen und kostete 186 Claims mit 141 ohne
Gold-Entsprechung.

Vier Fälle, in dieser Reihenfolge entschieden:

| Fall | Entscheidung | Grund |
|---|---|---|
| Anker außerhalb der angefragten Lücken | `reject: outside_requested_gap` | Der Lauf war nach bestimmten Passagen gefragt; anderswo schreibt er eine Zweitmeinung zu Text, der schon eine hat |
| Anker fügt keine unverankerten Zeichen hinzu | `reject: adds_no_uncovered_text` | Die Beinahe-Dublette des Doppellaufs, unter einem Mindestanteil neuer Zeichen (Vorgabe 50 %) |
| Inhalt bereits zugelassen, Anker neu | `admit: duplicate_content_other_anchor` | Zwei Sprechakte, kein Claim mit zwei Ankern — und markiert, damit das Dossier das Paar zeigen kann |
| sonst | `admit: new_claim` | Wofür der Lauf da ist |

Zwei Dinge daran folgen aus dem bestehenden Gate und nicht aus Geschmack.

**Die Inhaltsadresse trägt den Wortlaut, nicht den Offset.** Ein Knoten wird
über `document_id`, `claim_type`, `canonical_content` und `raw_span` gebildet.
Zwei Vorschläge mit identischem Wortlaut *und* identischem Zitat fallen deshalb
schon heute zu einem Knoten zusammen; unterscheidet sich das Zitat, entstehen
zwei. Der dritte Fall oben ist also kein neues Verhalten, sondern die Frage, ob
der Reparaturlauf ihn erzeugen darf — und er darf, weil „die Regierung trug X
vor" und die spätere Wiedergabe desselben X durch den Gerichtshof zwei
Sprechakte sind. Genau dieses Paar wird jetzt gemessen: `measure_drift.py`
meldet fast gleiche Claims an getrennten Stellen, damit vor dem Bau bekannt
ist, wie oft der Fall real vorkommt.

**Ein doppelt vorkommendes Zitat ist bereits geregelt.** Findet das Gate den
`raw_span` mehrfach im Dokument, verankert es an der ersten Fundstelle und
setzt `anchor_ambiguous` sowie `human_review_required`. Der Reparaturlauf ändert
daran nichts und darf es nicht: Ein Anker, den die Maschine nicht eindeutig
bestimmen kann, gehört vor einen Menschen und nicht in eine Heuristik.

Was die Regel ausdrücklich nicht tut: Sie fügt keinen Claim hinzu, sie bewertet
keinen als wahr, und sie beschneidet keine Spanne, damit sie in eine Lücke
passt — ein Claim wird mit dem Zitat zugelassen, das er führt, oder gar nicht.
Jede Ablehnung trägt ihren Grund in der Form, die der Audit schon kennt.

Offen bleibt die Messung: Ein Reparaturlauf muss an den Deckungsanteilen der
harten Fälle gemessen werden, mit Wiederholungen über Sitzungen, sonst gilt für
ihn dieselbe Unsichtbarkeit wie für die Prompt-Änderungen aus 3d.

## 3l. Sprechergrenzen, Dubletten, und was von den harten Fällen bleibt

Der erste Lauf mit den neuen Messgeräten, 001-141170, Produktionsprompt,
16.384 Tokens: 40 Claims, 20/24 bei 80 Prozent, 21/24 bei 50, verankerter
Anteil 0,76.

**Anker über eine Sprechergrenze hinweg: 0 von 40.** Kein einziger Claim reicht
in den Text zweier Sprecher. Die Vermutung, die Spannengrenzen trennten die
Akteure sauber, ist damit an unseren Daten gemessen und nicht nur behauptet —
und zwar, ohne dass der Claim-Vertrag je danach gefragt hätte. Ein Vorbehalt
bleibt: ein Dokument, ein Lauf, und die EGMR-Annotation legt Akteurswechsel auf
Absatzgrenzen, was die Aufgabe erleichtert.

**Fast gleiche Claims an getrennten Stellen: 0.** Der dritte Fall des
Merge-Gates aus 3k kommt in einem einzelnen Lauf also nicht vor. Das ist genau
so zu lesen und nicht weiter: Die Prüfung verlangt 80 Prozent Wortüberlappung,
und die frühere Beobachtung zu G03 — ein Claim zur selben Sache, an der
Wiedergabe des Gerichtshofs verankert — war *anders formuliert* und wäre hier
nie aufgefallen. Die starke Form meiner Vermutung ist unbelegt, die schwache
ungeprüft. Für das Merge-Gate ändert das nichts: Die Regel greift dort, wo der
Reparaturlauf den Graphen als Negativkontext bekommt und deshalb ähnlich
formulieren *wird*.

**Im Grenzband um 80 Prozent: 0 von 24.** Zwanzig Spannen liegen bei 86 bis 100
Prozent, siebzehn davon bei genau 100; dann folgen 71, 23, 20 und 0. Die
Verteilung ist noch schärfer zweigipflig als in 3j, und die Schwelle leistet auf
diesem Dokument keine willkürliche Arbeit.

**Von den harten Fällen bleiben drei.** Über die beiden Läufe mit
Deckungsmessung:

| Spanne | 29.08. | 31.08. | Lesart |
|---|---:|---:|---|
| G03 | 0 % | 0 % | nie berührt, stabil |
| G09 | 20 % | 20 % | nie berührt, stabil |
| G19 | 38 % | 23 % | angefasst, nie ausgeschöpft |
| G08 | 81 % | 71 % | Grenzfall, kippt |
| G18 | 66 % | 100 % | schwankt stark |
| G22 | 19 % | 100 % | schwankt stark |

Die Suite harter Fälle schrumpft damit auf **G03, G09 und G19** — der Rest
schwankt zwischen Läufen und misst kein Verfahren. Genau das war der Grund, sie
über den Deckungsanteil statt über bestanden/verfehlt zu führen: Mit einer
binären Zählung sähe der Lauf vom 31.08. wie eine Verbesserung um zwei Spannen
aus, obwohl G19 und G08 gleichzeitig schlechter geworden sind.

Nebenbefund: Die Wortdeckung der Claims gegen ihr Zitat liegt in diesem Lauf bei
Median 1,00 und Minimum 0,89, gegen 0,67 zwei Tage zuvor. Und 40 Claims mit
20/24 liegen genau im Bereich der fünf Wiederholungen aus 3i — womit der Lauf
vom 29.08. mit 47 Claims und 18/24 eher der Ausreißer ist als die Regel. Die
Spannweite über Sitzungen bleibt 16 bis 20 Spannen.

## 3m. Der Reparaturlauf: eine Passage repariert, zwei nicht erfragt

Zwei Runden, 001-141170, Produktionsprompt, 16.384 Tokens, je ein Erst- und ein
Reparaturaufruf. Vorab festgelegt: **Erfolg**, wenn mindestens zwei der drei
stabilen harten Fälle (G03, G09, G19) um ≥ 20 Punkte im Deckungsanteil steigen
und der Recall nicht fällt; **Teilerfolg** bei genau einem; **Fehlschlag**, wenn
keiner steigt oder der Zuwachs mit über einem Viertel zusätzlicher Claims ohne
Gold-Entsprechung erkauft ist.

| | Runde 1 | Runde 2 |
|---|---|---|
| Lücken | 5 (2.362 Zeichen) | 5 (2.362 Zeichen) |
| Vorschläge | 7 | 6 |
| davon zugelassen | 3 | 1 |
| `source_span_not_found` | 4 | 5 |
| Recall 80 % | 19/24 → 19/24 | 20/24 → 20/24 |
| Claims | 41 → 44 | 40 → 41 |
| **G19** | 23 % → **71 %** | 23 % → **43 %** |
| G03 | 0 % → 0 % | 0 % → 0 % |
| G09 | 20 % → 20 % | 20 % → 20 % |

**Teilerfolg, in beiden Runden.** G19 steigt um 48 beziehungsweise 20 Punkte —
die Passage, auf die der Lauf gezeigt wurde, wird tatsächlich bearbeitet —, ohne
die 80-Prozent-Schwelle zu überschreiten, weshalb der Recall unverändert bleibt.
Aufgebläht wird nichts: drei und ein zugelassener Claim.

Zwei Befunde sind wichtiger als das Urteil.

**Die Merge-Regel aus 3k hat kein einziges Mal gegriffen.** Weder
`outside_requested_gap` noch `adds_no_uncovered_text` kam vor. Die bindende
Beschränkung ist eine andere: Vier von sieben und fünf von sechs Vorschlägen
scheitern am **wortgetreuen Zitat** — der Reparaturlauf gibt einen `raw_span` an,
den das Dokument so nicht enthält, und das Gate lehnt ihn ab, bevor die Regel
überhaupt gefragt wird. Die Vorsichtsmaßnahme, die ich für nötig hielt, war
nicht die, die nötig war. Warum das Zitieren hier häufiger misslingt als im
Erstlauf, ist offen; der Lauf druckt die abgelehnten Spannen jetzt mit, damit
die nächste Messung es sagen kann.

**G03 und G09 wurden nie erfragt.** Der Reparaturlauf wird von den
Abdeckungslücken getrieben, und eine Lücke entsteht nur dort, wo *kein* Claim
verankert ist, ab 120 Zeichen Länge. Eine zu 20 Prozent abgedeckte Passage
zerfällt in Reststücke, die einzeln unter der Schwelle bleiben — sie kommt nie
auf die Liste. Das ist keine Schwäche des zweiten Aufrufs, sondern eine des
Zielmechanismus: **Teilabdeckung ist blind.** Der Lauf berichtet deshalb jetzt
je Gold-Spanne, wie viel davon überhaupt erfragt wurde.

Daraus folgt die nächste Fassung, nicht ein weiterer Versuch derselben: Der
Reparaturlauf muss auf *unterdeckte* Passagen zielen, nicht nur auf unberührte —
also entweder mit niedrigerer Lückenschwelle oder mit einem zweiten Kriterium,
das eine lange, dünn verankerte Strecke als Lücke führt. Beides ist
deterministisch und braucht keinen weiteren Modellaufruf, um entworfen zu werden.

Vorbehalt wie immer: zwei Runden in einem Fenster, ein Dokument. Der G19-Zuwachs
ist in beiden Runden da, seine Größe schwankt aber um mehr als das Doppelte.

## 3n. Gebaut, noch nicht gemessen

Zwei Änderungen liegen fertig und ungemessen im Repository. Beide folgen aus
Abschnitt 3m, keine geht in die Produktion, bevor sie gegen **neue Dokumente**
gemessen ist — auf 001-141170 allein wäre jedes Ergebnis wieder eine Eigenschaft
dieses Dokuments.

**`--target thin`: unterdeckte Blöcke statt unberührter Lücken.** Eine
Abdeckungslücke entsteht nur, wo *kein* Claim verankert ist, ab 120 Zeichen; eine
zu 20 Prozent abgedeckte Passage zerfällt in Reststücke unter der Schwelle und
kommt nie auf die Liste. Der neue Zielmodus bewertet stattdessen **Blöcke** —
Absätze, oder den nummerierten Absatz auf eigener Zeile, dieselbe Einheit, die
der zerteilte Lauf nie schneidet — und meldet die, deren verankerter Anteil unter
0,5 liegt. Leerraum zählt nicht mit, sonst wäre ein eingerückter Block schon
wegen seiner Einrückung dünn. Wie die Lückenliste benennt auch das nur Passagen
und entscheidet nichts: Ein dünner Block kann eine Überschrift sein.

Der Unterschied zur Lückenliste ist die Frage, nicht die Schwelle: „Welche
Strecke berührt kein Anker?" gegen „Welcher Absatz ist kaum bearbeitet?". Nur die
zweite kann G09 finden, das zu einem Fünftel verankert ist.

**Zweistufige Extraktion (`two_stage`).** Ein Aufruf muss heute gleichzeitig
atomisieren, typisieren, verankern und verknüpfen. Stufe eins fragt den
Produktionsvertrag ohne seine Relationshälfte — die drei Passagen werden entfernt,
nachdem ihr Vorhandensein geprüft wurde, sonst vergliche das Experiment die
Produktionsprompt mit sich selbst. Stufe zwei bekommt die fertige Claim-Liste mit
Id, Typ, Proposition und Zitat und schlägt Kanten dazwischen vor, über das ganze
Dokument statt innerhalb eines Segments.

Zwei Grenzen sind fest verdrahtet: Stufe zwei darf keine Claims vorschlagen, und
eine Kante, die eine Id nennt, die Stufe eins nicht erzeugt hat, wird mit Grund
verworfen, bevor das Paket entsteht — dasselbe Geschäft, das das Gate für
unauflösbare Endpunkte macht, nur eine Ebene früher, damit der Grund bei dem Lauf
bleibt, der ihn verursacht hat.

Zwei Fragen hängen daran: ob der Claim-Recall steigt, wenn ein Aufruf weniger zu
tun hat, und ob die Segmentierung damit brauchbar wird — sie verliert heute jede
Relation über eine Segmentgrenze, weil Kanten nur dort entstehen, wo ein Aufruf
beide Enden gesehen hat.

**Was die Messung braucht.** Nicht 001-141170: neue Entscheidungen, mehrere
davon, und Wiederholungen über Sitzungen, weil die Streuung über Sitzungen bei
vier Spannen liegt. Und für die Zweistufigkeit gehört die eigene Fixture als
Gegenprobe dazu, deren Relationszahl in den eingefrorenen Kontrollen steht.

## 3o. Erster Lauf auf Papern: Teilübertrag

A24, 21.518 Zeichen, 219 Gold-Spannen, Produktionsprompt, 65.536 Tokens, ein
Aufruf. Vorab festgelegt: ≥ 60 Prozent der Decke ⇒ der Befund überträgt sich auf
Paper; < 30 Prozent ⇒ er überträgt sich nicht; dazwischen ⇒ Teilübertrag.

| | |
|---|---:|
| Gold-Spannen | 219 |
| Decke der Messung | 186 (85 %) |
| erreicht bei 80 % Überlappung | **80 (37 %)** |
| davon gemessen an der Decke | 43 % *(Angabe zurückgezogen, siehe 3p)* |
| Live-Claims | 70 |
| Claims ohne Gold-Entsprechung | 28 |
| Wortdeckung Claim gegen Zitat | Median 1,00, Minimum 1,00 |

**Teilübertrag.** Kein Abbruch, kein Schema-Fehler, keine Beinahe-Dubletten, und
die Zitattreue ist auf diesem Korpus makellos — jeder Claim gibt seinen Beleg
wörtlich wieder. Die Trefferquote liegt aber deutlich unter dem, was die
Gerichtsentscheidungen zeigen (83 Prozent der Decke).

**Die Verteilung ist binär.** Jede gefundene Spanne steht bei 100 Prozent, jede
verfehlte bei 0, im Grenzband um 80 Prozent liegen **0 von 219**. Das ist eine
Eigenschaft der Annotation: Klauselgroße Einheiten werden von einem Claim
entweder ganz eingeschlossen oder gar nicht berührt. Die Schwellendiskussion aus
Abschnitt 3j entfällt hier vollständig.

**Ein Teil der Lücke ist Vertragsunterschied, kein Extraktionsfehler.**

| Länge der Gold-Spanne | gefunden |
|---|---:|
| ≤ 10 Zeichen | 11/63 = 17 % |
| 11–30 | 18/39 = 46 % |
| 31–80 | 41/97 = 42 % |
| > 80 | 10/20 = 50 % |

51 der 63 kurzen Spannen sind **Zitatschlüssel** wie `DL03`, `Sta99`, `ELF05` —
im Sci-Arg-Schema als `data`, also als Evidenz annotiert. Unser Vertrag verlangt
atomare Propositionen mit wörtlichem Beleg; ein Claim, dessen `raw_span` „DL03"
lautet, wäre nach diesem Vertrag falsch. Drei von 51 werden zufällig mitgedeckt.
Ohne diese Klasse: **77/168 = 46 Prozent.**

Nach Komponententyp: `background_claim` 48 Prozent, `own_claim` 41 Prozent,
`data` 26 Prozent. Der Abstand von `data` zu den beiden Claim-Typen ist zum
großen Teil derselbe Zitat-Effekt.

**Was bleibt.** Auch bereinigt findet der Extraktor knapp die Hälfte der
propositionalen Argumenteinheiten eines Papers. Die verfehlten Spannen liegen in
langen zusammenhängenden Blöcken von Gold-Ids — ganze Abschnitte werden nicht
bearbeitet, während andere vollständig erfasst sind. Das ist dasselbe Muster wie
auf der Gerichtsentscheidung, nur ausgeprägter, und es ist genau der Fall, für
den `--target thin` gebaut wurde: ein Absatz mit niedrigem verankerten Anteil,
nicht eine Strecke ohne jeden Anker.

Vorbehalte: ein Paper, ein Lauf. Die Streuung ist auf diesem Korpus zwar
weniger lähmend — 219 statt 24 Spannen —, gemessen ist sie hier aber nicht.

## 3p. Vier Paper, zwei Reparaturläufe — und ein Fehler in meiner Decke

### Die Decke war keine Decke

Abschnitt 3o berichtete Recall „gemessen an der Decke", wobei die Decke die
Punktzahl der Gold-Antwort gegen sich selbst war: 186 von 219 auf A24. Ein
Reparaturlauf hat dann **210 von 219** erreicht — deutlich darüber. Damit ist die
Zahl widerlegt als das, wofür ich sie ausgegeben habe.

Der Fehler ist erklärbar und rückblickend offensichtlich. Die Gold-Antwort als
Extraktion einzuspeisen ist für ein inhaltsadressiertes Gate ein pathologischer
Eingang: Klauselgroße Fragmente wiederholen sich wörtlich, fallen zu einem
Knoten zusammen, und die Gold-Antwort verliert Spannen an sich selbst. Eine
*echte* Extraktion formuliert satzweise, deckt mit einem Claim mehrere kurze
Gold-Fragmente ab und leidet nicht unter dieser Kollision. `gold_ceiling` misst
also, was ein bestimmtes Paket erreicht, nicht was erreichbar ist.

Die Zahl bleibt nützlich als Diagnose — sie zeigt, wie stark die Referenz aus
wiederholten Fragmenten besteht —, aber sie ist **keine obere Schranke**, und
alle „Prozent der Decke"-Angaben aus 3o sind zurückgezogen. Es gelten die rohen
Trefferquoten.

### Vier Paper, gleiche Konfiguration

Produktionsprompt, 65.536 Tokens, ein Aufruf, Regionen von 21,5k bis 24,3k
Zeichen — also praktisch gleich lang.

| Paper | Gold | Recall 80 % | verankerter Anteil | Live-Claims |
|---|---:|---:|---:|---:|
| A40 | 250 | 50 (20 %) | 0,25 | 33 |
| A24 | 219 | 80 (37 %) | 0,37 | 70 |
| A21 | 257 | 112 (44 %) | 0,39 | 67 |
| A34 | 267 | 184 (69 %) | 0,75 | 130 |

Vorab festgelegt war: alle drei neuen Paper innerhalb ±10 Punkten um den
A24-Wert ⇒ die Zahl ist eine Korpus-Eigenschaft. **Klar verfehlt**: 20 bis 69
Prozent, ein Faktor von dreieinhalb, bei nahezu identischer Dokumentlänge.
Extraktionsqualität ist also auch auf Papern eine Eigenschaft des einzelnen
Dokuments, und eine Kennzahl aus einem Paper sagt über das nächste nichts.

**Der verankerte Anteil sagt es aber voraus.** Die Reihenfolge der vier
Dokumente ist nach beiden Spalten dieselbe, und die Werte laufen monoton
miteinander. Das ist der erste Beleg dafür, dass die Warnleuchte des Produkts —
eine Zahl, die ohne jede Gold-Antwort auskommt — den Recall-Einbruch anzeigt,
und zwar auf Dokumenten, gegen die nichts optimiert wurde. Ein Dossier mit 0,25
ist dünn, und das Produkt sagt das von sich aus.

### Der Reparaturlauf trägt auf Papern

| | `uncovered` | `thin` |
|---|---|---|
| Zielpassagen | 19 (9.494 Zeichen) | 22 (9.239 Zeichen) |
| Vorschläge | 51 | 38 |
| davon zugelassen | **51** | **38** |
| `source_span_not_found` | 0 | 0 |
| Recall 80 % | 124 → **210**/219 | 80 → **133**/219 |
| Claims | 102 → 153 | 62 → 100 |

Beide Modi gewinnen massiv, +86 und +53 Spannen, und **jeder einzelne Vorschlag
war wörtlich verankerbar und wurde zugelassen**. Auf der Gerichtsentscheidung
scheiterten vier von sieben und fünf von sechs Vorschlägen am Zitat (Abschnitt
3m) — das war also kein Fehler des Reparaturprompts, sondern eine Eigenschaft
des Rechtstextes oder jenes Laufs.

**Was der Vergleich nicht hergibt: welcher Zielmodus besser ist.** Die beiden
Erstläufe sind verschieden ausgefallen — 124 gegen 80 Spannen bei identischer
Konfiguration —, und das ist wieder die Lauf-zu-Lauf-Streuung aus Abschnitt 3i,
diesmal auf einem Paper und in einer Größe, die den Armunterschied überdeckt.
Der A/B-Vergleich ist damit **konfundiert und nicht auswertbar**; er müsste mit
mehreren Wiederholungen je Modus wiederholt werden. Was er zeigt, ist etwas
anderes und Wichtigeres: Der Reparaturgedanke trägt hier, unabhängig vom Modus.

Ein Nebenbefund zur Schema-Robustheit: In beiden Läufen schlug das Modell
Labels vor, die der geschlossene Katalog nicht kennt (`claim`, `RESOURCE`). Die
Claim-Partitionierung aus 3e hat das Paket beide Male gerettet — fünf Claims und
eine Relation abgelehnt, der Rest kam durch.

## 3q. Der Reparaturlauf, dreifach wiederholt: der erste große Gewinn

Sechs Runden auf A24 (219 Gold-Spannen), drei je Zielmodus, dazu zwei Runden auf
A40. Vorab festgelegt: Ausgewertet wird der **Zugewinn innerhalb einer Runde**,
weil jede Runde ihren eigenen Erstlauf hat und die Differenz damit gepaart ist —
genau daran war der Vergleich in 3p gescheitert. Unterschied der mittleren
Zugewinne ≥ 20 Spannen ⇒ die Zielwahl ist der Hebel; < 20 ⇒ gleichwertig, dann
gewinnt die einfachere Lückenliste.

| Runde | `uncovered` | `thin` |
|---|---|---|
| 1 | 76 → **215** (+139) | 85 → 147 (+62) |
| 2 | 176 → **203** (+27) | 80 → 140 (+60) |
| 3 | 80 → **206** (+126) | 81 → 118 (+37) |
| Mittlerer Zugewinn | **+97,3** | +53,0 |
| Mittlerer Endstand | **208/219 (95 %)** | 135/219 (62 %) |

**Unterschied 44 Spannen — das Kriterium ist klar erfüllt, und zwar gegen meine
eigene Konstruktionsannahme.** Ich hatte `thin` gebaut, weil die Lückenliste
teilabgedeckte Passagen nicht sieht (Abschnitt 3m). Auf Papern ist genau das kein
Nachteil: Die Gold-Einheiten sind klauselgroß und liegen in den **unverankerten
Strecken zwischen** den Claims, nicht in dünn verankerten Blöcken. Die
Lückenliste fragt deshalb mehr relevanten Text ab — 13,6k gegen 7,5k Zeichen in
Runde 1 —, und der Block-Filter „unter 50 Prozent verankert" schließt Absätze
aus, die zu 60 Prozent abgedeckt sind und trotzdem ungefundene Spannen tragen.
`thin` bleibt im Repository, geht aber nicht weiter; die Produktionsrichtung ist
die Lückenliste, die das Gate ohnehin berechnet.

**Der Endstand ist das eigentliche Ergebnis: 203 bis 215 von 219, im Mittel
95 Prozent.** Ein zweiter Aufruf hebt die Trefferquote auf A24 von rund 35 auf
rund 95 Prozent.

**Und er macht das Ergebnis vom Zufall unabhängig.** Die Erstläufe streuen
massiv — 76, 176, 80 —, die Endstände nicht: 215, 203, 206.

| | Streuung (SD) |
|---|---:|
| Erstläufe, `uncovered` | 46,2 |
| Endstände, `uncovered` | **5,1** |

Das ist die praktisch wichtigste Eigenschaft, die dieser Branch gemessen hat.
Die Lauf-zu-Lauf-Streuung, die jeden Prompt-Vergleich hier unlesbar gemacht hat,
wird vom Reparaturlauf zusammengezogen: Was der Erstlauf verpasst, holt der
zweite Aufruf nach, weil er nach genau den Stellen gefragt wird, die der erste
nicht berührt hat.

### Der harte Fall

A40 hatte in 3p den dünnsten Graphen: 33 Claims, 54 von 250 Spannen, verankerter
Anteil 0,25. Vorab festgelegt war +40 Spannen.

| Runde | Erstlauf | nach Reparatur |
|---|---|---|
| 1 | 54/250 (33 Claims) | **132/250** (107 Claims), +78 |
| 2 | 122/250 (119 Claims) | **171/250** (150 Claims), +49 |

Beide Male erfüllt. Runde 1 ist die aussagekräftige: ein wirklich dünner Lauf —
der Fall, in dem die Warnleuchte anschlägt — wird auf mehr als das Doppelte
gehoben. Nebenbei zeigt Runde 2, dass A40 kein schwieriges Dokument ist; der
Einzellauf aus 3p war eine dünne Ziehung, nicht eine Dokumenteigenschaft. Die
Korrelation aus 3p gilt also **pro Lauf** — der verankerte Anteil sagt die
Trefferquote *dieses* Laufs voraus —, und nicht als Aussage über das Dokument.
Für eine Warnleuchte ist genau das die richtige Eigenschaft.

### Was noch scheitert

`source_span_not_found` trat in jeder `uncovered`-Runde drei- bis fünfmal auf,
und die abgelehnten Spannen sagen jetzt warum: Es sind Formelpassagen und
Zitatmarken mit ungewöhnlichem Abstand — `φ n+1 = L u, φ n + 1 φ n − φ ̄ 2`,
`[ HK03 ]`. Das Modell normalisiert die Zwischenräume und trifft das Zitat nicht
mehr wörtlich. Das ist ein umgrenztes, benennbares Problem und keine allgemeine
Zitierschwäche — auf gewöhnlicher Prosa lag die Wortdeckung bei 1,00.

Der Schema-Katalog bleibt der zweite Reibungspunkt: `claim`, `condition`,
`DEFINES`, `RESOURCE` wurden vorgeschlagen und abgelehnt. Die
Claim-Partitionierung hat jedes Paket gerettet (bis zu 21 Claims und 6
Relationen verworfen), aber sie kostet jedes Mal einen zweiten bezahlten Aufruf.

## 3r. Die Gegenproben: unschädlich auf der Fixture, wirkungslos auf Rechtstext

### Eigene Fixture, zwei Runden

Der Fall ohne Reparaturbedarf: 2.009 Zeichen, 25 Gold-Claims, die der
Produktionsprompt vollständig erreicht. Vorab festgelegt: Recall bleibt 25/25
und der Graph wächst um weniger als ein Viertel.

| Runde | Ziel | Recall | Claims |
|---|---|---|---|
| 1 | **keine Lücken** | 25/25 | 22 (kein zweiter Aufruf) |
| 2 | 1 Passage (179 Zeichen) | 24/25 → **25/25** | 21 → 23 |

Erfüllt, und besser als das Kriterium verlangte. In Runde 1 fand die
Abdeckungsmessung **gar keine Lücke**, also unterblieb der zweite Aufruf
vollständig — der Mechanismus ist **selbstbegrenzend**: Wo nichts fehlt, gibt es
nichts zu fragen, und es entstehen keine Kosten. In Runde 2 fehlte eine Spanne,
eine Passage wurde erfragt, zwei Claims kamen dazu, und die fehlende Spanne war
drin. Kein Aufblähen, kein Verlust.

Das ist die Einschaltbedingung, die ich noch bauen wollte: Sie ist bereits
eingebaut.

### Gerichtsentscheidung, drei Runden

001-141170, 16.384 Tokens, wo der Erstlauf schon bei 18 bis 20 von 24 liegt.
Vorab festgelegt: mittlerer Zugewinn ≥ 2 Spannen.

| Runde | Vorschläge | zugelassen | Recall | G19 |
|---|---:|---:|---|---|
| 1 | 6 | **0** | 20 → 20 | 23 % → 23 % |
| 2 | 6 | 2 | 18 → 18 | 19 % → **67 %** |
| 3 | 6 | 2 | 20 → 20 | 23 % → **71 %** |

**Mittlerer Zugewinn 0 — verfehlt.** Der Gewinn ist damit papierspezifisch, wie
vor dem Lauf vermutet: Er entsteht, wo der Erstlauf ganze Abschnitte liegen
lässt, nicht dort, wo er nahe an seiner Grenze arbeitet.

Zwei Dinge sind trotzdem sichtbar geworden.

**Der Reparaturlauf zielt richtig.** G03 wurde in jeder Runde zu 100 Prozent
erfragt, G09 zu 80, G19 zu 77–79. Die Passagen, die dieser Branch seit Wochen
verfolgt, standen also in der Anfrage. G19 wird auch bearbeitet — 23 auf 71
Prozent —, überschreitet die Schwelle aber nicht.

**Der Engpass ist die wörtliche Verankerung, und zwar dramatisch.** Von 18
Vorschlägen scheiterten **14** an `source_span_not_found`, in Runde 1 alle
sechs. Auf den Papern waren es rund 7 Prozent. Dieselben drei Passagen
scheitern in jeder Runde, darunter genau die G03-Einlassung.

Eine naheliegende Erklärung habe ich geprüft und **verworfen**: Auf den Papern
sind gesperrte Zitatmarken (`[ HK03 ]`) und Formelsatz plausibel, aber das
EGMR-Dokument enthält **kein einziges** Mehrfach-Leerzeichen, und alle 24
Gold-Spannen sind wörtlich auffindbar. Die Ursache der Abweichung ist damit
offen. Der Lauf druckt die abgelehnten Spannen bisher auf 90 Zeichen gekürzt,
was zwischen einer weggelassenen Fußnotenmarke und einem umformulierten Zitat
nicht unterscheidet; `divergence` binärsucht deshalb jetzt das längste noch
auffindbare Präfix und zeigt beide Fortsetzungen. Die nächste Messung sagt, an
welchem Zeichen es bricht.

### Was daraus für die Produktion folgt

Der Reparaturlauf ist einschaltbar, weil er sich selbst begrenzt: Er kostet
nichts, wo nichts fehlt (Fixture), er hebt dünn geratene Läufe massiv (Paper,
Abschnitt 3q), und er schadet auch dort nicht, wo er nichts ausrichtet
(Rechtstext) — zwei zusätzliche Claims je Runde, kein Recall-Verlust. Vor einer
Produktionsentscheidung fehlt die Ursache der Zitat-Abweichung: Solange 78
Prozent der Vorschläge auf Rechtstext daran scheitern, ist das Verfahren dort
wirkungslos, und der Grund dafür ist ein benanntes, offenes Problem statt einer
Vermutung.

## 3s. Der Zeilenumbruch war der Engpass

Die Diagnose aus 3r hat die Bruchstelle benannt: Der Vorschlag passt bis Zeichen
58, 62 beziehungsweise 206, und dort steht im Dokument ein Zeilenumbruch, wo der
Vorschlag ein Leerzeichen oder nichts hat. Die Entscheidung ist hart umbrochen —
28 Zeilen auf 10.308 Zeichen, Median 323 —, also fallen Umbrüche mitten in Sätze,
und ein Vorschlag, der so eine Passage zitiert, schreibt sie als Fließtext.

Meine Prüfung in 3r war die falsche Sonde: Ich habe auf Mehrfach-Leerzeichen
getestet, nicht auf Zeilenumbrüche innerhalb einer Spanne, und daraufhin die
Ursache als offen gemeldet. Vier der 24 Gold-Spannen tragen einen Umbruch.

`relaxed_span` sucht den Anker auf einer leerraum-normalisierten Kopie des
Dokuments und gibt **die Textstelle des Dokuments** zurück, nie den Wortlaut des
Modells. Der Claim zitiert also weiterhin exakt die Quelle. Eine Passage, die das
Dokument abseits von Leerraum nicht enthält, wird weiter abgelehnt: Das toleriert
Satzspiegel, keine Umformulierung.

Drei Runden, 001-141170, sonst unverändert. Vorab festgelegt: `source_span_not_found`
unter 3 von 18 **und** mittlerer Recall-Gewinn ≥ 2 Spannen.

| Runde | Vorschläge | zugelassen | über Leerraum gerettet | Recall | G03 | G09 | G19 |
|---|---:|---:|---:|---|---|---|---|
| 1 | 7 | **7** | 4 | 20 → **23**/24 | 0 → **100 %** | 20 → **90 %** | 23 → 71 % |
| 2 | 8 | **8** | 3 | 18 → **20**/24 | 0 → **100 %** | 20 → **90 %** | 19 → 67 % |
| 3 | 7 | **7** | 4 | 20 → **23**/24 | 0 → **100 %** | 20 → **90 %** | 23 → 71 % |

**Beide Bedingungen erfüllt, dreimal von drei.** Keine einzige Ablehnung wegen
fehlender Verankerung mehr, gegen 14 von 18 zuvor. Mittlerer Zugewinn +2,7
Spannen, wo derselbe Lauf ohne die Toleranz 0 brachte.

**G03 ist drin.** Die Regierungseinlassung, die dieser Branch seit dem ersten
Recall-Lauf in *jedem* Lauf verfehlt hat, erreicht in allen drei Runden 100
Prozent. G09 steigt von 20 auf 90 und damit über die Schwelle; G19 bleibt bei
67–71 Prozent darunter. Der Endstand 23/24 ist der höchste je auf diesem Dokument
gemessene Wert — das bisherige Maximum war 20/24.

Der Graph wächst dabei moderat: 40→47, 45→53, 41→48 Claims.

Dasselbe Prinzip erklärt auch die Ausfälle auf den Papern — `[ HK03 ]` mit
gesperrten Klammern und der Formelsatz sind ebenfalls Leerraum-Unterschiede,
dort in kleinerer Zahl (rund 7 Prozent statt 78).

### Was das für die Produktion bedeutet, und was noch zu entscheiden ist

Die Toleranz steckt bisher nur im Experiment (`--relax-whitespace`, Vorgabe aus).
In die Produktion gehört sie ins Gate, in `_all_offsets` — und dort ist sie
**keine reine Erweiterung**, sondern eine neue Befugnis: Das Gate müsste den
`raw_span` eines Vorschlags durch die Textstelle des Dokuments **ersetzen**.
Bisher lässt es zu oder lehnt ab, es verändert keinen Vorschlag.

Dafür spricht, dass die Alternative schlechter ist: Verankerte man den Claim mit
dem Wortlaut des Modells, zitierte das Dossier Text, den das Dokument so nicht
enthält, und genau das soll der wörtliche Beleg verhindern. Dagegen spricht, dass
jede stille Veränderung eines Vorschlags die Prüfbarkeit angreift.

Der saubere Weg ist deshalb: ersetzen, aber **protokollieren** — ein Eintrag im
Audit, der sagt, dass der Anker über Leerraum gefunden und der Wortlaut auf die
Quelle gesetzt wurde. Das ist eine Schemafrage (0.2 → 0.3) und eine Entscheidung,
die nicht nebenbei fällt. Gemessen ist sie; gebaut ist sie nicht.

*Die Verankerungshälfte ist inzwischen gebaut, siehe 3z. Die Identitätshälfte ist
zurückgestellt: Eine Textstelle kann mehrere Aussagen tragen, und sie allein als
Knoten-Adresse zu nehmen hätte die zweite still verworfen.*

## 3t. Zweistufige Extraktion: die Vorab-Festlegung

Abschnitt 3n hat den Aufbau beschrieben und ausdrücklich offengelassen, was die
Messung braucht. Das hier ist diese Festlegung, geschrieben vor dem ersten
bezahlten Lauf.

**Was geprüft wird.** Nur eine der beiden Fragen aus 3n ist mit diesem Skript
überhaupt prüfbar. Ob der Claim-Recall steigt, wenn ein Aufruf weniger zu tun
hat: ja. Ob die Segmentierung damit brauchbar wird: nein — `two_stage_extract.py`
segmentiert nicht, es fragt beide Stufen über das ganze Dokument. Die zweite
Frage bleibt offen und wird hier nicht nebenbei mitbeantwortet.

**Die Arme.** A ist der Produktionsvertrag in einem Aufruf, B derselbe Vertrag in
zwei Stufen. Sonst identisch: A24, Produktionsprompt, 65.536 Tokens, `general`,
dasselbe Gold, dieselbe Messung. A24, weil 219 Gold-Spannen aus einer Spanne
Unterschied einen halben Prozentpunkt machen und nicht vier Prozent.

**Drei Wiederholungen je Arm, verschränkt in einem Fenster.** Der Grund steht in
3i und 3p: Auf A24 kamen zwei erste Durchgänge unter identischen Einstellungen
bei 124 und 80 Spannen heraus. Ein Paar aus je einem Lauf könnte einen Effekt von
44 Spannen nicht von der Streuung trennen, und ein Effekt dieser Größe ist nicht
zu erwarten. Die drei Läufe je Arm messen deshalb zuerst die Streuung des Arms
selbst; der Unterschied zwischen den Armen wird an ihr gelesen, nicht an den
Mittelwerten.

**Die Entscheidungsregel, vorab:**

- **Verbesserung** nur, wenn sich die Arme nicht überschneiden: min(B) > max(A)
  beim Recall auf 80 Prozent Überlappung. Bei drei gegen drei Läufen tritt eine
  vollständige Trennung unter Zufall in 10 Prozent der Fälle ein — das ist die
  schwächste Aussage, die diese Stichprobe tragen kann.
- **Kein Befund**, wenn sich die Arme überschneiden. Dann ist der Effekt kleiner
  als die Streuung, und die Zweistufigkeit bleibt ungemessen, nicht widerlegt.
- **Auflösung unzureichend**, wenn allein die Streuung innerhalb von Arm A
  40 Spannen oder mehr beträgt. Dann sagt der Vergleich unabhängig von den
  Mittelwerten nichts, und das ist das Ergebnis.
- Ein Lauf, der abbricht, zählt zu seinem Arm, wie in 3i.

**Zweitens, nur beschreibend:** zugelassene Relationen je Arm, Claims je Arm, in
Stufe zwei verworfene Kanten mit unbekannten Endpunkten, Beinahe-Dubletten. Für
die Relationszahl gibt es keine Vorab-Marke, weil es für A24 keinen gemessenen
Ausgangswert gibt — sie wird in diesem Lauf erst erhoben. Aus einer Zahl ohne
Vorhersage wird hier kein Befund gemacht.

**Die Gegenprobe.** Ein Lauf auf der eigenen Fixture, deren eingefrorenes Paket
25 Claims und 15 Relationen hat. Vorab: mindestens 24 der 25 Gold-Claims, sonst
ist die Aufspaltung eine Verschlechterung auf einem Dokument, das sie mühelos
schaffen müsste — und das schlägt jeden Gewinn auf Papern.

## 3u. Zweistufig gemessen — und was der Lauf stattdessen fand

Sieben Läufe nach der Festlegung in 3t, dann fünf weitere nach zwei Defekten, die
der Lauf in sich selbst fand. Die Defekte stehen im Commit; kurz: Stufe zwei kann
das geschlossene Schema nicht bestehen, weil sie eine leere Claim-Liste
zurückgeben soll und das Schema mindestens einen Claim verlangt — beide Hälften
waren getestet, die Nahtstelle zwischen ihnen nicht. Und die Gegenprobe auf der
Fixture war noch nie gelaufen: ihr Korpus überspringt den Fetch-Schritt, und
`mv` auf die fehlende Provenienzdatei ließ den Job unter `bash -e` scheitern,
bevor die Fixture kopiert war.

**Das Urteil nach der Vorab-Regel: Auflösung unzureichend.** Arm A streut heute
von 124 bis 201 Spannen, also 77 — die Regel nennt 40 als Grenze, ab der der
Vergleich unabhängig von den Mittelwerten nichts sagt. Zusätzlich überschneiden
sich die Arme, womit auch die zweite Bedingung (min(B) > max(A)) klar verfehlt
ist. Die Zweistufigkeit ist damit **nicht gemessen, nicht widerlegt**.

A24, 219 Gold-Spannen, Produktionsprompt, 65.536 Tokens, alles am 25.09. in einem
Fenster:

| | Vorschläge | zugelassen | Anker abgelehnt | Relationen | Recall@80 |
|---|---:|---:|---:|---:|---|
| A einstufig 1 | 111 | 102 | 9 | 29 | 194/219 (89 %) |
| A einstufig 2 | 122 | 115 | 7 | 73 | 201/219 (92 %) |
| A einstufig 3 | 111 | 80 | 31 | 30 | 124/219 (57 %) |
| A Drift-Probe | 121 | 115 | 6 | 31 | 209/219 (95 %) |
| B zweistufig 1 | 115 | 111 | 4 | 65 | 203/219 (93 %) |
| B zweistufig 2 | 116 | 84 | 32 | 42 | 127/219 (58 %) |
| B zweistufig 3 | 108 | 77 | 31 | 45 | 121/219 (55 %) |

Die Drift-Probe ist ein vierter einstufiger Lauf im Fenster der B-Läufe, getrennt
berichtet und nicht in Arm A hineingerechnet: Arm A lief zwanzig Minuten früher,
und ohne diese Probe wäre nicht auszuschließen, dass sich in der Zwischenzeit
etwas verschoben hat. Es hat sich nichts verschoben.

**Die Gegenprobe ist bestanden.** Auf der eigenen Fixture: 27 Claims, 19
Relationen, **25 von 25 Gold-Claims**, keine Lücke, keine Anker-Ablehnung. Die
Vorab-Marke war 24 von 25. Die Aufspaltung beschädigt also nichts, wo der
einstufige Aufruf schon alles erreicht — sie liefert dort sogar mehr Kanten als
das eingefrorene Paket (19 gegen 15).

**Ein einziger sauberer Unterschied, beschreibend.** Stufe zwei hat in keinem
Lauf eine Id erfunden: 67 von 67, 60 von 60, 65 von 65 Kanten waren auflösbar.
Der einstufige Aufruf verlor in zwei von vier Läufen Kanten an nicht zugelassene
Endpunkte. Das ist kein Recall-Argument, und es ist auch kein großer Effekt — es
heißt nur, dass eine Kantenfrage über eine fertige Claim-Liste keine Endpunkte
mehr halluziniert.

### Was der Lauf stattdessen fand

**Das ausgelieferte Modell hat sich geändert.** Dieselbe Anfrage schickt
weiterhin `deepseek-v4-flash`; die Antwort nennt seit dem 31.08. nicht mehr
`deepseek-v4-flash`, sondern `deepseek-flash`. Das Feld kommt aus dem Envelope
der API, nicht aus unserer Konfiguration — die Provenienz hat genau den Zweck
erfüllt, für den sie da ist. Dasselbe Dokument (gleicher sha256 des Korpus,
gleiche 21.518 Zeichen), dieselbe Prompt, dasselbe Budget:

| | Anker abgelehnt | davon echte Umformulierung | davon nur Leerraum | Recall@80 |
|---|---:|---:|---:|---|
| 31.08. | 64 von 134 | 54 | 10 | 80/219 (37 %) |
| 25.09. Lauf 1 | 9 von 111 | 0 | 9 | 194/219 (89 %) |
| 25.09. Lauf 2 | 7 von 122 | 0 | 7 | 201/219 (92 %) |
| 25.09. Lauf 3 | 31 von 111 | 11 | 20 | 124/219 (57 %) |

Der dominierende Fehlerterm im August war also **falsches Zitieren**, und er ist
fast verschwunden. Was bleibt, ist überwiegend Satzspiegel.

**Und deshalb: das Gate, nicht der Extraktor.** `gate_counterfactual.py` gatet ein
fertiges Paket zweimal — wie gemessen, und mit jeder Spanne, die sich vom
Dokument nur im Leerraum unterscheidet, ersetzt durch die Textstelle des
Dokuments. Kein neuer Aufruf, keine neuen Kosten, dieselbe Funktion, die der
Reparaturlauf schon benutzt:

| | wie gemessen | mit Leerraum-Toleranz |
|---|---|---|
| A 1 | 194 (89 %) | **216 (99 %)** |
| A 2 | 201 (92 %) | **219 (100 %)** |
| A 3 | 124 (57 %) | **192 (88 %)** |
| A Drift | 209 (95 %) | **218 (100 %)** |
| B 1 | 203 (93 %) | **218 (100 %)** |
| B 2 | 127 (58 %) | **198 (90 %)** |
| B 3 | 121 (55 %) | **196 (89 %)** |
| 31.08. | 80 (37 %) | 107 (49 %) |

**Die Streuung war größtenteils das Gate.** Arm A geht von 77 Spannen Streuung
auf 27, Arm B von 82 auf 22, und das Niveau springt auf 88 bis 100 Prozent. Das
heißt: der Extraktor ist viel stabiler, als jede Messung auf diesem Branch
aussah — was streute, war zu einem großen Teil, ob das Gate seine Zitate annimmt.
Ein Lauf erreicht 219 von 219.

### Was das an früheren Aussagen ändert

Vier Dinge sind damit zu relativieren, und keines davon ist angenehm.

1. **„Extraktionsqualität ist eine Eigenschaft des Dokuments"** (3p) steht unter
   Vorbehalt. Unter dem toleranten Gate landen alle Läufe auf A24 zwischen 88 und
   100 Prozent; die Unterschiede, die auf vier Papern nach Dokumenteigenschaft
   aussahen, könnten überwiegend Anker-Ablehnungen gewesen sein. Das ist auf den
   anderen drei Papern nachzurechnen — offline, ohne Kosten.
2. **Die Warnleuchte** (verankerter Anteil ordnet den Recall) hat ein
   Tautologieproblem, das ich bisher nicht benannt habe: Eine Anker-Ablehnung
   senkt mechanisch beides, den verankerten Anteil *und* den Recall. Die
   Korrelation über vier Paper kann deshalb zum Teil eingebaut sein. Ob die
   Leuchte auch dann noch ordnet, wenn das Anker-Problem behoben ist, ist offen.
3. **Der Gewinn des Reparaturlaufs** (3q, 124 → 210) ist teilweise
   Wiederbeschaffung dessen, was das Gate verworfen hat — für einen bezahlten
   zweiten Aufruf, wo die Gate-Toleranz nichts kostet.
4. **Jede Zahl auf diesem Branch von vor dem 25.09.** ist gegen eine andere
   ausgelieferte Modellkennung gemessen. Die Vergleiche innerhalb eines Fensters
   bleiben gültig; jeder Vergleich über Wochen hinweg ist keiner.

Und eine methodische Einordnung, die dazugehört: Die Leerraum-Rechnung ist
**nachträglich**, nicht vorab festgelegt. Sie ist eine Hypothese aus den Daten,
die sie erklärt, und was sie sagt, ist präzise begrenzt — was dieselben
Vorschläge unter einem anderen Gate erreicht hätten, nicht was ein Lauf unter
diesem Gate produzieren würde. Zweitrundeneffekte, etwa eine Abdeckungsmessung,
die andere Lücken meldet, und ein Reparaturlauf, der deshalb nach anderen
Passagen fragt, liegen außerhalb.

Die Produktionsentscheidung aus 3s bleibt damit unverändert offen, aber sie ist
jetzt teuer geworden: Das Gate müsste den `raw_span` eines Vorschlags durch die
Textstelle des Dokuments ersetzen und diesen Eingriff protokollieren
(Schema 0.2 → 0.3), und die Messung sagt, dass daran auf diesem Korpus zwischen
neun und achtundsechzig Spannen hängen.

## 3v. Die Streuung der Reviewer-Arme: die Vorab-Festlegung

Auf diesem Branch ist keine einzige Aussage über Befundqualität wiederholt
worden. Nach 3u ist das kein Versäumnis mehr, sondern ein bekannter Fehler.

**Warum die Arme zuerst allein gemessen werden.** Die Arme lesen den gegateten
Graphen, und der schwankte in 3u auf demselben Dokument zwischen 77 und 115
zugelassenen Claims. Eine Reviewer-Messung über frische Extraktionen misst
deshalb den Extraktor und schreibt das Ergebnis dem Reviewer zu. Der Eingang muss
also festliegen: das eingefrorene Paket des Repositorys durch das echte Gate,
fünf Läufe, dasselbe Dokument, dasselbe Profil (`budget`, weil dort eine
eingefrorene Kontrolle daneben steht). Die Kette Extraktion + Review wird danach
gemessen, nicht gleichzeitig.

**Gültigkeitsbedingung, keine Marke.** Dokument-Hash und die Liste der
zugelassenen Claim-Ids müssen in allen Läufen identisch sein. Sind sie es nicht,
hat sich der Eingang bewegt, und die Messung sagt nichts über die Arme — sie wird
dann nicht interpretiert, sondern abgebrochen.

**Die Identität eines Befunds.** Zwei Befunde sind derselbe, wenn sie dieselben
Claims aus demselben Grund benennen: Kategorie plus Claim-Ids. Der Wortlaut der
Zusammenfassung gehört nicht dazu, sonst wäre jede Umformulierung ein neuer
Befund. Gezählt wird ausschließlich die LLM-Hälfte; die deterministischen Befunde
sind konstruktionsgemäß identisch, und sie mitzuzählen berichtete die Stabilität
der Regeln als die der Arme.

**Das Maß:** Anteil = Zahl der Befunde, die in *allen* fünf Läufen vorkommen,
geteilt durch die mittlere Befundzahl eines Laufs.

- **≥ 0,8 ⇒ stabil.** Ein Ein-Lauf-Vergleich der Arme ist für Effekte brauchbar,
  die größer sind als die wechselnde Menge.
- **< 0,5 ⇒ instabil.** Dann darf keine Aussage über Befundqualität aus einem Lauf
  gemacht werden, und jede bestehende müsste pro Arm wiederholt werden, bevor sie
  stehen bleibt.
- **0,5 bis 0,8 ⇒ die Auflösung liegt dort.** Ein Effekt kleiner als die
  wechselnde Menge ist mit einem Lauf je Arm nicht zeigbar.

Ein Arm, der nicht antwortet, zählt als Lauf ohne Befunde und nimmt damit jeden
Befund aus dem stabilen Kern — wie in 3i, und aus demselben Grund: ein Arm, der
einmal von fünf ausfällt, ist genau das, was ein einzelner Lauf nicht sieht.

**Zweitens, nur beschreibend:** der Anteil je Arm getrennt, die Liste der
wechselnden Befunde mit Trefferzahl, die Zahl der abgelehnten Befunde je Lauf und
ob ein Aufruf eine Modellersetzung gemeldet hat.

## 3w. Die Arme, fünfmal über denselben Graphen

Fünf Läufe nach der Festlegung in 3v. Der Eingang lag fest und ist geprüft:
Dokument-Hash und Claim-Ids waren in allen fünf Läufen identisch, die Gültigkeits-
bedingung ist also erfüllt.

| Lauf | Arm-Befunde | davon verschieden | abgelehnt | Thinking-Arm |
|---|---:|---:|---:|---|
| 1 | 11 | 11 | 1 | **ohne Antwort** |
| 2 | 11 | 11 | 1 | **ohne Antwort** |
| 3 | 20 | 16 | 0 | 10 Befunde |
| 4 | 10 | 10 | 1 | **ohne Antwort** |
| 5 | 19 | 15 | 0 | 9 Befunde |

„Verschieden" zählt Befunde nach Identität — dieselben Claims aus demselben Grund
—, und beide Arme können denselben Befund liefern. Das ist eine Angabe, keine
Rechnung: 20 Befunde in Lauf 3 sind 16 verschiedene.

**Das Urteil nach der Vorab-Regel: die Auflösung liegt bei 0,63.** Acht Befunde
kommen in allen fünf Läufen vor, gegen ein Mittel von 12,6 verschiedenen pro Lauf.
Das ist die Mittelkategorie: ein Effekt, der kleiner ist als die wechselnde Menge,
ist mit einem Lauf je Arm nicht zeigbar. Getrennt nach Arm: der Evidenz-Arm
erreicht 0,77 bei 10 bis 11 Befunden pro Lauf, der Thinking-Arm 0,00 — und zwar
aus einem Grund, der die eigentliche Nachricht dieses Laufs ist.

### Der Thinking-Arm fällt in drei von fünf Läufen aus

`_FatalProviderError: DeepSeek output was truncated; raise max_tokens`, dreimal
von fünf, auf dem 1.700 Zeichen langen Antrag des eigenen Repositorys. Das
Reviewer-Budget ist in `anti_delphi.py` auf 8.192 Tokens festgeschrieben, und der
Thinking-Arm verbraucht es beim Denken, bevor er seine Findings schreibt. Bei
Abschneiden wird nicht wiederholt — dieselbe Anfrage bei Temperatur 0 endet
genauso —, also fehlt der Arm ganz.

Drei Dinge daran sind bemerkenswert und keines davon ist angenehm.

**Es ist ein Produktionsfehler, nicht ein Messartefakt.** Jeder zweite bis dritte
Review läuft mit einem statt zwei unabhängigen Armen, und das Anti-Delphi-Prinzip
— zwei Arme, die sich nicht sehen — ist dann nicht erfüllt. Der Anteil, den 3v
für den Thinking-Arm ausweist, ist deshalb keine Aussage über seine Stabilität,
sondern über seine Verfügbarkeit.

**Das Dossier hat es die ganze Zeit protokolliert.** `status: "failed"`,
`error_type`, und die Ablehnung mit ihrem Grund stehen in jedem betroffenen Lauf.
Es hat nur nie jemand hingesehen, weil die eingefrorenen Kontrollen offline
laufen und die Arme dort gar nicht aufgerufen werden, und weil jeder Live-Lauf
bisher ein einzelner war: dort sieht man „der Thinking-Arm hat nichts gefunden"
oder „er hat zehn gefunden" und kann nicht unterscheiden, was der Normalfall ist.
Genau das ist der Grund, aus dem 3v fünf Läufe verlangt hat.

**Und die Modellersetzung aus dem vorigen Abschnitt wird live bestätigt.** Jeder
erfolgreiche Aufruf meldet `model_substituted`, jeder fehlgeschlagene keinen — was
richtig ist, denn ohne Antwort ist kein ausgeliefertes Modell bekannt. Der
Mechanismus hat innerhalb einer Stunde nach dem Einbau einen echten Treffer
geliefert.

### Was daraus folgt, und was nicht

Nicht gemessen ist damit weiterhin, wie stabil der Thinking-Arm ist, wenn er
antwortet: zwei Läufe mit 10 und 9 Befunden sind zwei Läufe. Die Wiederholung
gehört nachgeholt, nachdem das Budget entschieden ist — und sie ist erst dann
aussagekräftig, weil ein Arm, der in drei von fünf Fällen fehlt, jede
Stabilitätszahl dominiert.

Die Entscheidung über das Budget fällt nicht hier. Drei Wege stehen offen: das
Reviewer-Budget global heben, es nur für den Thinking-Arm heben, oder den
Thinking-Arm um weniger bitten. Alle drei kosten pro Aufruf mehr oder verändern,
was der Arm liefert, und keine Messung sagt bisher, welcher Wert reicht.

Was ohne weitere Entscheidung gilt: **keine Aussage über Befundqualität auf diesem
Branch darf auf einem Lauf ruhen.** Bei 0,63 ist ein Ein-Lauf-Vergleich zweier
Prompts oder zweier Profile nicht lesbar, und das betrifft jede zukünftige
Reviewer-Arbeit genauso, wie es 3i die Extraktionsarbeit betroffen hat.

## 3x. Steckt die Instabilität in der Identität? Die Vorab-Festlegung

Working Paper 2 (Alexandria, SPL, §10.2) legt die Identität eines Claims als
`CIK = hash(subject_id, relation_id, object_id, scope)` fest — **ohne
Oberflächentext und ohne Score**, und begründet das genau mit dem Fall, den dieser
Branch gebaut hat: „two ClaimCandidates with the same subject-relation-object
triple but different candidate_scores would be treated as different propositions,
causing duplicate ingestion."

Unser Gate hasht stattdessen `document_id ∥ claim_type ∥ canonical_content ∥
raw_span` (`gate.py:64`). Beide Wortlaute — der des Modells und der des Dokuments
— stecken in der Identität, und `relation_id` hasht die Knoten-Ids beider Enden
(`gate.py:119`), also verändert ein umformulierter Claim **jede Kante, die ihn
berührt**.

Wenn das die Ursache der Streuung aus 3u ist, dann war jeder Patch dieses Branches
— die Leerraum-Toleranz, die `MINIMUM_NEW_SHARE`-Regel des Reparaturlaufs,
`near_duplicates` — ein Symptom.

**Was gemessen wird, und was nicht.** Kein neuer Aufruf: `identity_ladder.py`
schlüsselt fertige Pakete auf vier Stufen neu auf — `exact` (heutige Identität),
`span` (leerraum- und satzzeichennormalisiertes Zitat), `content`
(normalisierte Proposition), `proposition` (sortierte Token-Menge der
Proposition). Datenbasis: die sieben A24-Läufe vom 25.09. (vier einstufig, drei
zweistufig) und der Lauf vom 31.08., getrennt nach Arm und gepoolt.

`proposition` ist **kein CIK.** Ein CIK braucht Entitätsauflösung, die hier nicht
existiert. Die Stufe behält Funktionswörter absichtlich — sie weglassen wäre ein
Regler zum Nachjustieren —, verwirft dafür die Wortstellung, und sie kann keine
Synonyme zusammenziehen. Sie begrenzt den Effekt also einseitig: konservativ beim
Wortlaut, gar nicht beim Vokabular.

**Die Regel, vorab:** relativer Zuwachs des stabilen Kerns von `exact` zu
`proposition`.

- **≥ +50 Prozent**, bei höchstens 5 Prozent innerhalb eines Laufs verschmolzenen
  Claims ⇒ der Wortlaut in der Identität ist eine Hauptursache der Instabilität,
  und ihn herauszunehmen ist die Entitätsauflösung wert, die es kostet.
- **< +20 Prozent** ⇒ die Streuung ist nicht überwiegend Umformulierung. Der CIK
  löst unser Problem dann nicht, und die Idee wird geparkt statt gebaut.
- Dazwischen ⇒ Teileffekt; die `span`-Stufe sagt dann, wie viel davon allein
  Satzspiegel ist.
- **Mehr als 15 Prozent verschmolzene Claims innerhalb eines Laufs** ⇒ der
  Ersatzschlüssel zieht verschiedene Propositionen zusammen, und die Zahl sagt
  unabhängig vom Zuwachs nichts.

**Die zweite Messung hat keine Marke, weil sie eine Zählung ist.**
`relation_reach.py` zählt die Relationslabels, nach denen der Extraktor gegriffen
hat und die unser geschlossenes Vokabular nicht hat, und sortiert jedes in einen
von vier Fällen: unser eigener Claim-Typ im falschen Feld; eine Familie, die wir
abdecken (falsches Wort, richtige Familie — der Fall, den die Familie-zuerst-Frage
aus §5.3 des Papers fängt); eine Familie, von der wir kein einziges Mitglied
haben (dann ist das Vokabular zu eng, nicht die Prompt); oder keiner Familie
zuzuordnen. Die Zuordnung unserer vierzehn Relationen zu den sechs Familien des
Papers ist ein Urteil, einmal und offen getroffen, keine Messung.

## 3y. Nicht die Proposition, sondern das Zitat

Beide Messungen aus 3x sind gelaufen, offline, ohne einen Aufruf. Die erste
widerspricht der Deutung, mit der ich sie vorgeschlagen habe; die zweite
widerlegt eine Behauptung, die ich davor aufgestellt hatte.

### Messung 1: der Wortlaut des Modells ist das Instabile

| Stufe | A24 Arm A (4 Läufe) | A24 alle sieben | 001-141170 (3 Runden) |
|---|---|---|---|
| `exact` (heute) | 36 | 26 | 19 |
| `span_ws` | **75** (+108 %) | **59** (+127 %) | **30** (+58 %) |
| `span_norm` | **81** (+125 %) | **64** (+146 %) | **31** (+63 %) |
| `content` | 53 (+47 %) | 41 (+58 %) | 20 (**+5 %**) |
| `proposition` | 53 (+47 %) | 41 (+58 %) | 20 (+5 %) |

Die vorab festgelegte Hauptgröße war der Zuwachs von `exact` zu `proposition`:
+47 Prozent auf Arm A, +58 Prozent gepoolt, **+5 Prozent auf dem Rechtstext**.
Nach der Regel aus 3x ist das auf dem Paper ein Teileffekt und auf der
Entscheidung **unterhalb der Abbruchschwelle von 20 Prozent**. Die wörtliche
CIK-Lesart — Identität aus der Proposition, Oberflächentext heraus — erklärt
unsere Instabilität also **nicht**.

Die Regel sah für den Teileffekt vor, dass dann die `span`-Stufe sagt, wie viel
davon Satzspiegel ist. Sie sagt: fast alles. Und sie sagt mehr, als die Regel
erwartet hat — nicht „ein Teil der Streuung ist Satzspiegel", sondern:

**Der instabile Bestandteil der heutigen Identität ist `canonical_content`, der
Wortlaut des Modells. Das Zitat des Dokuments ist vergleichsweise stabil.**

Den Span aus der Identität zu nehmen bringt auf dem Rechtstext 5 Prozent; die
Proposition herauszunehmen bringt 58. Das ist die umgekehrte Richtung zu dem, was
ich vorgeschlagen habe, und auch zu dem, was das Paper vorsieht: §10.2 nimmt den
Oberflächentext ganz heraus und setzt subject/relation/object in die Identität —
alles drei vom Modell geschrieben. Unsere Daten sagen, dass genau das die
unzuverlässige Hälfte ist.

**Alle Schutzbedingungen halten.** Innerhalb eines Laufs verschmolzen: 0,0 / 0,0
/ 3,6 Prozent der Claims, gegen eine Vorab-Grenze von 5. Dass der Rechtstext der
einzige Fall mit Verschmelzungen ist, war vorhergesagt — juristische Prosa
wiederholt ganze Formeln. Und die Propositionen hinter einem gemeinsamen
Span-Key stimmen überein: Median 1,00, Minimum 0,71, **keiner von 170 Keys unter
0,5**. Der Span-Key zieht also keine verschiedenen Aussagen über dieselbe Stelle
zusammen; die drei schwächsten Fälle sind derselbe Satz mit aufgelöstem Pronomen
(„This approach" gegen „The BFECC approach").

**Leerraum genügt, Satzzeichen braucht es nicht.** `span_ws` (Kleinschreibung und
Leerraum) gegen `span_norm` (zusätzlich ohne Satzzeichen) unterscheidet sich um
sechs Keys auf A24 und einen auf der Entscheidung. Die schwächere und besser
begründbare Normalisierung trägt praktisch alles, und Satzzeichen können
bedeutungstragend sein — sie bleiben also in der Identität.

**Was das für die offene Entscheidung aus 3s bedeutet.** Die Frage war: darf das
Gate den `raw_span` eines Vorschlags durch die Textstelle des Dokuments
*ersetzen*? Sie stellt sich so nicht mehr. Die Identität würde über einen
leerraum-normalisierten Span berechnet, der wörtliche Span bleibt als Beleg
gespeichert. Kein Vorschlag wird umgeschrieben, das exakte Zitat bleibt im Audit,
und eine Satzspiegel-Variante ist derselbe Knoten statt gar keiner.

Der Preis bleibt und ist zu nennen: Knoten-Ids ändern sich, also ist das eine
Schemaänderung (0.2 → 0.3) und eine Einbahnstraße für bereits gespeicherte
Dossiers. Nur ist es jetzt eine kleinere und sauberere Änderung als beide
Varianten, die ich vorher zur Wahl gestellt habe.

### Messung 2: eine Rücknahme

18 Relations-Ablehnungen in 32 Dateien.

| Label | Treffer | Fall |
|---|---:|---|
| CAUSAL | 9 | **eigener Claim-Typ im Relationsfeld** |
| LIMITATION | 7 | **eigener Claim-Typ im Relationsfeld** |
| CAUSES | 1 | Familie vorhanden (DYNAMIC) |
| DEFINES | 1 | Familie vorhanden (ONTIC) |

**16 von 18 sind Feldverwechslungen**, keine Griffe nach einer fehlenden
Relation: `CAUSAL` und `LIMITATION` sind unsere *eigenen Claim-Typen*. Kein
einziger Fall fällt in „Familie ohne Mitglied".

Ich hatte vorher behauptet, jedes dieser Labels sei ein Familienlabel, nach dem
das Modell greift, weil unser konkretes Vokabular es nicht hat. **Das ist falsch.**
Es sind überwiegend unsere eigenen Claim-Typen im falschen Feld — und die
Produktionsprompt verbietet genau das ausdrücklich („Never put a claim_type such
as method, evidence or assumption into relation_type") und wird sechzehnmal
ignoriert. Die Familie-zuerst-Frage aus §5.3 des Papers würde den dominierenden
Fall deshalb **nicht** beheben.

**Was ihn behebt, haben wir schon gemessen, ohne es zu merken.** Nach Arm
getrennt:

| | vorgeschlagene Kanten | ungültige Labels |
|---|---:|---:|
| Arm A, einstufig, 4 Läufe | ~173 | **10** |
| Arm B, zweistufig, 3 Läufe | 192 | **0** |

Die Aufspaltung, die nach der Recall-Regel aus 3u „nicht lesbar" war, hat damit
eine zweite saubere Eigenschaft neben den auflösbaren Endpunkten: Stufe zwei hat
kein `claim_type`-Feld, aus dem etwas ins Relationsfeld lecken könnte. Dreimal
null bei vergleichbarer oder höherer Exposition.

**Und die Grenze dieser Zählung.** Sie sieht nur Labels, nach denen das Modell
*trotz* der geschlossenen Liste in der Prompt greift, also keine unterdrückte
Nachfrage. Dass unsere vierzehn Relationen nur vier der sechs Familien des Papers
abdecken — STATISTICAL und NORMATIVE haben **kein einziges Mitglied** — bleibt
strukturell wahr und hat in diesen Daten **keine Stütze**: das Modell hat nie
danach gefragt. Auf einer Entscheidung des EGMR, die von Geboten und Verboten
handelt, ist das Fehlen von NORMATIVE auffällig; es als gemessenen Bedarf zu
verkaufen wäre genau der Fehler, für dessen Verhinderung die vier Fälle gebaut
wurden.

### Was weiterhin offen ist

Die Abdeckung. Claims, die nie vorgeschlagen wurden, sind von keiner dieser
Messungen und von keinem Teil des Papers berührt; der Reparaturlauf bleibt dafür
der einzige Mechanismus, und er kostet einen bezahlten Aufruf.

## 3z. Gebaut: der Anker toleriert Satzspiegel — und nur das

Die Entscheidung aus 3s ist umgesetzt, aber **nur zur Hälfte**, und das ist eine
Korrektur an meinem eigenen Vorschlag.

3y hatte zwei Dinge zusammengezogen, die getrennt gehören:

- **A, die Verankerung.** Zuerst wörtlich suchen; nur ohne Treffer auf einer
  leerraum-normalisierten Kopie, und zurück kommt die Position im **Original**.
  Der Claim zitiert die Zeichen des Dokuments, nie den Wortlaut des Modells.
- **B, die Identität.** `canonical_content` aus der Knoten-Adresse nehmen.

Gebaut ist **A**. **B ist zurückgestellt**, weil es einen Fehler hat, den meine
Prüfung nicht gefunden hat.

### Warum B zurückgestellt ist

Eine Textstelle ist ein **Ort im Dokument, keine Proposition.** Ein Satz kann
mehrere Aussagen tragen, und derselbe Satz lässt mehrere Lesarten zu. Keyte man
den Knoten allein auf den Anker, würde die zweite Aussage an derselben Stelle als
`duplicate_claim_node` abgelehnt — die Maschine entscheidet sich still für die,
die zuerst kam. **Unterschiedliche Lesarten desselben Zitats müssen einen Konflikt
erzeugen, den ein Mensch vergleicht, keine automatische Dublette.**

Meine Prüfung von B war schwach, und das gehört protokolliert: Ich habe sechs
Verschmelzungen auf **einem** Dokument angesehen, alle aus dem Reparaturlauf —
einer Konfiguration, die Dubletten konstruktionsbedingt erzeugt, weil sie
denselben Text ein zweites Mal befragt. Bei einem Paar mit einer
Token-Überschneidung von 0,48 habe ich „dieselbe Aussage" **geurteilt, nicht
gemessen**, und daraus eine Regel für alle Fälle gemacht. Dass derselbe Branch
seit 3k den Spiegelfall kennt — die Regierungseinlassung und die spätere
Wiedergabe durch den Gerichtshof sind zwei Sprechakte — hat mich nicht daran
gehindert.

### Was A allein bringt, getrennt gemessen

Der **Recall-Gewinn liegt vollständig in A.** Dieselben sieben Vorhersagen,
diesmal ohne jeden Kollaps:

| Lauf | vorhergesagt | mit A allein | kollabierte Dubletten |
|---|---:|---:|---:|
| A1 | 216 | **216**/219 | 0 |
| A2 | 219 | **219**/219 | 0 |
| A3 | 192 | **192**/219 | 0 |
| A Drift | 218 | **218**/219 | 0 |
| B1 | 218 | **218**/219 | 0 |
| B2 | 198 | **198**/219 | 0 |
| B3 | 196 | **196**/219 | 0 |

Und auf der Gerichtsentscheidung: **24/24, 22/24, 24/24** — identisch zu dem, was
A und B zusammen lieferten, bei 53, 59 und 54 Claims statt 52, 57 und 51. Die
sechs Paare aus Erstpass und Reparaturlauf bleiben also als getrennte Claims
erhalten, **und der Recall ändert sich dadurch nicht.**

Daraus folgt der Satz, der die Aufteilung begründet: **Der Kollaps hat keinen
einzigen Gold-Span gekauft.** Er hat nur die Stabilitätszahl gehoben — und dafür
Propositionen bezahlt.

### Was A an Stabilität bringt, und was offen bleibt

Weil `raw_span` jetzt die Textstelle des Dokuments trägt, verändert A die
Identität ohnehin: Ein getyptes und ein exaktes Zitat derselben Passage sind
derselbe Knoten. Neu geschlüsselt über fertige Läufe, Claims die in *jedem* Lauf
vorkommen:

| | heute | **A allein** | A+B (zurückgestellt) |
|---|---:|---:|---:|
| A24, 4 Läufe | 36 | **44** | 75 |
| A24, alle sieben | 26 | **33** | 59 |
| 001-141170, 3 Runden | 19 | **19** | 30 |
| verschmolzene Claims | 0 | **0** | 0 / 0 / 6 |

A allein bringt auf Papern 22 bis 27 Prozent und auf Rechtstext **null**. Der
große Teil des Stabilitätsgewinns steckt in B — also genau in dem Stück, das
zurückgestellt ist. Das ist die ehrliche Bilanz: Der sichere Teil kauft den ganzen
Recall und einen kleinen Teil der Stabilität.

### Wie B aussehen müsste

Nicht eine Identität, sondern **zwei Ebenen**. Der Anker ist stabil und der
richtige Schlüssel für Abdeckung, Relationen und Lauf-Vergleiche. Der Claim an
diesem Anker trägt eine Proposition, von der es mehrere geben darf. Divergente
Lesarten an einer Stelle gehören dann markiert — als Konflikt mit menschlicher
Prüfung — statt abgelehnt.

Was dafür fehlt, ist der Begriff „vergleichbare Lesart": ohne ihn ist jede
Umformulierung eine neue Lesart und jeder Konflikt-Marker Rauschen. Den liefert
kein Zählen, sondern ein annotierter Prüfbestand (siehe die Planung in 3ac).

### Audit, Schema, Entferntes

`anchor_normalised` sagt, dass die Textstelle erst nach Ignorieren von Leerraum
gefunden wurde; `proposed_span` trägt dann den Wortlaut des Modells. Auf exakt
zitierten Claims sind beide leer. Damit ist die Forderung aus 3s erfüllt:
ersetzen, aber protokollieren — **der Originalbeleg bleibt erhalten.** Der Zustand
steigt nicht: ein Zeilenumbruch ist kein Fall für einen Menschen.

Beide Dossier-Schemata gehen auf 0.3, das Paketschema bleibt bei 0.2. Knoten-Ids
wandern; gespeicherte Dossiers werden nicht migriert. Die eingefrorenen
Kontrollen behalten ihre Zahlen.

`gate_counterfactual.py` ist entfernt: Es hat gemessen, was ein toleranter Anker
erreichen würde, und der Anker ist jetzt tolerant. Und `relaxed_span` im
Reparaturlauf ist ein dünner Wrapper über `anchor_spans`, damit es die
Leerraum-Suche nur einmal gibt.

## 3ac. Der Plan, der aus 3z folgt

3z hat die Identitätsfrage zurückgestellt, weil ihr ein Begriff fehlt:
**vergleichbare Lesart.** Ohne ihn ist jede Umformulierung eine neue Lesart, jeder
Konflikt-Marker Rauschen und jede Häufigkeitsverteilung über Lesarten eine
Verteilung über Zeichenketten. Dieselbe Lücke macht die Entropie- und
Divergenz-Maschinerie aus dem Working Paper unbrauchbar (siehe 3y).

Die Reihenfolge, in der das aufgelöst wird, steht hier, damit sie nicht nur in
einem Chat existiert.

**1. Die Leerraum-Reparatur allein übernehmen.** Erledigt, 3z: nachgewiesener
Fehler, Originalbeleg erhalten, kein Kollaps.

**2. Einen kleinen semantischen Prüfbestand bauen.** 20 bis 30 kurze, von Hand
eindeutig annotierte Beispiele, gezielt auf die Stellen, an denen Bedeutung
verlorengeht und die kein externer Korpus annotiert:

- Negation: „wirkt" gegen „wirkt nicht".
- Modalität: „verursacht" gegen „könnte verursachen".
- Korrelation gegen Kausalität.
- Bedingungen und Geltungsbereich.
- Sprecher: Behauptung der Regierung gegen Feststellung des Gerichts.
- Mehrere Aussagen innerhalb derselben Textstelle.

Je Beispiel wird festgehalten, **welche Bedeutung erhalten bleiben muss** und
**welche Lesarten der Text zulässt**. Geprüft wird die korrekte Wiedergabe der
Quelle — die Aussagen der Quelle können selbst falsch sein, und das ist nicht
Gegenstand der Messung.

**3. Drei Ergebnisse getrennt messen**, statt einer Zahl:

- Quellenverankerung (hat der Claim die richtige Stelle?),
- Bedeutungsübertragung (ist die Aussage erhalten?),
- Beziehungen zwischen Claims (sind die Kanten richtig?).

Der Grund für die Trennung steht in diesem Dokument mehrfach: Bisher kann eine
Änderung besser aussehen, weil sie *mehr Text erfasst*, ohne bessere semantische
Struktur zu erzeugen. Die Abdeckungsmessungen bleiben daneben nützlich.

**4. Erst darauf die empirische Projektion.** Wiederholte Extraktionen zeigen
dann, welche *vergleichbaren* Lesarten mit welcher Häufigkeit entstehen; gegen die
Annotationen wird geprüft, ob diese Häufigkeiten informativ sind. Erst dann haben
Entropie und Divergenz einen belastbaren Gegenstand, und erst dann ist
entscheidbar, wie die zweite Ebene der Identität aus 3z aussehen muss.

**Eine Gefahr, die zum Plan gehört.** Schreibe ich die Beispiele, schreibe ich die
Gold-Annotationen, und ist das geprüfte System aus derselben Modellfamilie, dann
erbt der Prüfbestand meine blinden Flecken — genau die Zirkularität, gegen die
dieses Repo gebaut ist. Die Gegenmaßnahme ist, dass die Prüfungen **mechanisch**
sein müssen: nicht „bedeutet der Claim dasselbe?", von einem Modell beurteilt,
sondern deklarierte, deterministisch prüfbare Anforderungen je Beispiel.

## 3ad. Der semantische Prüfbestand: Entwurf, noch nicht begutachtet

Schritt 2 aus 3ac ist gebaut:
`src/budget_review/fixtures/semantic_cases/cases.json`, 24 Fälle, zwölf
Bedeutungen in Deutsch und Englisch, über sechs Phänomene — Negation, Modalität,
Korrelation gegen Kausalität, Bedingung und Geltungsbereich, Sprecher, mehrere
Aussagen in einer Stelle.

**Warum es den Bestand überhaupt gibt.** Jeder Korpus, gegen den dieses Projekt
gemessen hat, annotiert, *wo* eine Argumenteinheit sitzt. Keiner annotiert, ob
der Claim, der sie zitiert, noch dasselbe bedeutet. Ein Claim kann perfekt
verankert sein und die Negation verlieren, aus „könnte" ein „senkt" machen oder
aus einer Korrelation eine Ursache — und der Span-Recall zählt das als Treffer.
Das ist die Lücke, die 3ac benannt hat und ohne die auch die Identitätsfrage aus
3z nicht entscheidbar ist.

**Die Prüfungen sind mechanisch, und das ist die Bedingung.** Keine Bedingung
fragt ein Modell, ob zwei Sätze dasselbe bedeuten — dann wären das geprüfte
System und sein Prüfer aus derselben Familie. Stattdessen Token-Gruppen und
Regexe. Sie sind absichtlich grob: Sie fangen den groben Fehler — eine Negation,
die einfach fehlt, eine erfundene Ursache — und sie fangen feine Verschiebung
nicht. Eine Prüfung, über die man nicht streiten kann, ist hier mehr wert als
eine, die öfter recht hat.

Geprüft wird **die treue Wiedergabe der Quelle.** Die Quellen sagen Dinge, die
falsch sein können; das ist nicht Gegenstand der Messung.

### Fünf Invarianten, und wofür die letzten zwei da sind

1. Jede Spanne kommt in ihrem Dokument genau einmal vor.
2. Jede Bedingungsgruppe hat mindestens eine ihrer Wendungen **in der Spanne
   selbst** — ein Fall kann also kein Wort verlangen, das die Quelle nicht
   enthält.
3. Kein Verbot trifft die Spanne — ein Fall kann also nicht den Wortlaut der
   Quelle verbieten.
4. Jedes Paar trägt beide Sprachen, dasselbe Phänomen, dieselbe Zahl von Gruppen
   und dieselbe Claim-Zahl. Sprache ist damit eine Variable und kein Störfaktor.
5. Jede aufgeführte **zulässige** Lesart erfüllt die Bedingungen, und jede
   **verbotene** verletzt mindestens eine.

Die fünfte ist die wichtigste: Ein Fall, dessen eigener ausgeschriebener
Fehlerfall seine eigenen Prüfungen passiert, misst nichts. Sie läuft über alle
achtzehn Einzel-Claim-Fälle; für die sechs Fälle mit `min_claims_on_span ≥ 2` ist
sie abgeschaltet, weil ihr Fehlerfall „nur ein Claim" lautet und keine
Inhaltsprüfung ist. Für diese sechs ist also **nicht maschinell belegt**, dass
ihre verbotene Lesart durchfällt, und das steht als Schwäche im Review-Auftrag.

Sechs Mutationen auf dem Validator, darunter die drei, die ihn nutzlos machen
würden: eine Gruppe genügt statt aller, ein Wortverbot feuert innerhalb eines
anderen Wortes, und eine verbotene Lesart, die alles passiert, wird nicht mehr
gemeldet.

### Der Status ist Entwurf, und das ist kein Formalismus

Beispiele, Gold und Bedingungen sind **von einem Modell geschrieben** — aus
derselben Familie, die am Ende geprüft wird. Ohne unabhängige Durchsicht messen
wir, ob das System die Lesart eines Modells teilt. Der Auftrag für zwei
Durchsichten, die Fragen, die zu stellen sind, und die Stellen, die ich selbst
für die schwächsten halte, stehen in
[`semantic-cases-review.md`](semantic-cases-review.md), zusammen mit der Regel,
die den Beraterrollen Sinn gibt: **Uneinigkeit ist ein Filter auf Beispiele,
keine Abstimmung über Bedeutung.** Wer sich nicht einig ist, was ein Satz
bedeutet, streicht das Beispiel.

Dort steht auch die Governance-Regel für Erweiterungen: eine Token-Gruppe zu
erweitern, nachdem ein Lauf daran gescheitert ist, ist Anpassung des Tests an das
System — erlaubt nur mit Zustimmung einer Durchsicht und mit Vermerk. Auf diesem
Branch haben wandernde Marken schon zweimal Befunde entwertet.

### Was noch nicht da ist

Der Bestand validiert sich selbst, er **bewertet noch nichts.** Die drei
getrennten Ergebnisse aus 3ac — Quellenverankerung, Bedeutungsübertragung,
Beziehungen zwischen Claims — sind Schritt 3 und setzen voraus, dass das Gold
begutachtet ist. Ein Scorer vor der Durchsicht würde Zahlen gegen eine
unbestätigte Annotation produzieren, und solche Zahlen stehen in 3u bis 3ab schon
genug herum.

## 3ae. Die drei Ergebnisse: die Vorab-Festlegung

Schritt 3 aus 3ac. `semantic_score.py` bewertet den Bestand aus 3ad auf getrennten
Achsen, und die Trennung ist der Zweck: Bisher kann eine Änderung besser aussehen,
weil sie **mehr Text erfasst**, ohne bessere Struktur zu erzeugen.

| Achse | Frage |
|---|---|
| Verankerung | Berührt irgendein zugelassener Claim die annotierte Stelle? |
| Bedeutung | Halten die deklarierten Bedingungen, und verletzt kein Claim ein Verbot? |
| Beziehungen | Sind die Kanten zwischen Claims richtig? |

**Die dritte Achse ist auf diesem Bestand nicht messbar**, und das ist ein Mangel
des Bestands, nicht des Skripts: Die Fälle halten fest, welche Bedeutung erhalten
bleiben muss, und sagen nichts darüber, welche Kanten entstehen sollen.
Aufgefallen beim Implementieren. Sie wird als *nicht gemessen* berichtet und nicht
still weggelassen; die Annotation nachzuziehen gehört in die Durchsichtsrunde.

### Was dieser erste Lauf ist, und was er nicht ist

Der Bestand ist ein Entwurf, von einem Modell geschrieben und **nicht
begutachtet** (3ad). Diese Zahlen sind deshalb **kein Urteil über den Extraktor.**
Sie prüfen zwei andere Dinge, und das ist vorab festgelegt, damit es hinterher
nicht umdeutbar ist:

**1. Der Apparat funktioniert**, wenn jeder Fall ein Dossier liefert und in
mindestens 90 Prozent der Fälle wenigstens ein Claim auf der Spanne ankert. Das
sind Dokumente von einem bis drei Sätzen; scheitert die Verankerung breit, liegt
es am Apparat oder an der Dokumentgröße, und über Bedeutung ist dann nichts zu
lesen.

**2. Mein Gold ist falsch**, wo ein Fall in *allen* Wiederholungen scheitert und
der Claim-Text gelesen eine **treue** Wiedergabe ist. Dazu eine benannte
Vorhersage, die dieser Lauf bestätigen oder widerlegen kann: Ich halte `neg-02`
(„Nicht alle Schulen…") und `mod-02` (verlangt `zeigt/belegt/…`) für eingebaute
Falschalarme. Scheitern sie mit treuem Text, ist die Vorhersage bestätigt und die
beiden Fälle werden umgeschrieben. Passieren sie, war ich falsch.

**3. Der Extraktor verzerrt**, wo ein Fall mit Text scheitert, der tatsächlich
untreu ist — Negation weg, Ursache erfunden. Gezählt je Phänomen.

Der Unterschied zwischen 2 und 3 ist eine **Lesung von Hand** und keine
Maschinenentscheidung. Das ist die Grenze dieses Laufs und steht hier, weil sie
sonst später als Zahl missverstanden wird.

### Zwei Regeln, die nicht verhandelbar sind

**Keine Token-Gruppe wird in diesem Lauf erweitert.** Eine Bedingung, die auf
einem treuen Claim feuert, ist ein Mangel des Falls — behoben über den
Review-Auftrag mit Datum und Urheber, nie dadurch, dass die Liste so weit wächst,
bis der Lauf durchläuft. Wandernde Marken haben auf diesem Branch zweimal Befunde
entwertet.

**Der Bestand validiert sich vor jeder Messung selbst.** Verletzt er eine der
fünf Invarianten aus 3ad, bricht das Skript ab und bewertet nichts.

### Nebenbei die erste Live-Prüfung des neuen Gates

#18 ist auf main und wurde **nie live gelaufen** — verifiziert war es gegen
gespeicherte Pakete. Diese 24 Dokumente sind von Hand als einzeilige Sätze
geschrieben, also ist `anchor_normalised` über alle Läufe **erwartet 0**. Jeder
andere Wert ist eine Überraschung und wird nachgesehen.

24 Fälle, drei Wiederholungen, 72 bezahlte Aufrufe auf Dokumenten von rund 120
Zeichen.

## 3af. Erster Lauf auf dem Bedeutungsbestand: der Apparat läuft, mein Gold war falsch, und eine Bedingung bricht

24 Fälle, drei Wiederholungen, 72 bezahlte Aufrufe, 248 zugelassene Claims.

### 1. Der Apparat funktioniert

**24 von 24 Fällen ankerten in allen drei Läufen** einen Claim auf ihrer Spanne —
100 Prozent gegen eine Vorab-Marke von 90. Kein Lauf ist abgebrochen, keine
Prüfung ist gescheitert.

Und die Nebenprüfung aus 3ae: **`anchor_normalised` ist 0 über alle 248 Claims**,
wie vorhergesagt. Das war die erste Live-Ausübung des Gates aus #18, das bis
dahin nur gegen gespeicherte Pakete verifiziert war. Es verhält sich wie gebaut.

### 2. Meine Vorhersage war falsch — und mein Gold hat einen anderen Mangel

3ae hat benannt, was dieser Lauf an mir prüfen sollte: Ich hielt `neg-02` und
`mod-02` für eingebaute Falschalarme. **Beide haben 3/3 in beiden Sprachen
bestanden.** Die Vorhersage ist widerlegt.

Was ich nicht vorhergesehen habe, ist der tatsächliche Mangel: **Der Bestand
verwechselt Sprache mit Bedeutung.**

| Quelle | Claims | in der Sprache der Quelle | übersetzt |
|---|---:|---:|---:|
| Deutsch | 122 | 83 | **38 (31 %)** |
| Englisch | 126 | 117 | **0** |

Weil meine Bedingungen deutsche Token verlangen, scheitert eine **treue**
englische Wiedergabe an der Bedeutungsprüfung. Fünf der zwölf deutschen Fälle
sind betroffen, und die Claims sind tadellos:

| Fall | Ergebnis | Claim |
|---|---|---|
| `sco-01-de` | 0/3 | „In rural areas the program lowers the rate." — Geltungsbereich vollständig erhalten |
| `spk-02-de` | 0/3 | zwei getrennte Sprechakte, beide Sprecher benannt: „The government argued…" / „The court found…" |
| `mul-01-de` | 1/3 | beide Aussagen korrekt getrennt, auf Englisch |
| `cor-01-de` | 2/3 | „Participation correlates with higher completion rates." |

**Und ein dritter Mangel, aufgefallen beim Klassifizieren:** `spk-01-de` hat nur
*zufällig* bestanden. Ich hatte seine Bedingungsgruppe als
`["Regierung", "Government"]` geschrieben — dieser eine Fall toleriert die
Übersetzung, die anderen elf nicht. Meine Bedingungsgruppen waren unbeabsichtigt
unterschiedlich sprachtolerant, und damit waren die deutschen Fälle nicht einmal
untereinander konsistent.

### 3. Der Produktbefund, und er ist der wichtigere

**Die semantische Schicht übersetzt deutsche Dokumente still ins Englische.** Der
`raw_span` zitiert die deutsche Quelle, `canonical_content` ist englisch. Das
README sagt, zitierte Claims behielten ihren ursprünglichen Wortlaut — das gilt
für die Spanne und nicht für die Proposition. Keine Messung dieses Projekts hat
je auf die *Sprache* von `canonical_content` gesehen.

Es ist zudem genau das „language-dependent artifact", das das eigene Working
Paper 2 als einen von drei Gründen für eine Projektionsschicht nennt: *the same
content expressed in different languages yields different claim structures.*

Die Richtung ist einseitig: 38 deutsche Claims wurden englisch, kein englischer
wurde deutsch.

### 4. Der eine echte Bedeutungsfehler: die Bedingung bricht

Nach Abzug des Sprachenffekts bleiben **4 von 72 Fall-Läufen**, und sie liegen
alle auf demselben Phänomen.

`sco-02`, Quelle: „Wenn die Mittel bewilligt werden, beginnt der Ausbau im
Frühjahr."

| | Claims |
|---|---|
| englisch, 3 von 3 Läufen | „The funds will be granted." + „Construction begins in spring." |
| deutsch, 1 von 3 Läufen | „Die Mittel werden bewilligt." + „Der Ausbau beginnt im Frühjahr." |

**Die Bedingung wird zerlegt und verschwindet.** Übrig bleiben zwei unbedingte
Behauptungen, und eine davon — die Mittel *werden* bewilligt — behauptet etwas,
was die Quelle ausdrücklich nicht behauptet. Für eine Antragsprüfung ist das die
Fehlerklasse, für deren Entdeckung das Produkt existiert, erzeugt vom Produkt.

Damit lautet der Befund dieses Laufs: **Bedeutung überlebt überall außer bei der
Bedingung; jeder andere Fehlschlag war der Sprachwechsel.**

| Phänomen | erhalten | davon Fehlschläge durch Übersetzung |
|---|---|---|
| Negation | 12/12 | — |
| Modalität | 12/12 | — |
| Korrelation gegen Kausalität | 11/12 | 1 von 1 |
| Sprecher | 9/12 | 3 von 3 |
| mehrere Aussagen | 10/12 | 2 von 2 |
| Geltungsbereich | 3/6 | 3 von 3 |
| **Bedingung** | **2/6** | **0 von 4** |

### 5. Was nicht gemessen ist, und was ich nicht geändert habe

**Relationen:** weiter nicht messbar, der Bestand annotiert keine Kanten (3ae).

**Keine Token-Gruppe wurde erweitert.** Die Regel aus 3ad gilt: Eine Bedingung,
die auf einem treuen Claim feuert, ist ein Mangel des Falls, behoben über den
Review-Auftrag mit Datum — nicht dadurch, dass die Liste wächst, bis der Lauf
durchläuft. Die drei Gold-Mängel sind dort als Einträge vermerkt und warten auf
die Durchsicht.

**Die Sprachachse ist eine neue Messung, keine Lockerung.** Sie wurde offline aus
den 72 gespeicherten Dossiers gerechnet, ohne einen weiteren Aufruf, und wird
jetzt vom Scorer getrennt berichtet. Vier Mutationen darauf, darunter die beiden,
die sie nutzlos machen würden: ein unentscheidbarer Claim bekommt doch eine
Sprache zugewiesen, und die Achse besteht immer.

Dass die Achse überhaupt nötig ist, ist der Beleg für das Prinzip aus 3ac: Hätte
ich Verankerung, Sprache und Bedeutung nicht getrennt, stünde hier „der Extraktor
verliert bei Geltungsbereich und Sprecher die Hälfte der Bedeutung" — und das
wäre falsch.

## 3ag. Ist die verborgene Projektion steuerbar? Die Vorab-Festlegung

3af hat gemessen, dass 38 von 122 Claims aus deutschen Quellen auf Englisch
zurückkamen und 0 von 126 aus englischen Quellen auf Deutsch. Dazu gehören zwei
Erklärungen, und sie widersprechen sich nicht.

**Die banale.** Der Extraktionsvertrag erwähnte Sprache **überhaupt nicht.** Der
Reviewer-Vertrag trägt seit immer `_REVIEWER_LANGUAGE` („clear German" / „clear
English") und einen `language`-Parameter; die Extraktionsprompt hatte beides
nicht, ist selbst durchgehend englisch und ihr Beispielwert lautet
`"One atomic proposition."`. Das erklärt Richtung und Rate des Drifts — und es
macht die Sprachwahl des Produkts inkonsistent: `--language de` steuert Labels,
deterministische Regeln und beide Reviewer-Arme, aber nicht die Propositionen.

**Die tiefere.** Ein reiner Extraktor *kann* nicht übersetzen. Um einen deutschen
Satz als treue englische Proposition zu schreiben, muss das Modell Subjekt,
Prädikat, Geltungsbereich und Polarität bereits sprachunabhängig repräsentiert
haben und dann neu verbalisieren. **Die semantische Projektion findet also statt;
sie wird nur nicht als Artefakt behalten.**

Das erklärt rückblickend den Befund aus 3y, den ich dort als Tatsache berichtet
und nicht begründet habe: `raw_span` ist eine **Auswahl** — ein Index ins
Dokument — und deshalb reproduzierbar; `canonical_content` ist eine **Erzeugung**
und deshalb die instabile Hälfte. Der Sprachwechsel ist der Beleg, denn dieselbe
Erzeugung lief in einer anderen Sprache.

Working Paper 2 fordert „no direct text-to-claim" als Regel. Gemessen ist, dass
es ohnehin keinen direkten Weg gibt: Text → verborgene Projektion → Claim, und
behalten wird nur der letzte Pfeil.

### Die Änderung, und warum sie klein ist

**Eine Anforderung im Extraktionsvertrag**, direkt neben der Regel für wörtliche
Spannen, weil sie zur selben Familie gehört: `canonical_content` in der Sprache
des Dokuments, nicht übersetzt, mit dem Grund — ein Claim muss gegen seine
Spanne prüfbar sein.

Die Sprache wird **nicht als Parameter übergeben.** Sie ist eine Eigenschaft des
Dokuments und nicht der Aufrufer-Oberfläche: Ein deutsches Dokument mit
`--language en` geprüft braucht weiterhin deutsche Propositionen, weil die
Spanne, gegen die sie zu prüfen sind, deutsch ist. Alles andere am Vertrag ist
byte-identisch.

Dass die Änderung klein ist, ist Absicht. Jede strukturelle Änderung dieses
Projekts — Segmentierung, Doppellauf, Zweistufigkeit, Thin-Targeting — ist
gescheitert oder unlesbar geblieben; die eine, die wirkte, war klein und
mechanisch.

### Die Regel, vorab

Derselbe Bestand, drei Wiederholungen, dasselbe Profil, derselbe Scorer,
dieselben 24 Fälle **ohne eine geänderte Token-Gruppe.**

- **Steuerbar**, wenn übersetzte Claims aus deutschen Quellen auf **≤ 5** fallen
  (Basis 38 von 122). Dann ist die verborgene Projektion durch eine Anweisung
  kontrollierbar, und für das Sprachproblem braucht es keine explizite
  Projektionsschicht.
- **Nicht steuerbar** bei **> 15**. Dann greift eine Anweisung nicht an das, was
  die Schicht tut, und das ist das stärkste Argument für explizite
  Projektionsfelder.
- Dazwischen: Teileffekt, die Anweisung hilft und entscheidet nichts.
- **Englisch darf nicht regredieren:** 0 von 126 übersetzten bleibt 0.

**Schutzbedingung, die die Änderung zurücknimmt:** Bedeutung darf nicht
regredieren. Negation und Modalität stehen bei 12/12; fallen sie, hat die
Anweisung Sprache auf Kosten von Bedeutung gekauft, und sie wird rückgängig
gemacht.

### Der saubere Nebeneffekt, auf den ich setze

Vier deutsche Fälle — `sco-01-de`, `spk-02-de`, `mul-01-de`, `cor-01-de` — sind in
3af **ausschließlich an der Sprache** gescheitert; ihre Claims waren inhaltlich
tadellos. Antwortet das Modell jetzt auf Deutsch, erfüllen sie ihre
**bestehenden, unveränderten** Bedingungen.

Dann ist **M-1 ohne eine Gold-Änderung gelöst**, und die Frage aus dem
Review-Auftrag — ob eine zweisprachige Bedingung Schärfe verliert — stellt sich
nicht mehr. Bestehen sie die Sprachachse und scheitern weiter an den Token, sind
meine deutschen Listen wirklich zu eng und M-1 braucht die Durchsicht doch.

### Was diese Änderung nicht anfasst

Die **Bedingung.** `sco-02` verliert in 3/3 englischen Läufen das „wenn" und
behauptet, die Mittel *würden* bewilligt. Davon ist keine Sprachanweisung
betroffen, und wenn sie es doch wäre, wäre das eine Überraschung, die gegen die
Notwendigkeit expliziter Felder spricht. Berichtet wird es ohne Marke.

## 3ah. Die verborgene Projektion ist steuerbar — und übrig bleibt genau die Bedingung

Derselbe Bestand, dieselben 72 bezahlten Aufrufe, dasselbe Profil. Geändert sind
**drei Zeilen im Extraktionsvertrag** und sonst nichts: `cases.json` und der
Scorer sind zwischen beiden Läufen byte-identisch, und `meaning_preserved` ist
unverändert definiert. Der Vergleich hat eine Variable.

### 1. Die Vorab-Regel, beantwortet

| | 3af | dieser Lauf | Schwelle aus 3ag |
|---|---:|---:|---|
| übersetzte Claims, deutsche Quelle | 38 von 122 | **0 von 123** | ≤ 5 ⇒ steuerbar |
| übersetzte Claims, englische Quelle | 0 von 126 | 0 von 119 | muss 0 bleiben |
| Negation | 12/12 | 12/12 | Schutzbedingung |
| Modalität | 12/12 | 12/12 | Schutzbedingung |

**Steuerbar.** Der Effekt ist vollständig, nicht teilweise: nicht ein einziger
Claim aus einer deutschen Quelle kam übersetzt zurück. Die Schutzbedingung hält,
die Änderung bleibt. Für das Sprachproblem braucht es **keine** explizite
Projektionsschicht.

Die Ausbeute ist dabei nicht gefallen — 242 zugelassene Claims gegen 248. Die
Anweisung hat die Übersetzung abgeschaltet und nicht die Extraktion.

**Was die Zahl 0 nicht verdeckt.** 11 der 242 Claims klassifiziert die
Sprachachse als unentscheidbar (3af: 10 von 248), und unentscheidbar zählt nicht
als übersetzt — die 0 könnte also eine Schönung sein. Ist sie nicht: alle elf sind
von Hand geprüft und stehen in der Sprache ihrer Quelle. Ihr Mechanismus ist
mechanisch und kein Rauschen: Sätze wie „Construction began in spring." enthalten
nur Marker, die in **beiden** Listen stehen (`in`), also 1 zu 1, also „?".

### 2. Der Nebeneffekt, auf den ich gesetzt habe, ist eingetreten

Alle vier Fälle, die in 3af **ausschließlich an der Sprache** gescheitert sind,
bestehen jetzt ihre **bestehenden, unveränderten** Bedingungen:
`sco-01-de` 0/3 → 3/3, `spk-02-de` 0/3 → 3/3, `mul-01-de` 1/3 → 3/3,
`cor-01-de` 2/3 → 3/3.

**M-1 ist damit ohne eine Gold-Änderung gelöst.** Die offene Frage aus dem
Review-Auftrag — ob eine zweisprachige Bedingung Schärfe verliert — stellt sich
nicht mehr, weil keine zweisprachige Bedingung gebraucht wird. Meine deutschen
Token-Listen waren nicht zu eng; das Modell antwortete in der falschen Sprache.
M-2 (`spk-01-de` war versehentlich sprachtolerant) bleibt als Inkonsistenz
bestehen und ist jetzt wirkungslos, weil kein Fall mehr Toleranz braucht.

### 3. Bedeutung nach Phänomen: ein Phänomen bleibt

| Phänomen | 3af | dieser Lauf |
|---|---:|---:|
| Negation | 12/12 | 12/12 |
| Modalität | 12/12 | 12/12 |
| Korrelation gegen Kausalität | 11/12 | 12/12 |
| Sprecher | 9/12 | 12/12 |
| mehrere Aussagen | 10/12 | 12/12 |
| Geltungsbereich | 3/6 | 6/6 |
| **Bedingung** | **2/6** | **3/6** |
| **Summe** | **59/72** | **69/72** |

Verankerung unverändert bei 24/24 in allen drei Läufen, `anchor_normalised` 0
über alle Claims, 0 Verzerrungen, kein fehlgeschlagener Aufruf.

**Die Bedingung ist nicht besser geworden.** 2/6 gegen 3/6 ist auf sechs
Versuchen nichts, und ich berichte es als unverändert. 3ag hat vorhergesagt, dass
die Sprachanweisung die Bedingung nicht anfasst; das ist eingetreten.

### 4. Was der Lauf über die Bedingung genauer sagt

3af hat den Befund als „die Bedingung wird zerlegt und verschwindet" berichtet.
Die sechs Läufe dieses Durchgangs zeigen die Struktur schärfer, und meine
Formulierung in 3af war in einem Detail falsch — dort steht „The funds will be
granted", tatsächlich lautet der Claim „The funds are granted".

| Lauf | Claim auf der Spanne | Bedingung |
|---|---|---|
| de-1 | `assumption` „Die Mittel werden bewilligt." + `forecast` „Der Ausbau beginnt im Frühjahr." | verloren |
| de-2, de-3 | `forecast` „Wenn die Mittel bewilligt werden, beginnt der Ausbau im Frühjahr." + `assumption` „Die Mittel werden bewilligt." | erhalten |
| en-1, en-2 | `assumption` „The funds are granted." + `forecast` „Construction begins in spring." | verloren |
| en-3 | `forecast` „If the funds are granted, construction begins in spring." | erhalten |

Der Fehler ist **nicht**, dass die Bedingung fehlt. Er ist, dass der Extraktor
den Satz **am Komma zerlegt**: der Vordersatz wird ein eigener Claim, der
Nachsatz wird ein eigener Claim, und der Nachsatz steht dann **unbedingt** da.
Die Bedingung lebt in den drei bestehenden Läufen in *einem* Claim weiter, der
den ganzen Satz trägt.

Dass der Vordersatz als `assumption` getypt wird, hielt ich hier für die
*vertretbare* Hälfte: „Die Mittel werden bewilligt" als Annahme des Nachsatzes zu
führen ist eine zulässige Lesart der Quelle.

> **Korrektur (3ai).** Das trägt nicht. Der Extraktionsvertrag definiert keinen
> der 21 Claim-Typen, und in Lauf 3 von `sco-02-en` existiert diese Typung
> überhaupt nicht — die Typmenge dieses Falls wechselt über die drei identischen
> Läufe. Ich habe einem Münzwurf semantischen Gehalt zugeschrieben. Eine Lesart,
> keine Messung, also keine Rücknahme eines Befunds; aber sie hat den Fehler als
> halb-vertretbar erscheinen lassen, und das war unbegründet.

Die unvertretbare Hälfte ist der `forecast`, der ohne jede Annahme behauptet, der
Ausbau beginne im Frühjahr. Für eine Antragsprüfung ist das eine erfundene
Zusage, und sie steht unabhängig von jeder Typung.

**Und eine Prüfung meines Golds, die diesmal aufgeht.** `requires_all_groups`
besteht, sobald *irgendein* Claim auf der Spanne einen Bedingungsmarker trägt —
es sieht nicht, ob daneben die verbotene Lesart steht. Nachgerechnet: die
verbotene Lesart („Der Ausbau beginnt im Frühjahr.") erscheint in genau den drei
Läufen, die scheitern, und in keinem, der besteht. Beide Signale stimmen 6 von 6
überein, der Fall misst hier also das Richtige. Die **Lücke bleibt latent**: ein
Lauf, der die Bedingung *und* den unbedingten Nachsatz liefert, würde bestehen.
In diesem Lauf ist das nicht vorgekommen; als Mangel M-4 im Review-Auftrag
notiert, nicht als Messergebnis.

### 5. Was das für die Projektionsschicht heißt

Die Frage aus 3ag war die Entscheidungsfrage vor Option C (explizite Felder für
Subjekt, Relation, Objekt, Modalität, Geltungsbereich, Sprecher). Die Antwort
teilt sie in zwei:

- **Sprache: erledigt, und zwar durch eine Anweisung.** Die verborgene Projektion
  existiert und ist steuerbar. Die Beobachtung, die den Anstoß gab — „Das
  Übersetzen allein benötigt eigentlich eine semantische Schicht" — ist bestätigt
  und *gleichzeitig* entschärft: die Schicht ist da, und man muss sie nicht
  materialisieren, um ihr zu sagen, in welcher Sprache sie ausgeben soll.
- **Bedingung: offen, und jetzt der einzige gemessene Bedeutungsfehler im
  Bestand.** Eine Sprachanweisung hat ihn nicht berührt. Er ist genau die
  Fehlerklasse, für die explizite Felder gebaut würden: Modalität und
  Geltungsbereich eines Claims getrennt zu führen, statt sie dem Satzbau einer
  Proposition zu überlassen.

Das ist ein besser gestellter Gegenstand als vorher. Vorher stand Option C gegen
„die semantische Schicht ist unzuverlässig"; jetzt steht sie gegen ein einzelnes,
reproduzierbares, auf drei von sechs Läufen auftretendes Strukturversagen an
einer benannten Konstruktion. Ob ein Feld oder — wie bei jeder kleinen Änderung
dieses Projekts, die gewirkt hat — eine Vertragszeile reicht, ist die nächste
Vorab-Frage und nicht hier entschieden.

### 6. Was weiter nicht gemessen ist

**Relationen:** weiter nicht messbar, der Bestand annotiert keine Kanten (3ae).
Der Sprachbefund hat daran nichts geändert.

**Zwei unabhängige Durchsichten des Bestands fehlen weiter.** Zwei der vier
Gold-Mängel sind durch diesen Lauf erledigt oder wirkungslos, einer ist neu
(M-4), und keiner davon ersetzt die Durchsicht. Der Bestand bleibt ein Entwurf.

**Ein Dokument pro Fall, ein bis drei Sätze.** Dass eine Vertragszeile auf
24 kurzen Sätzen greift, sagt nichts darüber, ob sie auf 26.000 Zeichen
Gerichtstext greift. Die nächste Messung der Sprachachse gehört auf ein langes
Dokument und kostet dort nichts extra, weil sie offline aus gespeicherten
Dossiers läuft.

## 3ai. Der Claim-Typ ist die dritte instabile Hälfte — und zwei ausgelieferte Befunde hängen daran

Anlass war ein fremdes Paper ([arXiv 2610.02586](https://arxiv.org/abs/2610.02586),
1. Okt. 2026): Wo ein kurzer Optionsname neben einer ausgeschriebenen Definition
steht, entscheidet der **Name**, nicht die Definition. Definitionen zu entfernen
änderte die Genauigkeit kaum; Optionen auf A und B umzubenennen hob sie um etwa
0,15. Eine Konfidenzschwelle fängt das nicht.

Die Übertragung war schnell erledigt, weil sie keine ist. Der Blick in den
eigenen Vertrag:

| | im Extraktionsvertrag |
|---|---|
| `claim_type` | **21 Namen, null Definitionen** |
| `relation_type` | 14 Namen, 7 mit Richtungsglosse, plus ein ausdrückliches Verbot |

**Wir sind der Grenzfall.** Es gibt keine Definition, die ein Label überstimmen
könnte; das Label *ist* die ganze Spezifikation. Und `claim_type` ist nicht
dekorativ: er steckt im Node-Id-Hash (`gate.py`), also ist ein anderer Typ ein
anderer Knoten und jede Kante dorthin wandert mit; und zwei ausgelieferte
deterministische Befunde feuern auf ihm — `logical_gap` mit Konfidenz **0,9**,
`unsupported_assumption` mit **0,95**.

### Die Messung, und sie hat nichts gekostet

3y hat die zwei Hälften eines Claims getrennt: `raw_span` ist eine **Auswahl**
ins Dokument und reproduzierbar, `canonical_content` eine **Erzeugung** und die
instabile Hälfte. Der Typ ist ebenfalls eine Erzeugung, und **nie hat etwas ihn
gemessen.** Also offline aus den 72 bereits bezahlten Dossiers von 3ah,
`scripts/claim_type_stability.py`:

| | |
|---|---|
| Dokumente mit drei byte-identischen Läufen | 24 |
| davon mit **wechselnder Typmenge** | **8** |
| `unsupported_assumption`: Typ-Vorbedingung wechselt | **1 von 24** (`sco-02-en`) |
| `logical_gap`: Typ-Vorbedingung wechselt | 0 von 24 |

```
mod-01-de   delivery,fact,forecast   | delivery,forecast,target | delivery,forecast,target
neg-02-de   fact,fact,forecast       | fact,fact,forecast       | fact,forecast,scope
neg-02-en   fact,forecast,scope      | fact,fact,forecast       | fact,fact,forecast
sco-01-de   fact,limitation,scope    | causal,limitation,scope  | causal,limitation,scope
sco-02-en   assumption,causal,...    | assumption,causal,...    | causal,fact,forecast
```

`neg-02` wechselt zwischen `fact` und `scope` — in **beiden** Sprachen und in
umgekehrter Lauf-Position, also ein Münzwurf zwischen zwei Namen und kein
Sprachartefakt. `sco-01-de` wechselt zwischen `fact` und `causal`, wobei `causal`
in `cor-01` ausdrücklich als **Verzerrungsmarker verboten** ist: dasselbe
Vokabelwort ist in einem Fall ein Fehler und im anderen eine freie Variante.

**Und die Konfidenz fängt es nicht** — das ist der Detektionsbefund des Papers,
bei uns schärfer. 0,934 gegen 0,931 für die stabilen Fälle, also keine Trennung;
und das Feld ist entartet, 233 von 242 Claims stehen auf exakt 0,9 oder 0,95.
„Auf Konfidenz filtern" war nie eine Option, und wer es vorschlägt, hat die
Verteilung nicht gesehen.

### Die präzise Formulierung, denn die naheliegende wäre falsch

Nicht „der Extraktor ist instabil". Für „Nicht alle Schulen erhalten den
Zuschlag." sind `fact` und `scope` beide vertretbar, und **ohne Definitionen gibt
es keine Tatsache darüber, welcher richtig ist.** Der Befund lautet: **das
Vokabular hat keine Wahrheitsbedingungen, und darauf steht ein Befund mit 0,95.**

Das ist auch der Grund, warum die naheliegende Reparatur — Definitionen
nachtragen — nicht die erste Wahl ist: das Paper hat gemessen, dass Definitionen
neben vorhandenen Labels fast nichts ändern. Gewirkt haben *opake* Kennungen.

### Was mich das kostet

3ah hat geschrieben, die Typung des Vordersatzes als `assumption` sei „die
vertretbare Hälfte" des Bedingungsfehlers. In Lauf 3 von `sco-02-en` existiert
diese Typung nicht. **Ich habe einem Münzwurf semantischen Gehalt
zugeschrieben.** Das ist eine Lesart und keine Messung, also keine Rücknahme
eines Befunds — aber ich habe mich darauf gestützt, um den Fehler als
halb-vertretbar zu beschreiben, und das trägt nicht. Die Stelle ist dort
korrigiert.

Rückblickend erklärt es auch 3ab besser, als ich es dort erklärt habe: 16 von 18
ungültigen Relationslabels waren unsere eigenen Claim-Typen im Relationsfeld. Ich
nannte das **Feldverwechslung**. Mit 21 undefinierten und 14 teildefinierten
kurzen Namen in einem Vertrag ist es Auswahl nach Namensähnlichkeit in einem
Namensraum — derselbe Mechanismus, von der anderen Seite. Am Ergebnis ändert das
nichts (die Zweistufigkeit behebt es, 0 von 192), an der Erklärung alles.

### Die Entscheidung, und warum sie (b) ist

Zwei Wege standen offen: **(a)** deterministische Befunde nicht länger auf einen
erzeugten Label stützen, oder **(b)** sie mit der Herkunft ihres Auslösers
ausliefern. Gewählt ist **(b)**, damit ein späterer Reflexionslauf es aufgreifen
kann: Information behalten schlägt Information verwerfen, und (a) bleibt danach
offen, während es umgekehrt nicht gilt.

`Finding.trigger_rests_on` nennt, worauf der Auslöser steht — `document`,
`content`, `relation_type`, `claim_type` — und kommt aus **einer** Tabelle neben
den Regeltexten, nicht aus 14 Aufrufstellen. Damit kann keine Regel ohne
Deklaration dazukommen; ein Test prüft, dass jeder Regelschlüssel in der Tabelle
steht.

**Die Markierung ist konstant nutzlos, wenn sie nicht unterscheidet** — sie tut
es: `coverage_gap` rechnet aus Dokument und Ankern, die Budgetregeln aus dem
Claim-Text, und nur zwei der vierzehn stehen auf dem undefinierten Label.

**Und sie wird gerendert**, in Markdown und HTML, in beiden Sprachen. Der Grund
steht im Code: `anchor_ambiguous` wird vom Gate seit seinem Bau gesetzt und von
**keinem Teil des Produkts gelesen** — nur von einem Messskript. Eine vierte
Flagge dieser Art wäre Dekoration, die wie eine Sicherung aussieht.

**Ohne Zahl.** Die 8 von 24 stammen von Fällen aus einem bis drei Sätzen; sie an
einen Befund auf 26.000 Zeichen Gerichtstext zu hängen wäre geliehene Präzision
— der Fehler, den dieses Repo am häufigsten zurücknimmt. Der Hinweis sagt, dass
der Auslöser ein undefinierter, auf kurzen Belegen nicht wiederholstabiler Typ
ist. Ein Test verbietet eine Ziffer im Hinweistext.

### Nebenbefund, beim Testschreiben aufgefallen

**Die beiden label-getriebenen Regeln laufen nur im `general`-Profil.**
`deterministic_checks` ruft `_check_general_structure` im Budget-Profil nie auf.
Die Exposition ist also profilabhängig, was ich vorher nicht wusste und was die
erste Fassung eines Tests falsch annehmen ließ.

### Was nicht gemessen ist

**`relation_type`.** 14 Namen, 7 mit Glosse, und drei Befunde stehen allein
darauf (`internal_contradiction`, `scope_tension`, `overgeneralization`). Dieselbe
Messung darauf anzuwenden kostet nichts und ist nicht gemacht.

**Lange Dokumente.** 24 Fälle aus einem bis drei Sätzen. Dass `logical_gap` hier
0 von 24 wechselt, sagt über eine Gerichtsentscheidung mit 108 Claims nichts.

**Was das Paper eigentlich vorschlägt.** Die Dreiarm-Probe — sprechende Namen,
opake Kennungen, permutierte Namen — ist hier **nicht** gelaufen, und der
naheliegende Weg wäre falsch gewesen: unser Bedeutungsbestand prüft `claim_type`
in **2 von 24 Fällen** (`cor-01-de/en`). Gegen `meaning_preserved` gemessen hätte
die Permutation 216 bezahlte Aufrufe für eine Achse gekostet, die den Typ fast
nicht sieht. Das richtige Instrument ist Typstabilität, und die läuft gratis.

## 3al. Zwei unabhängige Durchsichten: zwölf von sechzehn Gegenbeispielen bestätigt, vier widerlegt, und drei Löcher in meinem Scorer

Der Bestand war seit #19 ein Entwurf, weil Beispiele, Gold und Bedingungen von
derselben Modellfamilie stammen, die geprüft wird. Zwei blinde Durchsichten sind
am 2026-10-08 gelaufen — `google/gemini-3.1-pro-preview` und `openai/gpt-5.2`,
zusammen **0,16 $**. Wörtlich in `docs/semantic-cases-review-1.md` und `-2.md`.

**Blind heißt: ohne die Mängelliste und ohne eine Zahl aus den beiden Läufen.**
Das Skript schneidet den Auftrag an der Überschrift und verweigert eine Anfrage,
die noch eine Mangel-Id oder Lauf-Zahl enthält.

### Ich habe sie nachgerechnet, statt sie zu übernehmen

Jede „würde durchkommen"-Behauptung ist eine Aussage über *unseren* Validator und
damit mechanisch prüfbar. Alle sechzehn gegen `scripts/semantic_cases.py`:

| Klasse | behauptet | Ergebnis |
|---|---:|---|
| **zu schwach** — untreue Wiedergabe besteht | 5 | **5 bestätigt** |
| **zu eng** — treue Wiedergabe fällt durch | 7 | **7 bestätigt** |
| rutscht durch die `forbids`-Liste | 4 | **4 widerlegt** |

**Die vier Widerlegungen haben eine gemeinsame Ursache, und beide Durchsichten
machen denselben Fehler:** Sie argumentieren allein über `forbids` und übersehen,
dass `requires_all_groups` ebenfalls erfüllt sein muss. „Das Programm senkte die
Abbrecherquote." als einziger Claim fällt nicht am Verbot — `\bsenkt\b` trifft
„senkte" nicht —, sondern daran, dass der Claim kein Modalitäts-Token trägt.
Dasselbe für „will lower" und „trägt dazu bei".

Daraus folgt ausdrücklich **nicht**, die Verbotslisten zu verlängern, wie beide
empfehlen. Die Prämisse ist widerlegt, und nach der Regel aus 3ad wäre es
Anpassung des Tests an eine Lücke, die nicht offen ist.

### Ihre Sorge überlebt aber, und zwar als M-4 in größerem Umfang

Steht die beanstandete Formulierung *neben* einem konformen Claim, ist
`requires_all_groups` erfüllt und das Verbot greift nicht:

| Fall | Claims auf der Spanne | |
|---|---|---|
| `mod-01-de` | „könnte … senken" **+** „senkte die Abbrecherquote" | **besteht** |
| `mod-01-en` | „could lower" **+** „will lower" | **besteht** |
| `cor-01-de` | „korreliert mit" **+** „trägt dazu bei, … zu verbessern" | **besteht** |

Das ist genau M-4, den ich für `sco-02` allein notiert hatte. Es sind mindestens
drei weitere Fälle.

### Und dabei sind drei Löcher in meinem Scorer aufgefallen, nicht eines

Beim Bauen der Gegenprüfung: **`meaning_preserved` hat `distortions` vollständig
ignoriert.**

```python
"meaning_preserved": satisfied and distinct_met and len(on_span) >= needed,
```

`distortions` stand daneben und ging nie ein. Also:

1. ein ausgelöstes `forbids`-Regex ließ den Fall **bestehen**;
2. ein verbotener `claim_type` ließ den Fall **bestehen**;
3. `forbidden_readings` wurde vom Scorer **überhaupt nie geprüft** — nur der
   Validator liest das Feld, und der prüft lediglich, dass eine verbotene Lesart
   *irgendeine* Bedingung verletzt, nie ob ein echter Claim eine ist.

Drei Löcher in dem Mechanismus, der Verzerrung fangen soll. Gefunden, weil zwei
Fremde die Angriffslinie vorgegeben haben — nicht an der Stelle, die sie meinten.

**Behoben**, und das ist ein Mangel unseres Codes und keine Gold-Änderung: eine
Verzerrung lässt den Fall jetzt scheitern, und eine deklarierte verbotene Lesart
unter den Claims ist eine Verzerrung, unabhängig davon, was daneben besteht. Die
Prüfung wird dadurch **strenger**, was die Regel aus 3ad ausdrücklich erlaubt.

### Die 72 Dossiers gegen den strengeren Scorer, gratis

`semantic_score.py --rescore` bewertet gespeicherte Dossiers ohne einen Aufruf.
Über dieselben 72 Dossiers aus 3ah:

| Phänomen | 3ah | neu bewertet |
|---|---:|---:|
| Negation | 12/12 | 12/12 |
| Modalität | 12/12 | 12/12 |
| Korrelation gegen Kausalität | 12/12 | 12/12 |
| Sprecher | 12/12 | 12/12 |
| mehrere Aussagen | 12/12 | 12/12 |
| Geltungsbereich | 6/6 | 6/6 |
| Bedingung | 3/6 | 3/6 |

**Null Bewegung.** Die Löcher waren offen und nie belegt. Damit stehen die Zahlen
aus 3ah auf einem strengeren Instrument — und das ist jetzt belegt und nicht
behauptet.

### Die fünf bestätigten „zu schwach"-Fälle sind der Ernstfall

| Fall | besteht mit |
|---|---|
| `neg-01-de` | „Die Maßnahme wirkt **nicht nur** auf die Abbrecherquote, sondern auch auf die Noten." — Bedeutung ins Gegenteil verkehrt, Token „nicht" vorhanden |
| `spk-01-de` | „Die Regierung ist wirksam." — völlig andere Proposition |
| `spk-02-de` | „Die Regierung ist eine Behörde." + „Der Gerichtshof steht in Straßburg." |
| `mul-01-de` | „Haushalt." + „Schulen." — **Fragmente** |
| `mul-02-de` | „Mittel." + „Ausbau." — **Fragmente** |

Beide Durchsichten urteilen unabhängig gleich über `spk-02` und `mul-*`: in dieser
Form messen sie nichts. Das ist keine Uneinigkeit, sondern Übereinstimmung
**gegen** den Entwurf.

**Und es schwächt veröffentlichte Zahlen, ohne sie zu widerlegen.** 3af und 3ah
berichten `Sprecher 12/12` und `mehrere Aussagen 12/12`. Die Claims jener Läufe
waren echte Propositionen — ich habe sie gelesen, die Zahlen sind richtig. Aber
die Fälle lassen Fragmente durch, also ist das Bestehen eine viel niedrigere
Hürde, als die Abschnitte vermuten lassen. **Die Zahlen stehen, ihre Beweiskraft
nicht.**

### Die eine Uneinigkeit über Bedeutung — und die Regel greift zum ersten Mal

`neg-02`: Durchsicht 2 bestreitet das Gold. „Nicht alle Schulen erhalten den
Zuschlag." ist streng logisch mit „Keine Schule erhält den Zuschlag." verträglich;
dass *einige* ihn erhalten, ist eine pragmatische Implikatur. Mein
`must_preserve` behauptet genau diese Implikatur.

Nach der Regel „Uneinigkeit ist ein Filter auf Beispiele" fällt damit das
Beispiel. `neg-02` war einer meiner beiden vorab benannten
Falschalarm-Verdachtsfälle; der Lauf hat die Vorhersage widerlegt (3/3), und
jetzt stirbt der Fall aus einem Grund, den ich nicht gesehen habe. Durchsicht 1
hält ihn dagegen nur für zu eng. Uneins, *welcher* Mangel — einig, dass einer
vorliegt.

### Was die Vorab-Festlegung wert war

Gefragt war, ob eine blinde Durchsicht **M-1** oder **M-4** findet.

- **M-1 nicht.** Durchsicht 2 findet die Inkonsistenz — `spk-01-de` ist
  sprachtolerant, die elf anderen nicht — und nennt sie „leaky". Das ist **M-2**,
  blind gefunden. Dass eine *treue englische* Wiedergabe an den elf scheitert,
  konnte sie nicht schließen, weil sie nicht weiß, dass das Modell übersetzt.
- **M-4 nicht an seinem Fall.** Beide behandeln `sco-02` nur als zu eng. Aber
  beide finden den Mechanismus, dessen Instanz M-4 ist, **breiter als ich**.

Das Urteil über diese Art Durchsicht ist damit genauer als „hat Zähne" oder
„nutzlos": **Sie findet, was durch Lesen zu finden ist, und breiter als der
Autor. Was eine Messung voraussetzt, findet sie nicht. Und wo sie über die
Mechanik spekuliert statt über die Beispiele, irrt sie — vier von vier Mal.**

### Was offen bleibt, und es ist nicht meine Entscheidung

Acht von 24 Fällen gehören nach beiden Durchsichten umgeschrieben oder
gestrichen: `neg-02` (Gold strittig), `spk-01`, `spk-02`, `mul-01`, `mul-02`
(Bedingung erzwingt kein Prädikat), `mod-02` (Syntaxfessel). Das ändert jede
Messung, die auf ihnen steht — darunter die 69/72 aus 3ah. Diese Entscheidung
treffe ich nicht allein.

**Das siebte Phänomen**, und hier sind die beiden uneins: zeitlicher
Geltungsbereich („wird eingeführt" → „ist eingeführt") gegen Zahlen und Einheiten
(Prozent gegen Prozentpunkte, „ca.", Basisrate). Keine Uneinigkeit über
Bedeutung, also greift die Regel nicht; es ist eine Priorität. Für ein Produkt,
das Budgets prüft, halte ich Zahlen und Einheiten für das teurere.

**Relationen** bleiben nicht annotiert (M-3). Keine der beiden Durchsichten hat
Kanten vorgeschlagen, und gefragt war danach ausdrücklich.

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
