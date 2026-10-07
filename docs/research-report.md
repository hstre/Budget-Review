# Content Review — Research Report

**What a claim-graph reviewer can and cannot do, measured against external gold
standards.**

This report collects what forty-odd paid measurement runs established, what they
refuted, and what is still open. It is written for someone who has not followed
the work: the chronological record is in [`architecture.md`](architecture.md)
§3a–§3ah, which is a log rather than a synthesis.

Every figure here comes from a committed script run against a real API on real
documents, with a success mark fixed *before* the run. Where a claim was later
withdrawn, it is listed as withdrawn rather than quietly dropped — there are
nine of those, and they are the most useful part of the document.

*(English first; dieselbe Fassung auf Deutsch weiter unten.)*

---

## 1. Summary

**The system was built on the assumption that the hard part is judgement. The
measurements say the hard part is extraction, and that most of what looked like
extraction noise was the gate refusing the extractor's quotations.**

Three findings carry the rest:

1. **Extraction quality, not reviewer quality, is the binding constraint.** The
   deterministic half — the admission gate, the coverage measurement, the
   closed-schema checks — behaves identically on a 1,700-character proposal and a
   27,000-character court decision. The extraction that feeds it loses between a
   third and four fifths of an expert-annotated argument structure, depending on
   the document.

2. **The run-to-run spread of one single configuration was larger than every
   effect we tried to measure.** On one court decision the same prompt, model,
   budget and temperature produced 16 to 20 of 24 gold spans across sessions; on
   one paper, 124 to 201 of 219 within a single twenty-minute window. Every
   comparison made with one run per arm before this was measured is
   uninterpretable, and two published findings had to be withdrawn because of it.

3. **Most of that spread was not the extractor.** It was the gate refusing a
   quotation that differed from the document only in whitespace, because the
   source is hard-wrapped and a line break falls inside the sentence. Fixing the
   anchoring takes recall on one paper from 194 to 216 of 219 and collapses the
   spread from 77 spans to 27. On the court decision the full gold answer — 24 of
   24 — is reached for the first time.

A fourth finding came from the first measurement that looked at *meaning* rather
than position: **the semantic layer was silently translating.** 38 of 122
propositions from German sources came back in English, which is both a product
defect and evidence that a semantic projection is already happening inside the
extractor — a pure extractor cannot translate. One line in the extraction
contract took it to 0 of 123, so that projection is steerable without being
materialised. What the line did not touch is the conditional: in half the runs
the extractor splits "if A, then B" at the comma and asserts B unconditionally,
which for a proposal review is an invented commitment. It is now the only
measured meaning failure (§4.12).

The last finding is about method rather than product, and it generalises past
this repository: **a measurement regime that does not first establish the spread
of a single configuration will produce findings at the rate the spread allows,
and they will survive review because they look like results.** Six of the nine
withdrawals in §7 have that one cause.

### Status at a glance

