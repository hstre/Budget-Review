# runs/takens-01 — Takens-Based Transformer probe

Criterion fixed beforehand in `docs/prereg-takens-01.md` (commit `613efb1`).
Result and reading in `docs/findings-takens-01.md`.

Subject: `KevinHaylett/takens-embedding-transformer` at commit
`42beb885fcacca5df7a915491478d3128f9b2f1d`. That repository is **not**
vendored here; it was cloned into its own directory outside this checkout and
read there. Its two shipped checkpoints were loaded with
`torch.load(..., weights_only=True)`, never with the repository's own
`torch.load` call, which unpickles.

| file | what it is |
|---|---|
| `oov.py`, `vocabulary-coverage.txt` | vocabulary coverage of the shipped weights on our condition triples, using the subject's own tokenizer and vocabulary |
| `trace.py`, `trace.txt` | one sentence traced through the subject's model: token ids, the Takens grid against the lagged input, hidden state, top predictions |
| `run_probe.py`, `raw.json` | the pre-registered run: 106 triples × 4 arms × 2 weight sets, every per-triple record |
| `summarise.py`, `summary.txt` | the run against the pre-registered criterion |
| `diagnose.py`, `diagnose.txt` | **post hoc**, after the criterion was evaluated: the length baseline and the agreement with untrained weights that void the one arm that passed |
| `paired.py`, `paired.txt` | **post hoc**: the per-triple verdicts crossed (2x2, with the discordant counts the accuracy difference rests on), the same figures stratified by what sentence length alone would say, and every interval recomputed over the 53 translation pairs instead of the 106 triples |
| `triples.json` | the texts used by `oov.py` |

Reproduce (needs `torch`; nothing here imports from `src/`):

    python3 run_probe.py <takens-clone> \
        ../../src/budget_review/fixtures/semantic_cases/cases.json raw.json
    python3 summarise.py raw.json
    python3 diagnose.py raw.json
