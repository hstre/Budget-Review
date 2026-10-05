"""Build a recall reference from the ECHR legal-argument corpus.

The frozen packets pin recall for documents the size of a project proposal —
about 1700 characters. Nothing pins it for a long document, and length is the
one dimension where single-shot extraction is expected to break: the extractor
is asked for a verbatim span per claim, so its output grows with the source
while the output budget does not.

Habernal et al., "Mining Legal Arguments in Court Decisions" (Artificial
Intelligence and Law, 2023), annotate 373 European Court of Human Rights
decisions with argument spans, an actor and an argument type, released under
Apache-2.0 at github.com/trusthlt/mining-legal-arguments. This script reads
those gold files and writes a document plus a gold packet; it vendors nothing.

Scope, which decides whether the number means anything: the corpus annotates
only the Court's legal argumentation, not the facts, the procedure or the
recitation of domestic law that precede it. Measuring over a whole judgment
would measure the annotators' scope rather than the extractor. The region from
the first to the last gold span is what they treated as exhaustive — 94 to 97
per cent of its characters carry an annotation — so that region is the
document, and the spans are re-based onto it.

Usage:
    echr_gold.py <gold_data-directory> <decision-id> <output-directory>
    echr_gold.py <gold_data-directory> --list
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from xml.etree import ElementTree

SOFA = "{http:///uima/cas.ecore}Sofa"
ARGUMENT = "{http:///webanno/custom.ecore}LegalArgumentation"


def read_decision(path: Path) -> tuple[str, list[tuple[int, int, str, str]]] | None:
    """The decision text and its gold spans, or None if the file carries neither."""
    root = ElementTree.parse(path).getroot()
    text = next((element.get("sofaString") for element in root if element.tag == SOFA), None)
    if text is None:
        return None
    # UIMA counts offsets in UTF-16 code units and Python in code points, so a
    # single character outside the BMP would silently shift every later span.
    if any(ord(character) > 0xFFFF for character in text):
        raise ValueError(f"{path.name}: non-BMP character, offsets would not line up")

    spans = sorted(
        (
            int(element.get("begin")),
            int(element.get("end")),
            element.get("Akteur") or "",
            element.get("ArgType") or "",
        )
        for element in root
        if element.tag == ARGUMENT
    )
    return (text, spans) if spans else None


def build(gold_data: Path, decision_id: str, out_dir: Path) -> None:
    parsed = read_decision(gold_data / f"{decision_id}.xmi")
    if parsed is None:
        raise SystemExit(f"{decision_id}: no gold spans")
    text, spans = parsed
    low, high = spans[0][0], spans[-1][1]
    region = text[low:high]

    claims = []
    for index, (begin, end, actor, argument_type) in enumerate(spans, start=1):
        raw = text[begin:end]
        # The re-based span must quote the same characters, or recall would be
        # measured against text the document does not contain.
        assert region[begin - low : end - low] == raw
        claims.append(
            {
                "proposal_id": f"G{index:02d}",
                "raw_span": raw,
                "begin": begin - low,
                "end": end - low,
                "actor": actor,
                "argument_type": argument_type,
            }
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{decision_id}.txt").write_text(region, encoding="utf-8")
    (out_dir / f"{decision_id}.gold.json").write_text(
        json.dumps({"document_id": decision_id, "claims": claims}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    annotated = sum(claim["end"] - claim["begin"] for claim in claims)
    print(
        f"{decision_id}: {len(region)} Zeichen, {len(claims)} Gold-Spannen, "
        f"{annotated / len(region):.3f} der Region annotiert"
    )


def catalogue(gold_data: Path) -> None:
    """List decisions by region size, so a case can be picked by length."""
    for path in sorted(gold_data.glob("*.xmi")):
        parsed = read_decision(path)
        if parsed is None:
            continue
        text, spans = parsed
        low, high = spans[0][0], spans[-1][1]
        region = high - low
        annotated = sum(end - begin for begin, end, _, _ in spans)
        print(
            f"{path.stem}\tregion={region}\tspans={len(spans)}\t"
            f"density={annotated / region:.3f}" if region else f"{path.stem}\tempty"
        )


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[2] == "--list":
        catalogue(Path(sys.argv[1]))
        return 0
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    build(Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
