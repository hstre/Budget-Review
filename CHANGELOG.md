# Changelog

Notable changes per release. Dates are release dates; the format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

The frozen offline controls are the reference for behaviour changes. Unless a
line says otherwise, they are unchanged: `polished` 5 claims / 5 relations /
3 findings, `rough` 4 / 4 / 0, `budget` 25 / 15 / 8.

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

### Changed

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
