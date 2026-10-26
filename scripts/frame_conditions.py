"""The four conditions, and the two controls that make the comparison mean something.

The claim under test is that interpreting a statement at several context levels,
in order, with a structured object carried between them, produces fewer meaning
errors than reading the same text. Two things could produce an apparent
advantage without the procedure being worth anything:

* **more text at once.** Condition B reads the whole available text in one
  request. If B matches C, the staging bought nothing over ordinary reading.
* **more calls.** Condition D revises its own answer over the same full text,
  as many times as C has stages on that case. If D matches C, the advantage was
  the extra passes and not the frames.

One arm exists to split what the first run could not: C both proceeds in
stages and keeps an object with candidate readings and a history, and the
restraint it showed could belong to either half. **B_object** asks for that same
object, with the same bookkeeping, over the whole text in a single call. If it
shows C's restraint, the bookkeeping is what does the work and the staging is
decoration; if it does not, the staging is load-bearing. The first run already
narrows the question: the staged arm without the object behaves like the
one-shot arm with it, to within a hundredth on both measures.

And one thing could produce an apparent advantage *for* B that is not fair:
B sees later text while C is still deciding on earlier text. A per-stage
comparison of B against C would then compare different information. So B is
also run on each prefix — F1 alone, then F1+F2, and so on, in a fresh context
each time. That arm is what the sequential comparison uses; plain B stays as
the one-shot reading of everything.

Every call is stateless: nothing is carried between calls except what a
condition puts in its own prompt. C carries the object it produced, which is
the procedure; D carries its own previous answer, which is the control.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("frame_object", HERE / "frame_object.py")
frame_object = importlib.util.module_from_spec(_spec)
sys.modules["frame_object"] = frame_object
_spec.loader.exec_module(frame_object)

CONDITIONS = ("A", "B", "B_staged", "C", "D", "B_object")

ROLE = (
    "Du liest einen Text und hältst fest, worauf er sich festlegt. Du erfindest "
    "nichts, was nicht im gezeigten Text steht, und du entscheidest nichts, was "
    "der gezeigte Text offen lässt."
)

TASK = (
    "Gib für die unten markierte Aussage ein semantisches Objekt zurück. "
    "Trenne dabei, was jemand kann, was jemand darf, was jemand muss und was "
    "tatsächlich geschehen ist: das sind verschiedene Angaben, und eine belegt "
    "die andere nicht."
)

_STAGE_RULES = (
    "Wenn der neue Abschnitt der bisherigen Lesart widerspricht und beide "
    "gleichzeitig gelten sollen, halte den Widerspruch fest statt ihn "
    "aufzulösen. Erfinde keine Ausnahme, keine Spezialregel und keinen "
    "zeitlichen Unterschied, um Verträglichkeit herzustellen. Eine ausdrückliche "
    "Berichtigung ersetzt die frühere Angabe; ein späteres Ereignis macht eine "
    "zutreffende frühere Angabe nicht rückwirkend falsch. Eine allgemein "
    "formulierte Regel verdrängt eine genau umgrenzte Ausnahme nicht."
)


def _frames_up_to(case: dict, after: str) -> list[dict]:
    labels = [frame["frame"] for frame in case["frames"]]
    return case["frames"][: labels.index(after) + 1]


def _running_text(frames: list[dict]) -> str:
    return "\n\n".join(frame["text"] for frame in frames)


def _statement(case: dict) -> str:
    return case["frames"][0]["text"]


def build(case: dict, after: str, condition: str, previous: str | None = None,
          passes_done: int = 0) -> tuple[str, str]:
    """The (system, user) pair for one call.

    `previous` is the model's own previous answer: the object for C, the earlier
    draft for D. Nothing else crosses a call boundary.
    """
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition!r}")
    frames = _frames_up_to(case, after)
    schema = frame_object.schema_for_prompt()
    system = f"{ROLE}\n\n{schema}"

    if condition == "A":
        # The statement by itself. Nothing else is shown, and the answer is
        # expected to say so where the sentence does not decide.
        body = (
            f"{TASK}\n\nAussage:\n{_statement(case)}\n\n"
            "Dir liegt nur dieser Satz vor."
        )
        return system, body

    if condition == "B_object":
        # C's bookkeeping without C's staging: the whole text at once, and the
        # same demands — several readings where the text allows several,
        # `undecided` where it decides nothing, each later passage placed, and
        # the development of the reading kept with the original.
        body = (
            f"{TASK}\n\nText:\n{_running_text(frames)}\n\n"
            f"Die Aussage, um die es geht, ist: {_statement(case)}\n\n"
            "Halte mehrere Lesarten fest, wenn die Aussage mehrere zulässt, und "
            "setze die geschlossenen Felder auf undecided, solange der Text sie "
            "nicht entscheidet. Ordne jede weitere Textstelle ein: Präzisierung, "
            "Einschränkung, Ausnahme, Gegenbehauptung, Berichtigung oder ohne "
            "Belang. Lege dich nur mit Begründung und Quellenverweis fest. Trage "
            "in history ein, wie sich die Lesart durch den Text entwickelt, und "
            f"erhalte die ursprüngliche Angabe und ihre Quelle.\n\n{_STAGE_RULES}"
        )
        return system, body

    if condition in ("B", "B_staged"):
        body = (
            f"{TASK}\n\nText:\n{_running_text(frames)}\n\n"
            f"Die Aussage, um die es geht, ist: {_statement(case)}\n\n{_STAGE_RULES}"
        )
        return system, body

    if condition == "C":
        if previous is None:
            body = (
                f"{TASK}\n\nAussage:\n{_statement(case)}\n\n"
                "Dies ist die erste Stufe: dir liegt nur diese Aussage vor. "
                "Halte mehrere Lesarten fest, wenn der Satz mehrere zulässt, "
                "und setze die geschlossenen Felder auf undecided, solange der "
                "Satz sie nicht entscheidet."
            )
            return system, body
        body = (
            f"{TASK}\n\nAussage:\n{_statement(case)}\n\n"
            f"Bisheriges Objekt:\n{previous}\n\n"
            f"Neu hinzugekommener Abschnitt:\n{frames[-1]['text']}\n\n"
            "Prüfe das bisherige Objekt gegen den neuen Abschnitt und gib das "
            "aktualisierte Objekt zurück. Ordne den Abschnitt ein: Präzisierung, "
            "Einschränkung, Ausnahme, Gegenbehauptung, Berichtigung oder ohne "
            "Belang. Ändere eine Festlegung nur mit Begründung und Quellenverweis; "
            "lass sie stehen, wenn der Abschnitt sie nicht berührt. Trage jede "
            "Änderung in history ein und erhalte die ursprüngliche Angabe und "
            f"ihre Quelle.\n\n{_STAGE_RULES}"
        )
        return system, body

    # D: the same full text again, with its own draft, as often as C has stages.
    if previous is None:
        return build(case, after, "B")
    body = (
        f"{TASK}\n\nText:\n{_running_text(frames)}\n\n"
        f"Die Aussage, um die es geht, ist: {_statement(case)}\n\n"
        f"Dein bisheriger Entwurf:\n{previous}\n\n"
        f"Überarbeite den Entwurf (Durchgang {passes_done + 1}). Dir liegt derselbe "
        "Text vor wie zuvor; nichts ist hinzugekommen. Korrigiere, was der Text "
        f"nicht trägt, und gib das Ergebnis im selben Format zurück.\n\n{_STAGE_RULES}"
    )
    return system, body


def render(case: dict, after: str, condition: str) -> str:
    """One string per call, for the leak check in frame_cases.py."""
    system, user = build(case, after, condition, previous="{}" if after != "F1" else None)
    return f"{system}\n{user}"


def plan(case: dict, condition: str) -> list[str]:
    """Which stages a condition is asked about, in order.

    A is asked once about the statement alone. B is asked once about everything.
    C and B_staged are asked at every frame. D is asked as many times as C,
    always about everything, so the call counts match and the comparison is
    about the frames rather than the budget.
    """
    labels = [frame["frame"] for frame in case["frames"]]
    if condition == "A":
        return [labels[0]]
    if condition in ("B", "B_object"):
        return [labels[-1]]
    if condition in ("B_staged", "C"):
        return labels
    return [labels[-1]] * len(labels)
