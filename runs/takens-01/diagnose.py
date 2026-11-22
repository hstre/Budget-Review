"""Post hoc, after the pre-registered run: what is my measure actually using?

Not pre-registered. Marked post hoc wherever it is reported.
"""
import json
import random
import sys

BOOT = 10000
SEED = 20261122


def boot_mean(vals):
    rng = random.Random(SEED)
    n = len(vals)
    d = sorted(sum(vals[rng.randrange(n)] for _ in range(n)) / n
               for _ in range(BOOT))
    return d[int(0.025 * BOOT)], d[int(0.975 * BOOT)]


r = json.load(open(sys.argv[1], encoding="utf-8"))
for wname, w in r["weights"].items():
    base = [x for x in w["arms"]["full"] if x["case_id"] != "brief-triple"]
    unt = {x["triple_id"]: x for x in w["arms"]["untrained"]}
    print(f"\n=== {wname} ===")

    # a pure length baseline: faithful wins iff its length is nearer
    lenb = [int(abs(x["ntok"][0] - x["ntok"][1]) < abs(x["ntok"][0] - x["ntok"][2]))
            for x in base]
    lo, hi = boot_mean(lenb)
    print(f"length-only baseline      : {sum(lenb)/len(lenb):.3f} [{lo:.2f},{hi:.2f}]")
    # does the model agree with the length baseline?
    agree = sum(1 for x, lb in zip(base, lenb, strict=True) if x["tbt_correct"] == lb)
    print(f"full agrees with length   : {agree}/{len(base)} "
          f"({100.0*agree/len(base):.0f}%)")
    agree_u = sum(1 for x in base
                  if x["tbt_correct"] == unt[x["triple_id"]]["tbt_correct"])
    print(f"full agrees with untrained: {agree_u}/{len(base)} "
          f"({100.0*agree_u/len(base):.0f}%)")
    # how close are the cosines to 1?
    cs = sorted(min(x["cos_faithful"], x["cos_distorted"]) for x in base)
    print(f"min cosine over all pairs : {cs[0]:.4f}   median: "
          f"{cs[len(cs)//2]:.4f}")
    # the all-unk subset: triples where every token of all three texts is unk
    allunk = [x for x in base if sum(x["oov"]) == sum(x["ntok"])]
    if allunk:
        acc = sum(x["tbt_correct"] for x in allunk) / len(allunk)
        lb = [int(abs(x["ntok"][0]-x["ntok"][1]) < abs(x["ntok"][0]-x["ntok"][2]))
              for x in allunk]
        print(f"triples with 100% oov     : {len(allunk)}  "
              f"full={acc:.3f}  length-only={sum(lb)/len(lb):.3f}  "
              f"agree={sum(1 for x, v in zip(allunk, lb, strict=True) if x['tbt_correct'] == v)}"
              f"/{len(allunk)}")
