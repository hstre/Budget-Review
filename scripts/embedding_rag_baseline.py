"""Compare the semantic layer with a simple embedding/RAG retrieval upper bound.

This is deliberately generous to RAG: once a chunk is retrieved, the whole chunk
counts as recovered. No generation step can improve retrieval recall, so this is
an upper bound for a conventional retrieve-then-read pipeline on this test.

The comparison is budget-matched per document. RAG may retrieve source chunks
until their union covers the same number of source characters as the governed
semantic claims. Queries are fixed before the run and do not use gold labels.

Usage:
    python scripts/embedding_rag_baseline.py <gold-xmi-directory> <output.json>
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from sentence_transformers import SentenceTransformer

from budget_review.gate import govern_packet
from budget_review.models import SemanticPacket
from budget_review.prompts import extraction_prompt

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("echr_gold", ROOT / "echr_gold.py")
echr_gold = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(echr_gold)

_spec2 = importlib.util.spec_from_file_location("variant", ROOT / "prompt_variant_extract.py")
variant = importlib.util.module_from_spec(_spec2)
assert _spec2.loader is not None
_spec2.loader.exec_module(variant)

CASES = ("001-141170", "001-172073", "001-61247")
MODEL = "sentence-transformers/all-mpnet-base-v2"
WINDOW = 700
STRIDE = 500
QUERIES = (
    "the applicant's legal arguments complaints submissions reasons and evidence",
    "the government's legal arguments objections submissions reasons and evidence",
    "the court's legal reasoning assessment findings conclusions and legal test",
    "legal rule factual premise evidence inference counterargument limitation and conclusion",
)


@dataclass
class Scores:
    char_coverage: float
    recall_50: float
    recall_80: float
    any_overlap: float


@dataclass
class Result:
    case_id: str
    document_chars: int
    gold_spans: int
    semantic_claims: int
    semantic_source_budget: int
    semantic: Scores
    rag_chunks: int
    rag_source_budget: int
    rag: Scores


def merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[list[int]] = []
    for start, end in sorted(spans):
        if out and start <= out[-1][1]:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return [(a, b) for a, b in out]


def union_len(spans: list[tuple[int, int]]) -> int:
    return sum(b - a for a, b in merge(spans))


def covered(span: tuple[int, int], covers: list[tuple[int, int]]) -> int:
    a, b = span
    return sum(max(0, min(b, y) - max(a, x)) for x, y in merge(covers))


def score(gold: list[tuple[int, int]], covers: list[tuple[int, int]]) -> Scores:
    gold_chars = union_len(gold)
    char_cov = sum(covered(g, covers) for g in gold) / gold_chars if gold_chars else 0.0
    shares = [covered(g, covers) / max(1, g[1] - g[0]) for g in gold]
    return Scores(
        char_coverage=round(char_cov, 4),
        recall_50=round(sum(s >= 0.50 for s in shares) / len(shares), 4) if shares else 0.0,
        recall_80=round(sum(s >= 0.80 for s in shares) / len(shares), 4) if shares else 0.0,
        any_overlap=round(sum(s > 0 for s in shares) / len(shares), 4) if shares else 0.0,
    )


def region_and_gold(path: Path) -> tuple[str, list[tuple[int, int]]]:
    parsed = echr_gold.read_decision(path)
    if parsed is None:
        raise RuntimeError(f"no gold spans in {path}")
    text, spans = parsed
    low, high = spans[0][0], spans[-1][1]
    region = text[low:high]
    gold = [(a - low, b - low) for a, b, _, _ in spans]
    return region, gold


def windows(document: str) -> list[tuple[int, int, str]]:
    out = []
    start = 0
    while start < len(document):
        end = min(len(document), start + WINDOW)
        # Prefer a nearby paragraph/sentence boundary without making windows tiny.
        if end < len(document):
            cut = max(document.rfind("\n", start + WINDOW // 2, end), document.rfind(". ", start + WINDOW // 2, end))
            if cut > start + WINDOW // 2:
                end = cut + (1 if document[cut:cut+1] == "\n" else 2)
        out.append((start, end, document[start:end]))
        if end == len(document):
            break
        start += STRIDE
    return out


def rag_spans(model: SentenceTransformer, document: str, budget: int) -> list[tuple[int, int]]:
    chunks = windows(document)
    texts = [c[2] for c in chunks]
    chunk_vecs = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    query_vecs = model.encode(list(QUERIES), normalize_embeddings=True, convert_to_numpy=True)
    scores = (chunk_vecs @ query_vecs.T).max(axis=1)
    order = sorted(range(len(chunks)), key=lambda i: float(scores[i]), reverse=True)
    selected: list[tuple[int, int]] = []
    for i in order:
        selected.append((chunks[i][0], chunks[i][1]))
        if union_len(selected) >= budget:
            break
    return selected


def run_case(model: SentenceTransformer, gold_dir: Path, case_id: str) -> Result:
    document, gold = region_and_gold(gold_dir / f"{case_id}.xmi")
    system, user = extraction_prompt(case_id, document, "general")
    packet_dict = variant.extract_packet(case_id, system, user, 16384)
    packet = SemanticPacket.from_dict(packet_dict)
    dossier = govern_packet(document, packet)
    semantic_spans = [(c.anchor_start, c.anchor_end) for c in dossier.claims]
    source_budget = union_len(semantic_spans)
    retrieved = rag_spans(model, document, source_budget)
    return Result(
        case_id=case_id,
        document_chars=len(document),
        gold_spans=len(gold),
        semantic_claims=len(dossier.claims),
        semantic_source_budget=source_budget,
        semantic=score(gold, semantic_spans),
        rag_chunks=len(retrieved),
        rag_source_budget=union_len(retrieved),
        rag=score(gold, retrieved),
    )


def mean(rows: list[Result], arm: str, metric: str) -> float:
    return round(sum(getattr(getattr(r, arm), metric) for r in rows) / len(rows), 4)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("gold_dir", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    model = SentenceTransformer(MODEL)
    rows = [run_case(model, args.gold_dir, case) for case in CASES]
    payload = {
        "design": {
            "embedding_model": MODEL,
            "cases": CASES,
            "window_chars": WINDOW,
            "stride_chars": STRIDE,
            "queries": QUERIES,
            "budget_rule": "RAG source-span union may grow until it reaches semantic source-span union",
            "rag_interpretation": "retrieval upper bound: every retrieved character counts as recovered; no generator penalty",
        },
        "results": [
            {**asdict(r), "semantic": asdict(r.semantic), "rag": asdict(r.rag)} for r in rows
        ],
        "macro": {
            arm: {metric: mean(rows, arm, metric) for metric in ("char_coverage", "recall_50", "recall_80", "any_overlap")}
            for arm in ("semantic", "rag")
        },
        "limitations": [
            "LAM:ECHR's evaluated region is very densely argumentative, so span retrieval is an easy target and does not test provenance or typed relations.",
            "RAG is deliberately advantaged: retrieval chunks count directly as recovered without requiring a generator to reconstruct claims.",
            "The semantic arm is one live DeepSeek draw per document; prior branch work shows cross-session variance, so this is a first comparison, not a final estimate.",
            "Fixed generic queries are chosen before the run and use no document-specific gold information.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
