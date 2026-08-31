# Changelog

Notable changes per release. Dates are release dates; the format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

The frozen offline controls are the reference for behaviour changes; every entry
says when it moves them. Their current values are `polished` 5 claims /
5 relations / 3 findings, `rough` 4 / 4 / 0, `budget` 25 / 15 / 10.

## [Unreleased]

### Added

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
