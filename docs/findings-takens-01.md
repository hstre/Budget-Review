# Findings — Haylett's Takens-Based Transformer against our condition cases

Criterion and measure fixed beforehand in `docs/prereg-takens-01.md`
(commit `613efb1`). Dossier: `runs/takens-01/`. No production code of this
repository was changed; the probe reads `src/budget_review/fixtures/
semantic_cases/cases.json` and nothing else of ours.

Subject: `KevinHaylett/takens-embedding-transformer` at commit
[`42beb88`](https://github.com/KevinHaylett/takens-embedding-transformer/tree/42beb885fcacca5df7a915491478d3128f9b2f1d).

## Answer

No — not with what the repository ships. The pre-registered criterion was
formally met by one of the two weight sets, and that result is **void**: the
same measure scores as well with **untrained, random weights**, and a
baseline that looks only at sentence length scores as well again. What the
measure separated was length, not meaning. The missing precondition is named
in §6.

## 1. What the code computes

| claim | where | what it is |
|---|---|---|
| the delay embedding | `takens_embedding.py:TakensEmbedding.forward` | builds `[batch, seq, 1+8, dim]`; channel 0 is the token embedding, channel *j* is the same tensor shifted by `delays[j]`, zero-padded before the start. Default delays `[1,2,4,8,16,32,64,128]` |
| the "adaptive" variant | `takens_embedding.py:AdaptiveTakensEmbedding.forward` | flattens that grid and applies one `nn.Linear`. Despite its docstring ("learns to weight different delays") it is the same linear map as the non-adaptive path plus a LayerNorm and dropout |
| a layer | `tbt_architecture.py:TBTLayer.forward` | `x + ff(norm(x))` — position-wise, no token mixing |
| the stack | `tbt_architecture.py:TakensTransformer.forward` | delay embedding, then *N* such layers, then a norm |
| the model | `mvec_model.py:MVecLanguageModel.forward` | token embedding ⊕ a 3-way identity embedding, the stack, two linear heads: vocabulary logits and a binary end-of-turn logit |

`tbt_architecture.py:3` states it plainly: "Attention-free sequence model
using delay-coordinate embeddings." That is accurate. **The delay grid is the
only place in the whole model where information crosses token positions.**
Everything after it is position-wise. Verified by search: no attention module,
and the only `softmax` calls are over the vocabulary at sampling time.

I verified the grid is literally lagged copies rather than anything inferred —
`runs/takens-01/trace.txt`, position 11 of a 12-token input:

    grid[0,11,0] == x[0,11]        : True
    grid[0,11,j] == x[0,11-delay]  : [(1,True),(2,True),(4,True),(8,True),
                                      (16,pad=0.0),(32,…),(64,…),(128,…)]

## 2. Attractors and basins of attraction: no

Searched the whole repository. In Python, "attractor" occurs **once**:
`training_utils.py:149 generate_lorenz_attractor`, a synthetic Lorenz
time-series generator used to make test data. "Manifold" occurs only inside
`print` statements in four training scripts. "Basin" does not occur in any
`.py` file at all; in `README.md:3` it is used for a "research basin" of
related literature, a metaphor, not a basin of attraction.

Nothing estimates a delay or an embedding dimension (no mutual information,
no false-nearest-neighbours), nothing computes a Lyapunov exponent, a
recurrence plot, or any attractor diagnostic. The delays are the fixed
constant list above.

So: the code uses the **form** of a delay-coordinate embedding — concatenate
`x(t)`, `x(t-1)`, `x(t-2)`, … — and invokes Takens' theorem as the reason
that form is appropriate. It does not reconstruct, test, or use an attractor.
Treated as an architecture, it is a fixed-lag context window flattened into a
linear layer, which is a legitimate thing to build and much older than the
framing; treated as dynamical-systems analysis, there is none in the code.

The repository is candid about its status. `SCOPE_AND_LIMITATIONS.md`:
"purely as a proof of principle", "The author is not a professional software
engineer", "developed with the assistance of Large Language Models", "not
intended to serve as a production-grade system, research benchmark, or
general-purpose language modelling library", with "Simplified text encoding
and tokenisation" and "Minimal vocabulary handling" listed as known limits.
Nothing below contradicts the author's own description of his work.

Two files (`README.md:3`, `llm.txt`) address automated readers directly and
ask them to reconstruct the surrounding research rather than match surface
terminology. That request is noted; it is not a reason to report the code as
doing something it does not do, and the finding above concerns the code only.

## 3. There is no sentence representation, so the measure is mine

`forward` returns per-token hidden states `[1, seq, 128]` and per-token
logits. The repository offers no sentence vector and no similarity measure.
Everything comparative below rests on **my own construction** — mean-pool the
stack output over positions, compare by cosine — and a negative result is
therefore a result about *my* measure on *his* weights.

## 4. The weights, and the language they were trained in

Both shipped checkpoints are **English**, tiny, and closed-vocabulary.

| | `solar_system` | `qba` |
|---|---|---|
| vocabulary | 1651 words | 111 words |
| parameters | 1,137,493 | 741,713 |
| embed / hidden / layers | 128 / 128 / 4 | 128 / 128 / 4 |
| training data | 9419 Q&A rows about the planets, 1651 distinct words (`solar_system.csv`) | 64 trivia Q&A rows, 111 distinct words (`qba_basic.csv`) |
| final val word loss | 0.119 | 0.339 |

The only other corpora in the repository (`models/brown/brown.txt`,
`models/corpus_ancora/`) ship **without weights**. There is no German model,
and no multilingual model.

Measured with the repository's own tokenizer and vocabulary
(`runs/takens-01/vocabulary-coverage.txt`): across the German and English
texts of our condition triples, `solar_system` knows 26.6 % of tokens and
`qba` 8.3 %. For the sentence named in the brief,

    Wenn die Förderung bewilligt wird, stellen wir zwei Techniker ein.

`solar_system` knows **2 of 12 tokens, and both are punctuation** — the comma
and the full stop. Everything else becomes `<unk>`
(`mvec_encoder.py:encode_word` returns 0 for anything unseen). The model's own
top prediction for that input is `<unk>` at logit 20.6. On the English
control "How hot is Mercury?" it answers sensibly ("Mercury", 16.4), so the
pipeline works — on the vocabulary it was trained on.

The repository ships `vocab_checker.py`, whose stated purpose is to "identify
OOV words before inference". The limitation is the author's own.

## 5. The run, and why its one success is void

106 triples from our fixture (53 German, 53 English), plus the triple named
in the brief. Accuracy = fraction where
`cos(v(original), v(faithful)) > cos(v(original), v(distorted))`.
Intervals are 10,000-draw bootstraps resampling triples.

| arm | `solar_system` | `qba` |
|---|---|---|
| full model | 0.698 [0.61, 0.78] | 0.774 [0.70, 0.85] |
| delay channels zeroed | 0.642 [0.55, 0.74] | 0.406 [0.31, 0.50] |
| word order shuffled | 0.679 [0.58, 0.76] | 0.774 [0.69, 0.85] |
| **untrained (random weights)** | **0.764 [0.68, 0.84]** | **0.783 [0.71, 0.86]** |
| Jaccard word overlap | 0.660 [0.58, 0.75] | 0.660 [0.58, 0.75] |
| full − Jaccard | +0.038 [−0.066, +0.142] | +0.113 [+0.009, +0.208] |
| full − delays zeroed | +0.057 [−0.028, +0.142] | +0.368 [+0.264, +0.472] |

Against the pre-registered criterion: `solar_system` **fails** (it does not
beat overlap). `qba` **meets all three parts** — above overlap clear of zero,
above chance in its own right, above the zeroed-delay control clear of zero.

That success is void, for three reasons measured in the same run:

1. **Untrained, randomly initialised weights score 0.783** — at least as well
   as the trained model, which they cannot do if the number reflects anything
   the training learned. The two arms give the *same verdict in 103 of 106
   triples* (`runs/takens-01/diagnose.txt`, post hoc).
2. **A baseline that knows only sentence length scores 0.764** (post hoc:
   "the faithful reading wins iff its token count is nearer the original's").
   The full model agrees with it in 97 of 106 triples. Our distorted readings
   are shortenings and our faithful readings are rewordings, so length alone
   separates them — and that is all the measure found.
3. **Shuffling word order changes the verdict in 2 of 106 triples.** A
   representation that is this close to order-blind is not reading syntax, let
   alone a condition.

Supporting evidence of the same thing: the cosine between *any* two sentences
is at least 0.966 under `qba` (median 0.998); 12 of 53 German triples are
degenerate, with the faithful and distorted readings less than 1e-4 apart; 56
of 106 triples have 100 % out-of-vocabulary input, and the model scores 0.750
on exactly those — it is scoring where it can read nothing at all.

The named cases are "correct" for the same empty reason:

    sco-02-de  cos faithful +1.0000  distorted +0.9983  -> ok
    brief      cos faithful +0.9999  distorted +0.9983  -> ok (Jaccard: wrong)

Both German triples consist, as far as this model can see, of a comma, a full
stop and ten unknown tokens.

**My pre-registration was under-specified, and I am recording that as my own
error.** I listed the untrained floor as control 3 but did not put it in the
criterion, so a measure driven by sentence length could pass. The criterion
should have required the full model to beat the untrained floor. Stated for
the next run of this kind: *a comparison measure must beat random weights of
the same architecture before any other comparison counts.*

One thing the run does show, and it is worth keeping: **Jaccard overlap ranks
the brief's own triple wrongly** (faithful 0.09, distorted 0.38, because the
faithful reading rewords everything while the distorted one copies). Word
overlap is genuinely unfit for this job. That raises the value of finding a
real representation; it says nothing in this one's favour.

## 6. The missing precondition

A meaningful run needs a model whose vocabulary covers the text. Here, that
means training this architecture from scratch on German governance prose —
the repository's own `unified_training.py` is the path, with a corpus we do
not have, at a vocabulary and parameter scale two to three orders of
magnitude above the shipped models. Until that exists, every number computed
on our cases measures tokenisation artefacts.

## 7. What this does and does not settle

It settles that the shipped artefacts cannot be tried on our failure cases:
the inputs do not survive the tokenizer. It does not settle whether a
delay-coordinate architecture, trained properly, would represent a condition
better than attention — that question is untouched by this run, and the
author does not claim the shipped code answers it either.
