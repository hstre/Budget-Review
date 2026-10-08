"""The prompt an independent review of the meaning set is asked, assembled.

The set's own review brief says two independent reviews decide whether it is more
than a draft, and that neither may come from the family that wrote it nor from the
system under test. This script builds what those reviews are sent, so that what
was asked sits in the repository rather than in a chat log.

Two decisions are built in, and both change what a review can say.

**The review is blind to the measurements.** The brief grew a section of gold
defects that the two paid runs found. That section is cut here by position rather
than by hand, and `--check` refuses a prompt that still names a run or a defect
id. A reviewer who knows that 38 of 122 propositions came back translated, and
that one contract line took it to 0, is being invited to approve the gold because
the number moved. The question put to them is whether the cases are good tests,
not whether they produced convenient results.

**Which makes the reviews themselves testable.** Two of the defects the runs found
are visible by reading the set alone. M-1: the requirements conflate language with
meaning, so a faithful English rendering fails a German token group. M-4:
`sco-02` passes as soon as *any* claim on the span carries a conditional marker,
so a run returning the condition *and* the bare consequent would pass. Both cost
paid runs to find. A blind reading that finds either corroborates it from outside
the family that wrote the set; one that finds neither bounds what a review of this
kind is worth. That expectation is recorded before the reviews are sent, in
`docs/semantic-cases-review.md`.

The prompt carries the field semantics, because a reviewer cannot judge a token
group without knowing that single words match on word boundaries and phrases as
substrings, nor judge the five invariants without knowing that the fifth is
switched off for the six multi-claim cases.

Usage:
    semantic_cases_review_prompt.py              # the prompt, on stdout
    semantic_cases_review_prompt.py --check      # assert it leaks no result
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIEF = ROOT / "docs" / "semantic-cases-review.md"
CASES = ROOT / "src" / "budget_review" / "fixtures" / "semantic_cases" / "cases.json"

# Everything from this heading on is what the paid runs found. A review that sees
# it is no longer blind, so the cut is by position and not by judgement.
RESULTS_HEADING = "## Gefundene Gold-Mängel"

# What a leak looks like: a defect id, a log section, or a figure from either run.
LEAKS = (
    r"\bM-[0-9]+\b",
    r"§3a[a-z]\b",
    r"\b38 von 122\b",
    r"\b0 von 123\b",
    r"\b69 von 72\b",
    r"\bübersetzt\w*\b",
)

PREAMBLE = """Du bist als **unabhängige Durchsicht** eines semantischen Prüfbestands
beauftragt. Der Bestand gehört zu einem Werkzeug, das Dokumente in einen prüfbaren
Claim-Graphen zerlegt: zu jeder Aussage wird eine wörtliche Textstelle (`span`)
zitiert und eine Proposition (`canonical_content`) geschrieben.

Der Prüfbestand soll messen, ob die Proposition die **Bedeutung** der Textstelle
treu wiedergibt — nicht, ob die Quelle recht hat. Die Quellen dürfen Unsinn
behaupten; geprüft wird die Wiedergabe.

Die Bedingungen sind absichtlich **mechanisch** (Token-Gruppen, Regexe) und nicht
modellbasiert, damit das geprüfte System und sein Prüfer nicht aus einer Familie
kommen. Aus demselben Grund bist du beauftragt: der Entwurf unten ist von einem
Modell geschrieben, und du bist nicht aus dessen Familie.

**Du siehst absichtlich keine Messergebnisse.** Es sind bezahlte Läufe über diesen
Bestand gelaufen, und du erfährst nicht, was sie ergeben haben. Das ist Absicht:
du sollst beurteilen, ob die Fälle gute Prüfungen sind, nicht ob sie bequeme
Zahlen erzeugt haben.

So lesen sich die Felder eines Falls:

- `document` / `span` — die Quelle und die annotierte Stelle darin.
- `requires_all_groups` — Liste von Gruppen. Ein Claim auf der Spanne muss aus
  **jeder** Gruppe mindestens eine Wendung tragen. Einzelwörter werden mit
  Wortgrenzen gematcht, Mehrwortphrasen als Teilstring.
- `requires_distinct_claims` — ein Eintrag je Claim, den die Stelle tragen muss,
  und ein Eintrag ist eine Liste von Gruppen, die **ein** Claim gemeinsam
  erfüllen muss. Verschiedene Einträge müssen von **verschiedenen** Claims
  erfüllt werden.
