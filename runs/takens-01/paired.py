"""Post hoc, on the stored per-triple verdicts of runs/takens-01.

Two questions the first summary did not answer:

1. Do the length baseline and the full model get the *same* triples right, or
   do they agree only in the aggregate? Reported as a 2x2 table with the
   discordant counts, which is what a difference in accuracy actually rests on.
2. The 53 German and 53 English triples are translation pairs — 19 case pairs,
   each with one German and one English case of identical shape, aligned
   reading by reading. A triple and its translation are therefore not two
   independent observations. Every interval here resamples the 53 **pairs**,
   each contributing both of its triples, and the per-triple interval is printed
   beside it so the difference is visible.

Usage: paired.py raw.json
"""
import json
import random
import sys
from collections import defaultdict

BOOT = 10000
SEED = 20261122


def pair_key(triple_id):
    """'sco-02-de/f1d1' -> ('sco-02', 'f1d1'): the language-free item."""
    case, rest = triple_id.split("/")
    for suffix in ("-de", "-en"):
        if case.endswith(suffix):
            return case[: -len(suffix)], rest
    raise ValueError(triple_id)


def length_correct(row):
    n_o, n_f, n_d = row["ntok"]
    return int(abs(n_o - n_f) < abs(n_o - n_d))


def length_margin(row):
    """< 0 when the faithful reading is nearer the original in token count."""
    n_o, n_f, n_d = row["ntok"]
    return abs(n_o - n_f) - abs(n_o - n_d)


def clusters(rows):
    """Group rows into one unit per translation pair."""
    by = defaultdict(list)
    for r in rows:
        by[pair_key(r["triple_id"])].append(r)
    return list(by.values())


def boot_acc(units, key, rng):
    n = len(units)
    draws = []
    for _ in range(BOOT):
        hit = tot = 0
        for _ in range(n):
            for r in units[rng.randrange(n)]:
                hit += key(r)
                tot += 1
        draws.append(hit / tot)
    draws.sort()
    return draws[int(0.025 * BOOT)], draws[int(0.975 * BOOT)]


def boot_diff(units, key_a, key_b, rng):
    n = len(units)
    draws = []
    for _ in range(BOOT):
        tot = cnt = 0
        for _ in range(n):
            for r in units[rng.randrange(n)]:
                tot += key_a(r) - key_b(r)
                cnt += 1
        draws.append(tot / cnt)
    draws.sort()
    return draws[int(0.025 * BOOT)], draws[int(0.975 * BOOT)]


def table(rows, key_a, key_b, name_a, name_b):
    both = sum(1 for r in rows if key_a(r) and key_b(r))
    only_a = sum(1 for r in rows if key_a(r) and not key_b(r))
    only_b = sum(1 for r in rows if key_b(r) and not key_a(r))
    neither = sum(1 for r in rows if not key_a(r) and not key_b(r))
    print(f"\n  {name_a} x {name_b}")
    print(f"    both right      {both:>4}")
    print(f"    only {name_a:<11}{only_a:>4}")
    print(f"    only {name_b:<11}{only_b:>4}")
    print(f"    both wrong      {neither:>4}")
    print(f"    agree on {both + neither}/{len(rows)} triples "
          f"({100.0 * (both + neither) / len(rows):.0f} %); the accuracy "
          f"difference rests on {only_a} against {only_b}")
    return only_a, only_b


def main(argv):
    r = json.load(open(argv[0], encoding="utf-8"))
    for wname, w in r["weights"].items():
        rows = [x for x in w["arms"]["full"] if x["case_id"] != "brief-triple"]
        unt = {x["triple_id"]: x["tbt_correct"]
               for x in w["arms"]["untrained"]}
        units = clusters(rows)
        print(f"\n{'=' * 70}\nweights {wname}: {len(rows)} triples in "
              f"{len(units)} translation pairs")
        assert all(len(u) == 2 for u in units), "a pair is not two triples"

        keys = {
            "full": lambda x: x["tbt_correct"],
            "length": length_correct,
            "jaccard": lambda x: x["jac_correct"],
            "untrained": lambda x, u=unt: u[x["triple_id"]],
        }
        print("\n  accuracy, resampling translation pairs (53 units):")
        for name, key in keys.items():
            acc = sum(key(x) for x in rows) / len(rows)
            lo, hi = boot_acc(units, key, random.Random(SEED))
            lo1, hi1 = boot_acc([[x] for x in rows], key, random.Random(SEED))
            print(f"    {name:<10} {acc:.3f}  pairs [{lo:.3f}, {hi:.3f}]   "
                  f"triples [{lo1:.3f}, {hi1:.3f}]")

        print("\n  stratified by what sentence length alone would say")
        print("  (margin = |n(o)-n(f)| - |n(o)-n(d)|; negative means the "
              "faithful")
        print("   reading is the nearer one in token count)")
        strata = (
            ("length points wrong", lambda x: length_margin(x) > 0),
            ("length is a tie    ", lambda x: length_margin(x) == 0),
            ("length points right", lambda x: length_margin(x) < 0),
        )
        for label, pick in strata:
            sel = [x for x in rows if pick(x)]
            if not sel:
                continue
            scores = "  ".join(
                f"{name}={sum(k(x) for x in sel) / len(sel):.3f}"
                for name, k in keys.items())
            print(f"    {label}  n={len(sel):<4}{scores}")

        for a, b in (("full", "length"), ("full", "jaccard"),
                     ("full", "untrained"), ("length", "jaccard")):
            only_a, only_b = table(rows, keys[a], keys[b], a, b)
            d = (sum(keys[a](x) for x in rows)
                 - sum(keys[b](x) for x in rows)) / len(rows)
            lo, hi = boot_diff(units, keys[a], keys[b], random.Random(SEED))
            lo1, hi1 = boot_diff([[x] for x in rows], keys[a], keys[b],
                                 random.Random(SEED))
            print(f"    {a} - {b}: {d:+.3f}  pairs [{lo:+.3f}, {hi:+.3f}]  "
                  f"clear of zero: {lo > 0}   "
                  f"triples [{lo1:+.3f}, {hi1:+.3f}] clear: {lo1 > 0}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
