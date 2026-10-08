# Changelog

Notable changes per release. Dates are release dates; the format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

The frozen offline controls are the reference for behaviour changes; every entry
says when it moves them. Their current values are `polished` 5 claims /
5 relations / 3 findings, `rough` 4 / 4 / 0, `budget` 25 / 15 / 10.

## [Unreleased]

### Measured

- **A claim's type is the third generated component, and nothing had ever looked
  at it.** §4.5 separated `raw_span` (a selection into the document, reproducible)
  from `canonical_content` (a generation, the unstable half). The type is also a
  generation. Measured offline from runs already paid for, over 24 documents with
  three byte-identical repeats each: **8 of 24 change their claim-type multiset.**
  `neg-02` alternates between `fact` and `scope` in both languages and in opposite
  run positions, so it is a coin flip between two names rather than a language
  artifact; `sco-01-de` alternates between `fact` and `causal`, and `causal` is
  explicitly a distortion marker in another case.
- **Two shipped findings fire on that type.** `logical_gap` at confidence 0.9 and
  `unsupported_assumption` at 0.95 — whose type precondition flips in 1 of 24. The
  type is also hashed into the claim node id, so a different type is a different
  node and every edge to it moves with it.
- **Confidence does not catch it, and could not have.** 0.934 against 0.931 for
  the stable cases, no separation, and the field is degenerate: 233 of 242 claims
  sit on exactly 0.9 or 0.95. Gating on confidence was never available.
- **The precise statement, because the obvious one is wrong.** Not "the extractor
  is unstable". The extraction contract names twenty-one claim types and defines
  none of them, so for a sentence where two labels are both defensible there is no
  fact of the matter about which is right. The vocabulary has **no truth
  conditions**, and a 0.95-confidence finding stands on it.
- Noticed while writing the tests: **the two label-keyed rules only run in the
  `general` profile.** The budget profile never reaches them, so the exposure is
  profile-specific.

### Changed

- **Every deterministic rule now declares what its trigger rests on** —
  `document`, `content`, `relation_type` or `claim_type` — on
  `Finding.trigger_rests_on`, from one table beside the rule prose rather than
  from fourteen call sites, so a rule cannot be added without declaring it. A test
  asserts every message key is in the table.
  The choice was to ship the provenance rather than remove the dependency, so that
  a later reflection run can take it up: keeping information beats discarding it,
  and removing the dependency stays open afterwards while the converse does not.
  The marker discriminates rather than being constant — `coverage_gap` is computed
  from the document and the anchors, the budget rules from the claim text, and only
  two of fourteen stand on the undefined label.
  It travels into the dossier JSON **and onto the rendered page**, in Markdown and
  HTML and both languages, because `anchor_ambiguous` is the precedent for what
  happens otherwise: set by the gate since it was built and read by no part of the
  product, only by a measurement script.
  The rendered caveat carries **no number** — the 8-of-24 comes from cases of one
  to three sentences, and attaching it to a finding on a 27,000-character decision
  would borrow precision from the wrong corpus. A test forbids a digit in it.
- `LOGICAL_GAP_TYPES` and `UNSUPPORTED_ASSUMPTION_TYPE` hoisted out of the rule
  bodies, so the measurement script imports the types the rules actually use
  instead of restating them and drifting. No behaviour change.

### Added

- **The prompt an independent review of the meaning set is asked**, as a committed
  script rather than a chat log: `scripts/semantic_cases_review_prompt.py`. It
  assembles the brief and all 24 cases, and carries the field semantics a reviewer
  needs in order to judge a token group at all — that single words match on word
  boundaries and phrases as substrings, and that the fifth invariant is switched
  off for the six multi-claim cases.
  **The review is blind to the measurements.** The script cuts the brief at the
  heading where the measured defects begin and refuses a prompt that still names a
  defect id, a log section or a figure from either run. A reviewer who knows that
  one contract line took the translated propositions to zero is being invited to
  approve the gold because the number moved; the question put to them is whether
  the cases are good tests. Five mutations, including the two that would make the
  cut and the refusal useless.
  **Which makes the reviews themselves testable, and the expectation is recorded
  before they are sent.** Two of the four known gold defects are visible by reading
  the set alone, and both cost paid runs to find: the requirements conflating
  language with meaning, and `sco-02` passing as soon as any claim on the span
  carries a conditional marker. A blind reading that finds either corroborates it
  from outside the family that wrote the set; one that finds neither bounds what a
  review of this kind is worth, and is not evidence the defects are absent.
  Two families are excluded for the same reason the repository exists: the one that
  wrote the set, and the system under test.
- `scripts/claim_type_stability.py`: type stability and the two label-keyed
  triggers, from any directory of stored dossiers named `<group>-<repeat>.json`.
  Eight mutations, including the one that found a bad test of mine — collapsing the
  multiset to a set survived, because the case I had written differed in its set
  too. Fixed by a case whose sets match and whose multisets do not.

### Corrected

- **§4.12 reported the conditional's antecedent typed `assumption` as the
  defensible half of that failure.** In one of three identical runs that typing
  does not exist. Semantic content was credited to a coin flip. A reading rather
  than a measurement, so nothing measured is withdrawn, but the inference was
  unsupported.
- §4.10 called the invalid relation labels — sixteen of eighteen being our own
  claim types in the relation field — **field confusion**. With twenty-one
  undefined and fourteen partly defined short names in one contract it is
  selection by name similarity within one namespace: the same mechanism from the
  other side. The conclusion is unchanged (the two-stage split fixes it, 0 of
  192); the explanation is not.

### Not done

- The three-armed label permutation the prompting paper proposes. The obvious way
  would have been wrong: the meaning set checks `claim_type` in 2 of 24 cases, so
  measuring a permutation against meaning preservation would have spent 216 paid
  calls on an axis that barely sees the type.
- The same measurement on `relation_type`, on which three further findings rest
  alone. It costs nothing and has not been run.


### Fixed

- **The extraction contract now names the document's language, and the silent
  translation stops completely.** Three lines beside the verbatim-span rule:
  `canonical_content` in the language of the document, not translated, with the
  reason — a claim has to be checkable against the span it quotes. Re-run over
  the same 24 cases, the same 72 paid calls, the same profile, with `cases.json`
  and the scorer byte-identical and `meaning_preserved` unchanged, so the
  comparison has one variable: **0 of 123 claims from German sources came back
  translated, against 38 of 122 before.** English stays at 0 of 119. The yield
  did not fall (242 admitted claims against 248): the instruction switched off
  the translation and not the extraction.
  The language is deliberately **not** a parameter. It is a property of the
  document and not of the caller's interface — a German document reviewed with
  `--language en` still needs German propositions, because the span they are
  checked against is German.
  This also answers the question the change was built to answer: the hidden
  semantic projection — which must exist, since a pure extractor cannot
  translate — **is steerable by instruction.** The language problem does not
  require an explicit projection layer.