- `forbids` — Regexe. Trifft einer auf einen Claim, gilt er als verzerrt.
- `forbidden_claim_types` — Claim-Typen, die auf dieser Stelle falsch sind.
- `min_claims_on_span` — so viele Claims müssen auf der Stelle ankern.
- `must_preserve` — Prosa: was erhalten bleiben muss. Nicht maschinell geprüft.
- `permitted_readings` / `forbidden_readings` — Beispielpropositionen. Ein
  Validator prüft, dass jede zulässige die Bedingungen erfüllt und jede verbotene
  mindestens eine verletzt. Für Fälle mit `min_claims_on_span` >= 2 ist diese
  Prüfung **abgeschaltet**, weil ihr Fehlerfall „nur ein Claim" lautet.

---

# Der Auftrag, wie er im Repository steht

"""

TASK = """

---

# Der Prüfbestand, vollständig

```json
{cases}
```

---

# Was ich von dir brauche

Arbeite die fünf Fragen in ihrer Reihenfolge ab und **sei konkret**: nenne
`case_id`, das Problem und, wo möglich, den Satz oder die Wendung, an der es
hängt. Eine Durchsicht, die „sieht insgesamt solide aus" sagt, ist wertlos.

Halte dich an die eine Regel: **Uneinigkeit ist ein Filter auf Beispiele, keine
Abstimmung über Bedeutung.** Wenn du mit dem Gold über die *Bedeutung* eines
Satzes nicht einig bist, sag das — dann fällt das Beispiel, und das ist das
wertvollste Ergebnis, das du liefern kannst. Schlage nicht vor, eine Token-Liste
zu erweitern, bis ein Fall durchläuft, wenn das eigentliche Problem der Fall ist.

Sag ausdrücklich, wo du **nichts** zu beanstanden hast. Erfinde keine Mängel, um
nützlich zu wirken; eine kurze, harte Liste ist besser als eine lange, weiche.

Gliedere so:

1. **Eindeutigkeit des Golds** — Fälle mit einer zweiten, ebenso treuen Lesart.
2. **Zu enge Bedingungen** — treue Wiedergaben, die durchfallen (Falschalarme).
3. **Zu schwache Bedingungen** — untreue Wiedergaben, die durchkommen. Nenne für
   jeden Fall, den du angreifst, eine konkrete Proposition, die bestehen würde und
   die Bedeutung dennoch verfehlt.
4. **Die Sprachpaare** — wo ist eine Sprache leichter als die andere?
5. **Fehlendes Phänomen** — welches siebte würde in der Praxis am meisten
   Bedeutung kosten, und warum?
6. **Urteil** — ist der Bestand als Messinstrument brauchbar, mit welchen
   Auflagen? Welche Fälle gehören gestrichen oder umgeschrieben, nicht geflickt?

Antworte auf Deutsch.
"""


def brief_before_results(brief: str) -> str:
    """The brief as it stood before the runs: everything above the defect list."""
    cut = brief.find(RESULTS_HEADING)
    if cut < 0:
        raise SystemExit(
            f"the brief no longer contains {RESULTS_HEADING!r}; refusing to guess "
            "where the measured results begin"
        )
    return brief[:cut].rstrip()


def leaks(prompt: str) -> list[str]:
    """Traces of a measured result, which a blind review may not see."""
    return [pattern for pattern in LEAKS if re.search(pattern, prompt)]


def build(brief: str, cases: dict) -> str:
    return (
        PREAMBLE
        + brief_before_results(brief)
        + TASK.format(cases=json.dumps(cases, ensure_ascii=False, indent=1))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="print nothing; fail if the prompt carries a measured result",
    )
    args = parser.parse_args()

    prompt = build(
        BRIEF.read_text(encoding="utf-8"),
        json.loads(CASES.read_text(encoding="utf-8")),
    )
    found = leaks(prompt)
    if found:
        print(
            "The prompt would tell the review what the runs found, which is "
            f"exactly what it may not know. Patterns matched: {found}",
            file=sys.stderr,
        )
        return 1
    if args.check:
        print(f"clean: {len(prompt)} characters, no measured result", file=sys.stderr)
        return 0
    sys.stdout.write(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
