# Durchsicht 2 des semantischen Prüfbestands

**Wörtliche Antwort, unverändert.** Dies ist der Beitrag einer unabhängigen
Durchsicht und **kein Befund dieses Projekts.** Was daraus übernommen wurde und
was nicht, steht in `semantic-cases-review.md` — dort mit der mechanischen
Gegenprüfung, die jeden hier behaupteten Gegenbeispiel-Fall gegen den echten
Validator hält.

| | |
|---|---|
| Modell | `openai/gpt-5.2` |
| Datum | 2026-10-08 |
| Anfrage | erzeugt von `scripts/semantic_cases_review_prompt.py`, 28.934 Zeichen |
| Blind | ja — ohne die Mängelliste und ohne eine Zahl aus den beiden Läufen |
| Token | 7.787 ein / 5.050 aus |
| Kosten | 0,0843 $ |

---

## 1) Eindeutigkeit des Golds (zweite, ebenso treue Lesart möglich?)

**neg-02-de / neg-02-en**  
- **Problem (Bedeutung umstritten/mehrdeutig):** Der Span „Nicht alle Schulen erhalten den Zuschlag.“ ist in strenger Logik kompatibel mit „Keine Schule erhält den Zuschlag.“ (weil „nicht alle“ nur „nicht (alle)“ sagt, nicht „einige schon“).  
- **Konflikt mit `must_preserve`:** Dort steht „einige erhalten ihn, nicht keine“ – das ist **eine pragmatische Implikatur**, aber nicht zwingend der Satzinhalt.  
- **Folge:** Als Gold für eine mechanische Bedeutungsprüfung ist das Beispiel **nicht eindeutig genug**. Hier würde ich nach eurer Regel klar sagen: **Fall umschreiben oder streichen**, nicht „per Bedingungen zurechtbiegen“.

**Ansonsten:** Bei den übrigen Fällen sehe ich *keine* Gold-Mehrdeutigkeiten, die so fundamental sind (mod-02 ist eher ein *Bedingungs*-Problem, s.u.).

---

## 2) Zu enge Bedingungen (treue Wiedergaben, die durchfallen würden)

Hier geht es um Falschalarme durch zu wenige erlaubte Formulierungen / falsche Wortformen.

**mod-02-de** („Die Studie zeigt, dass … senkt.“)  
- **Zu eng:** `requires_all_groups` verlangt explizit eines aus {„zeigt“, „belegt“, „weist nach“, „ergibt“}.  
- **Treue Wiedergabe, die scheitert:** „**Laut Studie** senkt das Programm die Quote.“ (bedeutungstreu: Quelle attribuiert an Studie; die Behauptungsstärke bleibt hoch) — enthält keins der verlangten Wörter.  
- **Bewertung:** Das ist nicht “zu schwer”, sondern schlicht eine **zu enge Lexik-Fessel**, die Bedeutung (Evidenz/Attribution) unnötig an ein Verb koppelt.

**mod-02-en** analog  
- Treu, aber würde scheitern: “**According to the study**, the programme lowers the rate.”

**sco-02-de** (Bedingung „Wenn …, beginnt …“)  
- **Zu eng (Flexion/Wortform):** Gruppe enthält „voraussetzt“, aber eine sehr typische treue Formulierung wäre „**vorausgesetzt** die Mittel werden bewilligt, …“.  
- Treu, aber würde scheitern: „**Vorausgesetzt** die Mittel werden bewilligt, beginnt der Ausbau im Frühjahr.“

**cor-02-de / cor-02-en** (Kausalität „verursachte / caused“)  
- **Zu eng:** Kausalität kann treu ohne die verlangten Trigger-Wörter paraphrasiert werden.  
- Treu, aber würde scheitern (de): „**Wegen der Kürzung** fielen zwei Kurse weg.“  
- Treu, aber würde scheitern (en): “**Because of the cut**, two courses were dropped.”

**mod-01-de / mod-01-en** („könnte/could“)  
- **Möglich zu eng:** Modalität kann treu ohne eure Modalwörter ausgedrückt werden, z.B. de „ist **geeignet**, die Quote zu senken“ / „hat das **Potenzial**, …“. Das ist in vielen Kontexten noch Möglichkeit/Disposition und nicht Indikativ-Fakt. Solche Renderings würden derzeit durchfallen.

**neg-02-de / neg-02-en** (zusätzlich zu (1) auch „zu eng“)  
- Selbst wenn man eure intendierte Lesart akzeptiert: Treu, aber scheitert (de): „**Ein Teil der Schulen geht leer aus.**“ (drückt genau “nicht alle bekommen’s” aus).  
- Das ist genau der von euch selbst vorweggenommene Engpass – ich bestätige ihn.

---

## 3) Zu schwache Bedingungen (untreue Wiedergaben, die *durchkommen* würden)

Hier sind die größten Messlücken: Bedingungen prüfen Tokens, aber nicht die behauptete Relation/Struktur.

