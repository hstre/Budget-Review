from __future__ import annotations

import ast
import csv
import io
import json
import os
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from budget_review.provider import DeepSeekProvider

BASE = "https://raw.githubusercontent.com/trusthlt/mining-legal-arguments/main/data/agent"
CASES = ["001-100543", "001-100897"]
CHUNK_CHARS = 12000
SAMPLES_PER_CASE = 3


@dataclass
class ChunkResult:
    sample_id: str
    document_chars: int
    gold_argument_spans: int
    gold_argument_chars: int
    predicted_claims: int
    located_predicted_claims: int
    gold_argument_char_coverage: float
    gold_component_hit_any: float
    gold_component_hit_20pct: float
    predicted_char_overlap_with_gold: float


def fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read().decode("utf-8")


def load_case(case_id: str) -> tuple[str, list[tuple[int, int]]]:
    raw = fetch(f"{BASE}/{case_id}.csv")
    reader = csv.DictReader(io.StringIO(raw), delimiter="\t")
    parts: list[str] = []
    gold: list[tuple[int, int]] = []
    cursor = 0

    for row in reader:
        tokens = ast.literal_eval(row["tokens"])
        labels = ast.literal_eval(row["labels"])
        if len(tokens) != len(labels):
            raise ValueError(f"token/label length mismatch in {case_id}")

        line_parts: list[str] = []
        token_offsets: list[tuple[int, int]] = []
        line_cursor = 0
        for token in tokens:
            if line_parts:
                line_cursor += 1
            start = line_cursor
            line_parts.append(token)
            line_cursor += len(token)
            token_offsets.append((start, line_cursor))
        line = " ".join(line_parts)

        run_start = None
        run_end = None
        for label, (start, end) in zip(labels, token_offsets):
            argumentative = label != "O"
            begins = label.startswith("B-")
            if argumentative:
                if run_start is None or begins:
                    if run_start is not None:
                        gold.append((cursor + run_start, cursor + run_end))
                    run_start = start
                run_end = end
            elif run_start is not None:
                gold.append((cursor + run_start, cursor + run_end))
                run_start = None
                run_end = None
        if run_start is not None:
            gold.append((cursor + run_start, cursor + run_end))

        parts.append(line)
        cursor += len(line) + 1

    return "\n".join(parts), gold


def make_chunks(document: str, gold: list[tuple[int, int]]) -> list[tuple[str, list[tuple[int, int]], int]]:
    lines = document.splitlines(keepends=True)
    chunks: list[tuple[str, list[tuple[int, int]], int]] = []
    start = 0
    buf: list[str] = []
    size = 0
    for line in lines:
        if buf and size + len(line) > CHUNK_CHARS:
            text = "".join(buf).rstrip("\n")
            end = start + len(text)
            local_gold = [(max(a, start) - start, min(b, end) - start) for a, b in gold if a < end and b > start]
            chunks.append((text, local_gold, start))
            start += size
            buf = []
            size = 0
        buf.append(line)
        size += len(line)
    if buf:
        text = "".join(buf).rstrip("\n")
        end = start + len(text)
        local_gold = [(max(a, start) - start, min(b, end) - start) for a, b in gold if a < end and b > start]
        chunks.append((text, local_gold, start))
    return chunks


