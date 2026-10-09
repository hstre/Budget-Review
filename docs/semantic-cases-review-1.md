# Durchsicht 1 des semantischen Prüfbestands

**Wörtliche Antwort, unverändert.** Dies ist der Beitrag einer unabhängigen
Durchsicht und **kein Befund dieses Projekts.** Was daraus übernommen wurde und
was nicht, steht in `semantic-cases-review.md` — dort mit der mechanischen
Gegenprüfung, die jeden hier behaupteten Gegenbeispiel-Fall gegen den echten
Validator hält.

| | |
|---|---|
| Modell | `google/gemini-3.1-pro-preview` |
| Datum | 2026-10-08 |
| Anfrage | erzeugt von `scripts/semantic_cases_review_prompt.py`, 28.934 Zeichen |
| Blind | ja — ohne die Mängelliste und ohne eine Zahl aus den beiden Läufen |
| Token | 8.883 ein / 4.514 aus |
| Kosten | 0,0719 $ |

---

Hier ist die unabhängige Durchsicht. Ich habe den Bestand streng nach deinen Vorgaben geprüft. Die mechanischen Bedingungen sind ein hartes, aber ehrliches Werkzeug – allerdings zeigen sie an einigen Stellen genau die Schwächen, die du bereits vermutet hast, und an anderen weisen sie blinde Flecken auf.

Hier ist die detaillierte Auswertung entlang deiner fünf Fragen.

### 1. Eindeutigkeit des Golds (Alternative, treue Lesarten)

Einige Fälle lassen treue Lesarten zu, die an den Token-Gruppen scheitern würden.

*   **`neg-02-de` / `neg-02-en`:** Deine Vermutung ist absolut richtig. Eine Lesart wie *"Ein Teil der Schulen geht leer aus"* ist eine perfekte, treue Wiedergabe der Bedeutung. Sie scheitert an `requires_all_groups`, da "ein Teil" nicht in der Liste steht (nur "nur ein Teil"). Im Englischen gilt dasselbe für *"A fraction of the schools miss out"*. **Fazit:** Das Gold ist hier zu eng gefasst. Wenn das System abstrahiert (was gut ist), wird es bestraft.
*   **`sco-02-de`:** *"Vorbehaltlich der Mittelbewilligung beginnt der Ausbau im Frühjahr."* Dies ist eine hochgradig treue, professionelle Wiedergabe der Bedingung. Sie fällt durch, weil "vorbehaltlich" in der Liste `["wenn", "falls", "sofern", "unter der Bedingung", "voraussetzt"]` fehlt.
*   **Keine Beanstandung:** `sco-01` (Geltungsbereich Land/Stadt) und `spk-01` (Sprecher) sind eindeutig und robust.

### 2. Zu enge Bedingungen (Falschalarme bei treuer Wiedergabe)

Hier fallen korrekte Claims durch die mechanische Prüfung.

*   **`mod-02-de` / `mod-02-en`:** Dein Verdacht trifft voll ins Schwarze. Eine Wiedergabe wie *"Laut Studie senkt das Programm die Quote"* (oder *"According to the study, the programme lowers the rate"*) ist eine völlig treue Extraktion. Sie lagert die Quelle ("Laut Studie") korrekt aus und nennt den Fakt. Sie fällt aber durch, weil Wörter wie `zeigt / belegt` fehlen. **Fazit:** Dieser Fall ist als mechanischer Test unbrauchbar, da er eine bestimmte syntaktische Struktur (Matrixsatz + Dass-Satz) erzwingt, statt die Semantik zu prüfen.
*   **`cor-01-de`:** *"Teilnahme und höhere Abschlussquoten treten gemeinsam auf."* Eine treue Umschreibung einer Korrelation. Fällt durch, da die Token-Liste stark auf Fremdwörter (`korreliert`, `assoziiert`) oder das spezifische Wort `Zusammenhang` fokussiert ist.

### 3. Zu schwache Bedingungen (Untreue Wiedergaben, die durchkommen)

Das ist die gefährlichste Kategorie. Hier gibt es massive Lücken in den Regexes und Token-Listen.

*   **`neg-01-de` / `neg-01-en`:** Die Bedingung verlangt lediglich das Vorhandensein von Negationswörtern.
    *   *Untreuer Claim, der besteht:* *"Die Maßnahme wirkt **nicht nur** auf die Abbrecherquote, sondern auch auf die Noten."*
    *   *Warum das fatal ist:* Das System hat die Bedeutung ins exakte Gegenteil verkehrt (es behauptet, sie wirkt sehr wohl darauf), besteht aber die Prüfung, weil das Token "nicht" gefunden wird.
