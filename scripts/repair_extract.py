"""A coverage-repair second pass: ask only about the passages nothing reached.

Three gold spans on 001-141170 sit at 0, 20 and 23 per cent coverage across
runs, and segmenting the document did not reach them (§3c). What is left to try
is a second call that is told where the graph is thin and what it already
contains, so it adds rather than re-interprets.

Two rules make this an experiment rather than a wish.

The passages come from the product's own coverage measurement, never from the
gold answer. Feeding back which gold spans were missed would measure nothing
except our ability to read the answer key, and the resulting design could not
run on a document without one.

And every proposal is judged by `repair_merge.verdict` before it may join the
graph: outside the requested passages, or adding no uncovered characters, and
it is rejected with a reason. The double run showed what the unfiltered version
costs — 186 claims and 141 without a gold match for two extra gold spans.

Relations are not requested in the repair pass. An edge between a repair claim
and a first-pass claim would be proposed by a model that saw only one of them
in full, and building relations over the stabilised claim set is a separate
question.

The first run showed the targeting, not the second call, to be the limit: two
of the three hard cases were never in the request, because a coverage gap exists
only where no claim is anchored at all. --target thin asks instead about blocks
whose anchored share is low, which is the same question one level coarser.

Usage:
    repair_extract.py <gold_data-directory> <output-directory> <decision-id>
                      [--repeats N] [--max-tokens N] [--watch G03,G09,G19]
                      [--target uncovered|thin]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


echr = _load("echr_gold")
segmented = _load("segmented_extract")
variant = _load("prompt_variant_extract")
recall = _load("measure_recall")
repair_rule = _load("repair_merge")

from budget_review.gate import govern_packet, sha256_text  # noqa: E402
from budget_review.models import SemanticPacket  # noqa: E402

THRESHOLD = 0.8

REPAIR_SYSTEM = """