def sampled_chunks(case_id: str) -> list[tuple[str, str, list[tuple[int, int]]]]:
    document, gold = load_case(case_id)
    chunks = make_chunks(document, gold)
    if len(chunks) <= SAMPLES_PER_CASE:
        indexes = list(range(len(chunks)))
    else:
        indexes = [0, len(chunks) // 2, len(chunks) - 1]
    return [(f"{case_id}-chunk-{i+1}-of-{len(chunks)}", chunks[i][0], chunks[i][1]) for i in indexes]


def locate_claims(document: str, spans: list[str]) -> list[tuple[int, int]]:
    located: list[tuple[int, int]] = []
    for span in spans:
        start = document.find(span)
        if start < 0:
            continue
        if document.find(span, start + 1) >= 0:
            continue
        located.append((start, start + len(span)))
    return located


def union_len(spans: list[tuple[int, int]]) -> int:
    if not spans:
        return 0
    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return sum(end - start for start, end in merged)


def overlap_len(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def covered_len(targets: list[tuple[int, int]], covers: list[tuple[int, int]]) -> int:
    intersections: list[tuple[int, int]] = []
    for a in targets:
        for b in covers:
            start, end = max(a[0], b[0]), min(a[1], b[1])
            if start < end:
                intersections.append((start, end))
    return union_len(intersections)


def score_chunk(provider: DeepSeekProvider, sample_id: str, document: str, gold: list[tuple[int, int]]) -> ChunkResult:
    packet = provider.extract(sample_id, document, profile="general")
    raw_spans = [c["raw_span"] for c in packet.to_dict()["claims"]]
    predicted = locate_claims(document, raw_spans)

    gold_chars = union_len(gold)
    predicted_chars = union_len(predicted)
    overlap = covered_len(gold, predicted)
    any_hits = 0
    hit_20 = 0
    for g in gold:
        g_len = g[1] - g[0]
        best = max((overlap_len(g, p) for p in predicted), default=0)
        if best > 0:
            any_hits += 1
        if g_len and best / g_len >= 0.20:
            hit_20 += 1

    return ChunkResult(
        sample_id=sample_id,
        document_chars=len(document),
        gold_argument_spans=len(gold),
        gold_argument_chars=gold_chars,
        predicted_claims=len(raw_spans),
        located_predicted_claims=len(predicted),
        gold_argument_char_coverage=round(overlap / gold_chars, 4) if gold_chars else 0.0,
        gold_component_hit_any=round(any_hits / len(gold), 4) if gold else 0.0,
        gold_component_hit_20pct=round(hit_20 / len(gold), 4) if gold else 0.0,
        predicted_char_overlap_with_gold=round(overlap / predicted_chars, 4) if predicted_chars else 0.0,
    )


def main() -> None:
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise SystemExit("DEEPSEEK_API_KEY missing")
    provider = DeepSeekProvider(timeout=180, retries=1)
    samples = [sample for case_id in CASES for sample in sampled_chunks(case_id)]
    results = [score_chunk(provider, *sample) for sample in samples]

    out = Path("benchmark-output")
    out.mkdir(exist_ok=True)
    payload = {
        "dataset": "TrustHLT mining-legal-arguments / data/agent",
        "dataset_url": "https://github.com/trusthlt/mining-legal-arguments",
        "sampling": f"first/middle/last chunks, max {CHUNK_CHARS} chars, from two held-out public ECHR cases",
        "samples": [asdict(r) for r in results],
        "macro": {
            "gold_argument_char_coverage": round(sum(r.gold_argument_char_coverage for r in results) / len(results), 4),
            "gold_component_hit_any": round(sum(r.gold_component_hit_any for r in results) / len(results), 4),
            "gold_component_hit_20pct": round(sum(r.gold_component_hit_20pct for r in results) / len(results), 4),
            "predicted_char_overlap_with_gold": round(sum(r.predicted_char_overlap_with_gold for r in results) / len(results), 4),
        },
        "limitations": [
            "LAM:ECHR labels argumentative spans by actor role; Content Review extracts atomic claims, so this is a coverage stress test, not an exact claim-type benchmark.",
            "The long cases are chunked only because the current provider caps extraction output at 16,384 tokens and the full-document run truncated.",
            "Chunking means this run does not test cross-chunk relations or true full-document long-context behavior.",
            "Source text is reconstructed from public token rows with single spaces, preserving gold labels but not original typography.",
            "Predicted raw spans that occur more than once are conservatively left unlocated rather than guessed.",
        ],
    }
    (out / "results.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "README.md").write_text("# Independent ECHR benchmark\n\n```json\n" + json.dumps(payload, indent=2, ensure_ascii=False) + "\n```\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