- Meaning preserved rises from 59 of 72 case-runs to **69 of 72**, and every
  remaining failure is the conditional. Scope 3/6 → 6/6, speaker 9/12 → 12/12,
  several assertions in one passage 10/12 → 12/12, correlation against causation
  11/12 → 12/12. Negation and modality hold at 12/12, which was the pre-set guard
  that would have reverted the change. Anchoring unchanged at 24 of 24 in all
  three runs, `anchor_normalised` 0, no distortions, no failed call.
- **Gold defect M-1 is resolved without a gold change.** All four cases that
  failed in the first run *on language alone* now pass their existing,
  unmodified requirements. The proposed bilingual requirement is not
  implemented and is not needed; the token lists were not too narrow.

### Measured

- **The conditional is now the only measured meaning failure in the set, and it
  did not move.** 2 of 6 runs preserved it before, 3 of 6 now, which on six
  trials is nothing, and it is reported as unchanged — as §3ag predicted a
  language instruction would leave it. The six runs do sharpen the diagnosis, and
  correct the first run's wording of it (the claim reads "The funds are granted",
  not "will be granted"): the extractor **splits the sentence at the comma**. The
  antecedent becomes its own claim, typed `assumption`, which is a defensible
  reading. The consequent becomes its own claim, typed `forecast`, asserted
  **unconditionally** — "construction begins in spring" with no condition
  attached, which is an invented commitment. In the three passing runs one claim
  carries the whole conditional sentence instead.
  A re-check of the gold on this point holds: the forbidden reading appears in
  exactly the three failing runs and in none of the passing ones, so the two
  signals agree 6 of 6. The structural gap — a run delivering the conditional
  *and* the bare consequent would pass — is recorded as latent defect M-4 and was
  not observed.
- 11 of 242 claims are undecidable on the language axis (10 of 248 before), and
  undecidable does not count as translated, so the 0 could be flattering. It is
  not: all eleven were read by hand and stand in the language of their source.
  The mechanism is mechanical rather than noise — "Construction began in spring"
  contains only markers that appear in *both* word lists.
- **The semantic layer silently translates German documents into English
  propositions.** 38 of 122 claims from German sources came back in English and 0
  of 126 from English sources came back in German, over 24 hand-annotated cases
  run three times. The `raw_span` quotes the German source while
  `canonical_content` does not, so the README's promise that quoted claims keep
  their original wording holds for the span and not for the proposition. No
  measurement in this project had ever looked at the language of
  `canonical_content`. It is also the "language-dependent artifact" the project's
  own working paper names as one of three reasons for a projection layer.
  **Fixed in this same release — see Fixed above. This bullet is the measurement
  that found it, not the current behaviour.**
- **Conditionals collapse.** The one genuine meaning failure, and the only
  phenomenon that fails once the language effect is removed. The wording of the
  claim below is corrected in the second run's entry above — it reads "The funds
  are granted": "If the funds are granted, construction begins in spring" becomes
  "The funds are granted" plus
  "Construction begins in spring" — three of three runs in English, one of three
  in German. The condition is gone and one claim asserts what the source
  explicitly does not. For a proposal review that is the error class the product
  exists to catch.
- Negation and modality survive 12 of 12 each. Correlation against causation,
  speaker and multiple assertions fail only where the claim was translated.
- The apparatus works: 24 of 24 cases anchored a claim on their span in all three
  runs, against a mark of 90 per cent fixed beforehand. `anchor_normalised` is 0
  across all 248 claims as predicted, which is the first live exercise of the gate
  merged in #18 — it had only ever been verified against stored packets.
- **My pre-registered prediction was wrong.** `neg-02` and `mod-02` were named in
  advance as containing built-in false alarms; both passed 3 of 3 in both
  languages. The real defect in my gold is one I did not foresee: the requirements
  conflate language with meaning, and one case (`spk-01-de`) passed only because I
  had accidentally made its group language-tolerant while the other eleven were
  not. All three gold defects are recorded as dated entries in
  `docs/semantic-cases-review.md` and **nothing was changed**, because widening a
  token list until a run passes is fitting the test to the system.

### Added

- A **language axis** in `scripts/semantic_score.py`, reported apart from
  anchoring and meaning. It was computed offline from the 72 stored dossiers at no
  further cost. Without it the run would have read as "the extractor loses half
  the meaning on scope and speaker", which is false — which is itself the evidence
  for measuring the outcomes separately. Function words counted, crude like the
  meaning checks, and it has to classify all 24 case documents correctly before it
  may classify a claim, which the test suite asserts. Four mutations, nine on the
  scorer in total.

### Added

- **A hand-annotated set for meaning, as a draft pending independent review.**
  `src/budget_review/fixtures/semantic_cases/cases.json`: 24 cases, twelve
  meanings in German and English, over negation, modality, correlation against
  causation, condition and scope, speaker, and several assertions in one passage.
  Every corpus measured against so far annotates *where* an argument unit sits
  and none annotates whether the claim quoting it still means the same thing — a
  claim can anchor perfectly and lose the negation, and span recall counts that
  as a hit.
  Every requirement is a token group or a regex, never a model judging whether
  two sentences mean the same, because the system under test and its examiner
  would then come from one family. The checks are crude on purpose: they catch a
  negation that is simply gone or a cause invented, not subtle drift.
  `scripts/semantic_cases.py` validates the set against five invariants, of
  which the last two would catch a check that proves nothing: every permitted
  reading must satisfy the requirements and every declared forbidden reading must
  violate one. That holds for the eighteen single-claim cases; for the six that
  require two claims it is switched off, since their failure is "only one claim",
  and that weakness is written into the review brief rather than left implicit.
  Six mutations on the validator.
- **`docs/semantic-cases-review.md`** — the brief for two independent reviews,
  because the draft was authored by the same kind of model it will be used to
  test. It carries the five questions to ask, the five places I think are weakest,
  the rule that **disagreement filters examples rather than voting on meaning**,
  and the governance rule for extending a token group after a run has failed
  against it. Until both reviews are recorded there, the set stays a draft.

### Changed

- **The gate anchors a quote that differs from the document only in whitespace.**
  Exact matches win outright, so a proposal that quoted correctly anchors exactly
  as before and the tolerance can only add anchors where there were none. When it
  applies, the claim carries the document's own characters and never the model's
  wording. Measured over 465 proposals on one paper: 412 anchor verbatim, 42
  differ only in whitespace, 11 are genuine paraphrase and stay refused, and 0
  need case folding — so case is not folded and punctuation is not stripped. The
  offline counterfactual predicted seven recall figures before this existed and
  the built gate reproduces all seven exactly: 216, 219, 192, 218, 218, 198 and
  196 of 219. On the court decision three repair rounds reach **24/24, 22/24,
  24/24** — the full gold answer twice of three, where the previous maximum was
  23 and the figure this work started from was 16. Six mutations.
- Two fields record what the gate did: `anchor_normalised` when whitespace had to
  be ignored, and `proposed_span` with the wording the model sent. Both absent on
  an exactly quoted claim, so the frozen controls carry neither. The original
  evidence is therefore preserved rather than overwritten. A normalised anchor
  does not raise the semantic state: typesetting is not something a human has to
  adjudicate.
