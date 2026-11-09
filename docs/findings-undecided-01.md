# Findings — the option to decline was offered and never taken

Run 2026-11-09, two draws on the frozen fixture, budget profile, extraction
only. Declared in `docs/prereg-undecided-01.md` before dispatch. Both dossiers
are in `runs/undecided-01/`.

| | draw A | draw B | frozen offline control |
|---|---|---|---|
| claims | 32 | 31 | 25 |
| relations | 14 | 16 | 15 |
| findings | 6 | 6 | 10 |
| **`undecided` claims** | **0 of 32** | **0 of 31** | — |
| schema rejections | 0 | 0 | — |

## The criterion

1. **It still works — holds.** Both draws completed, every claim parsed, no
   rejection. A contract the extractor cannot satisfy would have failed here,
   and it did not.
2. **The option is reachable — fails.** Not one claim in either draw came back
   `undecided`. Under the pre-registered rule this is recorded as *offered and
   never taken*, and **no claim is made that the change improved anything.**
3. **Not a default — holds trivially**, since it was never used at all.

## Why that is the interesting half

The obvious reading of a zero would be that the fixture has no ambiguous
claims. The extractor's own behaviour says otherwise. Thirty spans appear in
both draws, and **two of them are typed differently between the draws**:

```
budget / resource    | The programme will purchase 25 laptops
delivery / method    | Monthly in-person workshops will be delivered at all twelve rural sites
```

Those are exactly the cases the new value exists for: two labels fit, and the
contract now says to decline and name both. In neither draw did it. The
ambiguity is real and it surfaced as **instability across draws rather than as
a declared uncertainty** — the same shape §4.13 measured, where the type
multiset changed in 8 of 24 cases across byte-identical repeats, now with a way
to decline available and unused.

So the restraint measured in §4.21 did not transfer to the extraction contract.
What differs between the two settings is not subtle: there, every field had
`undecided` in its own enumerated value list with its own instruction, and the
task was one statement. Here, `undecided` is the twenty-second entry in a
comma-separated list, with one sentence of instruction, for thirty claims at
once. Whether that is the cause is untested — it is the obvious next thing to
test, not a conclusion.

## A flaw in my own run design

Neither draw produced a single `logical_gap` or `unsupported_assumption`
finding. Those are the two rules that key on `claim_type`, and the whole point
of letting a label be declined is that such a rule should not fire on a label
the extractor had to invent. **On this document the mechanism could not have
been observed even if `undecided` had been used.** The fixture was chosen
because the production prompt reaches it in full; it should also have been
chosen for firing the rules in question, and it was not.

## Reported, not scored

The live-to-live spread on this document and profile: 1 claim, 2 relations, 0
findings. That is a second draw's worth of noise floor for anything measured
here later, and it is far smaller than the frame runs' drift — a different
prompt family, as decision 10 anticipated.

The live counts run above the frozen offline control (32 and 31 against 25).
The control replays a stored packet and the live run extracts afresh, so the
two are not the same measurement; no conclusion is drawn from the difference.

Token counts were not captured on this path. The smoke job does not record
usage the way the frame runner does, so this run reports four calls and no
token figure rather than an invented one.

## What stands

The contract change stays in. Nothing broke, the schema holds both ways, the
offline controls did not move, and the value is a precondition for any later
attempt to make it usable. What does not stand is any claim that it helps: on
the one document measured, it is a field the extractor never reaches for, on
spans where its own two draws disagree.
