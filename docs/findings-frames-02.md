# Findings — which half of the staged procedure does the work

Second run, 2026-10-26, declared in the addendum to `docs/prereg-frames-01.md`
before any call. 154 calls, none failed, 146,896 input and 69,377 output tokens.
No price asserted. Complete inputs and outputs in `runs/frames-02/`.

The first run showed one clear effect — the staged procedure leaves open what
the text leaves open, where arms that read the same text decide — and could not
say which half of the procedure produced it: proceeding in stages, or keeping an
object with candidate readings, explicit `undecided` values and a history.

## The answer: the bookkeeping, not the staging

`B_object` asks for that same object over the whole text **in one call**.

| comparison | correctness | openness |
|---|---|---|
| C against B_object, same stage, same run | +0.024 [−0.034, +0.080] | **+0.006 [−0.050, +0.069]**, pairs 9/8/7 |
| B_object against B, same stage | −0.008 [−0.041, +0.030] | **+0.064 [0.030, 0.101]**, pairs 10/13/1 |
| B_object against D, same stage | −0.024 [−0.063, +0.018] | **+0.054 [0.020, 0.093]**, pairs 9/13/2 |
| B_staged against B, first run | −0.008 [−0.029, +0.015] | −0.003 [−0.017, +0.010] |

Read down that column. Asking for the object in one call gets the restraint
(+0.064 and +0.054 against the two arms that read the same text without it,
both intervals clear of zero). Adding the staging on top of it gets +0.006, with
an interval four times as wide as the effect and the pairs split nine to seven.
And staging *without* the object got nothing at all in the first run.

**The prediction held.** The declared expectation was B_object within 0.03 of C
and clear of B; it came out within 0.006 of C.

So the procedure's one real effect belongs to the cheap half. Asking a model for
a structured object with `undecided` as an available answer, over the whole text,
in a single call, reproduces what four staged calls produce — on this set, at
48 calls instead of 106.

The staged half is not free either. Within the same run, C asserted values the
text excludes more often than B_object: 0.824 against 0.856, **−0.033
[−0.065, −0.007]**, clear of zero and against the staged arm. It also invented
one contradiction where B_object invented none.

## And a second finding, which bears on everything above

C was re-run in the same job so both arms would come from one draw. At
temperature 0, with identical prompts, **1 of 106 replies came back identical**.

The measures moved with it:

| measure | first run | second run | drift |
|---|---|---|---|
| correct | 0.732 | 0.717 | −0.015 [−0.041, +0.006] |
| left_open | 0.804 | 0.785 | −0.020 [−0.039, +0.003] |
| revised_when_due | 0.657 | 0.571 | −0.086 [−0.184, 0.000] |
| held_when_not_due | 0.783 | 0.696 | −0.087 [−0.263, +0.077] |
| contradiction_invented (avoided) | 0.750 | 0.833 | +0.083 [0.000, +0.250] |

That is the yardstick every difference in both runs has to be read against, and
it is not a small one. This repository has withdrawn six claims for exactly this
reason — a comparison made with one run per arm before the spread of one
configuration was known — and the same rule applies to its own new findings.

### Re-read against the drift

* **Openness: stands.** 0.05 to 0.10 between arms against 0.020 of drift, in the
  same direction in two independent runs, and now with the mechanism located in
  the object rather than the staging. This is the one finding the measurement
  supports.
* **Correctness: never was an effect.** The largest difference reported anywhere
  was +0.028; the drift on the same measure is 0.015 and every interval crossed
  zero.
* **Revising when due: not settled.** The first run's +0.171 is about twice the
  drift on that same measure (0.086), from a single run, with an interval that
  touched zero. Downgraded from "suggestive" to "not settled by this
  measurement", and the six-category direction argument goes with it: the drift
  moved that measure by 0.086 between two runs of one arm.
* **The staged arm inventing more contradictions: direction only.** C was the
  worst arm on this in both runs — 0.750 against 0.909/0.917/0.909 in the first,
  0.909 against 1.000 in the second — but the magnitude moved by more than the
  gap. The direction replicated; the size is not established.
* **`exception_kept` stayed 0 of 6** in both arms of the second run too, which
  confirms the withdrawal: the gold encoded one fact twice, and no arm has ever
  satisfied it.

## What this changes in practice

If the point of the procedure is to stop a reading from over-committing, the
part worth building is the object: closed fields with `undecided` as a real
value, candidate readings kept, and each passage placed. The staged loop over
context levels, on text this short, adds cost, one more invented conflict, and
no measurable restraint beyond what one call with the object already gives.

What this does not test: staging on text long enough that the whole of it does
not fit one call usefully. Every case here is two or three sentences, so "the
whole text in one call" is always available. The staging may be exactly what
matters at document length, and nothing in either run speaks to that.

## Caveats specific to this run

* B and D were not re-run beside B_object, so those two comparisons cross runs
  and carry the drift as their noise floor. The drift on openness is 0.020 and
  the differences are 0.064 and 0.054, so they survive it — but they are not as
  clean as the within-run comparison against C.
* One model, one language, 48 constructed cases of two or three sentences.
