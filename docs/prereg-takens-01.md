# Pre-registration — can Haylett's Takens-Based Transformer separate a faithful from a distorted reading?

Committed before the run. What follows is the criterion, not a result.

Subject: `KevinHaylett/takens-embedding-transformer` at commit
`42beb885fcacca5df7a915491478d3128f9b2f1d`
(<https://github.com/KevinHaylett/takens-embedding-transformer/tree/42beb885fcacca5df7a915491478d3128f9b2f1d>),
with the two sets of weights that repository ships:
`models/solar_system/solar_system_model.pt` (vocabulary 1651, English,
1,137,493 parameters) and `models/qba/qba_model.pt` (vocabulary 111, English,
741,713 parameters). No production code of this repository is touched; the
probe lives outside it and reads our case fixture only.

## The question

Our §4.12 failure is one representation problem: the extractor drops the
condition and asserts the consequent on its own. A representation we could
use would have to place a reading that **keeps** the condition closer to the
original than a reading that **drops** it.

Does a sentence representation taken from this implementation do that, better
than counting shared words?

## What the subject provides, and what I had to build

The repository computes per-token hidden states and per-token vocabulary
logits (`mvec_model.MVecLanguageModel.forward`). It provides **no**
sentence-level representation and no similarity measure, so there is nothing
of his to apply. The measure below is therefore **my own construction, not
his**, and a negative result is a result about my construction on his weights,
not about a measure he proposed.

## Measure (my construction)

For a sentence *s*: run the repository's own tokenizer and vocabulary
(`mvec_encoder.MVecEncoder.tokenize`, `.encode_sequence`), take the
delay-stack output `model.tbt(x)` — shape `[1, seq, 128]` — and mean-pool
over positions to one 128-vector `v(s)`. Similarity is cosine.

For each triple (original *o*, faithful reading *f*, distorted reading *d*)
the measure **ranks correctly** iff

    cos(v(o), v(f)) > cos(v(o), v(d))

Ties count as wrong. Our fixture
`src/budget_review/fixtures/semantic_cases/cases.json` yields **106 triples**
(53 German, 53 English) as every `permitted_readings` × `forbidden_readings`
pair per case, `span` as the original.

The condition case `sco-02` and the triple named in the brief
("Wenn die Förderung bewilligt wird, stellen wir zwei Techniker ein." /
"Die Einstellung von zwei Technikern ist für den Fall einer Förderzusage
zugesagt." / "Wir stellen zwei Techniker ein.") are reported separately by
name as well as inside the total.

## Baseline

Token Jaccard overlap on the same tokenizer, same ranking rule. This is a
hard baseline here, not a straw man: the distorted reading is usually a
*shortening* of the original and so shares most of its words, while the
faithful reading *rewords* them. Overlap should often rank wrongly, which is
precisely why beating it would mean something.

## Controls

1. **Delay channels zeroed.** Same weights, but every delayed copy in the
   Takens grid replaced by the pad value, leaving `grid[:, :, 0, :]` only.
   Removes the temporal information and nothing else. If the full model does
   not beat this, the delay embedding contributed nothing to the result.
2. **Word order shuffled.** Each sentence's tokens permuted with a fixed
   seed. If scores barely move, the representation is order-blind.
3. **Untrained weights.** Same architecture, random initialisation, same
   measure. The floor.
4. Both shipped weight sets, reported apart.

## Success criterion

The attempt **succeeds** iff, on the 106 triples:

- the full model ranks correctly in strictly more triples than the Jaccard
  baseline, and that paired difference is clear of zero in a 10,000-draw
  bootstrap resampling **triples** (the same convention as
  `scripts/frame_score.paired_difference`), and
- the full model is above chance in its own right (lower bound of its
  accuracy interval above 0.50), and
- the full model beats control 1, so that some of the effect is the delay
  embedding rather than the token embedding alone.

Anything less is a failure, including a win on English alone, which would be
reported but would not meet the criterion, since our documents are German.

## Prediction, recorded so it can be wrong

I expect failure, for a reason measured before the run: with the repository's
own tokenizer and the larger of its two vocabularies, the German sentences of
the named triple have **2 of 12 tokens in vocabulary, and both are
punctuation** — the comma and the full stop. Across the triple texts,
coverage is 26.6 % (solar_system) and 8.3 % (qba). Every other token becomes
`<unk>` (`encode_word` returns 0 for anything unseen). So I predict:

- German triples at or below chance, and
- a **degeneracy**: distinct German sentences of equal length and punctuation
  collapsing to nearly the same vector, because the only varying input is
  `<unk>`.

## Degeneracy check, reported either way

Fraction of the 106 triples in which `v(f)` and `v(d)` differ by less than
1e-4 in cosine, and the number of distinct vectors among all sentences used.
If the inputs cannot be told apart, the measure cannot work and the headline
number is not interpretable as a statement about the architecture.

## What this run cannot show

It cannot show that the architecture is unsuitable for our problem **in
principle**. It can only show whether *these shipped weights*, with the
repository's own text pipeline and a sentence measure I had to invent, are
usable on our cases now. A negative result names the missing precondition;
it does not refute the idea.
