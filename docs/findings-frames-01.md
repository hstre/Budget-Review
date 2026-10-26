# Findings — does a staged context check reduce meaning errors?

Run on 2026-10-25 through the repository's paid workflow, 414 calls, none
failed, 17 minutes of wall clock. 356,559 input and 153,732 output tokens. No
cost is claimed here: tokens are recorded, and the price per million has to come
from the provider's own account page rather than from this file.

Criterion and predictions were fixed in `docs/prereg-frames-01.md` before the
first paid call. The run's complete inputs and outputs are in
`runs/frames-01/`; `comparison.txt` is the criterion applied by
`scripts/frame_compare.py`.

## The answer

**The criterion is not met.** The staged context check does not read the text
more correctly than one-shot reading of the same text.

| arm | correct | left_open | contradiction found | invented (avoided) | revised when due | held when not due | usable |
|---|---|---|---|---|---|---|---|
| A — statement alone | 0.76 / 248 | 0.80 / 328 | — | — | — | — | 1.00 |
| B — whole text, one call | 0.69 / 252 | 0.69 / 313 | 1.00 / 4 | 0.91 / 11 | — | — | 1.00 |
| B_staged — one call per prefix | 0.72 / 548 | 0.68 / 711 | 1.00 / 5 | 0.92 / 12 | 0.49 / 35 | 0.74 / 23 | 1.00 |
| **C — staged, object carried** | **0.73 / 548** | **0.80 / 711** | 1.00 / 5 | 0.75 / 12 | 0.66 / 35 | 0.78 / 23 | 1.00 |
| D — same text, revised as often as C | 0.71 / 252 | 0.70 / 313 | 1.00 / 4 | 0.91 / 11 | — | — | 1.00 |

The primary comparison, C against the arm with the same information horizon:

* **correctness +0.011, interval [−0.030, +0.051]**, 9 of 24 pairs favouring C,
  8 favouring B_staged, 7 level. Part 1 of the criterion fails.
* openness **+0.121, interval [0.074, 0.167]**, 16 pairs to 2. Part 2 holds, and
  this is the largest effect in the run.
* contradictions found: 1.00 against 1.00. Part 3 holds, trivially.
* contradictions invented: C avoided 9 of 12, B_staged 11 of 12 —
  **−0.167, interval [−0.385, 0.000]**. Part 4 holds only because the interval
  touches zero; the direction is against C and is reported as such.

So the honest summary is not "it works" and not "it does nothing". It is: **the
procedure buys restraint, not accuracy, and pays for it with contradictions it
invents.**

## What the measurement supports

**Carrying a structured object with explicit `undecided` values preserves
openness, against every alternative.** C leaves open what the text leaves open
in 0.80 of the opportunities, against 0.68 for the same information read in one
call per prefix (+0.121, [0.074, 0.167]). Against the two arms that answer once,
compared on the stage all three answer: 0.786 against 0.687 for the whole text
in one call (+0.099, [0.053, 0.146], 15 pairs to 2) and against 0.697 for the
same text revised as often as C has stages (+0.089, [0.043, 0.137], 14 to 2).
Three comparisons, three intervals clear of zero, same direction.

A fourth figure places the effect further. **Staging alone, without the object,
moves nothing:** the prefix arm against the one-shot arm is −0.008 on
correctness and −0.003 on openness, both intervals across zero and both arms
level on 16 of 24 pairs. Whatever C does, it is not the staging by itself. Which
half of C carries it is what the second run asks.

**Context costs restraint, and the staged object gives it back.** Comparing the
local arm against the one-shot arm *at the stage both answer*, correctness is
indistinguishable (+0.012, [−0.018, +0.042]) while openness falls by 0.098
([−0.142, −0.053]) once the section is shown. A sentence read alone is held
open; the same sentence with its section attached gets decided. C ends up at the
local arm's level of restraint (0.80 against 0.80) while reading three times as
much text.

**Revising when something relevant arrives is better, in every category.** C
revises when gold requires it in 0.657 of the opportunities against 0.486
(+0.171, interval [0.000, 0.333], 8 pairs to 2). The interval touches zero, so
on its own that is suggestive rather than settled — but broken out by category
the direction is the same in all six, with one tie: 0.75 against 0.50, 1.00
against 1.00, 0.60 against 0.40, 0.71 against 0.57, 0.33 against 0.00, 0.33
against 0.17. Six categories in one direction is harder to get by accident than
one interval suggests.

**The version history survives.** C returned a history with at least one entry
per completed stage in 57 of 58 staged calls.

**Nothing was quoted that was not there.** Across 414 calls and 1,068 quoted
spans, every quote was a verbatim substring of the text shown at that point.

## What the measurement does not support

**That the procedure reads more correctly.** +0.011 on correctness, interval
across zero, and the pair count is nearly even. On the categories where it does
help — capability against permission, 0.93 against 0.85 — it loses elsewhere:
on time and correction it is 0.57 against 0.59.

