# Pre-registration — does a staged context check reduce meaning errors?

Committed before any paid call. What follows is the criterion, not a result.

## The question

A statement is interpreted at several context levels — the sentence alone, its
section, the whole text so far, and text that arrives later — and the readings
are required to be compatible, with a larger context allowed to replace a local
reading as the preferred hypothesis while the original and its source are kept.

Does that reduce meaning errors against reading the same text, **without**
removing local exceptions, open ambiguities or real contradictions?

## Arms

Five, 48 held-out cases each, every call in a fresh context, nothing carried
between calls except what the arm puts in its own prompt.

| arm | what it is | why it exists |
|---|---|---|
| A | the statement alone | the floor: what one sentence licenses |
| B | the whole available text in one call | ordinary reading. If C only matches B, the staging bought nothing |
| B_staged | B on each prefix: F1, then F1+F2, … | the fair sequential comparison — the same information horizon as C at every stage |
| C | staged frames, structured object carried forward, history | the procedure under test |
| D | the same full text, revised as many times as C has stages | the budget control. If D matches C, extra calls did the work, not the frames |

B, B_staged, C and D all receive the same interpretive rules: keep a
contradiction rather than resolve it, invent no exception and no temporal
difference, an explicit correction replaces and a later event does not, a
general rule does not displace a precise exception. **What separates C is the
staging, the carried object and the history — not better instructions.** A is
not given the staging rules, because they concern reconciling a new section
with an earlier reading and A never sees one.

What this design cannot separate: the staging from the bookkeeping. C both
proceeds in stages and keeps an object with a history. A sixth arm — one call
over the whole text, asked for the same object with a history — would split
those, and is not run here.

## Primary comparison and criterion

**C against B_staged on `correct`**, the share of explicitly supported meaning
components that the answer gets right, with the difference's 95% interval
resampled over whole minimal pairs rather than cases.

The procedure counts as helping only if **all four** hold:

1. the difference on `correct` is positive and its interval excludes zero;
2. `left_open` — leaving undecided what the text leaves undecided — does not
   fall: its interval does not lie entirely below zero;
3. `exception_kept` and `contradiction_found` do not fall, by the same reading;
4. `contradiction_invented` does not rise.

Any single failure means the procedure did not clear the bar as stated, and
that is reported as the result. A gain on `correct` bought by deciding more
often is not a gain: that is what 2 and 4 are for.

## Predictions

Stated to be wrong about. I expect the procedure to help less than its
description suggests.

1. **C beats B_staged on `correct`, but by little** — under 0.10, and the
   interval may well include zero.
2. **C does not beat D by much on `correct`.** If the difference is near zero,
   a second and third look at the same text is most of what C is.
3. **C loses to B_staged on `held_when_not_due`.** A prompt that hands over an
   object and asks whether to update it invites an update; the control that is
   never asked has nothing to revise.
4. **Every arm is worst on the contradiction category.** Reconciling is what
   these models do; `contradiction_found` will be the lowest measure in all
   five arms.
5. **The largest spread between arms is `left_open`, not `correct`.** One-shot
   reading decides what the text leaves open.
6. **D ≈ B on every measure**, because nothing is added between D's passes.
7. **No arm reaches the ceiling on `correct`.** If one does, the set is too
   easy and the comparison says nothing; that would be reported as a defect of
   the set.

## What the offline run already establishes

No model was called for these; they are facts about the instrument.

* An answer equal to gold reaches 1.00 on all thirteen measures in all five
  arms. The standard is reachable, and gold does not contradict itself.
* Answering `undecided` everywhere scores 1.00 on openness and 0.00 on
  correctness, contradiction-finding, exception-keeping and revision. It cannot
  win.
* Answering `contradictory` everywhere scores 1.00 on contradiction-finding and
  0.00 on its mirror.
* Never revising scores 1.00 on holding and 0.00 on revising.
* An unreadable reply scores zero on every measure, including the avoidance
  ones: silence is not a careful reading.

## Withdrawal rule

* If an arm's `usable` share is below 0.90, that arm's meaning numbers are
  withdrawn and reported as a format failure instead. A procedure that cannot
  return the agreed object has not been measured on meaning.
* If the run stops on its budget or its failure breaker, what completed is
  reported with the number of cases, and no comparison is drawn across arms
  that did not see the same cases.
* The 13 contested field decisions are excluded from every headline number and
  reported separately. F07 is marked contested as a whole case.
* Repeats are measurements of one model, not independent judges, and are never
  counted as additional evidence about the procedure.

## Reach

One model at temperature 0, one language, 48 constructed cases of two or three
sentences each. The cases are built to isolate one distinction at a time, which
is what makes them scorable and also what makes them unlike real documents: no
case is longer than a paragraph, and the decisive sentence is always present
and always well formed.

What this cannot say: whether the procedure helps on a real document, whether
it helps another model, whether it helps in English, or whether the gold
convention — a field not mentioned must be `undecided` — is the convention a
human reviewer would apply.

## Cost

Tokens are recorded for every call. A price is reported only when one is passed
in explicitly; this file asserts no price, because a figure invented here would
be worse than none.

---

## Addendum — the sixth arm, declared before its own run

Committed before any call of the second run. The first run left one question
open by design, and this is the arm that answers it.

### What it tests

C both proceeds in stages and keeps an object with candidate readings, explicit
`undecided` values and a history. Its one clear effect — restraint — could
belong to either half. **B_object** asks for that same object, with the same
bookkeeping, over the whole text in a single call: C's bookkeeping without C's
staging.

The first run already narrows the question. Compared on the stage both answer,
the staged arm *without* the object behaves like the one-shot arm: −0.008 on
correctness and −0.003 on openness. Staging alone moved nothing.

### Prediction

**B_object shows most of C's restraint.** I expect its openness within 0.03 of
C's 0.786 and clear of B's 0.687 — that is, the bookkeeping carries the effect
and the staging is close to decoration on cases this short.

What would refute it: B_object at B's level, with C still above both. That
would mean the incremental reading is load-bearing after all, and the first
run's finding would have to be read as being about staging rather than about
the object.

### How it is read

* Openness for B_object within 0.03 of C and with its interval against B clear
  of zero → the effect is the bookkeeping.
* B_object within 0.03 of B and C's interval against B_object clear of zero →
  the effect needs the staging.
* Anything else → not separated by this run, and reported as not separated.

### What else this run buys

C is run again in the same job, so both arms come from one draw rather than
being compared across runs. That re-run is also a determinism check: the first
run was at temperature 0, and the share of C's answers that come back identical
is reported as a fact about the provider, not as evidence about the procedure.

### Cost

154 calls against the first run's 414. Tokens recorded; no price asserted.

### A correction carried into this addendum

The first run's secondary comparisons summed each arm's own stages, so a staged
arm answering two or three times was set against a one-shot arm answering once.
Restricted to the stage both arms answer, C against B on openness is +0.099
[0.053, 0.146] rather than +0.118, and C against D is +0.089 [0.043, 0.137]
rather than +0.108. Both still clear of zero; the primary comparison was always
staged against staged and is unaffected. The restriction now applies to every
comparison between arms with different stage sets, and `docs/findings-frames-01.md`
carries the corrected figures.
