# Content Review — Research Report

**What a claim-graph reviewer can and cannot do, measured against external gold
standards.**

This report collects what forty-odd paid measurement runs established, what they
refuted, and what is still open. It is written for someone who has not followed
the work: the chronological record is in [`architecture.md`](architecture.md)
§3a–§3ao, which is a log rather than a synthesis.

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

That number rests on a set of cases this project wrote itself, so the set was sent
to two independent reviews — neither from the family that wrote it nor the system
under test, and neither shown a figure from any run. **They broke half of it.**
Twelve of the 24 cases could be passed by renderings that lose the meaning, and in
one case the gold asserted a pragmatic implicature rather than what the sentence
entails. Their sixteen counterexamples were checked against the validator before
anything changed: twelve held, four were refuted, and the four were refuted for one
reason both reviews shared. The cases were then rewritten with the documents left
untouched, so the runs already paid for could be scored again — and **69 of 72 came
back unchanged against a strictly harder instrument** (§4.16). The headline figure
survived an outside attempt to break the thing that produced it, which is the only
sense in which it is worth reporting.

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
| 16 | A claim's *type* is the third generated component, and two shipped findings fire on it | **in production**; findings carry what their trigger rests on (§4.13) |
| 17 | **4 of 24 documents emit a different finding set** across byte-identical runs, including one at severity high | open; measured with the real rules (§4.14), and three of the four causes sit on the relation half |
| 18 | On long documents **no finding category holds still** — contradictions at severity high run 2, 7, 5 on one decision | open, and the sharpest open problem in this report (§4.15) |
| 19 | Half the meaning set could be passed without preserving the meaning; rewritten, and the figures do not move | **resolved** (§4.16). The set is examined rather than a draft, and 69 of 72 survives a strictly harder instrument |
| 20 | Six fields the dossier carries are written and never read, and `semantic_state` is a state machine with no transitions | open; audited rather than noticed (§4.17), and blocked on the schema decision from §4.5 |
| 21 | Reviewer comparisons rest on an assumption the artefacts could not confirm: the arms recorded no prompt hash and no output budget | both are recorded now (§4.18), but only from here on — every stored reviewer run predates the guard |

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

### 4.13 A claim's type is the third generated component, and two findings stand on it

§4.5 separated the two halves of a claim: `raw_span` is a *selection* into the
document and reproducible; `canonical_content` is a *generation* and the unstable
half. There is a third component, and nothing here had ever measured it.

The extraction contract **names twenty-one claim types and defines none of them.**
The relation vocabulary at least gets a direction gloss for seven of fourteen; the
claim types get a bare list. So the label is the whole specification.

That is not decoration. `claim_type` is hashed into the claim node id, so a
different type is a different node and every edge to it moves with it. And two
shipped deterministic findings fire on it: `logical_gap` at confidence 0.9 and
`unsupported_assumption` at 0.95.

Measured offline from runs already paid for, over 24 documents with three
byte-identical repeats each:

| | |
|---|---|
| documents whose **claim-type multiset changes** across repeats | **8 of 24** |
| `unsupported_assumption`: type precondition flips | **1 of 24** |
| `logical_gap`: type precondition flips | 0 of 24 |

`neg-02` alternates between `fact` and `scope` in both languages and in opposite
run positions, so it is a coin flip between two names rather than a language
artifact. `sco-01-de` alternates between `fact` and `causal` — and `causal` is
explicitly a distortion marker in another case, so one vocabulary item is an error
in one place and a free variant in another.

