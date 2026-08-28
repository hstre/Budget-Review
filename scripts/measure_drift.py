"""Screen a graph for claims whose content is not carried by the text they quote.

Anchoring proves that a claim points at a real passage. It cannot prove that
the claim says what the passage says. That is the one blind spot character
arithmetic has by construction, and it is the failure that would matter most
here: an anchored claim reading "the cohort is 250" against a span that says 25
would be invisible to the gate, to the coverage measurement and to both
reviewer arms alike.

Two checks, of very different strength.

The numeric check is hard evidence. A digit sequence in canonical_content that
does not occur in the quoted span cannot have come from it, and for a tool that
reasons about quantities that is the worst silent error available.

Spelled-out numbers have to be folded in on both sides or the check reports
correct work: the frozen budget packet writes "twelve" in the span and 12 in
the claim, which is exactly the normalisation the extraction contract asks for.
Running this against the hand-built packets before trusting it is what surfaced
that, and the table below is the reason those three reports are gone. It is
wider than the one the deterministic rules use, which is left alone so that
rule behaviour and the frozen controls do not move.

The word-overlap check is a screen, not a verdict, and is deliberately reported
as a ranking rather than a threshold. canonical_content is meant to be a
normalised proposition, so it shares fewer words with its span the better it
does its job; a faithful paraphrase can score low. The frozen packets are the
control for what normal looks like, since they were built by hand.

Usage:
    measure_drift.py <dossier-or-packet.json> [more.json ...]
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
DIGITS = re.compile(r"\d[\d.,]*")

# Both languages the dossier speaks. Single words only: a compound like
# "twenty-five" is split on the hyphen and contributes 20 and 5, which is
# enough for a screen and never invents a number that is not written.
NUMBER_WORDS = {
    # "one" and "ein/eine" are left out on purpose: in both languages they are
    # articles at least as often as numerals, and reading "One six-person team"
    # as the quantity 1 reported a correct claim in the rough control. The cost
    # is that a claim writing 1 against a span writing "one" is still reported;
    # that is the rarer direction, and the report is a question, not a verdict.
    "zero": 0, "null": 0,
    "two": 2, "zwei": 2,
    "three": 3, "drei": 3,
    "four": 4, "vier": 4,
    "five": 5, "fünf": 5,
    "six": 6, "sechs": 6,
    "seven": 7, "sieben": 7,
    "eight": 8, "acht": 8,
    "nine": 9, "neun": 9,
    "ten": 10, "zehn": 10,
    "eleven": 11, "elf": 11,
    "twelve": 12, "zwölf": 12,
    "thirteen": 13, "dreizehn": 13,
    "fourteen": 14, "vierzehn": 14,
    "fifteen": 15, "fünfzehn": 15,
    "sixteen": 16, "sechzehn": 16,
    "seventeen": 17, "siebzehn": 17,
    "eighteen": 18, "achtzehn": 18,
    "nineteen": 19, "neunzehn": 19,
    "twenty": 20, "zwanzig": 20,
    "thirty": 30, "dreißig": 30,
    "forty": 40, "vierzig": 40,
    "fifty": 50, "fünfzig": 50,
    "sixty": 60, "sechzig": 60,
    "seventy": 70, "siebzig": 70,
    "eighty": 80, "achtzig": 80,
    "ninety": 90, "neunzig": 90,
    "hundred": 100, "hundert": 100,
    "thousand": 1000, "tausend": 1000,
    "million": 1000000, "millionen": 1000000,
}

# Function words carry no evidence either way, and keeping them would flatter
# every claim equally.
STOPWORDS = frozenset(
    """a an the and or but if then than that this these those of in on at to for with by from
    as is are was were be been being it its their his her our your they we he she you i not no
    nor so such can could may might must shall should will would do does did done have has had
    there here which who whom whose what when where why how all any both each few more most
    other some only own same too very just about into over under again further once""".split()
)


def content_words(text: str) -> set[str]:
    return {word.lower() for word in WORD.findall(text)} - STOPWORDS


def numbers(text: str) -> set[str]:
    """Digit sequences with thousands separators removed, so 1,200 equals 1200.

    Nothing else is normalised. Stripping trailing zeros would turn 250 into 25
    and hide the very substitution this is here to catch. A decimal comma, as
    German writes it, is read as a separator and will not match its English
    spelling — the check errs towards reporting, never towards silence.
    """
    found = set()
    for token in DIGITS.findall(text):
        cleaned = token.replace(",", "").rstrip(".")
        if cleaned:
            found.add(cleaned)
    for word in WORD.findall(text.replace("-", " ")):
        value = NUMBER_WORDS.get(word.lower())
        if value is not None:
            found.add(str(value))
    return found


def claims_of(data: dict) -> list[dict]:
    if "semantic" in data:
        return data["semantic"]["claims"]
    return data["claims"]


def report(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    claims = claims_of(data)
    print(f"=== {path.name}: {len(claims)} Claims ===")

    invented: list[tuple[str, set[str], str, str]] = []
    shares: list[tuple[float, str, str, str]] = []
    for claim in claims:
        content = claim["canonical_content"]
        span = claim["raw_span"]
        identifier = claim.get("proposal_id") or claim.get("claim_node_id", "?")

        extra = numbers(content) - numbers(span)
        if extra:
            invented.append((identifier, extra, content, span))

        words = content_words(content)
        if words:
            share = len(words & content_words(span)) / len(words)
            shares.append((share, identifier, content, span))

    if shares:
        values = [share for share, _, _, _ in shares]
        print(
            f"  Wortdeckung: Median {statistics.median(values):.2f}  "
            f"min {min(values):.2f}  max {max(values):.2f}"
        )
        shares.sort()
        print("  Schwächste fünf (Screening, kein Urteil):")
        for share, identifier, content, span in shares[:5]:
            print(f"    [{share:.0%}] {identifier}")
            print(f"        Claim: {' '.join(content.split())[:100]}")
            print(f"        Stelle: {' '.join(span.split())[:100]}")

    print()
    if invented:
        print(f"  ZAHLEN OHNE DECKUNG IM ZITAT: {len(invented)}")
        for identifier, extra, content, span in invented:
            print(f"    {identifier}: {sorted(extra)}")
            print(f"        Claim: {' '.join(content.split())[:100]}")
            print(f"        Stelle: {' '.join(span.split())[:100]}")
    else:
        print("  Keine Zahl im Claim, die nicht im zitierten Text steht.")
    print()
    return len(invented)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    total = sum(report(Path(argument)) for argument in sys.argv[1:])
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
