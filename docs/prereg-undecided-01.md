# Pre-registration — does the extractor use the option to decline?

Committed before the run. Two draws, as decision 10 requires.

## The question

`claim_type` now accepts `undecided` with at least two named candidates
(§3as). The gain measured in §4.21 was restraint from a closed field with a way
to decline — but that was measured on 48 constructed two-sentence cases with a
different prompt and a different schema. Whether a real extraction over a real
document uses the value at all is a separate question, and the offline controls
cannot answer it: they replay stored packets and never see a prompt.

Three things could be true, and they need different responses:

* the option is **never taken** — the contract changed and nothing did;
* the option is **taken everywhere** — the contract bought silence rather than
  restraint, which is the failure the frames work was built to catch;
* the option is **taken sometimes**, on claims where two labels fit.

## The run

The repository's own frozen fixture, budget profile, extraction only, no
reviewer arms. Two draws, dispatched separately. Four calls at most. The
fixture is the regression control the production prompt reaches in full, and
its offline control is 25 claims / 15 relations / 10 findings.

## Criterion

1. **It still works.** Both draws complete and every claim parses. A malformed
   `candidate_types` is a schema error, so a contract that the extractor cannot
   satisfy fails here rather than in production — this is the first thing being
   tested, not a formality.
2. **The option is reachable.** At least one claim across the two draws comes
   back `undecided`. If none does, the contract change is recorded as offered
   and never taken, and no claim is made that it improved anything.
3. **The option is not a default.** Fewer than half the claims in either draw
   are `undecided`. Above that, the change is withdrawn: an extractor that
   declines most labels has stopped answering, and the two label-keyed rules
   would go quiet with it.

## Reported, not scored

* The claim, relation and finding counts of both draws against the frozen
  control's 25 / 15 / 10, and against each other — the second draw is also the
  noise floor for the first.
* For every `undecided` claim: its span and its candidates. Whether those were
  genuinely cases where two labels fit is a judgement I will state as mine, not
  a number. Nothing here makes that judgement mechanical, and calling it one
  would be the substitution this project keeps finding.

## Reach

One document of about 1,700 characters, one profile, one model, two draws.
A fixture the prompt is known to reach in full is the easiest case there is:
it says whether the option is usable, not how often it should fire on a court
decision.