- Because `raw_span` now carries the document's passage, a typeset and an exact
  quote of one passage are the same node. That is the whole identity change in
  this release: **`canonical_content` stays in the node address.** A passage is a
  place in the document, not a proposition — one sentence can carry several
  assertions and admits several readings — so divergent readings of one quote stay
  separate claims for a human to compare, never an automatic duplicate. A mutation
  that drops `canonical_content` from the identity now fails a test.
- Both dossier schemas go to 0.3; the packet schema stays at 0.2, since the input
  contract is unchanged. Node ids move, so stored dossiers are not migrated. The
  frozen controls keep their counts.

### Removed

- `scripts/gate_counterfactual.py` and its tests. It measured what a gate
  tolerating typesetting would score; the gate now does.
- The repair pass's own copy of the whitespace search. `relaxed_span` is a thin
  wrapper over the package's `anchor_spans`, so the rule exists once and the
  gate's is the one that decides admission.

### Withdrawn

- **Keying a claim on its anchor alone.** It was built, and the validation that
  let it through was six merges on one document, all produced by the repair pass —
  a configuration that manufactures duplicates — with a 0.48-overlap pair judged
  rather than measured. Separating the two halves showed the collapse had bought
  **no recall at all**: the anchoring half alone reproduces every figure above
  while keeping the six pairs as distinct claims. It bought only the stability
  number (44 against 75 claims present in every run on one paper, 19 against 30
  on the decision) and paid in propositions. What the identity needs instead is a
  two-level design, and that needs a notion of a comparable reading that only an
  annotated test set can supply — see `docs/architecture.md` §3z and §3ac.

### Added

- **`docs/research-report.md`** — a synthesis of the measurement work for readers
  who have not followed it: what is established, what we do not know as a list of
  unmade measurements, the problems solved and the problems still open, and the
  eight claims that were reported and later withdrawn. Bilingual, and each finding
  carries whether it is in production, in review, measured only, or open, because
  two of the largest results are in open pull requests rather than on main.
  `README.md` and `docs/architecture.md` point at it; the latter stays the
  chronological record behind it.

### Added

- **The unstable half of a claim's identity is the model's wording, not the
  document's.** `identity_ladder.py` re-keys finished packets at five rungs and
  reports, per rung, how many claims survive in every run and how many a looser
  key folds together inside one run. Taking the quoted span out of the identity
  buys 5 per cent on the court decision; taking the model's `canonical_content`
  out buys 58. On A24 the figures are +125 and +47 across four single-call runs,
  +146 and +58 across all seven. That is the opposite direction to Working Paper 2
  §10.2, which removes the surface text and puts subject, relation and object —
  all model-authored — into the identity. Guards: 0.0, 0.0 and 3.6 per cent of
  claims merged inside a run against a 5 per cent mark fixed beforehand, and the
  propositions behind a shared span agree at median 1.00, minimum 0.71, none of
  170 keys below 0.5. Casefolding and whitespace do almost all of it; stripping
  punctuation adds six keys on a paper and one on the decision, so punctuation
  stays in. Ten mutations.
- The open question from §3s changes shape as a result. It is no longer "may the
  gate replace a proposal's `raw_span`" but "is the identity computed over a
  whitespace-folded span, with the verbatim span kept as evidence" — nothing is
  rewritten, the exact quote stays in the audit, and a typeset variant becomes the
  same node instead of none. Still a schema change (0.2 → 0.3) and a one-way
  migration for stored dossiers, since node ids move.
- **A retraction.** I had said the relation labels the extractor reaches for are
  family-level labels missing from our vocabulary. `relation_reach.py` counts 18
  such rejections across 32 files and **16 are our own claim types in the relation
  field** — CAUSAL nine times, LIMITATION seven — which the production prompt
  explicitly forbids and which no family-first ask would fix. Two are the wrong
  word for a family we already cover; none is a missing family. What does fix it
  is the split already measured in §3u: the single-call arm produced 10 invalid
  labels over roughly 173 proposed edges, the two-stage arm **0 over 192**, because
  its relation stage has no claim-type field to leak from. Seven mutations.
- That our fourteen relations cover only four of the paper's six families —
  STATISTICAL and NORMATIVE have no member at all — stays true structurally and
  has no support in this data: the model never asked for them. The count sees only
  what is reached for despite a closed list in the prompt, so it cannot measure
  suppressed demand, and the gap is recorded as untested rather than as a finding.

- **The reviewer arms, five times over a graph that cannot move** — the repository's
  frozen packet through the real gate, one document, one profile, so that the only
  thing able to vary is the arms. By the mark fixed in §3v the resolution lands at
  0.63: eight findings appear in all five runs against a mean of 12.6 distinct
  findings per run, which means no comparison of reviewer prompts or profiles may
  rest on a single run. The evidence arm reaches 0.77 at 10 to 11 findings a run.
- **The thinking arm was absent in three of five runs**, and this is a defect in the
  product rather than in the measurement. `_FatalProviderError: DeepSeek output was
  truncated; raise max_tokens` — the reviewer budget is fixed at 8,192 tokens and
  the thinking arm spends it before it writes its findings, on a 1,700-character
  proposal. Truncation is not retried, so the arm is simply missing and every
  second or third review runs with one independent arm instead of two. The dossier
  has recorded it all along under `status` and `error_type`; nobody looked, because
  the frozen controls never call the arms and every live run so far was a single
  run, where a silent arm and a productive one are indistinguishable. The budget
  decision is not taken here: raising it globally, raising it for that arm alone,
  or asking that arm for less all cost more per call or change what it returns, and
  no measurement yet says which value suffices.
- The model-substitution report added an hour earlier produced a true positive on
  its first live run: every successful reviewer call reported a substituted model,
  and every failed one reported none, which is correct — with no answer, no served
  model is known.

- **The dossier says when the provider substituted the model.** Today's run found
  the served model had changed under the branch four weeks earlier, and it found
  it in an experiment rather than in the product. `complete_json` now reports the
  requested id alongside the served one and whether they differ; an envelope
  naming no model is recorded as no comparison rather than as agreement. Each
  reviewer run carries `requested_model_id` and `model_substituted`, and the
  comparison is made inside the audit from the two ids it holds, so no provider
  can suppress it by omitting a flag. A failed run no longer records the
  requested model under `model_id` — no answer arrived, so nothing is known about
  which model ran, and the audit stops claiming otherwise. When a substitution
  happened it appears in the Markdown and HTML audit as one line; when none
  happened, nothing is added. Reported, never enforced: a substitution is a fact
  about the run, not a finding about the document. Five mutations.

