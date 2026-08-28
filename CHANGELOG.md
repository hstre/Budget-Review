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
- **The extraction prompt, not the model, was the constraint.** Replacing two
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
- **One unsupported claim type can cost the whole extraction, and the repair
  round does not reliably prevent it.** On a court decision the model reaches for
  `claim_type: conclusion`, which the closed proposal-shaped vocabulary lacks.
  `provider.extract` regenerates once with the schema error fed back, and that
  round has been observed both to fix it and to fail with the same label twice —
  temperature 0 is not a determinism guarantee. An earlier note here called this
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
  `scripts/compare_runs.py` computes it from two dossiers.
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

### Fixed

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