**Confidence does not catch it,** which is the detection result in the paper that
prompted the look ([arXiv 2610.02586](https://arxiv.org/abs/2610.02586)): 0.934
against 0.931 for the stable cases, no separation, and the field is degenerate —
233 of 242 claims sit on exactly 0.9 or 0.95. Gating on confidence was never
available.

**The precise statement matters, because the obvious one is wrong.** Not "the
extractor is unstable". For "Nicht alle Schulen erhalten den Zuschlag." both
`fact` and `scope` are defensible, and with no definitions **there is no fact of
the matter about which is right.** The finding is that the vocabulary has no truth
conditions, and a 0.95-confidence finding stands on it.

It also costs a reading from §4.12: the conditional's antecedent typed
`assumption` was reported there as the defensible half of that failure. In one of
three identical runs that typing does not exist. Semantic content was credited to
a coin flip — a reading rather than a measurement, so nothing measured is
withdrawn, but the inference was unsupported and is corrected.

**What was done, and the choice behind it.** Two options: stop keying
deterministic findings on a generated label, or ship them with the provenance of
their trigger. The second, so a later reflection run can take it up — keeping
information beats discarding it, and the first option stays open afterwards while
the converse does not hold.

Every rule now declares what its trigger rests on — `document`, `content`,
`relation_type`, `claim_type` — from one table beside the rule prose rather than
from fourteen call sites, so a rule cannot be added without declaring it. The
marker discriminates rather than being constant: `coverage_gap` is computed from
the document and the anchors, the budget rules from the claim text, and only two
of fourteen stand on the undefined label. It travels into the dossier JSON, where
a reflection run reads it, **and onto the rendered page** — because
`anchor_ambiguous` is the precedent for what happens otherwise: set by the gate
since it was built, read by no part of the product, only by a measurement script.

The rendered caveat carries **no number**. The 8-of-24 comes from cases of one to
three sentences; attaching it to a finding on a 27,000-character decision would
borrow precision from the wrong corpus, which is the failure this repository
retracts most often. A test forbids a digit in the text.

**Not measured.** `relation_type`, on which three further findings rest alone —
the same measurement would cost nothing and has not been run. Long documents: that
`logical_gap` never flips across 24 short cases says nothing about a decision with
108 claims. And the three-armed probe the paper actually proposes was not run,
because the obvious way would have been wrong: the meaning set checks `claim_type`
in 2 of 24 cases, so measuring a label permutation against meaning preservation
would have spent 216 paid calls on an axis that barely sees the type. The right
instrument is type stability, and it is free.

---

### 4.14 A finding that does not reproduce: 4 of 24 documents

§4.13 measured the *preconditions* of a rule. This measures the findings, and it
corrects two numbers there.

`logical_gap` is an **argument from silence**: it fires when a claim typed
`thesis`, `inference` or `recommendation` has no incoming `SUPPORTS` or `ENTAILS`
and no outgoing `EVIDENCED_BY`. Absence is the trigger. This project has measured
repeatedly that extraction loses much of the argument structure, so the finding
reads as a property of the document while part of it is a property of the run.

`scripts/finding_warrant.py` rebuilds the packet from a stored dossier, re-gates
it against the document and calls **the real `deterministic_checks`** — no
re-implemented rule logic — then compares the finding set across repeats.

| document | finding | per run | cause |
|---|---|---|---|
| `mul-02-de` | `internal_contradiction` (**high**) | 1, 0, 0 | claim types **identical** in all three runs; run 1 emits one `CONTRADICTS` edge, runs 2–3 emit three different edges and none |
| `neg-01-de` | `logical_gap` (0.9) | 0, 1, 1 | one edge on the same claim pair is called `EVIDENCED_BY` once and `DEPENDS_ON` twice |
| `sco-02-de` | `unsupported_assumption` (0.95) | 1, 0, 0 | the `assumption` type is present in all three runs; the `ASSUMPTION_FOR` edge only in run 1 |
| `sco-02-en` | `unsupported_assumption` (0.95) | 1, 1, 0 | the type half moves (§4.13) |

**20 of 24 documents are stable; 4 are not.** Four distinct mechanisms, and three
of them sit on the *relation* half, which §4.13 had listed as not measured.
`mul-02-de` is the cleanest: nothing about the claim set moves, and a
**high**-severity finding appears and vanishes.

Two corrections to §4.13. Its "`logical_gap`'s type precondition flips in 0 of 24"
is true and nearly empty — three claims of those types exist across all 72
dossiers, all in one document — and it concealed that the finding itself flips 2:1
there. And `unsupported_assumption` moves in **2** documents, not 1, once the
whole trigger is evaluated.

**What the obvious transfer cannot do.** The paper that prompted this
([arXiv 2610.07753](https://arxiv.org/abs/2610.07753)) scores outcome against
warrant: an outcome being right does not show the evidence for it was established
first. Scoring every finding twice, once by correctness and once by demonstrable
warrant, is **not available here** — nothing in this project is a gold answer
about whether a `logical_gap` is right. The benchmark has task success; we have
nothing comparable, so no success-versus-warrant rate was computed.

Reproducibility is what can be computed, and it is a **lower bound**: a finding
that does not recur under identical input cannot be warranted by the document. The
converse does not hold — recurring three times does not make a finding warranted.
4 of 24 is a floor, not a rate.

**And why the evidence card cannot be built at emission.** The companion proposal
([EviSkill, arXiv 2610.05030](https://arxiv.org/abs/2610.05030)) was to store the
finding with its instability as a provisional, evidence-bound object, with the
three dossiers as replay context. In production those three dossiers do not exist:
extraction runs once per document, so at the moment a finding is emitted, runs 2
and 3 do not exist and whether *this* finding moves is not knowable.

That is the honest limit of the choice made in §4.13, and it was not stated there:
**the marker names the kind of dependency, not the observed instability**, because
the observed instability is constitutively unavailable at emission. A reader sees
the same caveat on a finding whose type was rock solid across three runs and on
one that moved. So that choice is the maximum available without a **repeat-run
policy**, which costs three times the extraction per document — a decision with a
price tag, now in §10.

The evidence card itself already exists, in the right place: the `--json` output of
both measurement scripts is exactly that cross-run record. What is missing is not a
data structure but a **link** from a shipped finding to it, and that link only
means something once repeats exist.

**Not measured.** Long documents: 24 cases of one to three sentences, four or five
claims and nought to three edges each. A decision with 108 claims has far more
edges for the same thing to happen on, and measuring it there costs nothing beyond
a run already stored. And the reviewers' own findings: only the deterministic ones
are measured here, the two LLM arms have their own separately measured spread
(§5.4), and the two numbers do not add.

---

### 4.15 On a long document, no finding category holds still

§4.14 measured 24 cases of one to three sentences and found 4 of 24 documents
emitting a different finding set. Its open item was that a decision with a hundred
claims has far more edges for the same thing to happen on. The runs were already
stored, so the measurement cost nothing.

Three sets, each with an **identical `prompt_hash` across its runs** — the
condition under which a comparison measures run-to-run spread rather than a
difference in configuration.

| set | document | runs | claims | edges |
|---|---|---|---|---|
| A24, two-stage | 21,789 characters | 3 | 115/116/108 | 67/60/65 |
| A24, variant | 21,789 characters | 2 | 111/111 | 29/35 |
| decision 001-141170 | 10,371 characters | 3 | 53/59/54 | 30/45/41 |

The hash guard earned itself immediately. The research log describes experiment 18
as three runs per arm; of the three stored artifacts for the single-call arm only
**two** share a prompt hash, and the third is a different configuration. Pooling
them would have reported a configuration difference as instability. The script now
refuses and prints the hashes.

| | per run |
|---|---|
| `internal_contradiction` (**high**), decision | **2, 7, 5** |
| `logical_gap` (0.9), A24 | **16, 19, 13** |
| `coverage_gap`, A24 | 6, 10, 10 |
| `coverage_gap`, A24 variant | 7, 13 |
| `logical_gap`, A24 variant | 9, 15 |
| `overgeneralization`, A24 | 6, 6, 5 |
| `logical_gap`, decision | 2, 6, 3 |
| `scope_tension` | 0,0,1 and 0,1,0 |
| `unsupported_assumption` (0.95), A24 | 0, 1, 0 |

**In all three sets: nought categories hold constant across the runs.** On the
decision the high-severity contradiction count peaks at three and a half times its
floor — an examiner submitting the same text twice is told of between two and
seven contradictions. Against §4.14 this is not the same finding scaled up but a
different state: short cases with four claims and nought to three edges are the
special case in which anything holds still at all.

**It corrects §4.13's table.** `coverage_gap` was given `("document",)`, the most
trusted label there, and that is wrong: the gap list is computed deterministically,
but *which* anchors exist is an extraction outcome. The rule fires on the
**absence** of an admitted claim, as `logical_gap` fires on the absence of a
supporting edge and `unsupported_assumption` on the absence of evidence. The table
now carries a fifth kind, `absence`, and three of the fourteen rules declare it.
That is not a label added out of caution: these three are the largest movers here.
Silence is the weakest input, because extraction is known to lose argument
structure, so the absence may be the run's rather than the document's.

**Three limits.** The decision runs are post-repair-pass, and that pass
manufactures duplicates (§4.6), so part of that spread may be its. It cannot be
separated here — but both A24 sets are un-repaired and show the same picture, so
the finding does not rest on the repair pass. The packets are re-gated with
today's tolerant anchoring, so these numbers are what the same proposals score now
and not what those runs reported at the time, the same post-hoc caveat as §4.3.
And there is still no gold for findings, so reproducibility remains a lower bound:
these are floors, not rates.

**What follows, and what does not.** Not "the deterministic rules are broken" —
they compute what they are meant to. What moves are their *inputs*, and for the
three absence rules the absence itself moves. What does follow is §4.14's decision
at a harder price. There the marker was said to name the kind of dependency rather
than the observed instability, because production runs once. On short cases that
was a subtlety. On a document where **no** category holds still, a single run is
not a sample but a draw — and a dossier reporting 16 logical gaps where a second
run would have reported 13 looks exactly as final. The repeat-run policy is
therefore no longer a thrift question but the question of whether a finding may be
reported as a number at all.

### 4.16 Half the meaning set rewritten, and the figures do not move

§4.12's table reported meaning preserved at 69 of 72 case-runs. Two independent
blind reviews then found that twelve of the 24 cases — six pairs — could be passed
by renderings that lose the meaning, and in one case that the gold asserted a
pragmatic implicature rather than what the sentence entails. All sixteen of their
counterexamples were checked against the validator before anything changed: twelve
held, four were refuted.

The cases were rewritten rather than dropped, under the constraint that decided the
whole exercise: **documents and spans are untouched, all 24.** Only requirements,
forbidden patterns and gold prose changed. So every dossier already paid for could
be scored again, and the rewrite is followed by a measurement rather than a hope.

| case | before | after |
|---|---|---|
| `spk-01` | one group, which also accepted the other language's word | speaker **and** speech act in one claim |
| `spk-02` | two groups: a name, a name | per claim: speaker, act, content |
| `mul-01`, `mul-02` | one group per claim | per claim: subject, predicate, figure |
| `mod-02` | a reporting verb from a list of four | the source named and the effect stated; which verb is irrelevant |
| `neg-02` | the gold asserted an implicature | the gold reduced to the entailment |
| `neg-01`, `mod-01`, `cor-01` | — | the reversed scope and the missing inflections forbidden |

That needed one schema change. A requirement of one group per claim is satisfied by
a single word from it, so two bare fragments passed a case whose point was that two
assertions survive. It is now a list of groups per claim, all of which one claim
must satisfy.

Seven confirmed false alarms were fixed too — faithful renderings the requirements
rejected, such as "according to the study" where a reporting verb was demanded.
Each is recorded with its date and the review that named it, and **none came from a
failing run**: they came from reading the cases, which is the distinction the
governance rule exists to protect.

**Then the measurement.** The same 72 dossiers against the rewritten set:

| phenomenon | §4.12, weak set | now, twelve cases harder |
|---|---:|---:|
| negation, modality, correlation, speaker, several assertions | 12/12 each | 12/12 each |
| scope | 6/6 | 6/6 |
| condition | 3/6 | 3/6 |
| **total** | **69/72** | **69/72** |

§4.12 had to say the numbers held but their evidential weight did not. That is now
**refuted — by a measurement rather than an argument.** The extractor's actual
output passes the strict set exactly as it passed the weak one, so 69 of 72 was not
an artifact of weak cases. One thing is newly visible: `sco-02` reports three
distortions where it reported none, because the forbidden-reading check now names
the unconditional consequent for what it is. The verdict does not change; the
instrument now says *what* went wrong rather than only *that* it did.

The reviews' sixteen counterexamples are kept as a test file, so a later widening
of any token list has to leave all sixteen verdicts intact. The 0.16 dollars bought
permanent test coverage rather than an opinion.

**What this does not mean.** The set is no longer a draft — two independent reviews
are recorded, checked and acted on — which makes it examined rather than good. It is
still 24 passages of one to three sentences, written by the same party that built
the system, and the two reviews are two models and not an expert opinion. The
seventh phenomenon stays open because the reviews disagree about it, and relations
stay unannotated because neither proposed an edge when asked.

---

### 4.17 Six fields the product never reads, and one state machine with no transitions

`anchor_ambiguous` was found to be write-only by accident, while a different flag
was being added (§4.13). The lesson taken from it was that a marker nothing renders
is not a safeguard. `scripts/unread_fields.py` now asks the question for every
field over the syntax tree, instead of waiting for the next accident — and finds
**six** written and never read, where a grep over the same tree found four.

| | written, never read |
|---|---|
| **provenance, correctly unread** | `anchor_normalised`, `proposed_span` — sitting in the JSON is the whole job |
| **identifiers nothing resolves** | `finding_id`, `relation_id` — a primary key with no foreign key; right for a human citing a dossier, dead for the product |
| **borderline** | `anchor_ambiguous` — the gate recomputes the condition inline and it is not rendered. §4.13's lesson, never applied |
| **the one that matters** | `semantic_state` |

One more sits deeper: **`Finding.state` is never set and never read**, carrying only
its default. That is a stronger statement than unread, and the audit reports it
apart.

**Unread does not mean wrong**, and that belongs before the list rather than after
it. Four of the six are provenance or identifiers and correct as they are.

**The one that matters** was named by [arXiv 2610.06496](https://arxiv.org/abs/2610.06496),
whose finding is that models confuse "mentioned" with "still in force": after a
proposal is rejected, the inactive content reappears in 59.63 per cent of the new
errors. Checked against this codebase, the good half holds by construction — a
proposal the gate refuses reaches neither the deterministic rules nor the reviewers,
so provenance and force are already separate **before** admission.

What is missing is the case *after* admission. A claim admitted and later withdrawn
by a human, or superseded by a better reading, has no state that says so.
`semantic_state` is where it would live, and it is **a state machine with no
transitions**: two values the gate can set, exactly one observed across all 242
stored claims, no reader anywhere, and nothing able to change it once the gate has
run. So the paper reveals no new defect; it names the failure mode that makes an
already-listed gap cost something, and supplies a vocabulary for it.

Two papers from the same batch have nothing to take here, and the reason is worth
recording. [U-Space](https://arxiv.org/abs/2610.09087) derives uncertainty
directions from the residual stream; **we have no activations**, since we call an
API and get text, which is a boundary rather than an obstacle. Its transferable
lesson — that a predictor may be tracking length (68.6 % AUROC, 52.4 % under length
control) — is already applied in §4.4, which compares across four papers of similar
length and names its own remaining confound; the re-run open there is **not free**,
because only one of those four documents is still stored.
[Accurate but Not Humble](https://arxiv.org/abs/2610.12360) describes a conflict
noticed early and dropped later, which §4.15 has measured in this system's terms:
`internal_contradiction` at severity high runs 2, 7, 5 across identical runs. Ours
is between runs and theirs within a trajectory, and within one run the decay cannot
happen here because the rule is deterministic. Its humility-against-accuracy
trade-off is not measurable here, since §4.14 established there is no gold for
findings.

**The decision is not mine.** `semantic_state` either becomes a real state with
transitions — which requires the versioned-overlay schema decision open since §4.5
— or it is removed. A field with one observed value that nothing reads is decoration
that looks like a safeguard, which is exactly what `anchor_ambiguous` cost, and the
lesson now applies a second time.

### 4.18 A guard for reviewer comparisons, built because exactly it was missing

A reviewer finding this work could not prove is what prompted the change. While
reading [BeliefScope](https://arxiv.org/abs/2610.11305), one measured axis turned
out to change its character with a condition that has nothing to do with the
evidence:

| Run set | Reviewer budget | `flash-evidence-skeptic` confidence values |
|---|---|---|
| `rv54` | 8,192 | 6 values, strictly on a 0.05 grid |
| `rb55` | 65,536 | 15 values, off that grid (0.82 · 0.87 · 0.88 · 0.91 …) |

Same model, same profile, same graph, same contract. The only *named* difference
is the output budget, and "the confidence became more differentiated" would here
be an artefact of the budget rather than a better judgement.

**That sentence cannot be substantiated.** The extraction has recorded a
`prompt_hash` since it existed, and that guard has earned itself once: of three
artefacts the log described as one arm's three runs, only two shared a hash, and
pooling them would have reported a configuration difference as run-to-run
instability. For the reviewer arms no such field existed, so every reviewer
comparison in this record rests on the assumption that the arms were asked the
same question.

What is now recorded is the smallest thing that makes the question answerable:
`prompt_fingerprint(system, user)` gives the convention a single name, because two
expressions that almost agree are worse than one missing hash — they compare as
unequal and report a difference that is not there. The hash is written on **both**
reviewer paths, the failed one included, and computed before the call, since the
prompt was sent either way and "the arm was asked and said nothing" is the case a
later comparison most needs to separate. Alongside it, `max_tokens` — the very
condition that produced the finding above and appeared nowhere in the artefact.

**It does not apply retroactively**, and that is the half that counts. Every
reviewer run stored so far carries no hash, by construction, so the `rv54`/`rb55`
sentence stays unproven and no later code can change that: it needs a new paid
run. The guard works from here forward, and a comparison across that boundary is
still unguarded.

Seven mutations were run against the new tests and six were caught at once. The
survivor removed the joining separator, and the test meant to catch it compared a
pair that differs with the separator *and* without it — so it asserted nothing.
Measured instead of assumed, the discriminating pair is `("ab","c")` against
`("a","bc")`, which collide without a separator. The same measurement exposed an
honest limitation: the convention is **not injective**, because a prompt
containing the separator makes two different splits collide. That is harmless in
this repository, where the system half is a fixed role prompt, but it is a
property of the repository rather than of the hash, so a test now asserts it
outright. Mutations keep finding bad tests rather than bad code — this is the
fifth time in this record.

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
| A finding's trigger could be an undefined label and nothing said so | Every deterministic rule declares what its trigger rests on; it travels into the JSON and onto the page | in review (§4.13) |

### Unsolved

| Problem | Why it is still open |
|---|---|
| Coverage — passages the extractor never reads | No mechanism but a second paid call, whose value is now unclear |
| The run-to-run spread itself | Reduced, not removed; 27 spans is still larger than most effects worth measuring |
| Reviewer stability | 0.27 under the strict rule, and the figure is not reproducible (§5.4) |
| Truncation on long documents | The cliff moves with the budget; it does not go away |
| Genuine paraphrase in quotations | 11 of 465 proposals, correctly refused, permanently lost |
| Relation expressivity | Four of six families covered; the gap is untested |
| A finding's state is never resolved | Needs a versioned overlay and a schema decision. §4.17 names what it costs: `semantic_state` exists, takes one observed value across 242 claims, and nothing reads it — so a claim withdrawn by a human after admission leaves no trace that it was |
| Conditionals | Split at the comma in half the runs; the consequent is then asserted unconditionally. A language instruction did not touch it (§4.12) |
| The claim-type vocabulary has no truth conditions | Twenty-one types, no definitions anywhere in the contract. Two defensible labels for one sentence is not a model error — it means there is no fact of the matter, and a 0.95-confidence finding stands on it (§4.13) |
| A finding can appear and vanish under identical input | On 24 short cases 4 of 24 documents emit a different finding set. On two long documents **no category holds still**: contradictions at severity high run 2, 7, 5 and logical gaps 16, 19, 13 across identical runs. Three rules fire on an *absence*, and extraction is known to lose argument structure, so the absence may be the run's (§4.14, §4.15) |
| A single run is a draw, not a sample | Production extracts once per document, so a dossier reporting 16 logical gaps where a second run would report 13 looks exactly as final. Repeats would fix it at three times the extraction cost (§4.15, decision 7) |
| Whether a finding was *warranted*, as opposed to reproducible | Not computable here: nothing in this project is a gold answer about whether a deterministic finding is right. Reproducibility is a lower bound only (§4.14) |
| Meaning of a claim, beyond 24 short sentences | The only meaning set that exists is 24 one-to-three-sentence cases. Two independent reviews are now recorded, checked and acted on (§4.16), so it is examined rather than a draft — but it is still 24 short passages written by the party that built the system |
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
scripts/                                 25 measurement scripts, each tested
docs/architecture.md §3a–§3ao            the chronological record, run by run
CHANGELOG.md                             what moved, including the retractions
```

The offline controls replay stored packets and never call a provider: `polished`
5 claims / 5 relations / 3 findings, `rough` 4 / 4 / 0, `budget` 25 / 15 / 10.
They are the reference for behaviour changes, and they cannot see a prompt
regression — only a live run against the frozen packet can.

472 tests and one skipped, `ruff check` clean.

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
7. **Whether extraction repeats become policy.** §4.14 showed that the marker from
   §4.13 names the kind of dependency and not the observed instability, because at
   emission there is only one run and whether *this* finding moves is not knowable.
   Three runs per document would make it knowable and cost three times the
   extraction. **§4.15 raises the stakes:** on a long document no finding category
   holds still, so a single run is a draw rather than a sample, and the question is
   no longer thrift but whether a finding may be reported as a bare number at all.
8. **Whether a deterministic finding may key on a generated label at all.**
   §4.13 chose to ship the provenance rather than remove the dependency, so this
   stays open. Adding definitions to the twenty-one types is the obvious repair
   and the measured-least-effective one; opaque identifiers are what worked in
   the paper, and they would cost the vocabulary's readability.

---
---

# Forschungsbericht (Deutsch)

**Was ein Claim-Graph-Reviewer kann und was nicht, gemessen gegen externe
Goldstandards.**

Dieser Bericht sammelt, was rund vierzig bezahlte Messläufe belegt haben, was sie
widerlegt haben und was offen ist. Er ist für jemanden geschrieben, der die
Arbeit nicht verfolgt hat; die chronologische Aufzeichnung steht in
[`architecture.md`](architecture.md) §3a–§3ao und ist ein Log, keine Synthese.

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

Diese Zahl ruht auf Fällen, die dieses Projekt selbst geschrieben hat, also ging
der Bestand an zwei unabhängige Durchsichten — keine aus der Familie, die ihn
geschrieben hat, keine das geprüfte System, und keiner wurde eine Zahl aus einem
Lauf gezeigt. **Sie haben die Hälfte zerlegt.** Zwölf der 24 Fälle waren mit
Wiedergaben bestehbar, die die Bedeutung verlieren, und in einem Fall behauptete
das Gold eine pragmatische Implikatur statt dessen, was der Satz entailt. Ihre
sechzehn Gegenbeispiele wurden gegen den Validator geprüft, bevor etwas geändert
wurde: zwölf hielten, vier waren widerlegt, und die vier aus einem Grund, den
beide Durchsichten teilten. Danach wurden die Fälle umgeschrieben, ohne die
Dokumente anzufassen, damit die bezahlten Läufe bewertbar blieben — und **69 von
72 kamen gegen ein strikt härteres Instrument unverändert zurück** (§4.16). Die
Kernzahl hat einen Angriff von außen auf das überstanden, was sie erzeugt hat, und
nur in diesem Sinn ist sie berichtenswert.

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
| 16 | Der *Typ* eines Claims ist die dritte erzeugte Komponente, und zwei ausgelieferte Befunde feuern darauf | **in Produktion**; Befunde tragen die Herkunft ihres Auslösers (§4.13) |
| 17 | **4 von 24 Dokumenten liefern eine andere Befundmenge** über byte-identische Läufe, einer davon mit Schweregrad high | offen; mit den echten Regeln gemessen (§4.14), und drei der vier Ursachen liegen auf der Relationshälfte |
| 18 | Auf langen Dokumenten bleibt **keine Befundart stehen** — Widersprüche mit Schweregrad high laufen 2, 7, 5 auf einer Entscheidung | offen, und das schärfste ungelöste Problem dieses Berichts (§4.15) |
| 19 | Die Hälfte des Bedeutungsbestands war bestehbar, ohne die Bedeutung zu erhalten; umgeschrieben, und die Zahlen bewegen sich nicht | **gelöst** (§4.16). Der Bestand ist geprüft statt Entwurf, und 69 von 72 übersteht ein strikt härteres Instrument |
| 20 | Sechs Felder des Dossiers werden geschrieben und nie gelesen, und `semantic_state` ist ein Zustandsautomat ohne Übergänge | offen; geprüft statt bemerkt (§4.17), und blockiert von der Schemaentscheidung aus §4.5 |
| 21 | Reviewer-Vergleiche ruhen auf einer Annahme, die die Artefakte nicht belegen konnten: die Arme zeichneten weder Prompt-Hash noch Ausgabebudget auf | beides wird jetzt aufgezeichnet (§4.18), aber erst von hier an — jeder gespeicherte Reviewer-Lauf liegt vor dem Wächter |

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

### 4.13 Der Typ eines Claims ist die dritte erzeugte Komponente, und zwei Befunde stehen darauf

4.5 hat die zwei Hälften eines Claims getrennt: `raw_span` ist eine **Auswahl**
ins Dokument und reproduzierbar, `canonical_content` eine **Erzeugung** und die
instabile Hälfte. Es gibt eine dritte Komponente, und hier hat sie nie etwas
gemessen.

Der Extraktionsvertrag **nennt 21 Claim-Typen und definiert keinen davon.** Das
Relationsvokabular bekommt immerhin für 7 von 14 eine Richtungsglosse; die
Claim-Typen bekommen eine nackte Liste. Das Label ist also die ganze
Spezifikation.

Das ist nicht dekorativ. `claim_type` steckt im Node-Id-Hash, also ist ein anderer
Typ ein anderer Knoten, und jede Kante dorthin wandert mit. Und zwei ausgelieferte
deterministische Befunde feuern darauf: `logical_gap` mit Konfidenz 0,9 und
`unsupported_assumption` mit 0,95.

Offline gemessen aus bereits bezahlten Läufen, über 24 Dokumente mit je drei
byte-identischen Wiederholungen:

| | |
|---|---|
| Dokumente mit **wechselnder Typmenge** über die Wiederholungen | **8 von 24** |
| `unsupported_assumption`: Typ-Vorbedingung wechselt | **1 von 24** |
| `logical_gap`: Typ-Vorbedingung wechselt | 0 von 24 |

`neg-02` wechselt zwischen `fact` und `scope`, in beiden Sprachen und in
umgekehrter Lauf-Position — also ein Münzwurf zwischen zwei Namen und kein
Sprachartefakt. `sco-01-de` wechselt zwischen `fact` und `causal`, und `causal`
ist in einem anderen Fall ausdrücklich ein Verzerrungsmarker: dasselbe
Vokabelwort ist an einer Stelle ein Fehler und an der anderen eine freie Variante.

**Die Konfidenz fängt es nicht** — das ist der Detektionsbefund des Papers, das
den Blick ausgelöst hat ([arXiv 2610.02586](https://arxiv.org/abs/2610.02586)):
0,934 gegen 0,931 für die stabilen Fälle, keine Trennung, und das Feld ist
entartet — 233 von 242 Claims stehen auf exakt 0,9 oder 0,95. Auf Konfidenz zu
filtern war nie verfügbar.

**Die präzise Formulierung ist wichtig, weil die naheliegende falsch ist.** Nicht
„der Extraktor ist instabil". Für „Nicht alle Schulen erhalten den Zuschlag." sind
`fact` und `scope` beide vertretbar, und ohne Definitionen **gibt es keine
Tatsache darüber, welcher richtig ist.** Der Befund lautet: das Vokabular hat
keine Wahrheitsbedingungen, und darauf steht ein Befund mit 0,95.

Es kostet außerdem eine Lesart aus 4.12: Dass der Vordersatz der Bedingung als
`assumption` getypt wird, stand dort als die vertretbare Hälfte jenes Fehlers. In
einem von drei identischen Läufen existiert diese Typung nicht. Einem Münzwurf
wurde semantischer Gehalt zugeschrieben — eine Lesart und keine Messung, also
wird nichts Gemessenes zurückgenommen, aber der Schluss war unbegründet und ist
korrigiert.

**Was getan wurde, und die Wahl dahinter.** Zwei Wege: deterministische Befunde
nicht länger auf einen erzeugten Label stützen, oder sie mit der Herkunft ihres
Auslösers ausliefern. Der zweite, damit ein späterer Reflexionslauf es aufgreifen
kann — Information behalten schlägt Information verwerfen, und der erste Weg
bleibt danach offen, während es umgekehrt nicht gilt.

Jede Regel deklariert jetzt, worauf ihr Auslöser steht — `document`, `content`,
`relation_type`, `claim_type` — aus **einer** Tabelle neben den Regeltexten statt
aus 14 Aufrufstellen, damit keine Regel ohne Deklaration dazukommen kann. Die
Markierung unterscheidet und ist nicht konstant: `coverage_gap` rechnet aus
Dokument und Ankern, die Budgetregeln aus dem Claim-Text, und nur zwei von
vierzehn stehen auf dem undefinierten Label. Sie reist ins Dossier-JSON, wo ein
Reflexionslauf sie liest, **und auf die gerenderte Seite** — denn
`anchor_ambiguous` ist der Präzedenzfall für das Gegenteil: vom Gate seit seinem
Bau gesetzt, von keinem Teil des Produkts gelesen, nur von einem Messskript.

Der gerenderte Hinweis trägt **keine Zahl.** Die 8 von 24 stammen aus Fällen von
einem bis drei Sätzen; sie an einen Befund auf 26.000 Zeichen Gerichtstext zu
hängen wäre geliehene Präzision — der Fehler, den dieses Repo am häufigsten
zurücknimmt. Ein Test verbietet eine Ziffer im Text.

**Nicht gemessen.** `relation_type`, auf dem drei weitere Befunde allein stehen —
dieselbe Messung würde nichts kosten und ist nicht gelaufen. Lange Dokumente: dass
`logical_gap` über 24 kurze Fälle nie wechselt, sagt über eine Entscheidung mit
108 Claims nichts. Und die Dreiarm-Probe, die das Paper eigentlich vorschlägt, ist
nicht gelaufen, weil der naheliegende Weg falsch gewesen wäre: der
Bedeutungsbestand prüft `claim_type` in 2 von 24 Fällen, eine Label-Permutation
gegen die Bedeutungserhaltung zu messen hätte also 216 bezahlte Aufrufe für eine
Achse gekostet, die den Typ fast nicht sieht. Das richtige Instrument ist
Typstabilität, und die ist gratis.

### 4.14 Ein Befund, der nicht wiederkehrt: 4 von 24 Dokumenten

4.13 hat die **Vorbedingungen** einer Regel gemessen. Hier sind es die Befunde,
und zwei Zahlen von dort werden korrigiert.

`logical_gap` ist ein **Schluss aus Schweigen**: er feuert, wenn ein Claim vom Typ
`thesis`, `inference` oder `recommendation` keine eingehende `SUPPORTS` oder
`ENTAILS` und keine ausgehende `EVIDENCED_BY` hat. Abwesenheit ist der Auslöser.
Dieses Projekt hat mehrfach gemessen, dass die Extraktion viel Argumentstruktur
verliert — der Befund liest sich also als Eigenschaft des Dokuments und ist zum
Teil eine Eigenschaft des Laufs.

`scripts/finding_warrant.py` baut aus einem gespeicherten Dossier das Paket
zurück, gatet gegen das Dokument neu und ruft **`deterministic_checks` selbst
auf** — keine nachgebaute Regellogik — und vergleicht dann die Befundmenge über
die Wiederholungen.

| Dokument | Befund | je Lauf | Ursache |
|---|---|---|---|
| `mul-02-de` | `internal_contradiction` (**high**) | 1, 0, 0 | Claim-Typen in allen drei Läufen **identisch**; Lauf 1 liefert eine `CONTRADICTS`-Kante, Läufe 2–3 drei andere und keine |
| `neg-01-de` | `logical_gap` (0,9) | 0, 1, 1 | dieselbe Kante auf demselben Claim-Paar heißt einmal `EVIDENCED_BY` und zweimal `DEPENDS_ON` |
| `sco-02-de` | `unsupported_assumption` (0,95) | 1, 0, 0 | `assumption` ist in allen drei Läufen da, die `ASSUMPTION_FOR`-Kante nur in Lauf 1 |
| `sco-02-en` | `unsupported_assumption` (0,95) | 1, 1, 0 | die Typhälfte wechselt (4.13) |

**20 von 24 Dokumenten sind stabil, 4 nicht.** Vier verschiedene Mechanismen, und
drei davon liegen auf der **Relations**hälfte, die 4.13 als nicht gemessen geführt
hat. `mul-02-de` ist der reinste Fall: am Claim-Satz bewegt sich nichts, und ein
Befund mit Schweregrad **high** erscheint und verschwindet.

Zwei Korrekturen an 4.13. Dessen „`logical_gap`: Typ-Vorbedingung wechselt 0 von
24" ist wahr und nahezu leer — in allen 72 Dossiers stehen drei Claims dieser
Typen, alle in einem Dokument — und es hat verdeckt, dass der Befund selbst dort
2:1 wechselt. Und `unsupported_assumption` wechselt in **2** Dokumenten, nicht in
einem, sobald der ganze Auslöser ausgewertet wird.

**Was die naheliegende Übertragung nicht leisten kann.** Das Paper
([arXiv 2610.07753](https://arxiv.org/abs/2610.07753)) misst Ergebnis gegen
Geltung: dass ein Ergebnis stimmt, zeigt nicht, dass die Evidenz dafür vorher
etabliert war. Jeden Befund zweimal zu bewerten, einmal nach Richtigkeit und
einmal nach nachweisbarer Geltung, ist hier **nicht verfügbar** — nichts in diesem
Projekt ist eine Gold-Antwort darauf, ob ein `logical_gap` richtig ist. Der
Benchmark hat Aufgabenerfolg, wir haben nichts Vergleichbares, also wurde keine
Erfolg-gegen-Geltung-Rate gerechnet.

Rechenbar ist **Reproduzierbarkeit, und sie ist eine untere Schranke**: Ein
Befund, der unter identischer Eingabe nicht wiederkehrt, kann vom Dokument nicht
gedeckt sein. Umgekehrt gilt es nicht — dreimal wiederzukehren macht einen Befund
nicht gedeckt. Die 4 von 24 sind ein Boden, keine Rate.

**Und warum die Evidenzkarte am Emissionszeitpunkt nicht gebaut werden kann.** Der
Begleitvorschlag ([EviSkill, arXiv 2610.05030](https://arxiv.org/abs/2610.05030))
war, den Befund samt Instabilität als vorläufiges, evidenzgebundenes Objekt zu
speichern, mit den drei Dossiers als Replay-Kontext. Im Produktionslauf gibt es
diese drei Dossiers nicht: extrahiert wird einmal je Dokument, also existieren in
dem Moment, in dem ein Befund emittiert wird, Lauf 2 und 3 nicht, und ob *dieser*
Befund wechselt, ist nicht wissbar.

Das ist die ehrliche Grenze der in 4.13 getroffenen Wahl, und sie stand dort
nicht: **die Markierung nennt die Art der Abhängigkeit, nicht die beobachtete
Instabilität** — weil die beobachtete Instabilität am Emissionszeitpunkt
konstruktiv nicht vorliegt. Ein Leser sieht denselben Hinweis an einem Befund,
dessen Typ über drei Läufe felsenfest war, und an einem, der wechselt. Damit ist
jene Wahl das Maximum ohne eine **Wiederholungspolitik**, und die kostet die
dreifache Extraktion je Dokument — eine Entscheidung mit Preisschild, jetzt in
§10.

Die Evidenzkarte selbst existiert schon, an der richtigen Stelle: die
`--json`-Ausgabe beider Messskripte ist genau dieser Querschnitt. Was fehlt, ist
keine Datenstruktur, sondern eine **Verknüpfung** von einem ausgelieferten Befund
dorthin — und die bedeutet erst etwas, wenn es Wiederholungen gibt.

**Nicht gemessen.** Lange Dokumente: 24 Fälle aus einem bis drei Sätzen, mit vier
bis fünf Claims und null bis drei Kanten. Eine Entscheidung mit 108 Claims hat
ungleich mehr Kanten, auf denen dasselbe passieren kann, und die Messung dort
kostet nichts außer einem Lauf, der schon gespeichert ist. Und die
Reviewer-Befunde: gemessen sind nur die deterministischen, die beiden LLM-Arme
haben eine eigene, separat gemessene Streuung (§5.4), und die zwei Zahlen gehören
nicht addiert.

### 4.15 Auf einem langen Dokument bleibt keine Befundart stehen

4.14 hat 24 Fälle aus einem bis drei Sätzen gemessen und fand 4 von 24
Dokumenten mit einer anderen Befundmenge. Der offene Punkt war, dass eine
Entscheidung mit hundert Claims ungleich mehr Kanten hat, auf denen dasselbe
passieren kann. Die Läufe lagen gespeichert, die Messung hat nichts gekostet.

Drei Sätze, jeder mit **identischem `prompt_hash` über seine Läufe** — die
Bedingung, unter der ein Vergleich Laufstreuung misst und nicht einen Unterschied
der Konfiguration.

| Satz | Dokument | Läufe | Claims | Kanten |
|---|---|---|---|---|
| A24, zweistufig | 21.789 Zeichen | 3 | 115/116/108 | 67/60/65 |
| A24, Variante | 21.789 Zeichen | 2 | 111/111 | 29/35 |
| Entscheidung 001-141170 | 10.371 Zeichen | 3 | 53/59/54 | 30/45/41 |

Der Hash-Wächter hat sich sofort bezahlt. Das Forschungsprotokoll beschreibt
Experiment 18 als drei Läufe je Arm; von den drei gespeicherten Artefakten des
einstufigen Arms teilen nur **zwei** einen `prompt_hash`, das dritte ist eine
andere Konfiguration. Sie zusammenzuwerfen hätte einen Konfigurationsunterschied
als Instabilität berichtet. Das Skript verweigert das und nennt die Hashes.

| | je Lauf |
|---|---|
| `internal_contradiction` (**high**), Entscheidung | **2, 7, 5** |
| `logical_gap` (0,9), A24 | **16, 19, 13** |
| `coverage_gap`, A24 | 6, 10, 10 |
| `coverage_gap`, A24-Variante | 7, 13 |
| `logical_gap`, A24-Variante | 9, 15 |
| `overgeneralization`, A24 | 6, 6, 5 |
| `logical_gap`, Entscheidung | 2, 6, 3 |
| `scope_tension` | 0,0,1 und 0,1,0 |
| `unsupported_assumption` (0,95), A24 | 0, 1, 0 |

**In allen drei Sätzen: null Befundarten, die über die Läufe konstant bleiben.**
Auf der Entscheidung ist das Maximum der Widersprüche mit Schweregrad *high* das
Dreieinhalbfache des Minimums — ein Prüfer, der denselben Text zweimal einreicht,
bekommt zwei bis sieben Widersprüche gemeldet. Gegenüber 4.14 ist das nicht
derselbe Befund in größerem Maßstab, sondern ein anderer Zustand: kurze Fälle mit
vier Claims und null bis drei Kanten sind der Sonderfall, in dem überhaupt etwas
stillsteht.

**Es korrigiert die Tabelle aus 4.13.** `coverage_gap` bekam dort
`("document",)`, das vertrauenswürdigste Etikett, und das ist falsch: die
Lückenliste rechnet deterministisch, aber *welche* Anker existieren, ist ein
Extraktionsergebnis. Die Regel feuert auf die **Abwesenheit** eines zugelassenen
Claims, so wie `logical_gap` auf die Abwesenheit einer Stützkante und
`unsupported_assumption` auf die Abwesenheit eines Belegs. Die Tabelle trägt jetzt
eine fünfte Art, `absence`, und drei der vierzehn Regeln deklarieren sie. Das ist
kein aus Vorsicht gesetztes Etikett: diese drei sind hier die größten Wanderer.
Schweigen ist der schwächste Eingang, weil die Extraktion nachweislich
Argumentstruktur verliert — die Abwesenheit kann die des Laufs sein und nicht die
des Dokuments.

**Drei Einschränkungen.** Die Entscheidungsläufe sind nach dem Reparaturlauf, und
der stellt Dubletten her (4.6), also könnte ein Teil jener Streuung von ihm
kommen. Trennen lässt sich das hier nicht — aber beide A24-Sätze sind unrepariert
und zeigen dasselbe Bild, der Befund hängt also nicht am Reparaturlauf. Die
Pakete sind mit der heutigen toleranten Verankerung neu gegatet, diese Zahlen
sagen also, was dieselben Vorschläge jetzt ergeben, und nicht, was die Läufe
damals gemeldet haben — derselbe Vorbehalt wie in 4.3. Und für Befunde gibt es
weiter kein Gold, Reproduzierbarkeit bleibt eine untere Schranke: das sind Böden,
keine Raten.

**Was folgt, und was nicht.** Nicht „die deterministischen Regeln sind kaputt" —
sie rechnen, was sie rechnen sollen. Was wandert, sind ihre **Eingänge**, und bei
den drei Abwesenheitsregeln wandert die Abwesenheit selbst. Was folgt, ist die
Entscheidung aus 4.14 zu einem härteren Preis. Dort hieß es, die Markierung nenne
die Art der Abhängigkeit und nicht die beobachtete Instabilität, weil im
Produktionslauf einmal extrahiert wird. Auf kurzen Fällen war das eine Feinheit.
Auf einem Dokument, auf dem **keine** Befundart stillsteht, ist ein einzelner Lauf
keine Stichprobe, sondern eine Ziehung — und ein Dossier, das 16 logische Lücken
meldet, wo ein zweiter Lauf 13 gemeldet hätte, sieht genauso endgültig aus. Die
Wiederholungspolitik ist damit keine Sparfrage mehr, sondern die Frage, ob ein
Befund überhaupt als Zahl berichtet werden darf.

### 4.16 Die Hälfte des Bedeutungsbestands umgeschrieben, und die Zahlen bewegen sich nicht

Die Tabelle in 4.12 berichtete Bedeutung erhalten mit 69 von 72 Fall-Läufen. Zwei
unabhängige blinde Durchsichten fanden danach, dass **zwölf der 24 Fälle** — sechs
Paare — mit Wiedergaben bestanden werden konnten, die die Bedeutung verlieren, und
in einem Fall, dass das Gold eine pragmatische Implikatur behauptete statt dessen,
was der Satz entailt. Alle sechzehn Gegenbeispiele wurden gegen den Validator
geprüft, **bevor** etwas geändert wurde: zwölf hielten, vier waren widerlegt.

Umgeschrieben statt gestrichen, unter der Bedingung, die die ganze Übung
entschieden hat: **Dokumente und Spannen sind unangetastet, alle 24.** Geändert
wurden nur Bedingungen, Verbote und Gold-Prosa. Deshalb blieb jedes bereits
bezahlte Dossier bewertbar, und der Umschreibung folgt eine Messung statt einer
Hoffnung.

| Fall | vorher | nachher |
|---|---|---|
| `spk-01` | eine Gruppe, die auch das Wort der anderen Sprache akzeptierte | Sprecher **und** Sprechakt in einem Claim |
| `spk-02` | zwei Gruppen: ein Name, ein Name | je Claim: Sprecher, Akt, Inhalt |
| `mul-01`, `mul-02` | eine Gruppe je Claim | je Claim: Subjekt, Prädikat, Zahl |
| `mod-02` | ein Berichtsverb aus einer Liste von vier | Quelle genannt und Wirkung benannt; welches Verb, ist gleichgültig |
| `neg-02` | das Gold behauptete eine Implikatur | das Gold auf das Entailment zurückgeführt |
| `neg-01`, `mod-01`, `cor-01` | — | umgekehrter Skopus und fehlende Flexionsformen verboten |

Dafür brauchte es eine Schema-Änderung. Eine Bedingung von einer Gruppe je Claim
ist erfüllt, sobald ein einzelnes Wort daraus vorkommt — deshalb bestanden zwei
nackte Fragmente einen Fall, dessen Zweck war, dass zwei Aussagen überleben. Jetzt
ist es eine Liste von Gruppen je Claim, die **ein** Claim gemeinsam erfüllen muss.

Sieben bestätigte Falschalarme wurden ebenfalls behoben — treue Wiedergaben, die
die Bedingung abgelehnt hat, etwa „laut Studie", wo ein Berichtsverb verlangt war.
Jede ist mit Datum und der Durchsicht vermerkt, die sie benannt hat, und **keine
kommt von einem gescheiterten Lauf**: sie kommen vom Lesen der Fälle, und das ist
der Unterschied, den die Governance-Regel schützen soll.

**Dann die Messung.** Dieselben 72 Dossiers gegen den umgeschriebenen Bestand:

| Phänomen | 4.12, schwacher Bestand | jetzt, zwölf Fälle härter |
|---|---:|---:|
| Negation, Modalität, Korrelation, Sprecher, mehrere Aussagen | je 12/12 | je 12/12 |
| Geltungsbereich | 6/6 | 6/6 |
| Bedingung | 3/6 | 3/6 |
| **Summe** | **69/72** | **69/72** |

4.12 musste sagen, die Zahlen stünden, ihre Beweiskraft aber nicht. Das ist jetzt
**widerlegt — durch eine Messung und nicht durch ein Argument.** Die tatsächliche
Ausgabe des Extraktors besteht den strengen Bestand genauso wie den schwachen, das
69 von 72 war also **kein** Artefakt schwacher Fälle. Eine Sache ist neu sichtbar:
`sco-02` meldet drei Verzerrungen, wo es keine meldete, weil die
Verbotslesart-Prüfung den unbedingten Nachsatz jetzt als solchen benennt. Am
Urteil ändert das nichts; das Instrument sagt jetzt, *was* schiefgeht, und nicht
nur *dass*.

Die sechzehn Gegenbeispiele der Durchsichten liegen als Testdatei im Repo, also
kostet jede künftige Weitung einer Token-Liste den Nachweis, dass alle sechzehn
Urteile intakt bleiben. Die 0,16 $ sind dauerhafte Testabdeckung geworden statt
einer Meinung.

**Was das nicht heißt.** Der Bestand ist kein Entwurf mehr — zwei unabhängige
Durchsichten sind vermerkt, nachgerechnet und umgesetzt —, und damit ist er
**geprüft, nicht gut.** Es sind weiter 24 Stellen von einem bis drei Sätzen,
geschrieben von derselben Partei, die das System gebaut hat, und die beiden
Durchsichten sind zwei Modelle und kein Fachgutachten. Das siebte Phänomen bleibt
offen, weil die Durchsichten darüber uneins sind, und die Relationen bleiben
unannotiert, weil keine der beiden auf Nachfrage eine Kante vorgeschlagen hat.

### 4.17 Sechs Felder, die das Produkt nie liest, und ein Zustandsautomat ohne Übergänge

Dass `anchor_ambiguous` write-only ist, war ein Zufallsbefund beim Einbau einer
anderen Markierung (§4.13). Die Lehre daraus: eine Markierung, die nichts rendert,
ist keine Sicherung. `scripts/unread_fields.py` stellt die Frage jetzt für **jedes**
Feld über den Syntaxbaum, statt auf den nächsten Zufall zu warten — und findet
**sechs** geschrieben und nie gelesen, wo ein Grep über denselben Baum vier fand.

| | geschrieben, nie gelesen |
|---|---|
| **Provenienz, zu Recht ungelesen** | `anchor_normalised`, `proposed_span` — im JSON zu stehen *ist* die Aufgabe |
| **Bezeichner, die nichts auflöst** | `finding_id`, `relation_id` — ein Primärschlüssel ohne Fremdschlüssel |
| **grenzwertig** | `anchor_ambiguous` — das Gate rechnet die Bedingung inline nochmal, gerendert wird sie nicht |
| **der eine, der zählt** | `semantic_state` |

Eines liegt noch tiefer: **`Finding.state` wird nie gesetzt und nie gelesen** und
trägt nur seinen Vorgabewert. Das ist eine stärkere Aussage als „ungelesen", und
die Prüfung berichtet es getrennt.

**Ungelesen heißt nicht falsch**, und das gehört vor die Liste. Vier der sechs sind
Provenienz oder Bezeichner und richtig so.

**Der eine, der zählt**, wurde von [arXiv 2610.06496](https://arxiv.org/abs/2610.06496)
benannt: Modelle verwechseln „erwähnt" mit „weiterhin wirksam" — nach einer
Zurückweisung taucht der inaktive Inhalt in 59,63 % der neuen Fehler wieder auf.
Gegen diesen Code geprüft hält die gute Hälfte konstruktionsbedingt: ein Vorschlag,
den das Gate ablehnt, erreicht weder die deterministischen Regeln noch die
Reviewer — Provenienz und Wirksamkeit sind **vor** der Zulassung schon getrennt.

Es fehlt der Fall *nach* der Zulassung. Ein Claim, der zugelassen und später von
einem Menschen verworfen oder durch eine bessere Lesart ersetzt wird, hat keinen
Zustand, der das sagt. `semantic_state` wäre die Stelle und ist **ein
Zustandsautomat ohne Übergänge**: zwei Werte, die das Gate setzen kann, über alle
242 gespeicherten Claims genau einer beobachtet, kein Leser irgendwo, und nach dem
Gate kann ihn nichts mehr ändern. Das Paper liefert also keinen neuen Mangel,
sondern den Fehlermodus, der eine schon gelistete Lücke etwas kosten lässt.

Zwei Paper aus derselben Zulieferung haben hier nichts zu holen, und der Grund
gehört festgehalten. [U-Space](https://arxiv.org/abs/2610.09087) gewinnt
Unsicherheitsrichtungen aus dem Residual Stream; **wir haben keine
Aktivierungen**, weil wir eine API rufen und Text bekommen — eine Grenze, keine
Hürde. Die übertragbare Lehre, dass ein Prädiktor bloß Länge nachspuren kann
(68,6 % AUROC, 52,4 % nach Längenkontrolle), wendet §4.4 schon an und benennt den
eigenen Reststörfaktor; der dort offene Nachlauf ist **nicht gratis**, weil nur
eines der vier Dokumente noch gespeichert ist.
[Accurate but Not Humble](https://arxiv.org/abs/2610.12360) beschreibt einen früh
erkannten und später verlorenen Konflikt, was §4.15 in unseren Begriffen gemessen
hat: `internal_contradiction` mit Schweregrad high läuft 2, 7, 5 über identische
Läufe. Unsere Version liegt zwischen Läufen, ihre innerhalb einer Trajektorie, und
innerhalb eines Laufs kann der Verfall hier nicht auftreten, weil die Regel
deterministisch ist. Der Demut-gegen-Genauigkeit-Handel ist hier nicht messbar,
weil §4.14 festgehalten hat, dass es für Befunde kein Gold gibt.

**Die Entscheidung ist nicht meine.** `semantic_state` wird entweder ein echter
Zustand mit Übergängen — was die seit §4.5 offene Schemaentscheidung über das
versionierte Overlay verlangt — oder es wird entfernt. Ein Feld mit einem
beobachteten Wert, das nichts liest, ist Dekoration, die wie eine Sicherung
aussieht; genau das hat `anchor_ambiguous` gekostet, und die Lehre gilt hier ein
zweites Mal.

### 4.18 Ein Wächter für Reviewer-Vergleiche, gebaut weil genau er fehlte

Anlass war ein eigener Befund, der sich **nicht belegen** ließ. Bei der Durchsicht
von [BeliefScope](https://arxiv.org/abs/2610.11305) zeigte sich, dass eine
gemessene Achse ihren Charakter mit einer Bedingung wechselt, die mit der Evidenz
nichts zu tun hat:

| Satz | Reviewer-Budget | Konfidenzwerte von `flash-evidence-skeptic` |
|---|---|---|
| `rv54` | 8.192 | 6 Werte, strikt im 0,05-Raster |
| `rb55` | 65.536 | 15 Werte, außerhalb dieses Rasters (0,82 · 0,87 · 0,88 · 0,91 …) |

Gleiches Modell, gleiches Profil, gleicher Graph, gleicher Vertrag. Der einzige
*benannte* Unterschied ist das Ausgabebudget, und „die Konfidenz ist
differenzierter geworden" wäre hier ein Artefakt des Budgets und kein besseres
Urteil.

**Dieser Satz ist nicht belegbar.** Die Extraktion zeichnet seit immer einen
`prompt_hash` auf, und dieser Wächter hat sich einmal bezahlt: von drei
Artefakten, die das Log als drei Läufe eines Arms führte, teilten nur zwei den
Hash — ein Pooling hätte einen Konfigurationsunterschied als
Lauf-zu-Lauf-Instabilität berichtet. Für die Reviewer-Arme gab es das Feld nicht,
also ruht jeder Reviewer-Vergleich dieser Aufzeichnung auf der Annahme, die Arme
seien gleich gefragt worden.

Aufgezeichnet wird jetzt das Kleinste, was die Frage beantwortbar macht:
`prompt_fingerprint(system, user)` gibt der Konvention **einen** Namen, denn zwei
Ausdrücke, die fast dasselbe bedeuten, sind schlechter als ein fehlender Hash —
sie vergleichen sich als ungleich und melden einen Unterschied, der nicht da ist.
Der Hash steht auf **beiden** Reviewer-Pfaden, auch auf dem fehlgeschlagenen, und
wird vor dem Aufruf berechnet: gesendet wurde der Prompt so oder so, und „der Arm
wurde gefragt und hat geschwiegen" ist der Fall, den ein späterer Vergleich am
dringendsten trennen muss. Daneben `max_tokens` — genau die Bedingung, die den
Befund oben erzeugt hat und im Artefakt nirgends stand.

**Rückwirkend gilt er nicht**, und das ist die Hälfte, die zählt. Jeder bisher
gespeicherte Reviewer-Lauf trägt konstruktionsbedingt keinen Hash; der
`rv54`/`rb55`-Satz bleibt also unbelegt, und kein späterer Code ändert das — es
braucht einen neuen, bezahlten Lauf. Die Sicherung wirkt ab hier, und ein
Vergleich über diese Grenze hinweg ist weiterhin ungeschützt.

Sieben Mutationen liefen gegen die neuen Tests, sechs wurden sofort gefangen. Die
überlebende entfernte das verbindende Trennzeichen, und der Test, der sie fangen
sollte, verglich ein Paar, das sich mit Trennzeichen *und* ohne unterscheidet —
er prüfte also nichts. Gemessen statt vermutet ist das unterscheidende Paar
`("ab","c")` gegen `("a","bc")`, das ohne Trenner kollidiert. Dieselbe Messung
legte eine ehrliche Grenze offen: die Konvention ist **nicht injektiv**, denn ein
Prompt, der das Trennzeichen enthält, lässt zwei verschiedene Aufteilungen
zusammenfallen. In diesem Repository ist das harmlos, weil die Systemhälfte ein
festes Rollenprompt ist — aber es ist eine Eigenschaft des Repositorys und nicht
des Hashes, und ein Test behauptet sie deshalb ausdrücklich. Mutationen finden
weiter schlechte Tests statt schlechten Code; in dieser Aufzeichnung zum fünften
Mal.

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
| Der Auslöser eines Befunds konnte ein undefinierter Label sein, ohne dass es dastand | Jede deterministische Regel deklariert, worauf ihr Auslöser steht; es reist ins JSON und auf die Seite | im Review (§4.13) |

### Ungelöst

| Problem | Warum es offen ist |
|---|---|
| Abdeckung — Passagen, die der Extraktor nie liest | Kein Mechanismus außer einem zweiten bezahlten Aufruf, dessen Wert jetzt unklar ist |
| Die Streuung selbst | Verkleinert, nicht beseitigt; 27 Spannen sind größer als die meisten messwerten Effekte |
| Reviewer-Stabilität | 0,27 nach der strengen Regel, und die Zahl ist nicht reproduzierbar (§5.4) |
| Abbruch auf langen Dokumenten | Die Grenze wandert mit dem Budget, sie verschwindet nicht |
| Echte Umformulierung im Zitat | 11 von 465 Vorschlägen, zu Recht abgelehnt, dauerhaft verloren |
| Relations-Ausdruckskraft | Vier von sechs Familien gedeckt; die Lücke ist ungeprüft |
| Der Zustand eines Befunds wird nie aufgelöst | Braucht ein versioniertes Overlay und eine Schemaentscheidung. §4.17 benennt, was es kostet: `semantic_state` existiert, nimmt über 242 Claims einen Wert an, und nichts liest es — ein nach der Zulassung von einem Menschen verworfener Claim hinterlässt also keine Spur davon |
| Bedingungssätze | In der Hälfte der Läufe am Komma zerlegt; der Nachsatz steht dann unbedingt da. Eine Sprachanweisung hat es nicht berührt (§4.12) |
| Das Claim-Typ-Vokabular hat keine Wahrheitsbedingungen | 21 Typen, nirgends im Vertrag definiert. Zwei vertretbare Labels für einen Satz sind kein Modellfehler — es heißt, dass es keine Tatsache darüber gibt, und darauf steht ein Befund mit 0,95 (§4.13) |
| Ein Befund kann unter identischer Eingabe erscheinen und verschwinden | Auf 24 kurzen Fällen liefern 4 von 24 Dokumenten eine andere Befundmenge. Auf zwei langen Dokumenten bleibt **keine Befundart stehen**: Widersprüche mit Schweregrad high laufen 2, 7, 5 und logische Lücken 16, 19, 13 über identische Läufe. Drei Regeln feuern auf eine *Abwesenheit*, und die Extraktion verliert bekanntlich Argumentstruktur — die Abwesenheit kann die des Laufs sein (§4.14, §4.15) |
| Ein einzelner Lauf ist eine Ziehung, keine Stichprobe | Im Produktionslauf wird einmal je Dokument extrahiert, ein Dossier mit 16 logischen Lücken sieht also genauso endgültig aus wie eines mit 13. Wiederholungen behöben das zum dreifachen Extraktionspreis (§4.15, Entscheidung 7) |
| Ob ein Befund *gedeckt* war, im Unterschied zu reproduzierbar | Hier nicht rechenbar: nichts in diesem Projekt ist eine Gold-Antwort darauf, ob ein deterministischer Befund richtig ist. Reproduzierbarkeit ist nur eine untere Schranke (§4.14) |
| Bedeutung eines Claims, jenseits von 24 kurzen Sätzen | Der einzige Bedeutungsbestand sind 24 Fälle von einem bis drei Sätzen. Zwei unabhängige Durchsichten sind jetzt vermerkt, nachgerechnet und umgesetzt (§4.16), er ist also geprüft statt Entwurf — aber es sind weiter 24 kurze Stellen, geschrieben von der Partei, die das System gebaut hat |
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
scripts/                                 25 Messskripte, jedes getestet
docs/architecture.md §3a–§3ao            die chronologische Aufzeichnung
CHANGELOG.md                             was sich bewegt hat, samt Rücknahmen
```

Die Offline-Kontrollen spielen gespeicherte Pakete ab und rufen keinen Provider:
`polished` 5 Claims / 5 Relationen / 3 Befunde, `rough` 4 / 4 / 0, `budget`
25 / 15 / 10. Sie sind die Referenz für Verhaltensänderungen — und sie können eine
Prompt-Regression nicht sehen; das kann nur ein Live-Lauf gegen das eingefrorene
Paket.

472 Tests und einer übersprungen, `ruff check` sauber.

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
7. **Ob Extraktionswiederholungen Politik werden.** §4.14 hat gezeigt, dass die
   Markierung aus §4.13 die Art der Abhängigkeit nennt und nicht die beobachtete
   Instabilität — am Emissionszeitpunkt gibt es einen Lauf, und ob *dieser* Befund
   wechselt, ist nicht wissbar. Drei Läufe je Dokument machten es wissbar und
   kosten die dreifache Extraktion. **§4.15 erhöht den Einsatz:** auf einem langen
   Dokument bleibt keine Befundart stehen, ein einzelner Lauf ist also eine
   Ziehung und keine Stichprobe, und die Frage ist nicht mehr Sparsamkeit, sondern
   ob ein Befund überhaupt als nackte Zahl berichtet werden darf.
8. **Ob ein deterministischer Befund überhaupt auf einem erzeugten Label stehen
   darf.** §4.13 hat die Herkunft ausgeliefert statt die Abhängigkeit zu
   entfernen, also bleibt das offen. Definitionen für die 21 Typen nachzutragen
   ist die naheliegende Reparatur und die gemessen wirkungsloseste; gewirkt haben
   opake Kennungen, und die kosten die Lesbarkeit des Vokabulars.