- **Two-stage extraction, measured.** Claims in one call and relations over the
  finished claim list in a second, against the production single call on A24,
  three runs per arm in one window. By the rule fixed beforehand the comparison
  cannot be read: the single-call arm alone spread 77 spans (124 to 201 of 219),
  where the rule names 40 as the point at which means say nothing, and the arms
  overlap besides. The split is neither shown to help nor shown to hurt. It
  passes its counter-check — 25 of 25 gold claims on the repo's own fixture, and
  19 relations where the frozen packet has 15 — and the relation stage invented
  no endpoint in any run, 67 of 67, 60 of 60, 65 of 65 resolvable.
- **The served model changed under the branch, and the provenance caught it.**
  The request still asks for `deepseek-v4-flash`; since 31 August the response
  envelope answers `deepseek-flash`. Same document, same corpus checksum, same
  prompt, same budget: anchoring rejections fall from 64 of 134 proposals to 7 to
  31 of 111 to 122, and of those rejections the ones that are genuine paraphrase
  rather than typesetting fall from 54 to 0, 0 and 11. Recall on A24 goes from 80
  of 219 to 194, 201, 124 and 209. Every cross-week comparison on this branch is
  therefore between two served models; comparisons inside one window stand.
- **`gate_counterfactual.py`: what a whitespace-tolerant gate would have scored,
  offline.** A finished packet is re-gated twice, once as measured and once with
  every span that differs from the document only in whitespace replaced by the
  document's own slice — the repair pass's existing function, never the model's
  wording. No call, no cost, and it changes nothing in the product. On the seven
  A24 runs it lifts 194 to 216, 201 to 219 of 219, 124 to 192, 203 to 218, 127 to
  198 and 121 to 196, and the run-to-run spread collapses from 77 to 27 spans in
  one arm and 82 to 22 in the other. Most of the spread this branch has been
  fighting was the gate refusing typeset quotes, not the extractor. The figure is
  post hoc, not pre-registered, and says only what the same proposals would have
  scored under a different gate. Five mutations, including the two ways it could
  flatter itself: amending the baseline along with the tolerant arm, and
  admitting a paraphrase.
- Four earlier statements are qualified in `docs/architecture.md` §3u as a
  result: extraction quality as a property of the document, the anchored-share
  warning light (a rejected anchor lowers both terms, so part of that correlation
  may be built in), the repair pass's gain, and every pre-25-September number.

- **Coverage measurement of the semantic extraction.** The gate can reject a
  claim but never add one, so a claim the extractor never proposed is invisible
  to every deterministic check and to both reviewer arms, and the dossier it
  produces looks clean. Every admitted claim already carries its exact source
  offsets, so the gate now reports the anchored share of the document and names
  contiguous passages no claim reaches. Whitespace does not count, overlapping
  anchors count a character once, and the result is replay-stable and recorded
  as `coverage` in the audit.
- A `coverage_gap` finding per named passage, in both languages. It carries no
  claim ids (a gap is the absence of one), sits at the lowest severity, and asks
  whether the passage should have carried a claim rather than asserting that it
  should — an uncovered stretch may be a heading or a transition.
- The technical audit in HTML and Markdown shows the anchored share and the
  number of uncovered passages.
- The threshold and the ratio are calibrated against AbstRCT (Mayer et al.,
  ECAI 2020), 293 clinical abstracts with expert-annotated argument spans, used
  as measurement input only and not vendored — it is CC BY-NC-SA and this repo
  is MIT. Feeding the gold spans in as if they were admitted claims shows the
  gap threshold is insensitive between 60 and 300 characters (1.31 to 1.01 gaps
  per document) and that the reported gaps account for 98% of the unanchored
  text, so the list decomposes the ratio rather than sampling it. It also shows
  the ratio is not a score: the same documents measure 0.48 when every
  annotated component counts and 0.14 when only conclusions do, so a ratio is
  comparable within one extraction contract and meaningless across different
  ones. Documented in `docs/architecture.md`.
- `scripts/measure_recall.py` compares a live extraction against a frozen
  packet for the same document by span overlap, since two extractions may split
  one sentence differently and both be right. Two offline controls pin it: a run
  reproducing the gold scores 1.0, one with eight claims withheld scores exactly
  17/25.
- A first live measurement, one DeepSeek V4 Flash extraction of the budget
  fixture, reached 25/25 gold claims at 80% span overlap and produced 29 claims
  in total, for a coverage ratio of 0.93 with no gaps against the packet's 0.63
  with two. All three of the extra claims fall inside the two passages the gap
  list had named, so an extraction that knew nothing of the measurement filled
  exactly the places it pointed at. That is one short synthetic document, not a
  benchmark, but it is the first evidence that the gap list points somewhere
  rather than merely somewhere unanchored — and it means the frozen packet is
  itself under-annotated relative to what the extractor finds.

- **Recall measured against a long external gold standard.** The 25-of-25 live
  result was a property of a 1700-character document, not of the extractor.
  Against the argument spans of the ECHR legal corpus (Habernal et al.,
  Artificial Intelligence and Law 2023, Apache-2.0, cloned at run time and not
  vendored), a 10,308-character court decision scores 16 of 24 gold spans at
  80% span overlap and 18 of 24 at 50%, and a 26,715-character one produces no
  extraction at all: the reply outgrows the 16k output budget, since every
  claim must carry its verbatim span. The middle case is the dangerous one — it
  returned 43 claims, 27 relations and 13 findings with no error, and the only
  signal that a third of the annotated argument never reached the graph was the
  anchored share, 0.68 against the gold answer's 0.95 on the same document.
  `scripts/echr_gold.py` builds the document and the gold packet; the paid
  workflow runs the measurement as a second job.
- **Segmenting the document does not repair recall.** Extracting the same
  10,308-character decision in five pieces of about 2,000 characters — the size
  the extractor handles perfectly on the fixture — moved recall from 16/24 to
  17/24 at 80% span overlap, against a success mark of 20/24 fixed before the
  run. It produced 52 claims instead of 43 and raised the anchored share from
  0.68 to 0.75, and at 50% overlap it reached 21/24 against 18/24. So less text
  per call makes the extractor touch more of the argument without decomposing it
  more thoroughly, at five times the calls. The result disconfirms the length
  explanation: segments the size of the fixture did not behave like the fixture,
  which points at the kind of text rather than its length. One document, one
  model, 24 spans. `scripts/segmented_extract.py` runs it.
- **The extraction prompt looked like the constraint; a repeat run withdrew that.** Replacing two
  proposal-specific passages — a claim-type vocabulary in which seven of
  twenty-one values describe a plan rather than an argument, and "decompose
  polished prose aggressively: an elegant sentence may contain several claims" —
  raised recall on the same document, model and single call from 16/24 to 20/24
  at 80% span overlap, meeting a mark of 20/24 fixed before the run. It did so
  with *fewer* claims, 40 against 43, and 23 rather than 30 claims matching no
  gold span: the problem was aim, not volume, which is why segmenting the
  document bought so little. One document, 24 spans, one run, and a bundle of
  two edits. It does not affect the truncation above 27,000 characters, and it
  has to clear the frozen controls before it can become the production prompt.
  `scripts/prompt_variant_extract.py` runs it against the production prompt.
  **Superseded by the sweep below:** a later run of the production arm on the
  same document, prompt, model and budget read 20/24, so the 16-to-20 gain
  claimed here is the size of the extractor's own run-to-run spread. The prompt
  change is neither confirmed nor refuted; it is unmeasured.
