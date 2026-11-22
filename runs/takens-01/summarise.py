import json
import random
import sys

BOOT = 10000
SEED = 20261122


def boot_pairs(pairs, rng):
    n = len(pairs)
    d = sorted(sum(a - b for a, b in (pairs[rng.randrange(n)] for _ in range(n))) / n
               for _ in range(BOOT))
    return d[int(0.025 * BOOT)], d[int(0.975 * BOOT)]


def boot_mean(vals, rng):
    n = len(vals)
    d = sorted(sum(vals[rng.randrange(n)] for _ in range(n)) / n
               for _ in range(BOOT))
    return d[int(0.025 * BOOT)], d[int(0.975 * BOOT)]


r = json.load(open(sys.argv[1], encoding="utf-8"))
print(f"triples from the fixture: {r['n_triples']}  "
      f"(+1 named in the brief, reported separately)")

for wname, w in r["weights"].items():
    print(f"\n{'='*72}\nweights {wname}: vocab {w['vocab_size']}, "
          f"config {w['config']}")
    base = [x for x in w["arms"]["full"] if x["case_id"] != "brief-triple"]
    rng = random.Random(SEED)

    # OOV over everything the measure saw
    tot = sum(sum(x["ntok"]) for x in base)
    oov = sum(sum(x["oov"]) for x in base)
    print(f"\ntoken coverage on these texts: {tot-oov}/{tot} known "
          f"= {100.0*(tot-oov)/tot:.1f}%  (oov {100.0*oov/tot:.1f}%)")
    for lang in ("de", "en"):
        s = [x for x in base if x["language"] == lang]
        t2 = sum(sum(x["ntok"]) for x in s)
        o2 = sum(sum(x["oov"]) for x in s)
        print(f"  {lang}: {100.0*(t2-o2)/t2:.1f}% known")

    print(f"\n{'arm':<15}{'all':>18}{'de':>18}{'en':>18}")
    for aname in ("full", "delays_zeroed", "shuffled", "untrained"):
        rows = [x for x in w["arms"][aname] if x["case_id"] != "brief-triple"]
        cells = []
        for sel in (rows, [x for x in rows if x["language"] == "de"],
                    [x for x in rows if x["language"] == "en"]):
            acc = sum(x["tbt_correct"] for x in sel) / len(sel)
            lo, hi = boot_mean([x["tbt_correct"] for x in sel],
                               random.Random(SEED))
            cells.append(f"{acc:.3f} [{lo:.2f},{hi:.2f}]")
        print(f"{aname:<15}" + "".join(f"{c:>18}" for c in cells))
    rows = base
    cells = []
    for sel in (rows, [x for x in rows if x["language"] == "de"],
                [x for x in rows if x["language"] == "en"]):
        acc = sum(x["jac_correct"] for x in sel) / len(sel)
        lo, hi = boot_mean([x["jac_correct"] for x in sel], random.Random(SEED))
        cells.append(f"{acc:.3f} [{lo:.2f},{hi:.2f}]")
    print(f"{'jaccard':<15}" + "".join(f"{c:>18}" for c in cells))

    # criterion 1: full - jaccard, paired over triples
    pairs = [(x["tbt_correct"], x["jac_correct"]) for x in base]
    lo, hi = boot_pairs(pairs, random.Random(SEED))
    d = sum(a - b for a, b in pairs) / len(pairs)
    print(f"\nfull - jaccard      : {d:+.3f} [{lo:+.3f}, {hi:+.3f}]"
          f"   clear of zero: {lo > 0}")
    # criterion 3: full - delays_zeroed
    z = {x["triple_id"]: x["tbt_correct"] for x in w["arms"]["delays_zeroed"]}
    pairs = [(x["tbt_correct"], z[x["triple_id"]]) for x in base]
    lo2, hi2 = boot_pairs(pairs, random.Random(SEED))
    d2 = sum(a - b for a, b in pairs) / len(pairs)
    print(f"full - delays_zeroed: {d2:+.3f} [{lo2:+.3f}, {hi2:+.3f}]"
          f"   clear of zero: {lo2 > 0}")
    s = {x["triple_id"]: x["tbt_correct"] for x in w["arms"]["shuffled"]}
    agree = sum(1 for x in base if x["tbt_correct"] == s[x["triple_id"]])
    print(f"full vs shuffled    : same verdict in {agree}/{len(base)} triples")

    # degeneracy
    ident = sum(1 for x in base if abs(x["cos_gap"]) < 1e-4)
    print(f"\ndegenerate triples (|cos gap| < 1e-4): {ident}/{len(base)}")
    for lang in ("de", "en"):
        s2 = [x for x in base if x["language"] == lang]
        print(f"  {lang}: {sum(1 for x in s2 if abs(x['cos_gap']) < 1e-4)}"
              f"/{len(s2)}")
    gaps = sorted(abs(x["cos_gap"]) for x in base)
    print(f"median |cos gap|: {gaps[len(gaps)//2]:.5f}   "
          f"max: {gaps[-1]:.5f}")

    # named cases
    print("\nnamed cases:")
    for x in w["arms"]["full"]:
        if x["case_id"].startswith("sco-02") or x["case_id"] == "brief-triple":
            print(f"  {x['triple_id']:<22} cos f={x['cos_faithful']:+.4f} "
                  f"d={x['cos_distorted']:+.4f} -> "
                  f"{'ok' if x['tbt_correct'] else 'WRONG':<5} | "
                  f"jac f={x['jac_faithful']:.2f} d={x['jac_distorted']:.2f} -> "
                  f"{'ok' if x['jac_correct'] else 'WRONG'}")
