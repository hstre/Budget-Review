"""Command-line interface for offline replay and DeepSeek-backed review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .consolidate import consolidate_findings
from .ingest import IngestError, ingest
from .models import SchemaError
from .pipeline import ReviewPipeline, load_packet
from .profiles import PROFILES
from .provider import DeepSeekProvider, ProviderError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="content-review",
        description="Content review over a governed ClaimGraph; style and authorship are ignored.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    review = subparsers.add_parser("review", help="review one or more source documents")
    review.add_argument("inputs", nargs="+", type=Path)
    review.add_argument("--document-id")
    review.add_argument("--packet", type=Path, help="frozen semantic packet for offline replay")
    review.add_argument("--provider", choices=("offline", "deepseek"), default="offline")
    review.add_argument("--extraction-model", default="deepseek-v4-flash")
    review.add_argument("--profile", choices=tuple(PROFILES), default="general")
    review.add_argument(
        "--live-review", action="store_true", help="run two independent LLM reviewer arms"
    )
    review.add_argument("--output", type=Path, default=Path("review-output"))

    demo = subparsers.add_parser("demo", help="run a frozen content-review control case")
    demo.add_argument("--profile", choices=tuple(PROFILES), default="general")
    demo.add_argument("--case", choices=("polished", "rough"), default="polished")
    demo.add_argument("--live-review", action="store_true")
    demo.add_argument("--output", type=Path, default=Path("review-output/demo"))
    demo.add_argument("--json", action="store_true", help="print a JSON summary")

    validate = subparsers.add_parser("validate", help="validate and gate a frozen extraction")
    validate.add_argument("source", type=Path)
    validate.add_argument("packet", type=Path)
    validate.add_argument("--profile", choices=tuple(PROFILES), default="general")
    validate.add_argument("--output", type=Path, default=Path("review-output/validation"))

    web = subparsers.add_parser("web", help="start the local bilingual web interface")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--no-browser", action="store_true")
    web.add_argument(
        "--allow-network",
        action="store_true",
        help="allow binding beyond localhost; add authentication before shared deployment",
    )
    return parser


def _provider(enabled: bool) -> DeepSeekProvider | None:
    return DeepSeekProvider() if enabled else None


def _run_review(args: argparse.Namespace) -> int:
    use_live = args.provider == "deepseek" or args.live_review
    provider = _provider(use_live)
    source = ingest(args.inputs, document_id=args.document_id)
    packet = load_packet(args.packet) if args.packet else None
    dossier = ReviewPipeline(provider, args.extraction_model, args.profile).run(
        source,
        packet=packet,
        live_review=args.live_review,
    )
    json_path, markdown_path, html_path = ReviewPipeline.write(dossier, args.output)
    print(
        f"claims={len(dossier.semantic.claims)} "
        f"relations={len(dossier.semantic.relations)} "
        f"findings={len(dossier.findings)}"
    )
    print(f"profile={dossier.profile}")
    print(f"json={json_path}")
    print(f"markdown={markdown_path}")
    print(f"html={html_path}")
    return 0


def _run_demo(args: argparse.Namespace) -> int:
    fixture_root = Path(__file__).resolve().parent / "fixtures"
    if args.profile == "budget":
        fixture_dir = fixture_root / "coherence_theatre"
        source_path = fixture_dir / "proposal.md"
        packet_path = fixture_dir / "semantic_packet.json"
        document_id = "regional-skills-bridge"
    else:
        fixture_dir = fixture_root / "content_theatre"
        source_path = fixture_dir / f"{args.case}.md"
        packet_path = fixture_dir / f"{args.case}_packet.json"
        document_id = f"content-{args.case}"
    source = ingest([source_path], document_id=document_id)
    packet = load_packet(packet_path)
    provider = _provider(args.live_review)
    dossier = ReviewPipeline(provider, profile=args.profile).run(
        source,
        packet=packet,
        live_review=args.live_review,
    )
    json_path, markdown_path, html_path = ReviewPipeline.write(dossier, args.output)
    issues = consolidate_findings(dossier.findings)
    summary = {
        "claims": len(dossier.semantic.claims),
        "profile": dossier.profile,
        "relations": len(dossier.semantic.relations),
        "semantic_rejections": len(dossier.semantic.rejections),
        "findings": len(dossier.findings),
        "review_points": len(issues),
        "review_rejections": len(dossier.review_rejections),
        "json": str(json_path),
        "markdown": str(markdown_path),
        "html": str(html_path),
    }
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(
            f"Frozen {summary['profile']} control: "
            f"{summary['claims']} claims, {summary['relations']} relations, "
            f"{summary['review_points']} consolidated review points "
            f"from {summary['findings']} raw findings."
        )
        print(f"Dossier: {html_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "web":
            if args.host not in {"127.0.0.1", "localhost", "::1"} and not args.allow_network:
                print(
                    "content-review: non-local binding requires --allow-network",
                    file=sys.stderr,
                )
                return 2
            from .web import serve

            serve(args.host, args.port, open_browser=not args.no_browser)
            return 0
        if args.command == "demo":
            return _run_demo(args)
        if args.command == "validate":
            args = argparse.Namespace(
                command="review",
                inputs=[args.source],
                document_id=None,
                packet=args.packet,
                provider="offline",
                extraction_model="deepseek-v4-flash",
                profile=args.profile,
                live_review=False,
                output=args.output,
            )
        return _run_review(args)
    except (IngestError, ProviderError, SchemaError, ValueError) as exc:
        print(f"content-review: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