- **One unsupported claim type can cost the whole extraction, and the repair
  round does not reliably prevent it.** On a court decision the model reaches for
  `claim_type: conclusion`, which the closed proposal-shaped vocabulary lacks.
  `provider.extract` regenerates once with the schema error fed back, and that
  round has been observed to fix it once and to fail with the same label twice in
  each of two further runs — one completion in three attempts on the same
  document, prompt and budget, since temperature 0 is not a determinism
  guarantee. The double run is blocked behind it: its production leg fails
  before anything can be merged, so the union figure of 39 of 49 stays computed
  rather than run. An earlier note here called this
  a fault of the experiment rather than of the product; that was too confident,
  since the production path runs the same loop and can end the same way after
  two paid calls. `_reject_invalid_relations` only rescues malformed edges;
  there is no equivalent for a claim type, so one label loses the whole packet.
  Untested candidates: carry the neutral prompt's "use the closest value, or
  'other'" note, which would also isolate half of that bundle, or reject the
  single claim rather than the packet, as the gate already does for edges.
- **The variants trade spans rather than adding them, and their union beats
  either.** Comparing which gold spans each run reaches: the neutral prompt is a
  strict improvement on 001-141170, where every span it misses the production
  prompt missed too, but a trade on 001-110144, where it gains three spans and
  loses two. Segmentation trades as well, gaining three and losing two. That is
  why budget and prompt do not add up — they move the extractor's attention
  instead of deepening it. On 001-110144 the union of the two prompt runs
  reaches 39 of 49 against 37 for the better single run, with ten misses shared
  and five exclusive, so the independence is measured rather than assumed.
  Merging is cheap because the gate addresses claims by content, so a claim both
  runs found collapses to one node and its edges survive.
  `scripts/compare_runs.py` computes it from two dossiers. Run through the whole
  pipeline, the merged extraction reaches exactly the predicted 39 of 49 at 80%
  overlap against 37 for the better single run, with 0.86 of the source anchored
  against 0.84. The cost is legibility: 215 proposals become 186 admitted claims
  after the gate collapses 29 by content address, and 141 of them match no gold
  span, so the dossier is nearly twice the size of a single run's and carries
  near-duplicate pairs — two prompts agree on a span far more readily than on its
  wording.
- The number check in `scripts/measure_drift.py` is a screen on legal text, not
  hard evidence. Its first live run reported four claims, all of them correct
  work: the span reads "this provision does not apply" and the claim reads
  "Article 8 does not apply", since the contract asks for a standalone
  proposition and resolving the reference is how one is produced. The digit comes
  from the document rather than the quoted span. Citation numbers behave this way
  generally, so the check needs to tell a quantity from a reference before it can
  be trusted outside the budget domain, where the controls stay silent.
- **The two prompt edits are redundant, not additive.** Each alone reaches the
  bundle's 20 of 24 on 001-141170, against 16 for the production prompt, and all
  three variants miss exactly the same four spans while the production prompt
  misses those four plus four more. So neither edit is necessary and either is
  sufficient: the change acts as a switch — the extractor either treats the text
  as a proposal or it does not — rather than as incremental care. The vocabulary
  note is the one to prefer, since it adds a sentence instead of replacing an
  existing instruction, and it also removes the cause of the `conclusion`
  abort. One run per arm on one document.
- The prompt gain does not replicate on a second legal document. With the
  budget raised and everything else equal, the neutral prompt moves 001-110144
  from 36 to 37 of 49 gold spans at 80% overlap, against a mark of 42 fixed
  before the run — 2 percentage points where the first decision gained 17. The
  finding is therefore narrower than it first read: the change helps markedly on
  one document, barely on another, and is unnecessary on the fixture. That it
  never hurts is measured; how much it helps is document-dependent and not
  established by two documents.
- The same prompt loses nothing on the document type it was written for. On the
  repo's own fixture it reaches the frozen packet's 25 of 25 gold claims, as the
  production prompt does, with 23 claims instead of 29 and an anchored share of
  0.98 against 0.93 — fewer claims, better placed, the same pattern the court
  decision showed. The frozen offline controls cannot see this either way: they
  replay stored packets and never call the extractor, so only a live run against
  the frozen packet can catch a prompt regression.
- **Raising the output budget helps, against expectation.** The 16,384-token cap
  is self-imposed; the model allows 384,000. The argument against raising it was
  that a document which fails loudly today would instead return a thin dossier
  nobody notices. It does not: at 65,536 tokens the 26,715-character decision
  that previously truncated produces 108 claims and reaches 36 of 49 gold spans
  at 80% span overlap and 46 of 49 at 50%, a *better* strict recall than the
  10,308-character decision manages with the same prompt. The coverage
  measurement still flags the shortfall — 0.82 against the gold answer's 0.977,
  with 13 named passages — so the warning survives the larger budget. The cap is
  left unchanged here; the measurement is what changes, and raising it is now a
  decision with evidence behind it rather than a guess.
- The deterministic half is unaffected by length: fed the gold spans as a
  packet, the gate admits all 24 and 49 claims with no rejections and the
  coverage measurement reports 0.946 and 0.977. The limit is extraction alone.
- **Measured: no anchor of forty reaches into two speakers' text, and no two
  claims say near-identical things at disjoint places.** On 001-141170 with the
  production prompt: 40 claims, 20 of 24 gold spans at 80% overlap, anchored
  share 0.76, zero speaker-boundary crossings and zero near-duplicates. The
  first number tests a property the claim contract never asked for and holds on
  this document; the second is narrower than it reads, since the check needs 80%
  word overlap and the earlier differently-worded case would not have shown up.
  Nothing of the 24 spans now falls within five points of the threshold — twenty
  sit at 86% or above, seventeen of them at 100%, then 71%, 23%, 20% and 0% —
  so the recall figure does no arbitrary work here. The hard-case list shrinks to
  three: G03 and G09 are stable at 0% and 20%, G19 fell from 38% to 23%, while
  G18 and G22 rose from 66% and 19% to 100%. Read as passed or failed, that run
  would look two spans better while two spans were getting worse, which is why
  they are tracked by share.
- **The line break was the bottleneck, and the repair pass now works on legal
  text.** With whitespace-tolerant anchoring, three rounds on 001-141170: not one
  `source_span_not_found` in 22 proposals, against 14 of 18 before, and a mean
  gain of 2.7 spans where the same run without it gained nothing. Both marks
  fixed beforehand were met, three times of three. G03 — the Government
  submission this branch has missed in every run since the first recall
  measurement — reaches 100% in all three rounds, G09 rises from 20% to 90%, and
  the end state of 23 of 24 is the highest ever measured on this document against
  a previous maximum of 20. The graph grows moderately, seven to eight claims.
  The same mechanism explains the paper losses: spaced citation brackets and
  formula setting are whitespace differences too, at about 7% instead of 78%.
  The tolerance lives in the experiment only. Putting it in the gate means giving
  the gate a power it does not have — replacing a proposal's raw_span with the
  document's own slice — which is right (quoting the model instead would put text
  in the dossier the document does not contain) but has to be recorded in the
  audit, and that is a schema decision rather than a patch.