*   **`mod-01-de` / `mod-01-en`:** Die Verbote (`\bsenkt\b`, `\blowers\b`) prüfen nur das Präsens.
    *   *Untreuer Claim, der besteht:* *"Das Programm **senkte** die Abbrecherquote."* (oder *"lowered"*).
    *   *Warum das fatal ist:* Der Claim macht aus einer Möglichkeit ("könnte") einen historischen Fakt. Die Verzerrung ist massiv, der Test merkt es nicht. Auch Nominalisierungen (*"Die Senkung der Quote durch das Programm"*) kommen durch.
*   **`spk-02` und `mul-*` (Alle Sprachen):** Wie du selbst angemerkt hast, ist Invariante 5 hier abgeschaltet. Die Prüfung verlangt *nur*, dass zwei Claims existieren und bestimmte Entitäten (z.B. "Regierung" und "Gerichtshof") aufgeteilt sind.
    *   *Untreuer Claim, der besteht (`spk-02-de`):* Claim 1: *"Die Regierung ist eine Behörde."* Claim 2: *"Der Gerichtshof steht in Straßburg."*
    *   *Warum das fatal ist:* Das System kann den kompletten semantischen Kern (die Wirksamkeit des Rechtswegs und den Widerspruch) halluzinieren oder weglassen. Solange es zwei Claims mit den richtigen Subjekten generiert, gibt es ein "Pass". Diese Fälle messen in der aktuellen Form **nichts**.

### 4. Die Sprachpaare (Semantische Gleichheit und Natürlichkeit)

Die Schwierigkeit zwischen Deutsch und Englisch ist gut ausbalanciert. Es gibt keine unfairen Asymmetrien in der Komplexität.

*   **Übersetzungs-Klang (Translationese):**
    *   `neg-01-de`: *"Die Maßnahme wirkt nicht auf die Abbrecherquote."* Das ist unidiomatisches Deutsch (klingt nach "does not affect"). Ein Muttersprachler würde schreiben: *"Die Maßnahme hat keine Auswirkung auf..."* oder *"beeinflusst die Abbrecherquote nicht"*.
    *   `mul-01-de`: *"Der Beschluss ist knapp gefasst."* (The resolution is briefly worded). Etwas hölzern, aber noch im Rahmen.
*   **Keine Beanstandung:** Die `cor-*` und `sco-*` Fälle klingen in beiden Sprachen natürlich und spiegeln exakt dieselbe semantische Tiefe wider.

### 5. Fehlendes Phänomen

Es fehlt **Zeitlicher Geltungsbereich (Temporal Scope / Tense)**.

*   *Beispiel:* "Das System wird im kommenden Jahr eingeführt." -> Claim: "Das System ist eingeführt."
*   *Warum das wichtig ist:* In administrativen, rechtlichen oder wissenschaftlichen Texten (aus denen deine Beispiele zu stammen scheinen) ist die Unterscheidung zwischen *Planung/Zukunft* und *abgeschlossener Tatsache* eine der häufigsten Fehlerquellen von LLMs. Ein Modell, das Zukunftsformen in Fakten der Gegenwart übersetzt, zerstört die Nutzbarkeit des Claim-Graphen völlig. Das kostet in der Praxis massiv Bedeutung.

### 6. Urteil und Auflagen

Der Prüfbestand ist im Kern eine exzellente Idee, um Zirkularität zu vermeiden, aber er ist in der aktuellen Form **noch nicht als verlässliches Messinstrument brauchbar**. Er würde zu viele Falschalarme produzieren und gleichzeitig gefährliche Halluzinationen durchwinken.

**Konkrete Auflagen für die Überarbeitung:**

1.  **Streichen / Komplett neu schreiben:**
    *   `mod-02`: Streichen. Die Bedingung zwingt das System zu einer bestimmten Syntax und bestraft legitime Extraktionen wie "Laut Studie...".
    *   `spk-02` und alle `mul-*` Fälle: In der aktuellen Form wertlos, da sie das Prädikat nicht prüfen. Sie müssen so umgeschrieben werden, dass `requires_all_groups` für *jeden* der geforderten Claims auch den inhaltlichen Kern (z.B. "wirksam" vs. "nicht wirksam") erzwingt.
2.  **Patchen (Regex/Token-Listen):**
    *   `mod-01`: Die `forbids`-Listen müssen zwingend um Vergangenheitsformen (`senkte`, `lowered`) und Nominalisierungen erweitert werden.
    *   `neg-01`: Muss um ein Verbot für Konstruktionen wie "nicht nur" / "not only" ergänzt werden.
3.  **Textanpassung:**
    *   `neg-01-de`: Den Quelltext in natürlicheres Deutsch ändern ("hat keine Auswirkung auf").

Sobald die Lücken in den Regexes geschlossen und die Multi-Claim-Fälle inhaltlich abgesichert sind, ist dieser Bestand ein scharfes, wertvolles Instrument. Bis dahin misst er eher, ob das System die Token-Listen errät, als ob es Bedeutung bewahrt.