"""End-to-end orchestration with explicit offline and live boundaries."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .anti_delphi import review_claim_graph
from .gate import govern_packet
from .ingest import SourceBundle
from .models import ReviewDossier, SemanticPacket
from .profiles import get_profile
from .provider import DeepSeekProvider, ProviderError
from .render import render_html, render_markdown


@dataclass
class ReviewPipeline:
    provider: DeepSeekProvider | None = None
    extraction_model: str = "deepseek-v4-flash"
    profile: str = "general"

    def run(
        self,
        source: SourceBundle,
        *,
        packet: SemanticPacket | None = None,
        live_review: bool = False,
    ) -> ReviewDossier:
        selected = get_profile(self.profile)
        if packet is None:
            if self.provider is None:
                raise ProviderError(
                    "offline mode requires --packet; live extraction requires DeepSeek"
                )
            packet = self.provider.extract(
                source.document_id,
                source.text,
                model=self.extraction_model,
                profile=selected.name,
            )
        if packet.document_id != source.document_id:
            raise ValueError(
                f"packet document_id {packet.document_id!r} does not match {source.document_id!r}"
            )
        semantic = govern_packet(source.text, packet)
        return review_claim_graph(
            semantic,
            provider=self.provider if live_review else None,
            profile=selected,
        )

    @staticmethod
    def write(dossier: ReviewDossier, output_dir: Path) -> tuple[Path, Path, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "dossier.json"
        markdown_path = output_dir / "dossier.md"
        html_path = output_dir / "dossier.html"
        json_path.write_text(
            json.dumps(dossier.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        markdown_path.write_text(render_markdown(dossier), encoding="utf-8")
        html_path.write_text(render_html(dossier), encoding="utf-8")
        return json_path, markdown_path, html_path


def load_packet(path: Path) -> SemanticPacket:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read semantic packet: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError("semantic packet JSON root must be an object")
    return SemanticPacket.from_dict(data)


__all__ = ["ReviewPipeline", "load_packet"]
