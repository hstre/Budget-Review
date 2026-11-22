"""Trace one sentence through Haylett's TBT implementation.

Usage: trace.py <takens_dir> <model.pt> <vocab.json> "<sentence>" ...
Prints, for each sentence: the token ids the repo's own encoder produces,
what the Takens grid at one position actually contains, the hidden state
the stack produces, and the model's top next-word predictions.
"""
import sys

import torch


def main(argv):
    takens_dir, model_path, vocab_path = argv[0], argv[1], argv[2]
    sentences = argv[3:]
    sys.path.insert(0, takens_dir)
    from mvec_encoder import MVecEncoder
    from mvec_model import MVecLanguageModel
    from tbt_architecture import create_exponential_delays

    enc = MVecEncoder()
    enc.load_vocab(vocab_path)
    ck = torch.load(model_path, map_location="cpu", weights_only=True)
    cfg = ck["model_config"]
    model = MVecLanguageModel(
        vocab_size=cfg["vocab_size"], embed_dim=cfg["embed_dim"],
        hidden_dim=cfg["hidden_dim"], num_layers=cfg["num_layers"],
        max_seq_len=512, delays=create_exponential_delays(128), dropout=0.1,
        use_identity_embed=cfg["use_identity_embed"],
        identity_embed_dim=cfg["identity_embed_dim"], tie_weights=False)
    model.load_state_dict(ck["model_state_dict"])
    model.eval()
    delays = model.tbt.takens_embed.takens.delays
    print(f"vocab={cfg['vocab_size']}  embed={cfg['embed_dim']}  "
          f"layers={cfg['num_layers']}  delays={delays}")
    print(f"parameters={sum(p.numel() for p in model.parameters()):,}")

    for sent in sentences:
        print("\n" + "=" * 68)
        print(f"input: {sent!r}")
        toks = enc.tokenize(sent)
        wid, iid, _ = enc.encode_sequence(sent, "USER")
        print(f"tokens ({len(toks)}): {toks}")
        print(f"word_ids          : {wid}")
        print(f"unk (id==0) count : {wid.count(0)}/{len(wid)}")
        ids = torch.tensor([wid])
        idn = torch.tensor([iid])
        with torch.no_grad():
            tok_emb = model.token_embed(ids)
            id_emb = model.identity_embed(idn)
            x = torch.cat([tok_emb, id_emb], dim=-1)
            grid = model.tbt.takens_embed.takens(x)
            print(f"token+identity x  : {tuple(x.shape)}")
            print(f"Takens grid       : {tuple(grid.shape)}  "
                  f"= [batch, seq, 1+{len(delays)} delays, dim]")
            t = len(wid) - 1
            same = []
            for j, d in enumerate(delays, start=1):
                if d <= t:
                    same.append((d, bool(torch.equal(grid[0, t, j], x[0, t - d]))))
                else:
                    same.append((d, f"pad={float(grid[0, t, j, 0]):.1f}"))
            print(f"grid[0,{t},0] == x[0,{t}]      : "
                  f"{bool(torch.equal(grid[0, t, 0], x[0, t]))}")
            print(f"grid[0,{t},j] == x[0,{t}-delay] : {same}")
            hidden = model.tbt(x)
            print(f"hidden            : {tuple(hidden.shape)}  "
                  f"(no sentence vector is produced)")
            logits = model.word_output(hidden)
            top = torch.topk(logits[0, -1], 5)
            words = [enc.decode_word(int(i)) for i in top.indices]
            print(f"top-5 next word   : "
                  f"{list(zip(words, [round(float(v), 2) for v in top.values], strict=True))}")
            pooled = hidden[0].mean(0)
            print(f"mean-pooled hidden (my construction, not his): "
                  f"dim={tuple(pooled.shape)} norm={float(pooled.norm()):.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
