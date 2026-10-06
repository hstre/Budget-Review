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

## Durchsicht 1

*Offen.* Modell, Datum, Einwände, und was geändert wurde.

## Durchsicht 2

*Offen.* Modell, Datum, Einwände, und was geändert wurde.

## Was DeepSeek hier nicht tun darf

Das geprüfte Modell darf **nicht** das Gold begutachten. Es darf eine andere
Rolle spielen, die nützlich und nicht zirkulär ist: nach *allen* Lesarten einer
Stelle gefragt werden. Nennt es eine Lesart, die der Entwurf verbietet, ist das
ein Hinweis, dass die Annotation zu eng ist — kein Urteil, sondern
gegnerischer Eingabestoff. Das kostet einen Actions-Lauf und ist noch nicht
gemacht.