- **The two controls: harmless where it cannot help, ineffective on legal text.**
  On the repo's own fixture, where the production prompt already reaches all 25
  gold claims, the coverage measurement found no gap at all in one round — so no
  second call was made — and one 179-character gap in the other, which two added
  claims filled to 25/25. The mechanism is self-limiting: the trigger condition
  is built in, not something still to be designed. On the court decision, three
  rounds with a first pass already at 18–20 of 24: mean gain **zero**, against a
  mark of 2, so the paper result is paper-specific. The targeting is right — G03
  was 100% inside the request every round, G09 80%, G19 77–79%, and G19 rises
  from 23% to 71% covered without crossing the threshold — but 14 of 18 proposals
  died on verbatim anchoring, against about 7% on papers. The obvious explanation
  is refuted: the ECHR document contains no multiple whitespace at all and every
  gold span is findable verbatim, so the cause is open. `divergence` now binary-
  searches the longest still-findable prefix of a rejected span and prints both
  continuations, which names the breaking character instead of guessing at it.
- **The repair pass repeated three times per mode: the first large, replicated
  win.** On A24, uncovered targeting ran 76→215, 176→203 and 80→206 of 219 gold
  spans; thin targeting 85→147, 80→140, 81→118. Mean gain +97 against +53, a
  44-span difference against a pre-registered mark of 20, so the targeting is the
  lever — and against the assumption the thin mode was built on. On papers the
  gold units are clause-sized and sit in the unanchored stretches *between*
  claims rather than inside thinly anchored blocks, so the gap list the gate
  already computes asks about more of the right text. Thin stays in the
  repository but goes no further. The mean end state is 208 of 219, about 95 per
  cent, from a first pass around 35. And the second call compresses the
  run-to-run spread that made every prompt comparison on this branch unreadable:
  the three first passes have a standard deviation of 46 spans, the three end
  states of 5. On A40, whose first pass was the thinnest graph measured here (33
  claims, 54 of 250, anchored share 0.25), the repair pass reached 132 and 171 —
  both above the mark of +40 — which also shows A40 is not a hard document but
  was a thin draw, so the anchored-share correlation holds per run rather than
  per document, which is what a warning light needs. What still fails is
  bounded and now named: verbatim quoting of formula passages and spaced citation
  markers, three to five per round.
- **Four papers, two repair runs, and a retraction.** The "ceiling" reported in
  the previous entry is withdrawn: a repair run reached 210 of 219 on A24 where
  the gold answer scores 186 against itself. Feeding gold spans back as claims is
  a pathological input for a content-addressed gate — identical short fragments
  collapse into one node — so the figure measures the reference, not an upper
  bound, and every "per cent of ceiling" is retracted in favour of raw recall.
  Four papers of near-identical length under one configuration: 50/250, 80/219,
  112/257, 184/267 — 20 to 69 per cent, against a mark that all three new papers
  land within ten points of A24. Missed decisively: extraction quality is a
  property of the document here too. **But the anchored share orders them
  identically** — 0.25, 0.37, 0.39, 0.75 — which is the first evidence that the
  product's own warning light, computed without any gold answer, tracks the
  recall it cannot see, on documents nothing was tuned against. And the repair
  pass carries on papers: 124→210 spans with uncovered targeting, 80→133 with
  thin, every one of 51 and 38 proposals verbatim-anchorable and admitted, where
  four of seven failed to quote on the court decision. Which targeting mode is
  better the run cannot say — the two first passes came out at 124 and 80 spans
  under identical settings, so the arms are confounded by the run-to-run spread.
- **First run against a scientific paper: a partial transfer.** A24, 21,518
  characters, 219 gold spans, production prompt at 65,536 tokens, one call: 70
  claims, 80 spans reached at 80% overlap against a measured ceiling of 186 — 43%
  of what the reference can give, against a mark of 60% fixed before the run. No
  truncation, no schema failure, no near-duplicates, and every claim quotes its
  span exactly. The coverage distribution is binary here, 100% or 0% with nothing
  within five points of the threshold, because the annotation is clause-sized.
  Part of the shortfall is a difference of contract rather than a miss: 51 of the
  63 spans under ten characters are citation keys like "DL03", annotated as
  evidence by this corpus and something our contract could not propose without
  breaking its own rule about atomic propositions. Excluding them, 77 of 168 =
  46%. By component: background_claim 48%, own_claim 41%, data 26%. The misses
  fall in long contiguous runs of gold ids — whole sections untouched while
  others are complete — which is the case `--target thin` was built for.
- **Two follow-ups built and left unmeasured, deliberately.** `--target thin`
  points the repair pass at blocks whose anchored share is below half rather than
  only at stretches no claim touches — the paragraph is the unit an argument is
  written in, whitespace does not count towards the share, and unlike the gap
  list it can name a passage that is anchored at twenty per cent. And
  `two_stage_extract.py` asks for claims and relations in separate calls: stage
  one is the production contract with its relation half removed, after asserting
  the removed passages were there, and stage two receives the finished claim list
  and proposes edges over the whole document. Stage two may not propose claims,
  and an edge naming an id stage one did not produce is dropped with a reason
  before the packet exists. Neither goes into production before it is measured
  against new documents with repeats across sessions — on the one decision this
  branch has been tuning, any result would again be a property of that document.
  Twelve tests, ten mutations, two of which initially survived: a whitespace-only
  anchor counted as coverage, and the claims-only prompt kept its relation
  template because the test looked for a string the appended note also carries.
- **The repair pass, measured: one passage repaired, two never asked about.**
  Two rounds on 001-141170 against a mark fixed beforehand — two of the three
  stable hard cases rising by 20 points or more. One did: G19 went from 23% to
  71% and, in the second round, to 43%, without crossing the 80% threshold, so
  recall stayed at 19/24 and 20/24 and the graph grew by three claims and by one.
  A partial success, and two findings that matter more. The merge rule never
  fired: four of seven and five of six proposals failed on verbatim quoting, so
  the binding constraint is the anchor, not the guard I built. And G03 and G09
  were never asked about — a coverage gap exists only where no claim is anchored
  at all and only above 120 characters, so a passage anchored at 20% breaks into
  remainders that each fall under the threshold. Partial coverage is blind to the
  targeting mechanism. The pass now prints the rejected spans and, per gold span,
  how much of it was actually in the request.