### Speaker-Fälle

**spk-01-de / spk-01-en**  
- **Zu schwach:** Es wird nur verlangt, dass „Regierung/Government“ im Claim vorkommt. Das erzwingt **keine Attribution** („trug vor / submitted“) und verhindert nicht, dass aus einer Parteibehauptung eine Tatsachenbehauptung wird.  
- **Untreu, würde bestehen (de):** „**Die Regierung**: Der Rechtsweg ist wirksam.“ (oder noch schlimmer: „**Die Regierung ist wirksam.**“ – völlig andere Proposition, enthält aber „Regierung“ und verletzt kein Verbot)  
- **Untreu, würde bestehen (en):** “**The Government**: the remedy was effective.” / “**The Government** was effective.”

**spk-02-de / spk-02-en**  
- **Zu schwach (und Invariante 5 ist aus):** `min_claims_on_span: 2` + `requires_distinct_groups` prüft faktisch nur „zwei Claims, einer enthält Regierung, einer enthält Gerichtshof/Court“.  
- **Untreu, würde bestehen (de):** Claim A: „**Regierung** äußerte sich zum Rechtsweg.“ Claim B: „**Gerichtshof** befasste sich mit dem Fall.“ (kein Widerspruch, keine Proposition “wirksam/nicht wirksam”, aber beide Gruppen erfüllt)

### Multiple-Assertions-Fälle

**mul-01-de / mul-01-en**  
- **Zu schwach:** Jede Gruppe ist ein OR; pro Gruppe reicht *ein* Wort („Haushalt“ ODER „vier Prozent“).  
- **Untreu, würde bestehen (de):** Claim 1: „**Haushalt**.“ Claim 2: „**Schulen**.“ (beide Gruppen erfüllt, aber keinerlei Aussage über Anstieg/4% bzw. größeren Anteil)  
- Dasselbe strukturell für Englisch.

**mul-02-de / mul-02-en**  
- **Untreu, würde bestehen (de):** Claim 1: „**Mittel**.“ Claim 2: „**Ausbau**.“ (Gruppen erfüllt, Ereignisse/Temporalität fehlen komplett)

### Correlation/Causation (zusätzliche Schwäche)

**cor-01-de / cor-01-en**  
- Ihr verbietet nur bestimmte Kausal-Wörter + Claim-Type „causal“. Ein System könnte aber kausal verfälschen **ohne** eure Trigger:  
- **Untreu, würde bestehen (de):** „Die Teilnahme **trägt dazu bei**, die Abschlussquote zu verbessern.“ (kausaler Sinn, aber kein „verursacht/bewirkt/führt zu/erhöht“; Claim-Typ “causal” wird evtl. nicht gesetzt → könnte durchrutschen)  
- **Untreu, würde bestehen (en):** “Participation **contributes to** higher completion rates.” (kein “causes/leads to/increases/raises”)

### Modality-Verbote (Formenlücken)

**mod-01-en**  
- Ihr verbietet `\blowers\b|\breduces\b|\bdecreases\b`, aber nicht z.B. “**will lower**”, “**is lowering**”, “**has lowered**”.  
- **Untreu, könnte bestehen:** “The programme **will lower** the dropout rate.” (Indikativ/Commitment statt Möglichkeit; enthält keines der verbotenen Tokens)

**sco-01-de / sco-01-en** (Scope)  
- Hier ist es weniger schlimm, aber grundsätzlich: Nur ein “rural/Land” Token erzwingt nicht, dass *die Senkung* auf diesen Scope beschränkt ist.  
- **Untreu, könnte bestehen (de):** „**Auf dem Land**: Das Programm senkt die Quote (insgesamt).“ (Scope rhetorisch vorgeschoben, aber semantisch verallgemeinert; eure Tests würden das nicht erkennen)

---

## 4) Sprachpaare (ist eine Sprache leichter als die andere?)

**Gemischte Sprach-Tokens in `requires_*` sind ein Störfaktor**  
- **spk-01-de** erlaubt als Erfüllung auch „Government“ (und umgekehrt **spk-01-en** erlaubt „Regierung“). Das macht die Paare **asymmetrisch und leaky**: Ein System, das (warum auch immer) englische Canonicals im deutschen Fall produziert, wird belohnt.  
- Ich würde Sprachmischung in Tokenlisten als eigenes Testziel verstehen; hier wirkt es unbeabsichtigt.

**neg-02** ist in beiden Sprachen gleichermaßen problematisch (s.o.), aber:  
- Englisch “Not all …” hat die gleiche logische Unterbestimmtheit wie Deutsch “Nicht alle …”. Also Paar ist konsistent – nur eben als Gold ungeeignet.

