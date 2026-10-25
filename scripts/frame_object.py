"""The semantic object, and the part of it a script can check.

The procedure under test interprets one statement at four context levels and
requires the readings to be compatible. To measure whether that reduces meaning
errors, the answer has to be checkable without asking a model what it meant —
otherwise the system under test and its examiner come from one family and the
measurement is circular, which is the mistake this repository has already made
once and refuses to repeat.

So the object has two halves. The **closed** fields take one of a declared set
of values, and those are the only fields scored. The **open** fields — the
quoted source, the actor, the preferred reading in words — are kept in the
record for reading afterwards and are never scored for equality, because
scoring free text means judging paraphrase, and a judge of paraphrase is the
thing being tested.

`UNDECIDED` is a value, not a missing field. The whole point of the procedure is
that a reading may be legitimately open, so refusing to answer has to be
expressible — and separately countable, so that answering `undecided`
everywhere cannot win.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

UNDECIDED = "undecided"

# Closed fields: value sets a script can compare. Every one of them has
# `undecided` available, so an honest refusal is always expressible.
CLOSED_FIELDS: dict[str, tuple[str, ...]] = {
    # What kind of statement the source is making.
    "statement_type": (
        "capability", "permission", "obligation", "assertion", "conjecture", UNDECIDED,
    ),
    # Whether the statement is negated as stated.
    "negated": ("yes", "no", UNDECIDED),
    # Whose claim it is: the document speaking, or the document reporting
    # someone else. E is the category that turns on this.
    "attribution": ("document", "third_party", UNDECIDED),
    # The three things the examples keep apart: being able to, being allowed to,
    # and having done it.
    "capability": ("affirmed", "denied", UNDECIDED),
    "permission": ("granted", "denied", "conditional", UNDECIDED),
    # Whether the action named in the statement itself has happened.
    "action_occurred": ("yes", "no", UNDECIDED),
    # Whether the action that the permission is *about* has happened. A
    # completed check, a granted permission and a carried-out change are three
    # facts, and the category that tests this needs all three to be separately
    # expressible: with two slots a model cannot be wrong about the third.
    "effect_occurred": ("yes", "no", UNDECIDED),
    # Whether an obligation is in force for the statement's subject.
    "obligation": ("present", "absent", UNDECIDED),
    "quantifier": ("all", "some", "none", UNDECIDED),
    # Whether a stated exception narrows the rule, and whether a condition
    # applies. B is the category that turns on the first.
    "exception_present": ("yes", "no", UNDECIDED),
    "condition_present": ("yes", "no", UNDECIDED),
    # The object's own state, as the procedure defines it.
    "status": ("open", "context_supported", "restricted", "contradictory", "superseded", UNDECIDED),
}

# Kept, never scored for equality.
OPEN_FIELDS = (
    "object_id",
    "source_quote",
    "actor",
    "action",
    "affected_object",
    "temporal_scope",
    "speaker",
    "candidate_readings",
    "preferred_reading",
    "supporting_quotes",
    "contradicting_quotes",
    "reason",
    "history",
)

# A field whose value decides something, as opposed to declining to.
def is_decided(value: Any) -> bool:
    return value not in (None, "", UNDECIDED)


@dataclass
class ParsedObject:
    """One answer, after parsing. `complaints` is why it is not usable."""

    closed: dict[str, str] = field(default_factory=dict)
    open: dict[str, Any] = field(default_factory=dict)
    complaints: list[str] = field(default_factory=list)
    raw: str = ""

    @property
    def usable(self) -> bool:
        return not self.complaints

    def to_dict(self) -> dict:
        return {
            "closed": self.closed,
            "open": self.open,
            "complaints": self.complaints,
        }


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def _first_json_object(text: str) -> tuple[dict | None, str]:
    """The first JSON object in a reply, fenced or bare."""
    fenced = _FENCE.search(text)
    candidates = [fenced.group(1)] if fenced else []
    start = text.find("{")
    if start >= 0:
        candidates.append(text[start:])
    for candidate in candidates:
        decoder = json.JSONDecoder()
        try:
            value, _ = decoder.raw_decode(candidate.strip())
        except ValueError:
            continue
        if isinstance(value, dict):
            return value, ""
    return None, "no JSON object in the reply"


def parse(text: str) -> ParsedObject:
    """Parse one answer into the object, complaining instead of guessing.

    An unparsable or out-of-vocabulary answer is a result: it is counted as a
    failed case, never silently repaired into the nearest legal value, because
    repairing it would score the repair rather than the answer.
    """
    parsed = ParsedObject(raw=text)
    payload, complaint = _first_json_object(text)
    if payload is None:
        parsed.complaints.append(complaint)
        return parsed

    for name, allowed in CLOSED_FIELDS.items():
        if name not in payload:
            parsed.complaints.append(f"missing closed field {name!r}")
            continue
        value = payload[name]
        if isinstance(value, bool):
            value = "yes" if value else "no"
        if not isinstance(value, str):
            parsed.complaints.append(f"{name}: {value!r} is not one of {allowed}")
            continue
        value = value.strip().lower()
        if value not in allowed:
            parsed.complaints.append(f"{name}: {value!r} is not one of {allowed}")
            continue
        parsed.closed[name] = value

    for name in OPEN_FIELDS:
        if name in payload:
            parsed.open[name] = payload[name]
    return parsed


def differences(before: ParsedObject, after: ParsedObject) -> list[str]:
    """Which closed fields changed between two frames.

    This is how revision is measured: a procedure that must revise has to move
    a field, and one that must not revise has to leave every field alone. A
    change of wording in the preferred reading is not a revision for this
    purpose — only a changed decision is.
    """
    moved = []
    for name in CLOSED_FIELDS:
        if before.closed.get(name) != after.closed.get(name):
            moved.append(name)
    return moved


def schema_for_prompt() -> str:
    """The field list as it is shown to the model.

    Shown in full to every condition, so the answer format is never what
    separates them. It carries no case id and no category: those would leak
    the answer, and the set's validator asserts they are absent.
    """
    lines = ["Antworte ausschließlich mit einem JSON-Objekt mit genau diesen Feldern.", ""]
    lines.append("Geschlossene Felder — jeweils genau einer der erlaubten Werte:")
    for name, allowed in CLOSED_FIELDS.items():
        lines.append(f"  {name}: {' | '.join(allowed)}")
    lines.append("")
    lines.append("Freie Felder:")
    lines.append('  object_id: string')
    lines.append('  source_quote: wörtliches Zitat der Aussage')
    lines.append('  actor, action, affected_object, temporal_scope, speaker: string')
    lines.append('  candidate_readings: Liste von Strings')
    lines.append('  preferred_reading: string oder "undecided"')
    lines.append('  supporting_quotes, contradicting_quotes: Listen wörtlicher Zitate')
    lines.append('  reason: ein bis zwei Sätze mit Quellenverweis, kein Denkprotokoll')
    lines.append("")
    lines.append("Die geschlossenen Felder geben wieder, worauf sich der gezeigte Text")
    lines.append("selbst festlegt. Berichtet der Text nur, was jemand anderes behauptet, so")
    lines.append("ist attribution third_party und der Inhalt bleibt undecided: eine")
    lines.append("wiedergegebene Behauptung ist keine Festlegung des Textes.")
    lines.append('  history: Liste von {frame, change, reason}')
    lines.append("")
    lines.append('"undecided" ist eine Antwort, kein Platzhalter: setze es, wenn der')
    lines.append("gezeigte Text die Frage nicht entscheidet. Erfinde keine Angabe, die")
    lines.append("nicht im gezeigten Text steht.")
    return "\n".join(lines)