- **The admission rule for a coverage-repair pass, decided before the pass
  exists.** `scripts/repair_merge.py` holds it as a tested function: a claim
  whose anchor lies outside the passages the pass was asked about is rejected, so
  is one that adds no uncovered characters (the near-duplicate the double run
  produced 141 times), while known content at a genuinely new anchor is admitted
  and flagged — "the Government contended X" and the Court's later restatement
  are two speech acts, not one claim with two anchors. Nothing in the rule adds a
  claim, marks one true, or trims a span to fit a gap. `measure_drift.py` now
  counts near-identical claims at disjoint anchors, so how often that third case
  occurs is known before anything is built. Eight plus four tests, nine
  mutations.
- **Two measurements ahead of the next change: hard cases by covered share, and
  speaker boundaries.** `measure_recall.py --watch` reports named gold spans by
  the share of them the anchors cover rather than as passed or failed, since
  four binary items move with any run while the share shows whether a change
  reached the passage at all. And because each ECHR gold span names its actor,
  the script now counts live anchors that reach into two speakers' text: a claim
  spanning the Government's submission and the Court's reply merges two
  epistemic positions into one node, and the anchor is the only record of who
  said it. Both are deterministic and free at run time. Six tests, six
  mutations, run with bytecode caching disabled after a length-preserving
  mutation was found to be scored against a stale `.pyc`.
- **A research log in the README**, in both languages: every paid experiment on
  this branch with the success mark that was fixed before it ran, its result and
  its current status — including the five that were met at the time and are now
  withdrawn, listed as withdrawn rather than quietly dropped. It separates what
  survived repetition from what rests on one call per arm, records what the
  detours cost, and names what is still open.
- **The covered share per gold span: the misses are real, the threshold is not
  doing the work.** Measured on one production run of 001-141170: three spans
  anchored at 0%, 19% and 20%, two at 38% and 66%, one at 77% just below the
  line, and the remaining seventeen at 86% or above with ten at 100%. The
  distribution is bimodal — the extraction reaches a span almost entirely or
  misses it badly — and only two of 24 spans lie within five points of the 80%
  threshold, so the recall figure does not turn on how a sentence happens to be
  split. Length explains the misses only partly: 1,145 characters at 38% against
  1,068 at 81%. The 0% span is probably not a hole but a misplaced anchor: the
  graph carries a claim about that passage, attached to the Court's later
  restatement rather than to the Government's submission the gold annotates,
  which is why gold spans are located by offset and never by text search.
- **Correction to the entry below: the five repeats measured a five-minute
  window, not run-to-run spread.** The same configuration later returned 47
  claims and 18/24, outside both ranges those repeats showed. In order, the
  measurements read 43 claims/16 spans, 20 spans, 38–41 claims/19–20 spans, 47
  claims/18 spans; both code paths issue the same prompt, budget and model. The
  across-session spread is therefore 16 to 20 spans and 38 to 47 claims — four
  spans, the size of the reported prompt effect — so the first pre-registered
  branch holds after all: single-run comparisons of this kind are uninformative,
  and the claim that sampling does not explain the 16/24 is withdrawn.
  Estimating an arm's spread needs runs spread across sessions.
- **Five repeats of one configuration: the spread is one span, so the 16/24 is
  not sampling noise.** Production prompt, 001-141170, 16,384 tokens,
  temperature 0, five runs: 20, 20, 20, 19, 20 of 24 gold spans with 38 to 41
  claims, five of five completing. Pre-registered: a spread of 4 or more would
  have made every single-run comparison here uninformative, a spread of 1 or
  less means sampling does not explain the earlier 16/24 and the cause lies
  elsewhere. The prompt file, the gate's admission logic and text ingestion are
  unchanged between the runs, so what remains is a rare outlier beyond five
  draws or a provider-side change, which these data cannot separate. The prompt
  conclusion is unaffected: the production prompt now misses exactly the four
  spans all three variants missed, where it used to miss those four plus four
  more, so the variants' advantage is gone rather than refuted. The lasting
  result is the miss pattern — four spans reached in none of the five runs, one
  flickering, nineteen always found, and a five-run union of 20/24: repeated
  sampling buys nothing here because the misses are systematic. Three of the
  four are among the six longest spans (median 1,068 characters against 309 for
  the found ones), which at an 80% overlap threshold is partly a property of the
  measurement; length does not decide it alone, since five spans above 450
  characters are found reliably and the 267-character one never is. Also
  measured in passing: three of five runs spent a second paid call on the
  `conclusion` label before the repair round corrected it, with no packet lost.
  `scripts/variance_run.py` runs it.
- **A sweep across five court decisions refutes the prompt optimisation and,
  with it, the evidential value of every single-run comparison here.** Same
  model, same 16,384-token budget, one call per arm, both packets scored through
  the real gate: the vocabulary note reaches 20/24, 17/21 and 7/23 where the
  production prompt reaches 20/24, 18/21 and 17/23 — 44 against 55 gold spans in
  sum, against a mark of at least 3 spans gained on at least 3 of the 5 fixed
  before the run. The note does not go into production, and the per-domain
  vocabulary it was meant to justify has nothing behind it. The more consequential
  reading is the production arm itself: 20/24 here against 16/24 in the earlier
  run of the identical configuration at temperature 0. A four-span spread between
  two draws is the whole effect the prompt work reported, so segmentation (+1),
  the budget comparison, the bundle taken apart and the double run are each one
  draw rather than a measurement. Their numbers stand; their status does not.
  Settling any of it needs repeats per arm, which no run here has paid for.
  Two of the five produced no row: 001-60917 truncated at 16,384 tokens, which is
  the documented budget limit, and 001-77936 was lost to the script defect fixed
  below. `scripts/prompt_sweep.py` runs it.

### Fixed

- **One unsupported label no longer costs the whole extraction.** The provider's
  last-resort recovery dropped malformed *edges* and kept the rest, but had no
  equivalent for a claim, so a single unusable `claim_type` lost the packet
  after two paid calls. It now partitions claims the same way: the offending
  proposal is dropped, the rest is kept, and the loss is written into the audit
  as a `claim_rejections` entry that the gate passes through to the dossier.
  Recovery still declines when it had nothing to drop, so a packet failing for
  an unrelated reason surfaces its own error instead of coming back quietly
  repaired, and a packet whose every claim is unusable still fails — recovering
  there would return a graph nobody proposed. A relation left pointing at a
  dropped claim needs no special handling: the gate admits an edge only when
  both endpoints were admitted.
- **The prompt experiment was stricter than the path it measured.**
  `extract_packet` raised after the second schema rejection, where production
  drops the single malformed proposal and keeps the packet, so a court decision
  the product handles was reported as unmeasurable and silently left the sweep's
  table one row short. It now takes the same recovery path, and the rejections
  are printed rather than swallowed. An instrument that fails where the measured
  path succeeds does not produce a wrong number, it produces a missing one,
  which is harder to notice.
- **A connection dropped mid-response crashed the run.** The retry loop caught
  `URLError` and `TimeoutError`, but a body that ends early or a peer that
  resets after `urlopen` has already returned raises `http.client.IncompleteRead`
  or `ConnectionError`, neither of which is a `URLError`. Those escaped as a
  traceback and killed the run, so a transient drop looked like a crash. Both
  are now retried, since unlike a token limit a retry can end differently. Found
  by a live gold-recall run that failed this way against DeepSeek.