This is a repair pass over a document that has already been extracted. The
claims listed in the user message are already in the graph. Do not propose them
again, and do not restate one in different words. Propose claims only for the
passages listed at the end of the message: every raw_span must lie inside one of
them, copied verbatim and exactly from the document, including its punctuation
and line breaks. Return an empty claims array if those passages carry
no claim of their own. Return "relations": [] — this pass proposes claims only.
"""


def repair_prompt(
    document_id: str, document: str, existing: list[str], gaps: list[tuple[int, int]]
) -> tuple[str, str]:
    """The production contract, plus where to look and what not to repeat."""
    system, _ = variant.extraction_prompt(document_id, document, "general")
    listed = "\n".join(f"- {content}" for content in existing)
    passages = "\n\n".join(
        f"[{index}] {document[start:end].strip()}" for index, (start, end) in enumerate(gaps, 1)
    )
    user = (
        f"DOCUMENT ID: {document_id}\n\nDOCUMENT:\n{document}\n\n"
        f"CLAIMS ALREADY IN THE GRAPH ({len(existing)}), do not propose these again:\n{listed}\n\n"
        f"PASSAGES THE GRAPH BARELY REACHES ({len(gaps)}):\n{passages}"
    )
    return system + REPAIR_SYSTEM, user


def merge(base: dict, repairs: list[dict], prompts: list[str], outputs: list[str]) -> dict:
    """First-pass packet plus the admitted repairs, under one provenance."""
    merged = dict(base)
    merged["claims"] = [*base["claims"], *repairs]
    merged["relations"] = base.get("relations", [])
    provenance = dict(base["provenance"])
    provenance["run_id"] = str(uuid.uuid4())
    provenance["prompt_hash"] = sha256_text("\n".join(prompts))
    provenance["output_hash"] = sha256_text("\n".join(outputs))
    merged["provenance"] = provenance
    return merged


def scored(packet_data: dict, document: str, gold: list) -> tuple[int, int, dict[str, float]]:
    """Spans reached, claims admitted, and the share per gold span."""
    semantic = govern_packet(document, SemanticPacket.from_dict(packet_data))
    union = recall.merged([(c.anchor_start, c.anchor_end) for c in semantic.claims])
    shares = {
        proposal_id: recall.covered_characters(span, union) / max(1, span[1] - span[0])
        for proposal_id, span, _ in gold
    }
    found = sum(1 for share in shares.values() if share >= THRESHOLD)
    return found, len(semantic.claims), shares


def thin_blocks(
    document: str,
    anchored: list[tuple[int, int]],
    min_share: float = 0.5,
    min_characters: int = 120,
) -> list[tuple[int, int]]:
    """Blocks of the document whose anchored share is low, not only zero.

    The first repair pass was driven by the coverage gaps, and two of the three
    hard cases were never in the request: a gap exists only where no claim is
    anchored at all, and only above 120 characters, so a passage anchored at 20
    per cent breaks into remainders that each fall under the threshold. Partial
    coverage is invisible to that mechanism.

    A block — a paragraph, or a numbered paragraph on its own line, the unit the
    segmented run never cuts — is what an argument is written in, and its
    anchored share is a statement about the passage rather than about the
    distance between two anchors. Whitespace does not count, so an indented
    block is not thin because of its indentation.

    Like the gap list, this names passages and decides nothing: a thin block may
    be a heading or a recital.
    """
    union = recall.merged(list(anchored))
    thin: list[tuple[int, int]] = []
    position = 0
    for block in segmented.blocks(document):
        start, end = position, position + len(block)
        position = end
        ink = sum(1 for character in document[start:end] if not character.isspace())
        if ink < min_characters:
            continue
        covered = sum(
            1
            for offset in range(start, end)
            if not document[offset].isspace()
            and any(u_start <= offset < u_end for u_start, u_end in union)
        )
        if covered / ink < min_share:
            thin.append((start, end))
    return thin


def gap_share(gold: list, gaps: list[tuple[int, int]]) -> dict[str, float]:
    """How much of each gold span the pass was actually asked about.

    A span the coverage gaps do not name cannot be repaired by a pass driven by
    them, however good the second call is. Partial coverage is the case to watch:
    the remainder of a half-anchored passage can fall below the gap threshold and
    then never reaches the list.
    """
    union = recall.merged(list(gaps))
    return {
        proposal_id: recall.covered_characters(span, union) / max(1, span[1] - span[0])
        for proposal_id, span, _ in gold
    }


def one_round(
    decision: str,
    document: str,
    gold: list,
    max_tokens: int,
    watch: list[str],
    target: str = "uncovered",
) -> dict:
    system, user = variant.extraction_prompt(decision, document, "general")
    first = variant.extract_packet(decision, system, user, max_tokens)
    before_found, before_claims, before_shares = scored(first, document, gold)

    semantic = govern_packet(document, SemanticPacket.from_dict(first))
    anchored = [(claim.anchor_start, claim.anchor_end) for claim in semantic.claims]
    if target == "thin":
        gaps = thin_blocks(document, anchored)
    else:
        gaps = [
            (gap.start, gap.end) for gap in (semantic.coverage.gaps if semantic.coverage else ())
        ]
    if not gaps:
        return {"gaps": 0, "before": (before_found, before_claims, before_shares)}

    existing = [claim.canonical_content for claim in semantic.claims]
    repair_system, repair_user = repair_prompt(decision, document, existing, gaps)
    second = variant.extract_packet(decision, repair_system, repair_user, max_tokens)

    admitted_union = anchored
    admitted_contents = set(existing)
    kept: list[dict] = []
    reasons: dict[str, int] = {}
    # A rejected proposal is only useful if it says why. The first run lost most
    # of them to verbatim quoting rather than to the merge rule, which is not
    # visible from a count.
    rejected: list[tuple[str, str]] = []
    for index, proposal in enumerate(second.get("claims", []), start=1):
        offset = document.find(proposal["raw_span"])
        if offset < 0:
            reasons["source_span_not_found"] = reasons.get("source_span_not_found", 0) + 1
            rejected.append(("source_span_not_found", proposal["raw_span"]))
            continue
        span = (offset, offset + len(proposal["raw_span"]))
        decision_, reason = repair_rule.verdict(
            span, proposal["canonical_content"], gaps, admitted_union, admitted_contents
        )
        reasons[reason] = reasons.get(reason, 0) + 1
        if decision_ == "admit":
            kept.append({**proposal, "proposal_id": f"Q{index:02d}"})
        else:
            rejected.append((reason, proposal["raw_span"]))

    merged_packet = merge(
        first,
        kept,
        [system, repair_system],
        [first["provenance"]["output_hash"], second["provenance"]["output_hash"]],
    )
    after_found, after_claims, after_shares = scored(merged_packet, document, gold)
    return {
        "gap_share": gap_share(gold, gaps),
        "rejected": rejected,
        "gaps": len(gaps),
        "gap_characters": sum(end - start for start, end in gaps),
        "proposed": len(second.get("claims", [])),
        "reasons": reasons,
        "before": (before_found, before_claims, before_shares),
        "after": (after_found, after_claims, after_shares),
        "watch": watch,
        "packet": merged_packet,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gold_data", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("decision")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--max-tokens", type=int, default=16384)
    parser.add_argument("--watch", default="G03,G09,G19")
    parser.add_argument(
        "--target",
        choices=("uncovered", "thin"),
        default="uncovered",
        help="uncovered uses the coverage gaps; thin uses blocks with a low anchored share",
    )
    args = parser.parse_args()

    echr.build(args.gold_data, args.decision, args.out_dir)
    document = (args.out_dir / f"{args.decision}.txt").read_text(encoding="utf-8")
    gold_packet = json.loads(
        (args.out_dir / f"{args.decision}.gold.json").read_text(encoding="utf-8")
    )
    gold = recall.gold_spans(gold_packet, document)
    watch = [name.strip() for name in args.watch.split(",") if name.strip()]

    for round_index in range(1, args.repeats + 1):
        try:
            result = one_round(args.decision, document, gold, args.max_tokens, watch, args.target)
        except (SystemExit, Exception) as error:  # noqa: BLE001
            print(
                f"Runde {round_index}: gescheitert ({type(error).__name__}: {error})",
                file=sys.stderr,
            )
            continue
        print()
        print(f"=== Runde {round_index} ===")
        before_found, before_claims, before_shares = result["before"]
        if not result.get("after"):
            print(f"  keine Lücken; {before_found}/{len(gold)}, {before_claims} Claims")
            continue
        after_found, after_claims, after_shares = result["after"]
        print(
            f"  Ziel ({args.target}): {result['gaps']} Passagen "
            f"({result['gap_characters']} Zeichen)"
        )
        print(f"  Vorschläge:    {result['proposed']}")
        for reason, count in sorted(result["reasons"].items()):
            print(f"    {reason}: {count}")
        print(f"  Recall 80 %:   {before_found}/{len(gold)} -> {after_found}/{len(gold)}")
        print(f"  Claims:        {before_claims} -> {after_claims}")
        for name in watch:
            before = before_shares.get(name)
            after = after_shares.get(name)
            if before is None:
                continue
            asked = result["gap_share"].get(name, 0.0)
            print(f"    {name}: {before:.0%} -> {after:.0%}   (davon erfragt: {asked:.0%})")
        for reason, span in result["rejected"][:3]:
            print(f"    abgelehnt [{reason}]: {' '.join(span.split())[:90]}")
        (args.out_dir / f"{args.decision}.repaired.{round_index}.json").write_text(
            json.dumps(result["packet"], ensure_ascii=False, indent=1), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
