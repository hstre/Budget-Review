"""Measure vocabulary coverage of Haylett's shipped weights on our cases.

Uses Haylett's own tokenizer regex (mvec_encoder.MVecEncoder.tokenize,
takens-embedding-transformer @ 42beb88) and his own vocab files, so the
numbers are produced by his pipeline's rules, not mine.
"""
import json
import re
import sys

# verbatim from mvec_encoder.py:51-54 @ 42beb88
TOKEN_RE = re.compile(r'\w+(?:-\w+)*|[.,!?;:\-\[\](){}"\'/\\]', re.UNICODE)


def tokenize(text):
    return TOKEN_RE.findall(text)


def load_vocab(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["vocab"]


def coverage(text, vocab):
    toks = tokenize(text)
    known = [t for t in toks if t in vocab]
    return len(toks), len(known), [t for t in toks if t not in vocab]


def main(argv):
    vocabs = {name: load_vocab(path) for name, path in
              (p.split("=", 1) for p in argv[1:] if "=" in p)}
    cases = json.load(open(argv[0], encoding="utf-8"))
    rows = []
    for name, vocab in vocabs.items():
        print(f"\n=== vocab {name}: {len(vocab)} entries ===")
        for case in cases:
            n, k, oov = coverage(case["text"], vocab)
            rows.append((name, case["id"], n, k))
            print(f"{case['id']:<28} {k:>2}/{n:<3} known  "
                  f"({100.0*k/n:5.1f}%)  oov={oov}")
    print("\n=== totals ===")
    for name in vocabs:
        sel = [r for r in rows if r[0] == name]
        n = sum(r[2] for r in sel)
        k = sum(r[3] for r in sel)
        print(f"{name:<14} {k}/{n} tokens known = {100.0*k/n:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
