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
| davon gemessen an der Decke | **43 %** |
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
