# Review-Auftrag: der semantische Prüfbestand

Dieses Dokument begleitet `src/budget_review/fixtures/semantic_cases/cases.json`
und ist der Grund, aus dem der Prüfbestand überhaupt etwas wert sein kann.

**Der Entwurf ist von einem Modell geschrieben.** Beispiele, Gold-Annotationen
und Prüfbedingungen stammen aus derselben Modellfamilie, die am Ende geprüft
werden soll. Ohne unabhängige Durchsicht messen wir, ob das System die Lesart
eines Modells teilt — genau die Zirkularität, gegen die dieses Repo gebaut ist.

Deshalb: **zwei unabhängige Durchsichten, keine davon von mir, keine von dem
Modell, das geprüft wird.** Ihre Einwände und was daraufhin geändert wurde stehen
unten. Ohne diesen Abschnitt ist der Prüfbestand ein Entwurf und wird als solcher
geführt.

## Die eine Regel, die den Beraterrollen Sinn gibt

**Uneinigkeit ist ein Filter auf Beispiele, keine Abstimmung über Bedeutung.**

Sind sich Durchsicht und Entwurf nicht einig, *was* ein Satz bedeutet, dann wird
das Beispiel umgeschrieben oder gestrichen — nicht per Mehrheit entschieden. Ein
Prüfbestand mit umstrittenem Gold misst nichts. Uneinigkeit ist damit das
wertvollste, was eine Durchsicht liefern kann.

## Was zu prüfen ist

Fünf Fragen, in dieser Reihenfolge:

1. **Ist das Gold eindeutig?** Lässt ein Beispiel eine zweite, ebenso treue
   Lesart zu, die der Entwurf nicht als zulässig aufführt? Dann ist entweder die
   Liste der zulässigen Lesarten zu kurz oder das Beispiel ungeeignet.
2. **Prüft die Bedingung, was sie zu prüfen behauptet?** Jede Bedingung ist eine
   Token-Gruppe oder ein Regex. Gibt es eine *treue* Wiedergabe, die daran
   scheitert? Dann ist die Bedingung zu eng und produziert Falschalarme.
3. **Gibt es eine *untreue* Wiedergabe, die durchkommt?** Dann ist die Bedingung
   zu schwach und das Beispiel misst nichts. Invariante 5 im Skript prüft das
   gegen die aufgeführten verbotenen Lesarten — aber nur gegen die, die ich
   aufgeschrieben habe.
4. **Sind die Sprachpaare semantisch gleich?** Deutsch und Englisch sollen
   dieselbe Bedeutung in derselben Schwierigkeit tragen. Wo eine Sprache leichter
   ist, ist Sprache kein Variable mehr, sondern ein Störfaktor.
5. **Fehlt ein Phänomen?** Sechs sind abgedeckt: Negation, Modalität, Korrelation
   gegen Kausalität, Bedingung und Geltungsbereich, Sprecher, mehrere Aussagen in
   einer Stelle. Welches siebte würde in der Praxis am meisten Bedeutung kosten?

## Was ich selbst für die schwächsten Stellen halte

Bitte hier zuerst angreifen:

- **`neg-02`** („Nicht alle Schulen erhalten den Zuschlag."). Die Bedingung
  verlangt eine von fünf Wendungen. Eine treue Wiedergabe wie „Ein Teil der
  Schulen geht leer aus" trägt keine davon und würde als Fehler gezählt. Ist die
  Liste zu kurz, oder ist der Fall zu schwer für eine mechanische Prüfung?
- **`mod-02`** verlangt ein Wort aus `zeigt / belegt / weist nach / ergibt`. Eine
  Wiedergabe als schlichter Indikativ („Das Programm senkt die Quote laut
  Studie") trägt keines — und ist trotzdem treu. Vermutlich ein Falschalarm, der
  eingebaut ist.
- **`spk-02` und `mul-*`** prüfen über `min_claims_on_span` und zwei getrennte
  Gruppen. Invariante 5 ist für sie abgeschaltet, weil ihr Fehlerfall „nur ein
  Claim" ist und keine Inhaltsprüfung. Für diese sechs Fälle ist also **nicht
  maschinell belegt**, dass ihre verbotene Lesart durchfällt.
- **Die Regex-Verbote** (`\bsenkt\b`, `\bcauses\b`) treffen eine Flexionsform.
  Welche Form fehlt?
- **Die Transliteration ist behoben**, das Deutsche trägt Umlaute. Aber die Sätze
  sind von mir erfunden und klingen vielleicht nach Übersetzung. Wo?

## Die Regel für Erweiterungen

Eine Token-Gruppe zu erweitern, **nachdem** ein Lauf daran gescheitert ist, ist
Anpassung des Tests an das System. Erlaubt ist das nur, wenn eine Durchsicht
zustimmt, dass die neue Wendung eine treue Wiedergabe ist — und jede Erweiterung
wird hier mit Datum und Urheber vermerkt. Sonst wandert die Marke mit dem
Ergebnis, und genau das hat auf diesem Branch schon zweimal Befunde entwertet.

## Gefundene Gold-Mängel, offen bis zur Durchsicht

Aus den beiden Läufen vom 2026-10-06 (§3af, §3ah). **Am Bestand ist nichts
geändert** — die Regel oben verlangt Zustimmung einer Durchsicht, und eine Liste
zu erweitern, bis ein Lauf durchläuft, ist Anpassung des Tests an das System.
M-1 ist erledigt, weil das *Produkt* geändert wurde und nicht der Test.

**M-1 (2026-10-06, Claude): Die Bedingungen verwechseln Sprache mit Bedeutung.**
31 Prozent der Claims aus deutschen Quellen kamen auf Englisch zurück, und weil
die deutschen Bedingungen deutsche Token verlangen, scheitert eine *treue*
englische Wiedergabe an der Bedeutungsprüfung. Betroffen: `sco-01-de`,
`spk-02-de`, `mul-01-de`, `cor-01-de`.
*Vorschlag:* Die Bedingungsgruppen eines Paares werden zur Vereinigung beider
Sprachen, und die Sprache wird als eigene Achse berichtet — getrennt messen statt
Liste weiten. Die Achse ist gebaut; die Gold-Änderung nicht.
*Zu prüfen:* Verliert die Prüfung damit Schärfe? Eine Bedingung, die beide
Sprachen akzeptiert, kann einen Fall nicht mehr fangen, bei dem das Modell die
deutsche Wendung durch eine englische *mit anderer Bedeutung* ersetzt.
**Erledigt (2026-10-06, §3ah), ohne eine Gold-Änderung.** Der Extraktionsvertrag
verlangt jetzt die Sprache des Dokuments, 0 von 123 deutschen Claims kamen
übersetzt zurück, und alle vier betroffenen Fälle bestehen ihre **unveränderten**
Bedingungen. Der Vorschlag oben wird damit **nicht** umgesetzt und die Frage nach
der Schärfe stellt sich nicht: es wird keine zweisprachige Bedingung gebraucht.
Meine Listen waren nicht zu eng — das Modell antwortete in der falschen Sprache.

**M-2 (2026-10-06, Claude): `spk-01-de` ist versehentlich sprachtolerant.**
Seine Gruppe lautet `["Regierung", "Government"]` — dieser eine Fall besteht
trotz Übersetzung, die anderen elf nicht. Die deutschen Fälle waren damit nicht
untereinander konsistent, und der Fall hat 3/3 bestanden, ohne dass es etwas
heißt.
**Wirkungslos seit §3ah**, weil kein Fall mehr Sprachtoleranz braucht. Die
Inkonsistenz steht weiter im Bestand und gehört aufgelöst, damit die zwölf
deutschen Fälle dieselbe Prüfung durchlaufen.

**M-3 (2026-10-06, Claude): Der Bestand annotiert keine Kanten.** Die dritte
Achse aus §3ac ist deshalb nicht messbar. Aufgefallen beim Implementieren des
Scorers, nicht beim Schreiben des Bestands.
*Zu prüfen:* Welche Kanten gehören bei `mul-*` und `spk-02` annotiert, ohne eine
Relationstaxonomie vorwegzunehmen, die das Produkt noch nicht hat?

**M-4 (2026-10-06, Claude, §3ah): `sco-02` kann die verbotene Lesart nicht
sehen, wenn sie neben einer bestehenden steht.** `requires_all_groups` besteht,
sobald *irgendein* Claim auf der Spanne einen Bedingungsmarker trägt. Ein Lauf,
der die Bedingung **und** den unbedingten Nachsatz liefert, würde bestehen,
obwohl der Graph eine erfundene Zusage enthält. In §3ah ist das nicht vorgekommen
— die verbotene Lesart erschien in genau den drei scheiternden Läufen und in
keinem bestehenden, beide Signale stimmen 6 von 6 überein. Die Lücke ist also
**latent und nicht gemessen.**
*Vorschlag:* `forbidden_readings` wird vom Scorer geprüft und nicht nur vom
Validator. Heute liest nur `scripts/semantic_cases.py` das Feld; der Scorer
kennt nur `forbids`.
*Zu prüfen:* Gilt das für mehr als `sco-02`? Jeder Fall, dessen Bedingung auf
*Anwesenheit* prüft, hat dieselbe Form, und das sind die meisten.

**Widerlegt:** Meine Vorhersage, `neg-02` und `mod-02` enthielten eingebaute
Falschalarme. Beide haben 3/3 in beiden Sprachen bestanden. Die beiden Stellen
oben, die ich zum Angreifen markiert habe, waren nicht die schwachen.

## Wie die beiden Durchsichten angefragt werden

Vorab festgelegt am 2026-10-07, bevor eine Anfrage hinausgegangen ist.

**Wer nicht in Frage kommt, und warum.** Zwei Familien sind ausgeschlossen, und
beide aus demselben Grund: Dieses Repo ist gegen Zirkularität gebaut.

- **Nicht die Familie, die den Bestand geschrieben hat.** Beispiele, Gold und
  Bedingungen sind von Claude. Eine Durchsicht von Claude würde prüfen, ob Claude
  Claudes Lesart teilt.
- **Nicht das geprüfte System.** DeepSeek extrahiert die Claims, gegen die
  gemessen wird. Es darf die Rolle unten spielen und nicht diese.

Bleiben zwei fremde Familien, jeweils das stärkste verfügbare Modell:
**`google/gemini-3.1-pro-preview`** und **`openai/gpt-5.2`**, über OpenRouter.
Der Schlüssel ist auf 10 $ begrenzt und selbst ablaufend; die beiden Aufrufe
kosten nach Listenpreis zusammen etwa 0,20 $. Das Budget war hier nie die
Einschränkung.

**Warum die Anfragen am 2026-10-08 noch nicht hinaus sind**, und es gehört
hierher und nicht in einen Chatverlauf: Nicht der Schlüssel fehlte. Die
Berechtigung, Repo-Inhalt an einen externen Endpunkt zu senden, ist in der
Umgebung gesperrt, aus der dieser Auftrag gebaut wurde. Zwei Schlüssel sind
daran vorbeigegangen, ohne etwas zu ändern. Der Auftrag und
`scripts/semantic_cases_review_prompt.py` sind fertig und geprüft; was fehlt, ist
eine Freigabe oder ein anderer Ausführungsort — nichts am Inhalt dieses
Dokuments.

**Die Durchsicht ist blind gegenüber den Messungen.** Sie bekommt diesen Auftrag
**ohne** die Mängelliste unten und ohne eine Zahl aus den beiden Läufen.
`scripts/semantic_cases_review_prompt.py` schneidet den Abschnitt an der
Überschrift heraus und verweigert eine Anfrage, die noch eine Mangel-Id, eine
Log-Nummer oder eine Lauf-Zahl enthält; fünf Mutationen darauf, darunter die, die
den Schnitt und die Prüfung nutzlos machen.

Der Grund ist nicht Förmlichkeit. Eine Durchsicht, die weiß, dass eine
Vertragszeile die Übersetzung abgeschaltet hat, wird eingeladen, das Gold zu
billigen, weil die Zahl sich bewegt hat. Gefragt ist, ob die Fälle gute Prüfungen
sind — nicht, ob sie bequeme Ergebnisse erzeugt haben.

**Damit sind die Durchsichten selbst prüfbar, und das ist die Vorhersage.** Zwei
der vier Mängel unten stehen im Bestand und sind durch Lesen zu finden: **M-1**
(die Bedingungen verwechseln Sprache mit Bedeutung) und **M-4** (`sco-02` besteht
schon, wenn *irgendein* Claim einen Bedingungsmarker trägt, sieht also die
verbotene Lesart daneben nicht). Beide haben bezahlte Läufe gekostet.

- Findet eine blinde Durchsicht M-1 oder M-4, ist der Mangel von außerhalb der
  Familie bestätigt, die den Bestand geschrieben hat — und die Durchsicht hat
  Zähne.
- Findet keine der beiden einen davon, begrenzt das, was eine Durchsicht dieser
  Art wert ist. Es ist **kein** Beleg, dass die Mängel nicht bestehen; sie sind
  gemessen.

Das steht hier, bevor die Antworten da sind, damit es hinterher nicht als
Bestätigung gelesen werden kann, was auch immer kommt.

**Und was eine Durchsicht nicht ist.** Sie ist Beratung, keine Autorität. Was sie
sagt, wird wörtlich vermerkt und dann einzeln entschieden — nach der Regel oben:
Uneinigkeit über Bedeutung streicht das Beispiel, sie stimmt nicht darüber ab.

## Durchsicht 1

*Offen.* `google/gemini-3.1-pro-preview`, blind. Datum, Einwände, und was
geändert wurde.

## Durchsicht 2

*Offen.* `openai/gpt-5.2`, blind. Datum, Einwände, und was geändert wurde.

## Was DeepSeek hier nicht tun darf

Das geprüfte Modell darf **nicht** das Gold begutachten. Es darf eine andere
Rolle spielen, die nützlich und nicht zirkulär ist: nach *allen* Lesarten einer
Stelle gefragt werden. Nennt es eine Lesart, die der Entwurf verbietet, ist das
ein Hinweis, dass die Annotation zu eng ist — kein Urteil, sondern
gegnerischer Eingabestoff. Das kostet einen Actions-Lauf und ist noch nicht
gemacht.