**That the frames rather than the extra calls do the work.** C against D, the
same full text revised as many times as C has stages: +0.021 on correctness,
interval [−0.028, +0.070]. And D against B — the same text looked at again with
nothing added — is +0.016 on correctness and +0.010 on openness, so the extra
passes themselves do nearly nothing. The frames are not what the extra calls
buy, but the extra calls are not what C's advantage is either: C's advantage is
restraint, and D does not have it.

**That it protects against inventing a contradiction.** It is the only arm that
got worse here. Three stages where gold forbids the verdict:

* `F06/F2` — "Bis zum 1. März bestand keine Schreibberechtigung." then
  "Korrektur: Die Berechtigung bestand schon vor dem 1. März." C called it
  contradictory; B_staged called it superseded, which is what an explicit
  correction is. C's own reason names the correction and then files it as a
  conflict anyway.
* `C05/F2` — two named sources asserting opposite permissions. C called it
  contradictory although its reason says correctly that the text commits to
  neither.
* `C02/F2` — the same rule for two different days. Both staged arms called it
  contradictory.

A procedure asked at every stage whether the new section conflicts with the
reading finds conflicts. That is the cost of the question.

## One measure withdrawn, and why

`exception_kept` scored **0 of 6 in all five arms**. The cause is a defect in
the declared gold, not a failure in the answers: every arm reported
`exception_present: yes` and kept `quantifier: all`, and the gold additionally
required the quantifier to stop being `all`.

That second requirement is a second encoding of the same fact. The schema holds
the exception in a field of its own, so "every write needs approval, except
automatic timestamps" is fully represented by `quantifier: all` plus
`exception_present: yes`. Demanding that the quantifier also be downgraded was
my convention and not an evident reading, and five arms agreeing against it is
the evidence that matters.

The measure is therefore withdrawn as declared. Under the alternative
convention — the exception is recorded and no general permission is derived —
the numbers are C 6 of 6, every other arm 5 of 6. **That number is post hoc.**
It was computed after seeing the answers, it is not part of the criterion, and
it cannot be used to claim the procedure helps.

The declared gold stays in the repository unchanged. Changing it now would make
the next run's result incomparable with this one for a reason that has nothing
to do with the procedure.

## Predictions

Five held, two refuted.

| | prediction | outcome |
|---|---|---|
| 1 | C beats B_staged on correctness, by under 0.10, interval possibly across zero | **held** — +0.011, [−0.030, +0.051] |
| 2 | C does not beat D by much | **held** — +0.021, [−0.028, +0.070] |
| 3 | C loses to B_staged on holding when nothing is due | **refuted** — C 0.78 against 0.74, +0.043 |
| 4 | every arm is worst on contradictions; finding them is the lowest measure | **refuted** — every arm found every declared contradiction, 1.00; the category is the hardest for correctness (0.57–0.64), but detection is the *highest* measure in the run |
| 5 | the largest spread between arms is openness, not correctness | **held** — openness 0.68 to 0.80, correctness 0.69 to 0.76 |
| 6 | D ≈ B on everything | **held** — +0.016 and +0.010 |
| 7 | no arm reaches the ceiling | **held** — best correctness 0.76 against a reachable 1.00 |

Prediction 4 is the one worth keeping. I expected these models to reconcile a
contradiction away, and on cases built to be unresolvable they did not: all five
arms marked every declared contradiction. The failure is in the other direction
— they mark conflicts that are not there — and the staged procedure does it most.

## A defect this run exposed in the instrument

The first reading of this run reported that context makes correctness *worse*,
0.72 against 0.76 with an interval clear of zero. That was an artifact: the
local arm is asked once, about the first frame, and the staged arms are asked at
every frame, so summing each arm's own stages compared two different sets of
questions. Restricted to the stage both arms answer, the difference is +0.012
with an interval across zero. `frame_compare.py` now restricts any comparison
involving the local arm to that stage, and a test holds the distinction.

The finding that survives the correction is the openness one, which was clear of
zero in both readings.

## Reach

One model at temperature 0, one language, 48 constructed cases of two or three
sentences. Every case is built so that one distinction decides it, which is what
makes it scorable and also what makes it unlike a real document.

Two limits of the design, both declared before the run:

* **Staging and bookkeeping are not separated by this run.** C both proceeds in
  stages and keeps an object with a history. The sixth arm that splits them —
  the whole text in one call, asked for the same object — is declared in the
  addendum to the pre-registration and run separately.
* **The fourth context level is not tested as itself.** Later text arrives in
  this set as just another frame; nothing distinguishes "a section further down"
  from "a passage added after the reading was complete".

What the run cannot say: whether any of this holds on a real document, in
another language, on another model, or under a different convention for what a
field not mentioned by the text should contain.