| | Finding | Status |
|---|---|---|
| 1 | The deterministic half scales with document length; extraction does not | **in production** |
| 2 | Truncation above ~27,000 characters at a 16,384-token budget is real; raising the budget helps and does not thin the dossier | **in production** (limit unchanged) |
| 3 | The anchored share is a usable warning light computed without any gold answer | **in production**, with a caveat (§4.4) |
| 4 | The coverage gap list decomposes the unanchored text — 98 % on short abstracts, a median 72 % on court decisions | **in production**, claim scoped |
| 5 | The run-to-run spread of one configuration exceeds every prompt effect measured | established, shapes all method |
| 6 | The quoting failure is a line break inside the sentence | **in production** (#18) |
| 7 | A claim's identity should carry the document's passage, not the model's prose | **withdrawn in that form** (§4.5, §7.8) |
| 8 | A coverage-repair second pass gains ~97 spans on papers and is self-limiting | **in production** |
| 9 | The provider silently changed the served model; the provenance caught it | **in production** |
| 10 | The thinking reviewer arm was missing from three of five reviews | **in review (#16)**, budget value open |
| 11 | The arms' own stability figure is not reproducible across sessions | open (§5) |
| 12 | Relation labels the extractor reaches for are field confusions, not vocabulary gaps | established, no action taken |
| 13 | Two-stage extraction: recall unreadable, relation validity perfect | measured, not adopted |
| 14 | The semantic layer was silently translating German documents into English propositions | **fixed** by one contract line (§4.12), **in review** |
| 15 | Conditionals are split at the comma and the consequent is asserted unconditionally | open, and now the only measured meaning failure (§4.12) |

---

## 2. What the system is

A pipeline that turns a document into an auditable claim graph and then has two
independent reviewers argue about the graph rather than the prose.

```
document → extraction (one LLM call) → semantic packet
         → admission gate (deterministic) → governed claim graph
         → deterministic checks + two independent LLM arms → findings
         → consolidation → dossier (JSON, Markdown, HTML)
```

Three properties are load-bearing for everything below:

- **The gate can reject a claim but never add one.** A claim the extractor never
  proposed is invisible to every downstream check, and the dossier it produces
  looks clean. This is why coverage had to be measured at all.
- **Every admitted claim quotes the document verbatim** and carries its exact
  character offsets. That is what makes the dossier checkable, and it is also the
  constraint that turned out to cost the most recall.
- **No component may mark a claim true.** The reviewers produce findings and
  questions; a human decides. Agreement between arms is explicitly not evidence.

### The corpora

Nothing external is vendored into the repository. Each is fetched at run time.

| Corpus | What it is | Licence | Used for |
|---|---|---|---|
| Repo fixture | 1,707-character budget proposal, 25 frozen gold claims | own | regression control |
| ECHR decisions | Habernal et al. 2023, 373 court decisions, 15,000 annotated argument spans | Apache-2.0 | recall on legal prose |
| Sci-Arg | Lauscher et al. 2018 over Dr. Inventor, 40 annotated papers | mirror states none | recall on dense scientific prose, measurement input only |
| AbstRCT | 293 expert-annotated clinical abstracts | CC BY-NC-SA | coverage calibration, measurement input only |

The ECHR and Sci-Arg corpora annotate only the argumentative part of a document.
Measuring over a whole judgment would have measured the annotation scope rather
than the extractor, so the region from the first to the last gold span is cut out
and the spans re-based onto it — 94 to 97 % of the characters in that region
carry an annotation.

---

## 3. The method, and why it looks like this

This section is the part most likely to be useful outside this repository.

**Every paid run carries a success mark fixed before dispatch.** Not a
hypothesis — a number, written into the commit that precedes the run. Several
runs missed their mark, and those are the entries worth reading.

**Every new test is mutation-tested.** The test is written, then the code it
covers is deliberately broken in the way that would make the measurement flatter
us, and the test must fail. Per-run counts are in the changelog entries; the
totals are not recoverable from the history, because the branch was squashed.

What the practice actually bought is better shown by the survivors than by a
count. Two examples, both of which passed their first mutation and should not
have: a test meant to check that the repair pass sends the passages it asks
about passed against a mutation that stopped sending them, because the whole
document is in the message anyway — it now asserts the numbered list. And a test
suite for two-stage extraction passed against a mutation that broke the seam
between the stages, because both halves were tested and the call site between
them was not; the run then died twice per document in production, after the first
stage had been paid for.

One mutation round was scored wrongly because length-preserving edits restored
within the same second were measured against cached bytecode. Every batch on the
branch was re-run with `PYTHONDONTWRITEBYTECODE=1 -p no:cacheprovider`; all still
failed as reported, but the defect is recorded because a mutation suite that
silently passes is worse than none.

**No single-run comparisons.** This rule was learned the expensive way, and it is
the subject of §4.2.

**The provenance records what the API answered, not what was asked.** That one
decision is the only reason a silent model substitution was ever noticed (§4.8).

---

## 4. What we know

### 4.1 The deterministic half scales; the extraction does not

Feeding the gold spans back in as a packet, the gate admits all 24 and all 49
claims of two court decisions with no rejection, and the coverage measurement
reports 0.946 and 0.977. The deterministic machinery is unaffected by document
length. Everything that degrades, degrades in the extraction.

Recall against expert annotation, strict (80 % span overlap):

| Document | Characters | Gold spans | Recall |
|---|---:|---:|---|
| Repo fixture | 1,707 | 25 | 25/25 |
| ECHR 001-141170 | 10,308 | 24 | 16–20/24 |
| ECHR 001-110144 | 26,715 | 49 | no extraction at 16,384 tokens; 36/49 at 65,536 |

The 25-of-25 that the project started from was a property of a short document.

### 4.2 The spread of one configuration, and what it invalidated

The production prompt scored 16 of 24 in one run and 20 in another on the same
document, model, budget and temperature 0 — the whole size of the effect the
prompt comparisons were reporting. Five repeats were then run with a
pre-registered rule.

The result was initially read as reassuring: a spread of 1. **That reading was
withdrawn.** The five repeats sat inside a five-minute window; across sessions the
same configuration gives 16 to 20 spans and 38 to 47 claims. On the dense paper
corpus the within-window spread is worse: 124 to 201 of 219 gold spans in twenty
minutes.

Two consequences:

- A comparison of two prompts, two profiles or two architectures with one run per
  arm cannot show an effect smaller than that spread, and nothing we tried to
  measure was larger.
- Any future comparison needs repeats **spread across sessions**, not across
  minutes. The five-minute window understates the spread by a factor of four.

### 4.3 The quoting failure, and the single largest recoverable loss

The gate requires a claim's `raw_span` to appear in the document verbatim. On the
court decision, 14 of 18 repair-pass proposals were refused for
`source_span_not_found` — on a document whose 24 gold spans are all findable.

The cause was diagnosed by binary-searching the longest still-matching prefix of
each refused span: the document is hard-wrapped — 28 lines over 10,308
characters, a median line of 323 — so line breaks fall inside sentences, and a
proposal quoting such a passage writes it as flowing prose. Four of the 24 gold
spans carry a break.

An earlier report had said the cause was open. That was premature: the probe had
looked for multiple spaces and found none, where the right probe was a newline
inside the span.

Classified over 465 proposals on one paper across four runs:

| | Count |
|---|---:|
| anchors verbatim | 412 |
| differs from the document only in whitespace | 42 |
| genuine paraphrase, correctly refused | 11 |
| needs case folding as well | **0** |

Anchoring the whitespace-only cases on a whitespace-collapsed copy of the
document, and returning the document's own characters, was computed offline on
seven finished runs before anything was built. The built gate reproduces all
seven predictions exactly:

| Run | predicted | measured | anchored via whitespace |
|---|---:|---:|---:|
| 1 | 216 | **216**/219 | 9 |
| 2 | 219 | **219**/219 | 7 |
| 3 | 192 | **192**/219 | 20 |
| 4 | 218 | **218**/219 | 6 |
| 5 | 218 | **218**/219 | 4 |
| 6 | 198 | **198**/219 | 25 |
| 7 | 196 | **196**/219 | 24 |

And on the court decision, over three repair rounds: **24/24, 22/24, 24/24.** The
full gold answer, twice of three, where the previous maximum on that document was
23 and the figure the work started from was 16.

The run-to-run spread falls from 77 spans to 27 in one arm and from 82 to 22 in
the other. **The extractor was far more stable than every measurement made it
look; what varied was whether the gate accepted its quotations.**

Status: in production (#18). Case is not folded and punctuation is not stripped —
measured, not chosen: casefolding anchors nothing further and changes no claim's
identity.

### 4.4 The anchored share as a warning light — and its tautology

The product computes, without any gold answer, the share of the document's
characters that some admitted claim anchors on. Across four papers of similar
length under one configuration it orders recall identically:

| Paper | Gold spans | Recall | Anchored share |
|---|---:|---|---:|
| A40 | 250 | 50 (20 %) | 0.25 |
| A24 | 219 | 80 (37 %) | 0.37 |
| A21 | 257 | 112 (44 %) | 0.39 |
| A34 | 267 | 184 (69 %) | 0.75 |

This is the only gold-free signal in the system that tracks the thing it cannot
see, and it was validated against an external reference on documents nothing was
tuned against.

**The caveat, which was added late and belongs in the finding:** a refused anchor
lowers *both* terms mechanically — fewer admitted claims means both a lower
anchored share and a lower recall. Part of that correlation may therefore be
built in. Whether it still orders documents once the anchoring problem is fixed
(§4.3) is unmeasured, and it is the first thing to re-run offline on the other
three papers.

### 4.5 A claim's identity: the model's wording was the unstable half

The gate addresses a claim node by hashing the document id, the claim type, the
model's `canonical_content` and the quoted `raw_span`. A relation hashes both
endpoints' node ids, so a reworded claim changes every edge touching it.

Re-keying finished runs at five identity rungs, counting the claims present in
*every* run:

| Rung | A24, 4 runs | ECHR, 3 rounds |
|---|---:|---:|
| today's identity | 36 | 19 |
| the quoted passage alone, whitespace-folded | **75** | **30** |
| the model's proposition alone | 53 | 20 |

Dropping the span from the identity buys 5 % on legal prose. Dropping the model's
wording buys 58 %. **The document's quote is the stable carrier; anything the
model writes is not.**

Guards, all passed: claims merged inside a single run 0.0 / 0.0 / 3.6 % against a
pre-registered 5 % limit, and the propositions behind a shared span agree at
median 1.00, minimum 0.71, none of 170 keys below 0.5. The only within-run merges
are first-pass-and-repair-pass pairs asserting the same thing at the same quote —
the near-duplicate case a hand-built heuristic existed for.

**This was built and then withdrawn in that form.** A passage is a place in the
document, not a proposition: one sentence can carry several assertions, and the
same sentence admits several readings. Keyed on the anchor alone, the second
assertion at one passage is refused as a duplicate and the machine silently keeps
whichever arrived first. Divergent readings of one quote have to become a conflict
a human compares, never an automatic duplicate.

The validation that let it through was weak, and that is the useful part: six
merges were inspected, on one document, all of them produced by the repair pass —
a configuration that manufactures duplicates by asking about the same text twice.
One pair at a token overlap of 0.48 was *judged* to be the same assertion rather
than measured, and a rule for every case was drawn from it.

Measured separately afterwards, **the collapse bought no recall at all**: the
anchoring half alone reproduces all seven predictions and both 24-of-24 rounds,
with the six pairs kept as separate claims. It bought only the stability figure —
44 against 75 claims present in every run on one paper, and 19 against 30 on the
decision — and paid for it in propositions.

Status: the anchoring half is in production (#18). The identity half needs a
two-level design — the anchor as the stable key for coverage, relations and
cross-run comparison, several claims permitted beneath it, divergence flagged —
and that needs a notion of a comparable reading, which no amount of counting
supplies. An annotated test set does.

This was prompted by the project's own earlier working paper, which specifies an
identity of subject, relation, object and scope with no surface text. The
distinction it draws — identity is not evidence is not state — is right and is
what unlocked the change. Its *assignment* is wrong for this setup: it puts three
model-authored fields in the identity, and model-authored fields are the
unreliable half here. It also presupposes entity resolution, which does not exist
in this system.

### 4.6 The coverage-repair second pass

The gate cannot add a claim, so a passage no claim reaches is invisible. The
coverage measurement names those passages; a second call asks about exactly them,
with the claims already held listed as what not to repeat, and every proposal
goes through an admission rule decided before the pass was built.

On papers, targeting uncovered gaps: mean gain **+97 spans**, end states 215, 203
and 206 of 219 (~95 %), and the spread of the end state falls to 5 where the
first pass varies by 46. Targeting thinly-anchored blocks instead gains +53 — the
design assumption behind that mode was wrong.

It is self-limiting: on the repo's own fixture one round found no gap at all and
made no second call; another found a single 179-character gap and two added
claims took 24/25 to 25/25. The condition for switching it on is in the gap list,
not in a decision still to be made.

**What it does not do:** on the court decision, before the quoting fix, three
rounds gained zero against a pre-registered mark of two. Part of its measured
gain on papers was recovering what the gate had refused — and after §4.3 the gate
no longer refuses it. Whether the pass still pays is therefore open.

### 4.7 Output budget

The 16,384-token limit is self-imposed; the model allows 384,000. The objection
to raising it was that it trades a loud failure for a quiet one: a document that
visibly truncates today would instead return a thin dossier nobody notices.

The measurement does not support that. At 65,536 tokens the 26,715-character
decision yields 108 claims, 36 of 49 strict and 46 of 49 at 50 % overlap, with an
anchored share of 0.82 — a *better* strict recall than the shorter decision
achieves with the same prompt, and not a thin graph. Two things stay true: the
coverage measurement still reports the gap, and the cliff moves in proportion
rather than disappearing (64k tokens reaches roughly 110,000 characters; the
longest decision in the corpus has 447,000).

The limit is unchanged in production. What changed is that raising it would now
be a decision with a measurement behind it.

### 4.8 The provider changed the served model under us

The request asks for `deepseek-v4-flash`. Since 31 August the response envelope
answers `deepseek-flash`. This was visible only because the provenance records
what the API answers rather than what was asked.

Same document, same corpus checksum, same prompt, same budget:

| | Anchor refusals | of which genuine paraphrase | of which whitespace only | Recall |
|---|---:|---:|---:|---|
| 31 August | 64 of 134 | 54 | 10 | 80/219 |
| 25 September, run 1 | 9 of 111 | 0 | 9 | 194/219 |
| 25 September, run 2 | 7 of 122 | 0 | 7 | 201/219 |
| 25 September, run 3 | 31 of 111 | 11 | 20 | 124/219 |

The dominant error term in August was inaccurate quoting, and it has nearly
vanished. **Every cross-week comparison in this work is therefore between two
served models**; comparisons inside one session stand.

The dossier now records the requested model beside the served one and says so in
one line when they differ. A failed call no longer records the requested model as
if it had run. Within an hour of that landing, a live run reported a substitution
on all ten of its calls.

### 4.9 The reviewer arms

Five runs over a frozen graph — the repository's own packet through the real gate,
so the only thing able to vary is the arms — found something the dossier had been
recording all along and nobody had read:

**The thinking arm was absent from three of five reviews**, truncated at the
hard-wired 8,192-token reviewer budget, on a 1,700-character proposal. Every
second or third review ran with one independent arm where the design calls for
two, so the Anti-Delphi property did not hold in those cases.

Raising the budget high enough that nothing truncates and reading off what the
arm actually spends:

| Run | Evidence arm | Thinking arm |
|---|---:|---:|
| 1 | 1,962 | 8,453 |
| 2 | 2,417 | 8,226 |
| 3 | 2,129 | 10,369 |
| 4 | 1,961 | **12,159** |
| 5 | 2,002 | 10,759 |

The arm needs 8,226 to 12,159 output tokens. The budget was 8,192 — **at the very
bottom edge of the requirement**, which is the worst place for a limit, because it
fails unpredictably rather than always. That is why the arm finished twice of five
rather than never. The factor of five between the arms, for the same eleven
findings, is the thinking itself.

The figure is measured on the shortest document in the repository and the reviewer
prompt carries the graph, so it is a lower bound. Status: parameterised in review
as #16; the production value is an open decision.

### 4.10 Relation labels: field confusion, not a vocabulary gap

Eighteen relation proposals across 32 run artifacts were refused for an unknown
`relation_type`. Sorted into cases:

| Label | Hits | Case |
|---|---:|---|
| CAUSAL | 9 | **our own claim type, in the relation field** |
| LIMITATION | 7 | **our own claim type, in the relation field** |
| CAUSES | 1 | a family we already cover |
| DEFINES | 1 | a family we already cover |

**Sixteen of eighteen are cross-field leakage**, which the production prompt
forbids in those words and which is ignored anyway. None is a missing relation
family. An earlier report had claimed the opposite — that each was a family-level
label reached for because the vocabulary lacked it — and that is withdrawn.

What does fix it is the split measured in §4.11: the single-call arm produced 10
invalid labels over roughly 173 proposed edges; the two-stage arm **0 over 192**,
because its relation stage has no claim-type field to leak from.

Separately and structurally: the fourteen relation types cover four of the six
families in the project's own working paper. **STATISTICAL and NORMATIVE have no
member at all** — the system cannot express "A correlates with B" without forcing
it into a causal or dependency relation, which the paper names as one of the most
common errors in automated knowledge-graph construction. That gap is real on
paper and has **no support in this data**: the model never asked for them. A count
of what is reached for despite a closed list cannot measure suppressed demand, so
the gap is recorded as untested rather than as a finding.

### 4.11 Two-stage extraction

Claims in one call and relations over the finished claim list in a second,
against the production single call, three runs per arm in one window, with the
rule fixed first: improvement requires the arms not to overlap.

| | Recall of 219 |
|---|---|
| single call | 194, 201, 124 (and 209 as a drift check) |
| two-stage | 203, 127, 121 |

The single-call arm alone spreads 77 spans, where the pre-registered rule names
40 as the point at which means say nothing. **Verdict: resolution insufficient.**
The split is neither shown nor refuted.

Two clean properties regardless: the counter-check on the fixture reaches 25 of 25
gold claims with 19 relations against the frozen 15, and the relation stage
invented no endpoint in any run — 67 of 67, 60 of 60, 65 of 65 resolvable —
besides the zero invalid labels above.

Not adopted: it costs a second paid call per document and its recall case is
unmade.

---

### 4.12 Meaning, measured apart from anchoring: the layer was translating

Every corpus measured against up to this point annotates *where* an argument unit
sits. None annotates whether the claim quoting it still means the same thing — a
claim can anchor perfectly and lose the negation, and span recall counts that as a
hit. So 24 short cases were hand-annotated, twelve meanings in German and English,
over negation, modality, correlation against causation, condition and scope,
speaker, and several assertions in one passage. Every requirement is a token group
or a regex, never a model judging whether two sentences mean the same, because the
system under test and its examiner would then come from one family.

Three outcomes are reported **separately** — anchoring, meaning, relations —
specifically so that a change cannot look better by capturing *more text*.

**First run, 72 paid calls.** The apparatus holds: 24 of 24 cases anchored a claim
on their span in all three runs against a mark of 90 per cent fixed beforehand,
and `anchor_normalised` is 0 across all 248 admitted claims — the first live
exercise of the anchoring gate merged as #18, which until then had only been
checked against stored packets.

Then the finding nobody was looking for. **38 of 122 propositions from German
sources came back in English; 0 of 126 from English sources came back in German.**
The `raw_span` quotes the German document and `canonical_content` does not. No
measurement in this project had ever looked at the *language* of a proposition,
and the README's promise that quoted claims keep their original wording held for
the span and not for the proposition.

Two explanations, and they do not compete. The mundane one: the extraction
contract never mentioned language at all, while the reviewer contract has carried
a language instruction since it existed. The deeper one: **a pure extractor
cannot translate.** To write a German sentence as a faithful English proposition
the model must already hold subject, predicate, scope and polarity independently
of the German wording, and then re-verbalise. The semantic projection is
happening — it is simply not kept. Which retrospectively explains §4.5, reported
there as a fact without a cause: `raw_span` is a *selection* into the document
and therefore reproducible; `canonical_content` is a *generation* and therefore
the unstable half.

**Second run, same 72 calls, one variable.** Three lines were added to the
extraction contract beside the verbatim-span rule: the proposition in the
language of the document, not translated, because a claim has to be checkable
against the span it quotes. The case file and the scorer are byte-identical
between the runs and `meaning_preserved` is unchanged.

| | before | after | pre-set threshold |
|---|---:|---:|---|
| translated, German source | 38 of 122 | **0 of 123** | ≤ 5 ⇒ steerable |
| translated, English source | 0 of 126 | 0 of 119 | must stay 0 |
| negation | 12/12 | 12/12 | guard: a fall reverts the change |
| modality | 12/12 | 12/12 | guard |
| meaning preserved, all cases | 59/72 | **69/72** | — |

**The hidden projection is steerable by instruction.** The effect is complete
rather than partial, the yield did not fall (242 claims against 248), and scope
went 3/6 → 6/6, speaker 9/12 → 12/12, several assertions 10/12 → 12/12,
correlation 11/12 → 12/12. All four cases that had failed *on language alone*
now pass their existing, unmodified requirements, which resolved a gold defect
without touching the gold. For the language problem, no explicit projection layer
is needed.

**What the instruction did not touch: the conditional.** "If the funds are
granted, construction begins in spring." In three of six runs the extractor
**splits the sentence at the comma**: the antecedent becomes its own claim, typed
`assumption`, which is a defensible reading, and the consequent becomes its own
claim, typed `forecast`, asserted **unconditionally**. "Construction begins in
spring" with no condition attached is an invented commitment — for a proposal
review, the error class the product exists to catch, produced by the product. In
the other three runs one claim carries the whole conditional sentence. 2 of 6
before and 3 of 6 after is nothing on six trials, and it is reported as unchanged.

It is now the only measured meaning failure in the set, which makes it a far
better-posed target than "the semantic layer is unreliable": a single
reproducible structural failure at a named construction. Whether it needs
explicit fields for modality and scope, or — as with every small change in this
project that worked — one more contract line, is the next pre-registered
question.

**Limits.** Relations remain unmeasurable: the set annotates no edges, found by
trying to implement the axis. The set is a **draft** pending two independent
reviews, which have not happened. Each case is one to three sentences, so a
contract line that works on 24 short sentences says nothing about 26,000
characters of court text.

---

## 5. What we do not know

Stated as questions, because each is a measurement nobody has made.

1. **Does the anchored-share warning light survive the anchoring fix?** Part of
   its correlation with recall may be mechanical (§4.4). Re-running it offline on
   the other three papers under the new gate is free and has not been done.
2. **Does the coverage-repair pass still pay?** Much of its gain was recovering
   refusals the gate no longer makes (§4.6). It costs a paid call per document.
3. **What is the extractor's spread across sessions, under the new gate?** The
   77-span figure was measured under the old one, and the counterfactual suggests
   27. That is an offline estimate, not a measurement.
4. **How stable are the reviewer arms?** The share of findings present in all five
   runs came out 0.63 with the thinking arm missing three times, and **0.27** with
   it working — below the 0.5 the pre-registration set for "unstable". Worse, the
   evidence arm alone fell from 0.77 to 0.27 on an identical graph with a budget
   that never bound it. Either the arms' stability figure is itself not
   reproducible across sessions, or the raised budget changed that arm's
   behaviour; the two are not separated, and separating them takes a run that
   keeps the old budget and changes only the session.
5. **What does the thinking arm need on a real document?** 12,159 tokens is
   measured on 25 claims; a court decision gives 40 to 57.
6. **Does extraction quality transfer across document kinds?** Four papers under
   one configuration gave 20, 37, 44 and 69 % — "a property of the document" was
   the conclusion, but under a tolerant gate all A24 runs land between 88 and
   100 %, so that conclusion is now in doubt and the other three papers have not
   been re-scored.
7. **Coverage.** Claims the extractor never proposed are untouched by every change
   above, and of 465 proposals on one paper 11 remain correctly refused as
   paraphrase. Nothing in this work addresses a passage the extractor simply did
   not read.
8. **Whether any of this holds on a document in German.** Every external corpus
   used is English. The product's own fixture and interface are bilingual; the
   measurements are not.
9. **Whether the relation vocabulary's two missing families cost anything**
   (§4.10). Measuring it requires an extraction that is not handed a closed list.
10. **Whether a reviewer finding's state can ever be resolved.** `Finding.state`
    is always `human_review_required` and nothing ever writes it. A design for
    resolving it against a revised version of the same document exists on paper
    and is unbuilt.

---

## 6. Problems: solved and unsolved

### Solved

| Problem | How | Status |
|---|---|---|
| A claim the extractor never proposed is invisible | Coverage measurement: anchored share plus named gaps, replay-stable | in production |
| The 98 % gap-coverage claim was scale-dependent | Scoped to short documents; median 72 % on court decisions | in production |
| A dropped connection ended a run as a crash | `IncompleteRead` and `ConnectionError` joined the retry loop | in production |
| One schema-invalid proposal cost a whole document | The proposal is dropped with a reason and the packet kept | in production |
| A proposal refused before the gate vanished from the audit | Pre-gate rejections travel with the packet into the dossier | in production |
| A silent model substitution was undetectable | Requested and served model both recorded, reported when they differ | in production |
| A whole section of a document left untouched | Coverage-repair second pass over exactly the uncovered gaps | in production |
| A quotation refused over a line break | Tolerant anchoring on a whitespace-collapsed copy | in production (#18) |
| A reworded claim is a different node, and changes every edge | *Not solved.* The fix as built would have dropped a second reading of one passage | withdrawn, §4.5 |
| The thinking arm silently absent from most reviews | Budget parameterised; requirement measured | in review (#16) |
| The proposition was silently translated out of the document's language | One line in the extraction contract: the proposition in the document's language, not translated | in review; 38 of 122 → 0 of 123 (§4.12) |

### Unsolved

| Problem | Why it is still open |
|---|---|
| Coverage — passages the extractor never reads | No mechanism but a second paid call, whose value is now unclear |
| The run-to-run spread itself | Reduced, not removed; 27 spans is still larger than most effects worth measuring |
| Reviewer stability | 0.27 under the strict rule, and the figure is not reproducible (§5.4) |
| Truncation on long documents | The cliff moves with the budget; it does not go away |
| Genuine paraphrase in quotations | 11 of 465 proposals, correctly refused, permanently lost |
| Relation expressivity | Four of six families covered; the gap is untested |
| A finding's state is never resolved | Needs a versioned overlay and a schema decision |
| Conditionals | Split at the comma in half the runs; the consequent is then asserted unconditionally. A language instruction did not touch it (§4.12) |
| Meaning of a claim, beyond 24 short sentences | The only meaning set that exists is 24 one-to-three-sentence cases, and it is a draft pending two independent reviews |
| Relations between claims | The third outcome of §4.12 is still unmeasurable: the meaning set annotates no edges |
| German-language evidence | 24 hand-annotated cases, half of them German, run twice — and nothing longer. No German document above fixture length has been measured |

---

## 7. Withdrawn claims

Each of these was reported, published in the repository, and later retracted. Six
of the nine have the same cause: a comparison made with one run per arm, before
the spread of a single configuration was known.

1. **"A per-domain prompt note raises recall from 16 to 20 of 24."** Swept across
   five decisions it gave 44 against 55 gold spans in sum and collapsed from 17/23
   to 7/23 on one document. **Refuted.**
2. **"The spread of one configuration is 1, so sampling does not explain 16
   against 20."** The five repeats sat in a five-minute window. Across sessions the
   spread is 16 to 20. **Withdrawn as a window artefact.**
3. **"The gold answer scores 186 of 219 against itself, so that is the ceiling."**
   A repair run reached 210. Feeding gold spans back as claims is a pathological
   input for a content-addressed gate — identical short fragments collapse — so the
   figure was never an upper bound. **Withdrawn; kept as a diagnostic.**
4. **"The cause of the quoting failure is open."** The probe had looked for
   multiple spaces; the right probe was a newline inside the span. **Premature.**
5. **"Every relation label the extractor reaches for is a family-level label our
   vocabulary lacks."** Sixteen of eighteen are our own claim types in the relation
   field. **Retracted.**
6. **"The gap list covers 98 % of the unanchored text."** True for
   1,700-character abstracts, a median 72 % on court decisions. **Scoped.**
7. **"The resolution of the reviewer arms is 0.63."** Measured with the thinking
   arm absent from three of five runs, so it described the one arm that answered.
   With both arms working it is 0.27. **Re-read.**
8. **"Keying a claim on its anchor alone is safe, because the merges it causes are
   duplicates."** Verified on six merges from one document, all produced by the
   repair pass, with a 0.48-overlap pair judged rather than measured. A passage
   can carry several assertions and admits several readings, so the rule would
   silently drop the second. **Withdrawn after the anchoring half shipped without
   it** — and the separation showed the collapse had bought no recall at all.
9. **"One run per budget step settles what the thinking arm needs — truncated is
   truncated."** The arm finished twice of five at the old budget, so the failure is
   stochastic and a staircase search reports whichever step got lucky. **Corrected
   before the run was paid for**, which with the eighth is one of only two caught
   in time.

Two smaller corrections that are not withdrawals, recorded because they were
published: the conditional's broken claim was first reported as "The funds *will
be* granted" where the model wrote "The funds **are** granted" — a misquotation
of the output, corrected from the six runs in §4.12. And a pre-registered
prediction that two of the meaning cases contained built-in false alarms was
**refuted**: both passed 3 of 3 in both languages, and the real defect in the set
was one not foreseen.

---

## 8. What the external work contributed

Two external inputs shaped the work, and it is worth being precise about how.

**The annotated corpora did the real work.** Without expert annotation there is no
recall figure, and without a recall figure the coverage measurement is a number
with nothing to calibrate against. Four of the findings above exist only because
somebody else annotated 15,000 argument spans in court decisions.

**The project's own working paper on a semantic projection layer** supplied the
distinction that unlocked §4.5: identity, evidence and state are three different
things, and a claim is the same proposition whether the extractor was 81 or 82 per
cent confident. That is right, and the system had collapsed all three into one
hash.

Its concrete prescriptions did not transfer:

- Its identity key is subject, relation, object and scope — three model-authored
  fields — where the measurement says model-authored fields are the unstable half.
  It also presupposes entity resolution, which this system does not have.
- Its two-stage projection splits on the relation hierarchy (family, then
  relation) and its rationale is exactly our failure mode. But the failure is
  cross-field leakage (§4.10), which a family-first ask does not touch.
- Its entropy and divergence machinery needs a calibrated distribution over
  relations. A single JSON completion does not give one, and the confidence floats
  a model writes are not probabilities. The paper's own open questions say the
  thresholds need empirical calibration that was never done.

The one adaptation worth keeping: **the repeats we already pay for are an
empirical distribution.** Five runs give, per claim, a relative frequency that is
calibrated by construction because it is counted rather than asserted. That turns
the spread from the thing that ruins every measurement into the thing the paper's
emission rules wanted. It is unbuilt.

---

## 9. Reproducing any of it

The paid path runs only on manual dispatch, and the key exists only as a GitHub
Actions secret — it is never available locally.

```
.github/workflows/live-deepseek.yml      every paid run, by dispatch input
scripts/                                 21 measurement scripts, each tested
docs/architecture.md §3a–§3ah            the chronological record, run by run
CHANGELOG.md                             what moved, including the retractions
```

The offline controls replay stored packets and never call a provider: `polished`
5 claims / 5 relations / 3 findings, `rough` 4 / 4 / 0, `budget` 25 / 15 / 10.
They are the reference for behaviour changes, and they cannot see a prompt
regression — only a live run against the frozen packet can.

360 tests and one skipped, `ruff check` clean.

---

## 10. Open decisions

Not measurements — judgements that cost money or change stored data, listed so a
reader knows what is waiting.

1. **The reviewer output budget.** 12,159 tokens measured on the shortest
   document; 32,768 is the first value with room against the extrapolation to a
   real one. Every call then costs more.
2. **How the two-level identity should work.** The anchoring half shipped; the
   identity half needs a notion of a comparable reading, which only an annotated
   test set can supply (§4.5).
3. **Whether the repair pass stays** once the gate no longer refuses what it was
   recovering.
4. **Whether to extend the relation vocabulary** to the two uncovered families, on
   evidence that does not yet exist.
5. **Whether the conditional needs explicit projection fields.** Modality and
   scope carried as their own fields rather than left to the sentence structure
   of a proposition. The language problem turned out not to need them (§4.12);
   the conditional is the remaining candidate, and it is the only measured
   meaning failure left.
6. **Who reviews the meaning set.** It is a draft by design: two independent
   reviews were asked for and none has happened, and until then every figure in
   §4.12 rests on cases written by the same party that built the system.

---
---

# Forschungsbericht (Deutsch)

**Was ein Claim-Graph-Reviewer kann und was nicht, gemessen gegen externe
Goldstandards.**

Dieser Bericht sammelt, was rund vierzig bezahlte Messläufe belegt haben, was sie
widerlegt haben und was offen ist. Er ist für jemanden geschrieben, der die
Arbeit nicht verfolgt hat; die chronologische Aufzeichnung steht in
[`architecture.md`](architecture.md) §3a–§3ah und ist ein Log, keine Synthese.

Jede Zahl hier kommt aus einem committeten Skript, gelaufen gegen eine echte API
auf echten Dokumenten, mit einer Erfolgsmarke, die **vor** dem Lauf festgelegt
wurde. Wo eine Aussage später zurückgezogen wurde, steht sie als zurückgezogen da
und wurde nicht still entfernt — es sind neun, und sie sind der nützlichste Teil
des Dokuments.

## 1. Zusammenfassung

**Das System wurde unter der Annahme gebaut, das Schwierige sei das Urteil. Die
Messungen sagen: das Schwierige ist die Extraktion — und das meiste, was wie
Extraktionsrauschen aussah, war das Gate, das die Zitate des Extraktors ablehnte.**

Drei Befunde tragen den Rest:

1. **Die Extraktionsqualität ist die bindende Grenze, nicht die Reviewer-Qualität.**
   Die deterministische Hälfte — Gate, Abdeckungsmessung, geschlossene
   Schemaprüfungen — verhält sich auf einem 1.700-Zeichen-Antrag genauso wie auf
   einer 27.000-Zeichen-Entscheidung. Die Extraktion, die sie speist, verliert je
   nach Dokument ein Drittel bis vier Fünftel einer fachlich annotierten
   Argumentstruktur.

2. **Die Streuung einer einzigen Konfiguration war größer als jeder Effekt, den
   wir messen wollten.** Auf einer Gerichtsentscheidung lieferten dieselbe Prompt,
   dasselbe Modell, dasselbe Budget und Temperatur 0 über Sitzungen hinweg 16 bis
   20 von 24 Gold-Spannen; auf einem Paper 124 bis 201 von 219 innerhalb eines
   Zwanzig-Minuten-Fensters. Jeder Vergleich mit einem Lauf je Arm von davor ist
   nicht interpretierbar, und zwei veröffentlichte Befunde mussten deswegen
   zurückgezogen werden.

3. **Das meiste dieser Streuung war nicht der Extraktor.** Es war das Gate, das
   ein Zitat ablehnte, das sich vom Dokument nur im Leerraum unterscheidet — weil
   die Quelle hart umbrochen ist und ein Zeilenumbruch mitten in den Satz fällt.
   Die Verankerung zu reparieren hebt den Recall auf einem Paper von 194 auf 216
   von 219 und drückt die Streuung von 77 auf 27 Spannen. Auf der
   Gerichtsentscheidung wird die vollständige Gold-Antwort — 24 von 24 — erstmals
   erreicht.

Ein vierter Befund kam aus der ersten Messung, die auf *Bedeutung* statt auf
Position gesehen hat: **Die semantische Schicht hat still übersetzt.** 38 von 122
Propositionen aus deutschen Quellen kamen auf Englisch zurück — ein Produktmangel
und gleichzeitig der Beleg, dass im Extraktor schon eine semantische Projektion
läuft, denn ein reiner Extraktor kann nicht übersetzen. Eine Zeile im
Extraktionsvertrag hat es auf 0 von 123 gebracht; diese Projektion ist also
steuerbar, ohne materialisiert zu werden. Was die Zeile nicht angefasst hat, ist
die Bedingung: in der Hälfte der Läufe zerlegt der Extraktor „wenn A, dann B" am
Komma und behauptet B unbedingt, was für eine Antragsprüfung eine erfundene
Zusage ist. Sie ist jetzt der einzige gemessene Bedeutungsfehler (§4.12).

Der letzte Befund betrifft die Methode und gilt über dieses Repository hinaus:
**Ein Messregime, das nicht zuerst die Streuung einer einzigen Konfiguration
feststellt, produziert Befunde in dem Tempo, das die Streuung erlaubt — und sie
überleben jedes Review, weil sie wie Ergebnisse aussehen.** Sechs der neun
Rücknahmen in §7 haben genau diese Ursache.

### Stand im Überblick

| | Befund | Stand |
|---|---|---|
| 1 | Die deterministische Hälfte skaliert mit der Länge, die Extraktion nicht | **in Produktion** |
| 2 | Abbruch über ~27.000 Zeichen bei 16.384 Tokens ist echt; Erhöhen hilft und liefert kein dünnes Dossier | **in Produktion** (Limit unverändert) |
| 3 | Der verankerte Anteil ist eine brauchbare Warnleuchte ohne jede Gold-Antwort | **in Produktion**, mit Vorbehalt (§4.4) |
| 4 | Die Lückenliste zerlegt den unverankerten Text — 98 % auf kurzen Abstracts, Median 72 % auf Entscheidungen | **in Produktion**, Aussage eingegrenzt |
| 5 | Die Streuung einer Konfiguration übersteigt jeden gemessenen Prompt-Effekt | belegt, prägt die ganze Methode |
| 6 | Der Zitierfehler ist ein Zeilenumbruch im Satz | **in Produktion** (#18) |
| 7 | Die Identität eines Claims gehört auf die Textstelle, nicht auf die Prosa des Modells | **in dieser Form zurückgezogen** (§4.5, §7.8) |
| 8 | Ein Reparaturlauf gewinnt ~97 Spannen auf Papern und ist selbstbegrenzend | **in Produktion** |
| 9 | Der Anbieter hat das ausgelieferte Modell stillschweigend gewechselt; die Provenienz hat es gefangen | **in Produktion** |
| 10 | Der Thinking-Arm fehlte in drei von fünf Reviews | **im Review (#16)**, Budgetwert offen |
| 11 | Die Stabilitätszahl der Arme ist selbst nicht reproduzierbar | offen (§5) |
| 12 | Relationslabels, nach denen der Extraktor greift, sind Feldverwechslungen, keine Vokabularlücken | belegt, nichts getan |
| 13 | Zweistufige Extraktion: Recall nicht lesbar, Relationsgültigkeit perfekt | gemessen, nicht übernommen |
| 14 | Die semantische Schicht hat deutsche Dokumente still in englische Propositionen übersetzt | **behoben** durch eine Vertragszeile (§4.12), **im Review** |
| 15 | Bedingungssätze werden am Komma zerlegt und der Nachsatz unbedingt behauptet | offen, und jetzt der einzige gemessene Bedeutungsfehler (§4.12) |

## 2. Was das System ist

Eine Pipeline, die ein Dokument in einen prüfbaren Claim-Graphen verwandelt und
dann zwei unabhängige Reviewer über den Graphen streiten lässt statt über die
Prosa.

```
Dokument → Extraktion (ein LLM-Aufruf) → semantisches Paket
         → Zulassungs-Gate (deterministisch) → gegateter Claim-Graph
         → deterministische Prüfungen + zwei unabhängige LLM-Arme → Befunde
         → Konsolidierung → Dossier (JSON, Markdown, HTML)
```

Drei Eigenschaften tragen alles Folgende:

- **Das Gate kann einen Claim ablehnen, aber niemals hinzufügen.** Ein Claim, den
  der Extraktor nie vorgeschlagen hat, ist für jede nachgelagerte Prüfung
  unsichtbar, und das Dossier sieht sauber aus. Deshalb musste Abdeckung überhaupt
  gemessen werden.
- **Jeder zugelassene Claim zitiert das Dokument wörtlich** und trägt seine exakten
  Zeichenoffsets. Das macht das Dossier prüfbar — und es ist die Bedingung, die am
  meisten Recall gekostet hat.
- **Keine Komponente darf einen Claim als wahr markieren.** Die Reviewer liefern
  Befunde und Fragen; ein Mensch entscheidet. Übereinstimmung zwischen den Armen
  ist ausdrücklich kein Beleg.

### Die Korpora

Nichts Externes liegt im Repository. Alles wird zur Laufzeit geholt.

| Korpus | Was es ist | Lizenz | Wofür |
|---|---|---|---|
| Repo-Fixture | 1.707 Zeichen Antrag, 25 eingefrorene Gold-Claims | eigen | Regressionskontrolle |
| EGMR-Entscheidungen | Habernal u. a. 2023, 373 Entscheidungen, 15.000 Argumentspannen | Apache-2.0 | Recall auf Rechtstext |
| Sci-Arg | Lauscher u. a. 2018 über Dr. Inventor, 40 annotierte Paper | Spiegel nennt keine | Recall auf dichter Wissenschaftsprosa, nur Messeingabe |
| AbstRCT | 293 fachlich annotierte klinische Abstracts | CC BY-NC-SA | Abdeckungskalibrierung, nur Messeingabe |

EGMR und Sci-Arg annotieren nur den argumentativen Teil. Über ein ganzes Urteil zu
messen hätte den Annotationsumfang gemessen statt den Extraktor, deshalb wird die
Region von der ersten bis zur letzten Gold-Spanne herausgeschnitten und die
Spannen darauf umgerechnet — dort tragen 94 bis 97 Prozent der Zeichen eine
Annotation.

## 3. Die Methode, und warum sie so aussieht

Dieser Abschnitt ist wahrscheinlich der, der außerhalb dieses Repositories am
meisten nützt.

**Jeder bezahlte Lauf trägt eine vor dem Versand festgelegte Erfolgsmarke.** Keine
Hypothese — eine Zahl, geschrieben in den Commit, der dem Lauf vorausgeht. Mehrere
Läufe haben ihre Marke verfehlt, und das sind die lesenswerten Einträge.

**Jeder neue Test wird mutationsgeprüft.** Der Test wird geschrieben, dann wird der
Code, den er deckt, absichtlich auf die Weise gebrochen, die die Messung
schmeichelhaft aussehen ließe, und der Test muss fehlschlagen. Die Zahlen je Lauf
stehen in den Changelog-Einträgen; eine Gesamtsumme ist aus der Historie nicht
rekonstruierbar, weil der Branch gesquasht wurde.

Was die Praxis wirklich bringt, zeigen die Überlebenden besser als eine Zahl.
Zwei Beispiele, die beide ihre erste Mutation überlebt haben und es nicht hätten
sollen: Ein Test, der prüfen sollte, dass der Reparaturlauf die Passagen schickt,
nach denen er fragt, überlebte eine Mutation, die das Schicken entfernte — weil
das ganze Dokument ohnehin in der Nachricht steht; er prüft jetzt die numerierte
Liste. Und eine Testsuite für die zweistufige Extraktion überlebte eine Mutation,
die die Naht zwischen den Stufen brach, weil beide Hälften getestet waren und die
Nahtstelle dazwischen nicht; der Lauf starb daraufhin in Produktion zweimal je
Dokument, nachdem die erste Stufe bezahlt war.

Eine Mutationsrunde wurde falsch bewertet, weil längengleiche, innerhalb derselben
Sekunde zurückgesetzte Änderungen gegen gecachtes Bytecode gemessen wurden. Jede
Runde wurde mit `PYTHONDONTWRITEBYTECODE=1 -p no:cacheprovider` wiederholt; alle
schlugen weiter fehl wie berichtet, aber der Defekt steht im Log, weil eine
Mutationsprüfung, die still durchläuft, schlimmer ist als keine.

**Keine Ein-Lauf-Vergleiche.** Diese Regel wurde teuer gelernt und ist Thema von
§4.2.

**Die Provenienz schreibt auf, was die API geantwortet hat, nicht was gefragt
wurde.** Diese eine Entscheidung ist der einzige Grund, aus dem ein stiller
Modellwechsel überhaupt aufgefallen ist (§4.8).

## 4. Was wir wissen

### 4.1 Die deterministische Hälfte skaliert, die Extraktion nicht

Speist man die Gold-Spannen als Paket ein, lässt das Gate alle 24 beziehungsweise
49 Claims zweier Entscheidungen ohne Ablehnung zu, und die Abdeckung liefert 0,946
und 0,977. Die deterministische Maschinerie ist von der Dokumentlänge unberührt.
Alles, was einbricht, bricht in der Extraktion ein.

| Dokument | Zeichen | Gold-Spannen | Recall (80 %) |
|---|---:|---:|---|
| Repo-Fixture | 1.707 | 25 | 25/25 |
| EGMR 001-141170 | 10.308 | 24 | 16–20/24 |
| EGMR 001-110144 | 26.715 | 49 | keine Extraktion bei 16.384; 36/49 bei 65.536 |

Die 25 von 25, mit denen das Projekt begann, waren eine Eigenschaft eines kurzen
Dokuments.

### 4.2 Die Streuung einer Konfiguration, und was sie entwertet hat

Die Produktionsprompt erreichte auf demselben Dokument, Modell, Budget und bei
Temperatur 0 in einem Lauf 16 von 24 und in einem anderen 20 — die ganze
Größenordnung des Effekts, den die Prompt-Vergleiche berichteten. Fünf
Wiederholungen wurden daraufhin mit einer Vorab-Regel gefahren.

Das Ergebnis wurde zunächst beruhigend gelesen: Streuung 1. **Diese Lesart ist
zurückgezogen.** Die fünf Wiederholungen lagen in einem Fünf-Minuten-Fenster; über
Sitzungen hinweg liefert dieselbe Konfiguration 16 bis 20 Spannen und 38 bis 47
Claims. Auf dem dichten Paper-Korpus ist die Streuung schon innerhalb eines
Fensters schlimmer: 124 bis 201 von 219 in zwanzig Minuten.

Zwei Folgen:

- Ein Vergleich zweier Prompts, Profile oder Architekturen mit einem Lauf je Arm
  kann keinen Effekt zeigen, der kleiner ist als diese Streuung — und nichts, was
  wir messen wollten, war größer.
- Jeder künftige Vergleich braucht Wiederholungen **über Sitzungen verteilt**,
  nicht über Minuten. Das Fünf-Minuten-Fenster untertreibt die Streuung um einen
  Faktor vier.

### 4.3 Der Zitierfehler, und der größte wiedergewinnbare Verlust

Das Gate verlangt, dass der `raw_span` eines Claims wörtlich im Dokument steht.
Auf der Gerichtsentscheidung wurden 14 von 18 Vorschlägen des Reparaturlaufs mit
`source_span_not_found` abgelehnt — auf einem Dokument, dessen 24 Gold-Spannen
alle wörtlich auffindbar sind.

Die Ursache wurde durch binäre Suche nach dem längsten noch passenden Präfix jeder
abgelehnten Spanne bestimmt: Das Dokument ist hart umbrochen — 28 Zeilen auf
10.308 Zeichen, Median 323 —, also fallen Umbrüche mitten in Sätze, und ein
Vorschlag, der so eine Passage zitiert, schreibt sie als Fließtext. Vier der 24
Gold-Spannen tragen einen Umbruch.

Ein früherer Bericht hatte die Ursache als offen gemeldet. Das war verfrüht: Die
Sonde hatte auf Mehrfach-Leerzeichen geprüft und keine gefunden, wo die richtige
Sonde ein Zeilenumbruch innerhalb der Spanne war.

Klassifiziert über 465 Vorschläge auf einem Paper, vier Läufe:

| | Anzahl |
|---|---:|
| wörtlich verankert | 412 |
| unterscheidet sich nur im Leerraum | 42 |
| echte Umformulierung, zu Recht abgelehnt | 11 |
| braucht zusätzlich Kleinschreibung | **0** |

Die Leerraum-Fälle auf einer normalisierten Kopie zu verankern und die Zeichen des
Dokuments zurückzugeben, wurde offline auf sieben fertigen Läufen gerechnet,
**bevor** etwas gebaut war. Das gebaute Gate reproduziert alle sieben Vorhersagen
exakt: 216, 219, 192, 218, 218, 198, 196 von 219.

Und auf der Gerichtsentscheidung, über drei Reparaturrunden: **24/24, 22/24,
24/24.** Die vollständige Gold-Antwort, zweimal von drei, wo das bisherige Maximum
23 war und der Ausgangswert 16.

Die Streuung fällt von 77 auf 27 Spannen im einen Arm und von 82 auf 22 im
anderen. **Der Extraktor war viel stabiler, als jede Messung aussah; was streute,
war, ob das Gate seine Zitate annimmt.**

Stand: in Produktion (#18). Kleinschreibung und Satzzeichen bleiben draußen —
gemessen, nicht gewählt: Casefolding verankert nichts weiter und verändert keine
Identität.

### 4.4 Der verankerte Anteil als Warnleuchte — und seine Tautologie

Das Produkt berechnet ohne jede Gold-Antwort den Anteil der Dokumentzeichen, auf
denen irgendein zugelassener Claim ankert. Über vier Paper ähnlicher Länge unter
einer Konfiguration ordnet er den Recall identisch:

| Paper | Gold-Spannen | Recall | verankerter Anteil |
|---|---:|---|---:|
| A40 | 250 | 50 (20 %) | 0,25 |
| A24 | 219 | 80 (37 %) | 0,37 |
| A21 | 257 | 112 (44 %) | 0,39 |
| A34 | 267 | 184 (69 %) | 0,75 |

Das ist das einzige gold-freie Signal im System, das der Größe folgt, die es nicht
sehen kann — validiert gegen eine externe Referenz auf Dokumenten, gegen die
nichts abgestimmt wurde.

**Der Vorbehalt, nachgetragen und zum Befund gehörend:** Eine abgelehnte
Verankerung senkt mechanisch *beide* Größen. Ein Teil der Korrelation kann also
eingebaut sein. Ob die Leuchte auch nach der Anker-Reparatur (§4.3) noch ordnet,
ist ungemessen — und das offline auf den anderen drei Papern nachzurechnen ist
gratis und nicht getan.

### 4.5 Die Identität eines Claims: der Wortlaut des Modells war die instabile Hälfte

Das Gate adressiert einen Knoten über `document_id`, `claim_type`,
`canonical_content` des Modells und das Zitat. Eine Relation hasht beide
Knoten-Ids, also verändert ein umformulierter Claim jede Kante, die ihn berührt.

Fertige Läufe auf fünf Identitätsstufen neu geschlüsselt, gezählt werden die
Claims, die in *jedem* Lauf vorkommen:

| Stufe | A24, 4 Läufe | EGMR, 3 Runden |
|---|---:|---:|
| heutige Identität | 36 | 19 |
| nur das Zitat, leerraum-normalisiert | **75** | **30** |
| nur die Proposition des Modells | 53 | 20 |

Den Span aus der Identität zu nehmen bringt auf Rechtstext 5 Prozent. Den Wortlaut
des Modells herauszunehmen bringt 58. **Das Zitat des Dokuments ist der stabile
Träger; was das Modell schreibt, ist es nicht.**

Schutzbedingungen, alle erfüllt: innerhalb eines Laufs verschmolzen 0,0 / 0,0 /
3,6 Prozent gegen eine Vorab-Grenze von 5; die Propositionen hinter einem
gemeinsamen Span-Key stimmen mit Median 1,00, Minimum 0,71 überein, keiner von 170
Keys unter 0,5. Die einzigen Verschmelzungen innerhalb eines Laufs sind Paare aus
Erstpass und Reparaturlauf, dieselbe Aussage am selben Zitat — der Fall, für den
eine Heuristik von Hand gebaut worden war.

**Das wurde gebaut und in dieser Form zurückgezogen.** Eine Textstelle ist ein Ort
im Dokument, keine Proposition: Ein Satz kann mehrere Aussagen tragen, und
derselbe Satz lässt mehrere Lesarten zu. Allein auf den Anker geschlüsselt wird
die zweite Aussage an einer Stelle als Dublette abgelehnt, und die Maschine
behält still die, die zuerst kam. Divergente Lesarten eines Zitats müssen ein
Konflikt werden, den ein Mensch vergleicht, keine automatische Dublette.

Die Prüfung, die das durchgelassen hat, war schwach, und das ist der nützliche
Teil: sechs Verschmelzungen, ein Dokument, alle aus dem Reparaturlauf — einer
Konfiguration, die Dubletten erzeugt, weil sie denselben Text zweimal befragt. Ein
Paar mit einer Token-Überschneidung von 0,48 wurde als dieselbe Aussage
*geurteilt* statt gemessen, und daraus eine Regel für alle Fälle gezogen.

Hinterher getrennt gemessen hat **der Kollaps keinen einzigen Gold-Span gekauft**:
Die Anker-Hälfte allein reproduziert alle sieben Vorhersagen und beide
24-von-24-Runden, bei erhaltenen sechs Paaren. Gekauft hat er nur die
Stabilitätszahl — 44 gegen 75 auf einem Paper, 19 gegen 30 auf der Entscheidung —
und dafür Propositionen bezahlt.

Stand: Die Anker-Hälfte ist in Produktion (#18). Die Identitäts-Hälfte braucht ein
zweistufiges Design — der Anker als stabiler Schlüssel für Abdeckung, Relationen
und Lauf-Vergleiche, mehrere Claims darunter erlaubt, Divergenz markiert — und das
braucht einen Begriff für vergleichbare Lesarten, den kein Zählen liefert. Ein
annotierter Prüfbestand schon.

Angestoßen hat das das eigene frühere Working Paper des Projekts, das eine
Identität aus Subjekt, Relation, Objekt und Scope ohne Oberflächentext
spezifiziert. Die Unterscheidung, die es zieht — Identität ist nicht Beleg ist
nicht Zustand — ist richtig und hat die Änderung erst möglich gemacht. Seine
*Zuordnung* passt für diesen Aufbau nicht: Sie setzt drei vom Modell geschriebene
Felder in die Identität, und vom Modell geschriebene Felder sind hier die
unzuverlässige Hälfte. Außerdem setzt sie Entitätsauflösung voraus, die es hier
nicht gibt.

### 4.6 Der Reparaturlauf

Das Gate kann keinen Claim hinzufügen, also ist eine Passage, die kein Claim
erreicht, unsichtbar. Die Abdeckungsmessung benennt diese Passagen; ein zweiter
Aufruf fragt nach genau ihnen, mit den bereits gehaltenen Claims als Liste dessen,
was nicht zu wiederholen ist, und jeder Vorschlag läuft durch eine
Zulassungsregel, die vor dem Bau entschieden wurde.

Auf Papern, gezielt auf unverankerte Lücken: mittlerer Gewinn **+97 Spannen**,
Endstände 215, 203 und 206 von 219 (~95 %), und die Streuung des Endstands fällt
auf 5, wo der erste Pass um 46 schwankt. Auf dünn verankerte Blöcke gezielt bringt
+53 — die Designannahme hinter diesem Modus war falsch.

Er ist selbstbegrenzend: Auf der eigenen Fixture fand eine Runde gar keine Lücke
und machte keinen zweiten Aufruf; eine andere fand eine einzige 179-Zeichen-Lücke,
und zwei Claims hoben 24/25 auf 25/25.

**Was er nicht tut:** Auf der Gerichtsentscheidung brachten drei Runden vor der
Zitat-Reparatur null, gegen eine Vorab-Marke von zwei. Ein Teil seines gemessenen
Gewinns auf Papern war Wiederbeschaffung dessen, was das Gate abgelehnt hatte —
und nach §4.3 lehnt es das nicht mehr ab. Ob der Lauf sich noch rechnet, ist damit
offen.

### 4.7 Ausgabebudget

Die 16.384 Token sind selbstgesetzt; das Modell lässt 384.000 zu. Der Einwand
gegen eine Erhöhung war, sie tausche einen lauten Fehler gegen einen leisen.

Die Messung stützt das nicht. Bei 65.536 liefert die 26.715-Zeichen-Entscheidung
108 Claims, 36 von 49 streng und 46 von 49 bei 50 Prozent Überlappung, verankerter
Anteil 0,82 — ein *besserer* strenger Recall als die kürzere Entscheidung mit
derselben Prompt, und kein dünner Graph. Zwei Dinge bleiben richtig: Die Abdeckung
meldet die Lücke weiterhin, und die Abbruchgrenze verschiebt sich proportional
statt zu verschwinden (64k Token reichen grob bis 110.000 Zeichen; die längste
Entscheidung im Korpus hat 447.000).

Das Limit ist in Produktion unverändert. Geändert hat sich, dass eine Erhöhung
jetzt eine Entscheidung mit Messung dahinter wäre.

### 4.8 Der Anbieter hat das Modell unter uns gewechselt

Die Anfrage verlangt `deepseek-v4-flash`. Seit dem 31. August antwortet das
Envelope `deepseek-flash`. Sichtbar war das nur, weil die Provenienz aufschreibt,
was die API antwortet.

Gleiches Dokument, gleicher Korpus-sha256, gleiche Prompt, gleiches Budget:

| | Anker-Ablehnungen | davon echte Umformulierung | davon nur Leerraum | Recall |
|---|---:|---:|---:|---|
| 31. August | 64 von 134 | 54 | 10 | 80/219 |
| 25. September, Lauf 1 | 9 von 111 | 0 | 9 | 194/219 |
| 25. September, Lauf 2 | 7 von 122 | 0 | 7 | 201/219 |
| 25. September, Lauf 3 | 31 von 111 | 11 | 20 | 124/219 |

Der dominierende Fehlerterm im August war falsches Zitieren, und er ist fast
verschwunden. **Jeder Vergleich über Wochen hinweg in dieser Arbeit vergleicht
daher zwei ausgelieferte Modelle**; Vergleiche innerhalb einer Sitzung stehen.

Das Dossier nennt jetzt das angefragte neben dem ausgelieferten Modell und sagt es
in einer Zeile, wenn sie abweichen. Ein fehlgeschlagener Aufruf nennt nicht mehr
das angefragte Modell, als wäre es gelaufen. Innerhalb einer Stunde nach dem
Einbau meldete ein Lauf eine Ersetzung in allen zehn Aufrufen.

### 4.9 Die Reviewer-Arme

Fünf Läufe über einen eingefrorenen Graphen — das eigene Paket durch das echte
Gate, sodass sich nur die Arme bewegen können — fanden etwas, das das Dossier die
ganze Zeit protokolliert hatte und niemand gelesen hat:

**Der Thinking-Arm fehlte in drei von fünf Reviews**, abgeschnitten am fest
verdrahteten Reviewer-Budget von 8.192 Tokens, auf einem 1.700-Zeichen-Antrag.
Jeder zweite bis dritte Review lief mit einem statt zwei unabhängigen Armen, das
Anti-Delphi-Prinzip war in diesen Fällen also nicht erfüllt.

Das Budget hoch genug gesetzt, dass nichts abschneidet, und abgelesen, was der Arm
verbraucht:

| Lauf | Evidenz-Arm | Thinking-Arm |
|---|---:|---:|
| 1 | 1.962 | 8.453 |
| 2 | 2.417 | 8.226 |
| 3 | 2.129 | 10.369 |
| 4 | 1.961 | **12.159** |
| 5 | 2.002 | 10.759 |

Der Arm braucht 8.226 bis 12.159 Ausgabe-Tokens. Das Budget war 8.192 — **genau an
der unteren Kante des Bedarfs**, die schlechteste Stelle für eine Grenze, weil sie
dort unvorhersagbar greift statt immer. Deshalb schrieb der Arm zweimal von fünf
fertig und nicht nie. Der Faktor fünf zwischen den Armen bei denselben elf
Befunden ist das Denken selbst.

Gemessen ist das auf dem kürzesten Dokument des Repos, und der Reviewer-Prompt
trägt den Graphen, also ist es eine untere Schranke. Stand: parametriert im Review
als #16; der Produktionswert ist eine offene Entscheidung.

### 4.10 Relationslabels: Feldverwechslung, keine Vokabularlücke

Achtzehn Relationsvorschläge über 32 Lauf-Artefakte wurden wegen unbekannten
`relation_type` abgelehnt:

| Label | Treffer | Fall |
|---|---:|---|
| CAUSAL | 9 | **eigener Claim-Typ im Relationsfeld** |
| LIMITATION | 7 | **eigener Claim-Typ im Relationsfeld** |
| CAUSES | 1 | Familie vorhanden |
| DEFINES | 1 | Familie vorhanden |

**16 von 18 sind Feldverwechslungen**, die die Produktionsprompt wörtlich verbietet
und die trotzdem passieren. Keiner ist eine fehlende Relationsfamilie. Ein
früherer Bericht hatte das Gegenteil behauptet; das ist zurückgenommen.

Was es behebt, ist die Aufspaltung aus §4.11: einstufig 10 ungültige Labels über
rund 173 vorgeschlagene Kanten, zweistufig **0 über 192**, weil die Relationsstufe
kein Claim-Typ-Feld hat, aus dem etwas lecken kann.

Getrennt davon und strukturell: Die vierzehn Relationstypen decken vier der sechs
Familien des eigenen Working Papers. **STATISTICAL und NORMATIVE haben kein
einziges Mitglied** — das System kann „A korreliert mit B" nicht ausdrücken, ohne
es in eine Kausal- oder Abhängigkeitsrelation zu pressen, was das Paper als einen
der häufigsten Fehler beim automatischen Graphenbau benennt. Die Lücke ist auf dem
Papier echt und hat in diesen Daten **keine Stütze**: Das Modell hat nie danach
gefragt. Eine Zählung dessen, wonach trotz geschlossener Liste gegriffen wird, kann
unterdrückte Nachfrage nicht messen; die Lücke steht als ungeprüft da, nicht als
Befund.

### 4.11 Zweistufige Extraktion

Claims in einem Aufruf, Relationen über die fertige Claim-Liste in einem zweiten,
gegen den einstufigen Produktionsaufruf, drei Läufe je Arm in einem Fenster, Regel
zuerst festgelegt: Verbesserung nur, wenn sich die Arme nicht überschneiden.

| | Recall von 219 |
|---|---|
| einstufig | 194, 201, 124 (und 209 als Drift-Probe) |
| zweistufig | 203, 127, 121 |

Arm A allein streut 77 Spannen, wo die Vorab-Regel 40 als Grenze nennt, ab der
Mittelwerte nichts sagen. **Urteil: Auflösung unzureichend.** Die Aufspaltung ist
weder gezeigt noch widerlegt.

Zwei saubere Eigenschaften unabhängig davon: Die Gegenprobe auf der Fixture
erreicht 25 von 25 Gold-Claims mit 19 Relationen gegen die eingefrorenen 15, und
die Relationsstufe hat in keinem Lauf eine Id erfunden — 67 von 67, 60 von 60, 65
von 65 auflösbar — neben den null ungültigen Labels oben.

Nicht übernommen: Es kostet einen zweiten bezahlten Aufruf je Dokument, und der
Recall-Fall ist nicht gemacht.

### 4.12 Bedeutung, getrennt von Verankerung gemessen: die Schicht hat übersetzt

Jedes bis hierher gemessene Korpus annotiert, *wo* eine Argumenteinheit sitzt.
Keines annotiert, ob der Claim, der sie zitiert, noch dasselbe bedeutet — ein
Claim kann perfekt ankern und die Negation verlieren, und der Span-Recall zählt
das als Treffer. Also wurden 24 kurze Fälle von Hand annotiert, zwölf Bedeutungen
auf Deutsch und Englisch, über Negation, Modalität, Korrelation gegen Kausalität,
Bedingung und Geltungsbereich, Sprecher und mehrere Aussagen in derselben
Textstelle. Jede Bedingung ist eine Token-Gruppe oder ein regulärer Ausdruck,
nie ein Modell, das beurteilt, ob zwei Sätze dasselbe bedeuten — sonst kämen das
geprüfte System und sein Prüfer aus einer Familie.

Drei Ergebnisse werden **getrennt** berichtet — Verankerung, Bedeutung,
Relationen — genau damit eine Änderung nicht dadurch besser aussehen kann, dass
sie *mehr Text* erfasst.

**Erster Lauf, 72 bezahlte Aufrufe.** Der Apparat hält: 24 von 24 Fällen haben in
allen drei Läufen einen Claim auf ihrer Spanne verankert, gegen eine vorab
gesetzte Marke von 90 Prozent, und `anchor_normalised` ist 0 über alle 248
zugelassenen Claims — die erste Live-Ausübung des Anker-Gates aus #18, das bis
dahin nur gegen gespeicherte Pakete geprüft war.

Dann der Befund, nach dem niemand gesucht hat. **38 von 122 Propositionen aus
deutschen Quellen kamen auf Englisch zurück, 0 von 126 aus englischen Quellen auf
Deutsch.** Der `raw_span` zitiert das deutsche Dokument, `canonical_content`
nicht. Keine Messung dieses Projekts hat je auf die *Sprache* einer Proposition
gesehen, und das Versprechen im README, zitierte Claims behielten ihren Wortlaut,
gilt für die Spanne und nicht für die Proposition.

Zwei Erklärungen, und sie konkurrieren nicht. Die banale: Der Extraktionsvertrag
erwähnte Sprache überhaupt nicht, während der Reviewer-Vertrag seit immer eine
Sprachanweisung trägt. Die tiefere: **Ein reiner Extraktor kann nicht
übersetzen.** Um einen deutschen Satz als treue englische Proposition zu
schreiben, muss das Modell Subjekt, Prädikat, Geltungsbereich und Polarität
bereits unabhängig vom deutschen Wortlaut repräsentieren und dann neu
verbalisieren. Die semantische Projektion findet statt — sie wird nur nicht
behalten. Das erklärt rückblickend 4.5, dort als Tatsache ohne Ursache berichtet:
`raw_span` ist eine *Auswahl* ins Dokument und deshalb reproduzierbar,
`canonical_content` eine *Erzeugung* und deshalb die instabile Hälfte.

**Zweiter Lauf, dieselben 72 Aufrufe, eine Variable.** Drei Zeilen kamen in den
Extraktionsvertrag, neben die Regel für wörtliche Spannen: die Proposition in der
Sprache des Dokuments, nicht übersetzt, weil ein Claim gegen die Spanne prüfbar
sein muss, die er zitiert. Fallbestand und Scorer sind zwischen beiden Läufen
byte-identisch, `meaning_preserved` ist unverändert definiert.

| | vorher | nachher | Schwelle, vorab |
|---|---:|---:|---|
| übersetzt, deutsche Quelle | 38 von 122 | **0 von 123** | ≤ 5 ⇒ steuerbar |
| übersetzt, englische Quelle | 0 von 126 | 0 von 119 | muss 0 bleiben |
| Negation | 12/12 | 12/12 | Schutzbedingung: ein Fall nimmt die Änderung zurück |
| Modalität | 12/12 | 12/12 | Schutzbedingung |
| Bedeutung erhalten, alle Fälle | 59/72 | **69/72** | — |

**Die verborgene Projektion ist durch eine Anweisung steuerbar.** Der Effekt ist
vollständig und nicht teilweise, die Ausbeute ist nicht gefallen (242 gegen 248
Claims), und Geltungsbereich ging 3/6 → 6/6, Sprecher 9/12 → 12/12, mehrere
Aussagen 10/12 → 12/12, Korrelation 11/12 → 12/12. Alle vier Fälle, die
*ausschließlich an der Sprache* gescheitert waren, bestehen jetzt ihre
bestehenden, unveränderten Bedingungen — ein Gold-Mangel, gelöst ohne das Gold
anzufassen. Für das Sprachproblem braucht es keine explizite Projektionsschicht.

**Was die Anweisung nicht angefasst hat: die Bedingung.** „Wenn die Mittel
bewilligt werden, beginnt der Ausbau im Frühjahr." In drei von sechs Läufen
**zerlegt der Extraktor den Satz am Komma**: der Vordersatz wird ein eigener
Claim, getypt als `assumption`, was eine zulässige Lesart ist, und der Nachsatz
wird ein eigener Claim, getypt als `forecast`, **unbedingt behauptet.** „Der
Ausbau beginnt im Frühjahr" ohne jede Bedingung ist eine erfundene Zusage — für
eine Antragsprüfung genau die Fehlerklasse, für deren Entdeckung das Produkt
existiert, erzeugt vom Produkt. In den anderen drei Läufen trägt ein Claim den
ganzen Bedingungssatz. 2 von 6 vorher gegen 3 von 6 nachher ist auf sechs
Versuchen nichts und wird als unverändert berichtet.

Sie ist jetzt der einzige gemessene Bedeutungsfehler im Bestand, und das ist ein
weit besser gestellter Gegenstand als „die semantische Schicht ist
unzuverlässig": ein einzelnes reproduzierbares Strukturversagen an einer
benannten Konstruktion. Ob es explizite Felder für Modalität und Geltungsbereich
braucht oder — wie bei jeder kleinen Änderung dieses Projekts, die gewirkt hat —
eine weitere Vertragszeile, ist die nächste Vorab-Frage.

**Grenzen.** Relationen bleiben nicht messbar: der Bestand annotiert keine Kanten,
aufgefallen beim Implementieren der Achse. Der Bestand ist ein **Entwurf** und
wartet auf zwei unabhängige Durchsichten, die nicht stattgefunden haben. Jeder
Fall ist ein bis drei Sätze; dass eine Vertragszeile auf 24 kurzen Sätzen greift,
sagt nichts über 26.000 Zeichen Gerichtstext.

## 5. Was wir nicht wissen

Als Fragen formuliert, weil jede eine Messung ist, die niemand gemacht hat.

1. **Übersteht die Warnleuchte die Anker-Reparatur?** Ein Teil ihrer Korrelation
   kann mechanisch sein (§4.4). Sie offline auf den anderen drei Papern unter dem
   neuen Gate nachzurechnen ist gratis und nicht getan.
2. **Rechnet sich der Reparaturlauf noch?** Viel von seinem Gewinn war
   Wiederbeschaffung von Ablehnungen, die das Gate nicht mehr ausspricht (§4.6).
3. **Wie groß ist die Streuung des Extraktors über Sitzungen unter dem neuen
   Gate?** Die 77 Spannen sind unter dem alten gemessen, die Rechnung legt 27
   nahe — eine Offline-Schätzung, keine Messung.
4. **Wie stabil sind die Reviewer-Arme?** Der Anteil der in allen fünf Läufen
   vorkommenden Befunde lag bei 0,63, als der Thinking-Arm dreimal fehlte, und bei
   **0,27**, als er arbeitete — unter der 0,5, die vorab für „instabil" festgelegt
   war. Schlimmer: Der Evidenz-Arm fiel allein von 0,77 auf 0,27, bei identischem
   Graphen und einer Grenze, die für ihn nie bindend war. Entweder ist die
   Stabilitätszahl selbst nicht reproduzierbar, oder das erhöhte Budget hat das
   Verhalten dieses Arms verändert; getrennt ist das nicht, und es zu trennen
   braucht einen Lauf mit dem alten Budget in einer anderen Sitzung.
5. **Was braucht der Thinking-Arm auf einem echten Dokument?** 12.159 Tokens sind
   auf 25 Claims gemessen; eine Gerichtsentscheidung ergibt 40 bis 57.
6. **Überträgt sich Extraktionsqualität zwischen Dokumentarten?** Vier Paper unter
   einer Konfiguration gaben 20, 37, 44 und 69 Prozent — „eine Eigenschaft des
   Dokuments" war der Schluss, aber unter einem toleranten Gate landen alle
   A24-Läufe zwischen 88 und 100 Prozent. Der Schluss steht damit in Zweifel, und
   die anderen drei Paper sind nicht nachgerechnet.
7. **Die Abdeckung.** Claims, die der Extraktor nie vorgeschlagen hat, sind von
   allem oben unberührt, und von 465 Vorschlägen bleiben 11 zu Recht als
   Umformulierung abgelehnt.
8. **Ob irgendetwas davon auf einem deutschen Dokument hält.** Jeder verwendete
   externe Korpus ist englisch. Fixture und Oberfläche des Produkts sind
   zweisprachig, die Messungen nicht.
9. **Ob die zwei fehlenden Relationsfamilien etwas kosten** (§4.10). Das zu messen
   braucht eine Extraktion, der keine geschlossene Liste vorgelegt wird.
10. **Ob der Zustand eines Befunds je aufgelöst werden kann.** `Finding.state` ist
    immer `human_review_required`, und nichts schreibt es je. Ein Entwurf, ihn
    gegen eine revidierte Fassung desselben Dokuments aufzulösen, existiert auf
    dem Papier und ist ungebaut.

## 6. Probleme: gelöst und ungelöst

### Gelöst

| Problem | Wie | Stand |
|---|---|---|
| Ein nie vorgeschlagener Claim ist unsichtbar | Abdeckungsmessung: verankerter Anteil plus benannte Lücken, replay-stabil | in Produktion |
| Die 98-Prozent-Aussage war skalenabhängig | Auf kurze Dokumente eingegrenzt; Median 72 Prozent auf Entscheidungen | in Produktion |
| Ein Verbindungsabbruch riss den Lauf als Absturz ab | `IncompleteRead` und `ConnectionError` im Retry | in Produktion |
| Ein schemawidriger Vorschlag kostete ein ganzes Dokument | Der Vorschlag fällt mit Grund, das Paket bleibt | in Produktion |
| Ein vor dem Gate abgelehnter Vorschlag verschwand aus dem Audit | Vor-Gate-Ablehnungen reisen mit dem Paket ins Dossier | in Produktion |
| Eine stille Modellersetzung war nicht erkennbar | Angefragtes und ausgeliefertes Modell protokolliert, Abweichung gemeldet | in Produktion |
| Ein ganzer Abschnitt blieb unbearbeitet | Reparaturlauf über genau die unverankerten Lücken | in Produktion |
| Ein Zitat scheitert an einem Zeilenumbruch | Toleranter Anker auf leerraum-normalisierter Kopie | in Produktion (#18) |
| Ein umformulierter Claim ist ein anderer Knoten und verändert jede Kante | *Nicht gelöst.* Die gebaute Fassung hätte eine zweite Lesart derselben Stelle verworfen | zurückgezogen, §4.5 |
| Der Thinking-Arm fehlte still in den meisten Reviews | Budget parametriert, Bedarf gemessen | im Review (#16) |
| Die Proposition wurde still aus der Sprache des Dokuments übersetzt | Eine Zeile im Extraktionsvertrag: die Proposition in der Sprache des Dokuments, nicht übersetzt | im Review; 38 von 122 → 0 von 123 (§4.12) |

### Ungelöst

| Problem | Warum es offen ist |
|---|---|
| Abdeckung — Passagen, die der Extraktor nie liest | Kein Mechanismus außer einem zweiten bezahlten Aufruf, dessen Wert jetzt unklar ist |
| Die Streuung selbst | Verkleinert, nicht beseitigt; 27 Spannen sind größer als die meisten messwerten Effekte |
| Reviewer-Stabilität | 0,27 nach der strengen Regel, und die Zahl ist nicht reproduzierbar (§5.4) |
| Abbruch auf langen Dokumenten | Die Grenze wandert mit dem Budget, sie verschwindet nicht |
| Echte Umformulierung im Zitat | 11 von 465 Vorschlägen, zu Recht abgelehnt, dauerhaft verloren |
| Relations-Ausdruckskraft | Vier von sechs Familien gedeckt; die Lücke ist ungeprüft |
| Der Zustand eines Befunds wird nie aufgelöst | Braucht ein versioniertes Overlay und eine Schemaentscheidung |
| Bedingungssätze | In der Hälfte der Läufe am Komma zerlegt; der Nachsatz steht dann unbedingt da. Eine Sprachanweisung hat es nicht berührt (§4.12) |
| Bedeutung eines Claims, jenseits von 24 kurzen Sätzen | Der einzige Bedeutungsbestand sind 24 Fälle von einem bis drei Sätzen, und er ist ein Entwurf vor zwei unabhängigen Durchsichten |
| Beziehungen zwischen Claims | Das dritte Ergebnis aus §4.12 ist weiter nicht messbar: der Bedeutungsbestand annotiert keine Kanten |
| Deutschsprachige Evidenz | 24 von Hand annotierte Fälle, die Hälfte davon deutsch, zweimal gelaufen — und nichts Längeres. Kein deutsches Dokument über Fixture-Länge ist gemessen |

## 7. Zurückgezogene Aussagen

Jede davon wurde berichtet, im Repository veröffentlicht und später zurückgezogen.
Sechs der neun haben dieselbe Ursache: ein Vergleich mit einem Lauf je Arm, bevor
die Streuung einer einzigen Konfiguration bekannt war.

1. **„Eine domänenspezifische Prompt-Notiz hebt den Recall von 16 auf 20 von
   24."** Über fünf Entscheidungen gesweept ergab sie 44 gegen 55 Gold-Spannen in
   Summe und fiel auf einem Dokument von 17/23 auf 7/23. **Widerlegt.**
2. **„Die Streuung einer Konfiguration ist 1, Sampling erklärt 16 gegen 20
   nicht."** Die fünf Wiederholungen lagen in einem Fünf-Minuten-Fenster. Über
   Sitzungen ist die Streuung 16 bis 20. **Als Fenster-Artefakt zurückgezogen.**
3. **„Die Gold-Antwort erreicht gegen sich selbst 186 von 219, das ist die
   Decke."** Ein Reparaturlauf erreichte 210. Gold-Spannen als Claims zurückzuspeisen
   ist für ein inhaltsadressiertes Gate ein pathologischer Eingang — identische
   kurze Fragmente kollabieren —, die Zahl war also nie eine Obergrenze.
   **Zurückgezogen, bleibt als Diagnose.**
4. **„Die Ursache des Zitierfehlers ist offen."** Die Sonde hatte auf
   Mehrfach-Leerzeichen geprüft; richtig war ein Zeilenumbruch in der Spanne.
   **Verfrüht.**
5. **„Jedes Relationslabel, nach dem gegriffen wird, ist ein Familienlabel, das
   unser Vokabular nicht hat."** 16 von 18 sind unsere eigenen Claim-Typen im
   Relationsfeld. **Zurückgenommen.**
6. **„Die Lückenliste deckt 98 Prozent des unverankerten Textes."** Richtig für
   1.700-Zeichen-Abstracts, Median 72 Prozent auf Entscheidungen. **Eingegrenzt.**
7. **„Die Auflösung der Reviewer-Arme ist 0,63."** Gemessen mit einem Arm, der in
   drei von fünf Läufen fehlte, beschrieb die Zahl den einen Arm, der antwortete.
   Mit beiden Armen sind es 0,27. **Neu gelesen.**
8. **„Einen Claim allein auf seinen Anker zu schlüsseln ist unbedenklich, weil die
   Verschmelzungen Dubletten sind."** Geprüft an sechs Verschmelzungen eines
   Dokuments, alle aus dem Reparaturlauf, mit einem Paar bei 0,48
   Überschneidung, das geurteilt statt gemessen wurde. Eine Textstelle kann
   mehrere Aussagen tragen und lässt mehrere Lesarten zu; die Regel hätte die
   zweite still verworfen. **Zurückgezogen, nachdem die Anker-Hälfte ohne sie
   ausgeliefert wurde** — und die Trennung zeigte, dass der Kollaps gar keinen
   Recall gekauft hatte.
9. **„Ein Lauf je Budgetstufe klärt, was der Thinking-Arm braucht — abgeschnitten
   ist abgeschnitten."** Der Arm schrieb beim alten Budget zweimal von fünf fertig,
   der Ausfall ist also stochastisch, und eine Treppensuche berichtet, welche Stufe
   Glück hatte. **Korrigiert, bevor der Lauf bezahlt war** — mit der achten einer
   von nur zwei, die rechtzeitig auffielen.

Zwei kleinere Korrekturen, die keine Rücknahmen sind, aber festgehalten gehören,
weil sie veröffentlicht waren: Der gebrochene Claim der Bedingung wurde zuerst
als „The funds *will be* granted" berichtet, wo das Modell „The funds **are**
granted" geschrieben hat — eine Falschzitierung der Ausgabe, korrigiert aus den
sechs Läufen in §4.12. Und eine vorab festgelegte Vorhersage, zwei der
Bedeutungsfälle enthielten eingebaute Falschalarme, ist **widerlegt**: beide
haben 3 von 3 in beiden Sprachen bestanden, und der wirkliche Mangel des
Bestands war ein nicht vorhergesehener.

## 8. Was die externe Arbeit beigetragen hat

**Die annotierten Korpora haben die eigentliche Arbeit getan.** Ohne fachliche
Annotation gibt es keine Recall-Zahl, und ohne Recall-Zahl ist die
Abdeckungsmessung eine Zahl ohne Kalibrierung. Vier der Befunde oben existieren
nur, weil jemand anders 15.000 Argumentspannen in Gerichtsentscheidungen annotiert
hat.

**Das eigene Working Paper des Projekts zu einem Semantic Projection Layer** hat
die Unterscheidung geliefert, die §4.5 erst möglich machte: Identität, Beleg und
Zustand sind drei verschiedene Dinge, und ein Claim ist dieselbe Proposition, ob
der Extraktor zu 81 oder 82 Prozent sicher war. Das ist richtig, und das System
hatte alle drei in einen Hash geworfen.

Seine konkreten Vorschriften haben sich nicht übertragen:

- Sein Identitätsschlüssel ist Subjekt, Relation, Objekt und Scope — drei vom
  Modell geschriebene Felder —, wo die Messung sagt, dass vom Modell geschriebene
  Felder die instabile Hälfte sind. Er setzt außerdem Entitätsauflösung voraus, die
  es hier nicht gibt.
- Seine zweistufige Projektion teilt entlang der Relationshierarchie (Familie,
  dann Relation), und ihre Begründung beschreibt genau unseren Fehlerfall. Nur ist
  der Fehler eine Feldverwechslung (§4.10), die eine Familie-zuerst-Frage nicht
  berührt.
- Seine Entropie- und Divergenz-Maschinerie braucht eine kalibrierte Verteilung
  über Relationen. Eine einzelne JSON-Completion liefert keine, und die
  Konfidenz-Zahlen, die ein Modell schreibt, sind keine Wahrscheinlichkeiten. Die
  offenen Fragen des Papers sagen selbst, dass die Schwellen eine empirische
  Kalibrierung brauchen, die nie gemacht wurde.

Die eine Anpassung, die es wert ist: **Die Wiederholungen, die wir ohnehin
bezahlen, sind eine empirische Verteilung.** Fünf Läufe geben pro Claim eine
relative Häufigkeit, die per Konstruktion kalibriert ist, weil sie gezählt und
nicht behauptet wird. Das verwandelt die Streuung von dem, was jede Messung
ruiniert, in das, was die Emissionsregeln des Papers wollten. Ungebaut.

## 9. Nachvollziehen

Der bezahlte Pfad läuft nur auf manuellen Anstoß, und der Key existiert nur als
GitHub-Actions-Secret — lokal ist er nie verfügbar.

```
.github/workflows/live-deepseek.yml      jeder bezahlte Lauf, über Dispatch-Eingaben
scripts/                                 21 Messskripte, jedes getestet
docs/architecture.md §3a–§3ah            die chronologische Aufzeichnung
CHANGELOG.md                             was sich bewegt hat, samt Rücknahmen
```

Die Offline-Kontrollen spielen gespeicherte Pakete ab und rufen keinen Provider:
`polished` 5 Claims / 5 Relationen / 3 Befunde, `rough` 4 / 4 / 0, `budget`
25 / 15 / 10. Sie sind die Referenz für Verhaltensänderungen — und sie können eine
Prompt-Regression nicht sehen; das kann nur ein Live-Lauf gegen das eingefrorene
Paket.

360 Tests und einer übersprungen, `ruff check` sauber.

## 10. Offene Entscheidungen

Keine Messungen — Urteile, die Geld kosten oder gespeicherte Daten verändern.

1. **Das Reviewer-Ausgabebudget.** 12.159 Tokens auf dem kürzesten Dokument
   gemessen; 32.768 ist der erste Wert mit Reserve gegen die Hochrechnung auf ein
   echtes. Jeder Aufruf kostet dann mehr.
2. **Wie die zweistufige Identität aussehen soll.** Die Anker-Hälfte ist drin; die
   Identitäts-Hälfte braucht einen Begriff für vergleichbare Lesarten, den nur ein
   annotierter Prüfbestand liefert (§4.5).
3. **Ob der Reparaturlauf bleibt**, wo das Gate nicht mehr ablehnt, was er
   wiederbeschafft hat.
4. **Ob das Relationsvokabular** um die zwei fehlenden Familien erweitert wird —
   auf Evidenz, die es noch nicht gibt.
5. **Ob die Bedingung explizite Projektionsfelder braucht.** Modalität und
   Geltungsbereich als eigene Felder, statt sie dem Satzbau einer Proposition zu
   überlassen. Für das Sprachproblem waren sie nicht nötig (§4.12); die Bedingung
   ist der verbleibende Kandidat und der einzige noch gemessene
   Bedeutungsfehler.
6. **Wer den Bedeutungsbestand durchsieht.** Er ist absichtlich ein Entwurf: zwei
   unabhängige Durchsichten sind angefragt und keine hat stattgefunden, und
   solange ruht jede Zahl in §4.12 auf Fällen, die dieselbe Partei geschrieben
   hat, die das System gebaut hat.