### Changed

- **The gap list decomposes the ratio only on short documents.** The 98% figure
  was established on 1700-character abstracts. On the 10k-to-40k-character
  argumentation of court decisions the named gaps cover a median 72% of the
  unanchored text, 77% below 15k characters and 63% above 30k, because 94% of
  the stretches between anchors fall under the 120-character threshold and
  their mass grows with the document. README, `docs/architecture.md` and the
  module docstring now say so; the threshold itself is unchanged.
- `scripts/measure_recall.py` believes a gold packet's own offsets once it has
  checked that they quote the span, and only searches for the text when none
  are given. Searching is wrong on a long document: legal prose repeats whole
  formulas, so the first match can sit in a different passage than the one
  annotated.
- The frozen budget control now yields 10 findings rather than 8: the fixture
  anchors 63% of its own source, and the two passages it misses are the
  justification for the cohort size and the scheduling assumption that is meant
  to resolve the laptop shortfall. The two content controls are unaffected at
  95% and 96% coverage, so their form-versus-content demonstration is unchanged.

## [0.2.0a3] — 2026-08-26

### Fixed

- **Gate: duplicate claim nodes and duplicate edges.** `claim_node_id` is a hash
  over `(document_id, claim_type, canonical_content, raw_span)`, but
  deduplication ran on `proposal_id` alone, so two proposals with identical
  content produced two claims sharing one node id, and relation dedup keyed on
  proposal ids let one resolved edge through twice with an identical
  `relation_id`. A repeated content address is now rejected as
  `duplicate_claim_node` while its proposal id keeps resolving to the admitted
  node, so its edges survive rather than failing as unadmitted endpoints.
  Relation dedup moved after endpoint resolution and keys on the resolved
  `relation_id`. Side effect: a low-confidence edge no longer suppresses a later
  high-confidence proposal for the same node pair.
- **Budget checks silenced by a single keyword.** Candidate selection evaluated
  the pattern inside the generator body while filtering on a keyword in the
  condition, so `next()` took the first claim carrying the keyword even when its
  pattern did not match, and the check then aborted. One unrelated claim such as
  "serve the region" disabled the capacity check entirely; the same shape
  affected the resource, completion-rate, halving and FTE checks. Selection now
  scans until a candidate actually matches.
- **Crash on an unreadable number.** `_number` raised `ValueError` on any
  lowercase word outside the small spelled-out table, which the `([a-z]+|[0-9]+)`
  cohort patterns can match — "several cohorts of 25" aborted the run. It now
  returns `None`, so an unreadable value is skipped like any other non-match and
  never reads as zero.
- **Consolidation showed a severity from one finding and text from another.** An
  issue took its severity from its most severe member but its title, category,
  explanation and question from the leader of a deterministic-first ordering, so
  a "critical" badge could sit above the text of a medium finding. Severity is
  now the primary sort key and the lead carries it; deterministic findings still
  lead among equally severe ones.
- **Unrelated findings merged through a chain.** Clustering ran union-find over
  `_same_issue`, which is not transitive, so findings over `(C01,C02)` and
  `(C03,C04)` merged through `(C02,C03)`. Grouping is now complete linkage: a
  finding joins a group only by overlapping every member.
- **Language switch was a state-changing GET.** Any foreign page could flip the
  stored setting with an `<img>` tag, and the redirect afterwards took its target
  from the `Referer` header. It is now a token-carrying POST, and redirects
  resolve against a fixed set of the app's own paths.
- **Malformed requests reached the handler unguarded.** A body that is not UTF-8
  and an unknown language both escaped as tracebacks that dropped the connection;
  an empty body answered 413 instead of 400; POST compared the raw path, so
  `/settings?x=1` was a 404 while GET parsed it. Both verbs now route on the
  parsed path behind a guard that returns 500 instead of killing the thread.
- **Deterministic provider failures were paid for three times.** The retry loop
  caught `ProviderError`, so a truncated response — identical on every attempt at
  temperature 0 — cost three calls. Truncation is now fatal on the first
  response. HTTP failures were retried regardless of status and collapsed to
  `HTTPError`, leaving a wrong API key indistinguishable from a network outage;
  4xx now fails immediately naming the status, while 408/429/5xx and network
  errors keep retrying.
- **`save_settings` raised on Windows.** `os.chmod` accepts a descriptor only
  where `fchmod` exists. The call is guarded and the post-rename `chmod` is
  best-effort.
- **The web UI wrote a dossier in the wrong language.** `ReviewPipeline.write`
  called `render_html` without a language, so the browser showed English while
  the file on disk was German.
- **The live smoke validator asserted German headings**, which would have failed
  the paid smoke test under an English default.

### Added

- **`--language de|en`** on `review`, `demo` and `validate`. The dossier is
  rendered in either language: interface labels, deterministic findings and the
  language the reviewer arms are asked to answer in. The default is the
  interface language already stored per OS user, so the web switch and the CLI
  agree. Quoted claims keep their original wording, since they are verbatim
  spans; only the quotation marks around them follow the language.
- Deterministic finding prose lives in one message catalogue keyed by check,
  with both languages side by side and the numeric explanations as format
  templates.
- Each review profile carries an English authority note.
- Tests for paths that previously had none: the live Anti-Delphi loop against a
  scripted provider, the web request handler including the review action, and
  the CSV, TSV, XLSX and PDF ingest formats. Coverage 88% to 93%.

### Changed

- **Deterministic rule provenance is now `content-rules/<profile>/0.3`.** The
  rules changed which findings they produce, so the identifier stamped into the
  audit moves with them; two dossiers can no longer claim one rule version for
  two different results.
- Prose in the JSON audit follows the dossier language, because findings are
  generated once rather than stored as resolvable keys. Structural fields do not
  move: category, severity, claim ids, confidence, provenance and the governed
  graph are identical across languages.
- The gate records two new rejection reasons, `duplicate_claim_node` and a
  `duplicate_relation` keyed on resolved edges.
- Responses carry `Referrer-Policy: no-referrer`, and the CSRF comparison is
  constant-time.
- The live DeepSeek workflow no longer triggers on pushes to `alpha/v0.1.0`, a
  branch that no longer exists and the one path that pulled the paid secret
  without a human. `workflow_dispatch` remains.
- `SECURITY.md` records that the web UI persists full dossiers under
  `./review-output/web/`, that there is no Host-header check, and that the
  `0600` promise on the settings file is POSIX-only.

## [0.2.0a2]

Bilingual local web interface, API-key settings, and the generalization of
Budget Review into Content Review with the `general` and `budget` profiles on
one governed semantic core.

## [0.1.0]

Budget Review alpha: governed ClaimGraph, Layer-9 gate, deterministic budget
checks and two independent Anti-Delphi reviewer arms.