**cor-01**: Deutsch hat ein besonderes Risiko durch das Verbotswort „erhöht“ (s.u. Hinweis)  
- In Deutsch kann „erhöhte Abschlussquoten“ leicht als rein beschreibende NP in einer Korrelation auftreten; euer deutsches `forbids` enthält aber ausgerechnet „erhöht“ (als Verb). Das ist kein 1:1-Problem im Englischen (weil ihr “increases” verbietet, nicht “increased”). → **Deutsch-Seite wird leichter falsch positiv**, Englisch nicht in gleicher Weise.

---

## 5) Fehlendes Phänomen (welches „siebte“ kostet in der Praxis am meisten Bedeutung?)

**Zahlen/Einheiten/Quantitative Präzision (inkl. Prozent vs. Prozentpunkte, „ca.“, Rundungen, Basisrate)**  
Warum das in der Praxis besonders teuer ist:
- Budget-/Policy-Dokumente sind voll von **Kennzahlen**, und kleine semantische Fehler sind gravierend:  
  - „um **4 Prozent**“ vs „um **4 Prozentpunkte**“  
  - „**4 %**“ vs „**bis zu 4 %**“  
  - „**ca. 4 %**“ vs „**genau 4 %**“  
  - „von 10 auf 6“ vs „um 4 gesunken“ (Basis implizit)  
- Das ist in Claim-Graphen extrem häufig und mit rein tokenbasierten Checks zumindest teilweise testbar (Zahlstring + Einheit + Hedging).

---

## 6) Urteil (Brauchbarkeit als Messinstrument, Auflagen; streichen/umschreiben statt flicken)

**Als Entwurf ist der Bestand nur teilweise als Messinstrument brauchbar**, weil mehrere Fälle aktuell eher *Token-Präsenz* als *Bedeutungstreue* messen.

### Fälle, die ich nach eurer Regel **umschreiben oder streichen** würde (nicht „Tokenliste nachziehen“)

1) **neg-02-de / neg-02-en**  
- **Grund:** Gold/Bedeutung nicht eindeutig (Skopus/Existenz-Implikatur).  
- **Aktion:** Umschreiben auf eine Formulierung, die „einige ja, einige nein“ explizit macht (oder Fall streichen).

2) **spk-01-*, spk-02-***  
- **Grund:** Bedingungen sind zu schwach, weil „Sprecher erhalten“ nicht durch bloße Erwähnung von “Regierung/Court” gemessen wird. Das misst sonst hauptsächlich Named-Entity-Dropping.  
- **Aktion:** Entweder (a) Fälle streichen, oder (b) so umschreiben, dass der relevante Bedeutungsunterschied mechanisch greifbar wird (z.B. direkte Rede/Markierung), ohne sich auf nur ein Token zu verlassen.

3) **mul-01-*, mul-02-***  
- **Grund:** Aktuelle Gruppen erlauben “Claim-Fragmente” (ein Wort reicht) und prüfen damit nicht “zwei Aussagen”, sondern “zwei Claims mit je irgendeinem Schlüsselwort”.  
- **Aktion:** Umschreiben/neu designen, sodass jede Aussage mechanisch an mehr als einem inhaltstragenden Marker hängt (sonst bleibt es ein Zähltest, kein Bedeutungs-Test).

### Fälle, die ich **im Kern gut** finde (mit kleineren, prinzipiellen Engstellen)

- **neg-01-de/en:** solide und eindeutig; Mechanik passt.  
- **sco-01-de/en:** Grundidee gut (Scope), aber rein tokenbasiert bleibt es grundsätzlich anfällig für rhetorische Tricks; trotzdem als einfacher Basistest ok.  
- **cor-02-de/en:** Intention gut (Kausal vs. bloßer Zusammenhang), aber aktuell zu eng (weil Kausalität oft ohne eure Trigger paraphrasiert wird).  
- **mod-01-de/en:** Intention gut (Möglichkeit vs. Fakt), aber Verbotslisten sind form-lückenhaft und Modal-Paraphrasen fehlen.

### Auflagen, damit es als Messinstrument taugt
- **Keine Fälle behalten, deren Gold semantisch strittig ist** (neg-02).  
- **`min_claims_on_span >= 2`-Fälle müssen auch inhaltlich mechanisch prüfbar sein**, sonst messen sie Claim-Anzahl + Keyword-Streuung, nicht Treue. Wenn das im Rahmen der Mechanik nicht geht: lieber streichen als Scheinmessung.  
- **Sprachmischung in Token-Gruppen entfernen**, sonst werden Paare unsauber.  
- **Verbots/Regex-Listen dürfen nicht auf zufälligen Oberflächenformen hängen** (engl. “will lower”, dt. Partizip/Infinitiv-Formen etc.), sonst entstehen systematische Durchrutscher.

Wenn du willst, kann ich im nächsten Schritt (separat) pro gestrichen/umzuschreibenden Fall je **eine** alternative Span-Formulierung vorschlagen, die *ohne* umstrittene Implikaturen auskommt und mechanisch prüfbar bleibt.