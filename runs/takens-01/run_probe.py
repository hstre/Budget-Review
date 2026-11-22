"""Pre-experiment: can a TBT sentence vector rank a faithful reading above a
distorted one, better than word overlap?

Measure, baseline, controls and criterion are fixed in
Budget-Review/docs/prereg-takens-01.md, committed before this ran.

Usage: run_probe.py <takens_dir> <cases.json> <out.json>
"""
import json
import random
import sys

import torch

BOOT = 10000
SEED = 20261122


def build_triples(path):
    data = json.load(open(path, encoding="utf-8"))
    out = []
    for c in data["cases"]:
        for i, f in enumerate(c["permitted_readings"], 1):
            for j, d in enumerate(c["forbidden_readings"], 1):
                out.append({
                    "triple_id": f"{c['case_id']}/f{i}d{j}",
                    "case_id": c["case_id"],
                    "language": c["language"],
                    "phenomenon": c["phenomenon"],
                    "original": c["span"], "faithful": f, "distorted": d,
                })
    return out


def load_model(takens_dir, model_path, trained=True):
    sys.path.insert(0, takens_dir)
    from mvec_model import MVecLanguageModel
    from tbt_architecture import create_exponential_delays
    ck = torch.load(model_path, map_location="cpu", weights_only=True)
    cfg = ck["model_config"]
    torch.manual_seed(SEED)
    model = MVecLanguageModel(
        vocab_size=cfg["vocab_size"], embed_dim=cfg["embed_dim"],
        hidden_dim=cfg["hidden_dim"], num_layers=cfg["num_layers"],
        max_seq_len=512, delays=create_exponential_delays(128), dropout=0.1,
        use_identity_embed=cfg["use_identity_embed"],
        identity_embed_dim=cfg["identity_embed_dim"], tie_weights=False)
    if trained:
        model.load_state_dict(ck["model_state_dict"])
    model.eval()
    return model, cfg


def vector(model, enc, text, zero_delays=False, shuffle=None):
    wid, iid, _ = enc.encode_sequence(text, "USER")
    if not wid:
        return None, 0, 0
    if shuffle is not None:
        order = list(range(len(wid)))
        random.Random(shuffle).shuffle(order)
        wid = [wid[k] for k in order]
    ids = torch.tensor([wid])
    idn = torch.tensor([iid])
    with torch.no_grad():
        x = torch.cat([model.token_embed(ids), model.identity_embed(idn)], -1)
        tak = model.tbt.takens_embed
        grid = tak.takens(x)
        if zero_delays:
            grid = grid.clone()
            grid[:, :, 1:, :] = tak.takens.pad_value
        flat = tak.takens.flatten_grid(grid)
        h = tak.layer_norm(tak.projection(flat))
        for layer in model.tbt.layers:
            h = layer(h)
        h = model.tbt.final_norm(h)
    return h[0].mean(0), wid.count(0), len(wid)


def cos(a, b):
    return float(torch.nn.functional.cosine_similarity(a[None], b[None]))


def jaccard(enc, a, b):
    sa, sb = set(enc.tokenize(a)), set(enc.tokenize(b))
    return len(sa & sb) / len(sa | sb) if sa | sb else 0.0


def boot_diff(pairs, rng):
    """Bootstrap over triples: percentile interval of mean(x - y)."""
    n = len(pairs)
    draws = []
    for _ in range(BOOT):
        s = [pairs[rng.randrange(n)] for _ in range(n)]
        draws.append(sum(a - b for a, b in s) / n)
    draws.sort()
    return draws[int(0.025 * BOOT)], draws[int(0.975 * BOOT)]


def boot_mean(vals, rng):
    n = len(vals)
    draws = []
    for _ in range(BOOT):
        draws.append(sum(vals[rng.randrange(n)] for _ in range(n)) / n)
    draws.sort()
    return draws[int(0.025 * BOOT)], draws[int(0.975 * BOOT)]


def main(argv):
    takens_dir, cases_path, out_path = argv
    sys.path.insert(0, takens_dir)
    from mvec_encoder import MVecEncoder

    triples = build_triples(cases_path)
    extra = [{
        "triple_id": "brief-triple", "case_id": "brief-triple",
        "language": "de", "phenomenon": "condition",
        "original": "Wenn die Förderung bewilligt wird, "
                    "stellen wir zwei Techniker ein.",
        "faithful": "Die Einstellung von zwei Technikern ist für den Fall "
                    "einer Förderzusage zugesagt.",
        "distorted": "Wir stellen zwei Techniker ein.",
    }]
    report = {"n_triples": len(triples), "boot_draws": BOOT, "seed": SEED,
              "weights": {}}

    for wname, mpath, vpath in (
        ("solar_system", f"{takens_dir}/models/solar_system/solar_system_model.pt",
         f"{takens_dir}/models/solar_system/solar_system_vocab.json"),
        ("qba", f"{takens_dir}/models/qba/qba_model.pt",
         f"{takens_dir}/models/qba/qba_vocab.json"),
    ):
        enc = MVecEncoder()
        enc.load_vocab(vpath)
        arms = {}
        for aname, trained, zero, shuf in (
            ("full", True, False, None),
            ("delays_zeroed", True, True, None),
            ("shuffled", True, False, SEED),
            ("untrained", False, False, None),
        ):
            model, cfg = load_model(takens_dir, mpath, trained=trained)
            rows = []
            for t in triples + extra:
                vo, oov_o, n_o = vector(model, enc, t["original"], zero, shuf)
                vf, oov_f, n_f = vector(model, enc, t["faithful"], zero, shuf)
                vd, oov_d, n_d = vector(model, enc, t["distorted"], zero, shuf)
                sf, sd = cos(vo, vf), cos(vo, vd)
                jf = jaccard(enc, t["original"], t["faithful"])
                jd = jaccard(enc, t["original"], t["distorted"])
                rows.append({**t, "cos_faithful": sf, "cos_distorted": sd,
                             "tbt_correct": int(sf > sd),
                             "jac_faithful": jf, "jac_distorted": jd,
                             "jac_correct": int(jf > jd),
                             "cos_gap": sf - sd,
                             "oov": [oov_o, oov_f, oov_d],
                             "ntok": [n_o, n_f, n_d]})
            arms[aname] = rows
        report["weights"][wname] = {"config": cfg, "arms": arms,
                                    "vocab_size": enc.get_vocab_size()}
    json.dump(report, open(out_path, "w"), ensure_ascii=False)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
