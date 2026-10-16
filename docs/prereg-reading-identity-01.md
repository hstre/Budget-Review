# Pre-registration: the first run of the reading-identity set

**Written and committed before the run was dispatched.** Everything below is
fixed in advance; the commit that adds this file contains no results, and the
run's outcome is reported separately. The point of the practice is that a
criterion chosen after seeing the numbers is not a criterion.

**Cost:** 16 cases × 3 repeats = **48 paid calls**, production prompt, profile
`general`, temperature 0, one session.

## What the instrument can and cannot see

Established before the run, by scoring the set's own declared examples — no paid
call:

| | |
|---|---:|
| Permitted renderings that pass | **16 of 16** |
| Forbidden readings that leak through | **0 of 34** |

That establishes the set is not vacuous. It does **not** establish that the
instrument sees everything the set distinguishes, and the limits differ by
status:

| Status | Fully measurable? |
|---|---|
| `determinate` | **Yes.** The controls require the explicit quantifier, so dropping it fails. |
| `underdetermined_quantifier` | **Yes.** Both resolutions are forbidden, so adding either fails. |
| `evidence_absent` | **Yes.** Hedges and invented attributions are forbidden. |
| `ambiguous` | **No, only half.** The forbids catch a projection that *adds* a commitment the span lacks. Which of the two readings a projection chose is not decidable with token groups when both readings use the span's own words. A pass here means "added nothing", not "kept the ambiguity open". |

This asymmetry is stated now so that a high `ambiguous` figure cannot later be
read as the set having worked.

## Predictions

Each is falsifiable, and each names the number that would refute it. 16 cases ×
3 repeats = 48 case-runs, distributed 18 determinate, 12 underdetermined, 12
ambiguous, 6 evidence-absent.

1. **Failures concentrate on the open plurals.** `underdetermined_quantifier`
   passes **at most 8 of 12**. Refuted by 9 or more.
   *Why:* the documents state the mixed situation ("three of the five sites"), so
   an extractor that resolves the plural from context rather than from the span
   adds a quantifier and fails. arXiv 2610.14438 measures models forcing plurals
   into a binary; this is the extraction analogue of that pressure.
2. **The negated plural is worse than the positive one.** `plu-02` (negated)
   passes **strictly fewer** case-runs than `plu-01`. Refuted by equal or better.
   *Why:* that paper's asymmetry — negated plurals came back as false 84 % of the
   time — is its sharpest finding, and if the pressure transfers at all, it should
   transfer asymmetrically.
3. **The controls hold.** `determinate` passes **at least 16 of 18**. Refuted by
   15 or fewer.
   *Why:* the span carries the quantifier verbatim, and `canonical_content`
   usually mirrors the span closely on one-sentence documents.
4. **No hedging.** `evidence_absent` passes **at least 5 of 6**. Refuted by 4 or
   fewer.
   *Why:* the contract forbids judging whether a claim is true, and adding
   "could" or inventing a source is such a judgement.
5. **The ambiguous cases add nothing.** `ambiguous` passes **at least 10 of 12** —
   and per the table above, this figure is weak evidence either way.
6. **Anchoring holds, as the guard.** At least **90 %** of case-runs anchor a
   claim on their span, the same mark the first set used. **If this fails, the
   meaning figures are not interpretable and will not be reported as results.**
7. **The language line still holds.** **0** translated propositions, in both
   directions.

## What would make me withdraw a case rather than report a failure

If a live run produces a proposition that the scorer passes **and** a reading of
the case says is wrong, the case is defective and is withdrawn before any figure
from it is reported. The first set had twelve such cases and two independent
reviews found them; the lesson is that my own judgement of my own set is the
weakest link in it, so this is written down rather than left to the moment.

Conversely, a case that every run fails is **not** evidence that it is too hard.
It is a candidate for being wrong, and the distinction is decided by reading the
produced propositions, not by the count.

## What this run cannot settle regardless of outcome

* **No edges.** The set annotates no relations, so the relation axis is
  structurally checkable (`relation_algebra.py`) and still not checkable against
  gold.
* **One session.** Everything measured in this project about run-to-run spread
  says a single session is a draw, not a sample. Three repeats inside one session
  measure sampling within a window, which has already been shown to understate
  the across-session spread.
* **Sixteen short cases.** Every document here is at most 122 characters. What a
  contract line does on one sentence says nothing about 26,000 characters of
  court text.
* **Whether spread detects ambiguity.** That was the motivation for the set, and
  it needs the `ambiguous` cases to be *fully* measurable, which per the table
  above they are not. This run can show that failures concentrate where the
  statuses predict; it cannot close the question that prompted the build.
