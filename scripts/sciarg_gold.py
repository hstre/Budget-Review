"""Build a recall reference from Sci-Arg, argument-annotated scientific papers.

Everything this branch measured comes from one legal corpus and, for the last
several experiments, from one court decision. A finding that only holds there is
a property of that document, which is the mistake the prompt work already made
once. Sci-Arg is the counterweight: forty full computer-graphics papers, in
brat standoff format, annotated with background_claim, own_claim and data —
Lauscher, Glavaš and Ponzetto, "An Argument-Annotated Corpus of Scientific
Publications" (5th Workshop on Argument Mining, 2018), layered onto the Dr.
Inventor corpus of Fisas, Ronzano and Saggion (LREC 2016).

Two differences from the ECHR reference change what can be measured. The
documents are two to six times longer, 21k to 63k characters, which is past the
truncation point at the default output budget and therefore only reachable with
a raised one. And the annotation is far denser: 183 to 559 spans per paper
against 24 in the decision this branch has been tuning on, so a run-to-run
difference of a few spans is a percentage point here instead of seventeen.

The corpus is fetched at run time and never vendored, as with every external
reference here. Its mirror states no licence, so it is treated as measurement
input only.

Scope: the same rule as the legal reference. The region from the first to the
last annotated span is the document, and the spans are re-based onto it, which
drops the title page and the bibliography the annotators did not treat. A span
the file cannot quote back — a discontinuous annotation, or one whose offsets
disagree with its text — is dropped and counted rather than repaired, since
guessing what was meant would put text into the gold answer that nobody
annotated.

Usage:
    sciarg_gold.py <compiled_corpus-directory> <paper-id> <output-directory>
    sciarg_gold.py <compiled_corpus-directory> --list
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

COMPONENTS = ("background_claim", "own_claim", "data")


def read_paper(text_path: Path) -> tuple[str, list[tuple[int, int, str]], int]:
    """The paper text, its component spans, and the number of unusable ones."""
    text = text_path.read_text(encoding="utf-8")
    if any(ord(character) > 0xFFFF for character in text):
        raise ValueError(f"{text_path.name}: non-BMP character, offsets would not line up")
    spans: list[tuple[int, int, str]] = []
    dropped = 0
    for line in text_path.with_suffix(".ann").read_text(encoding="utf-8").splitlines():
        if not line.startswith("T"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            dropped += 1
            continue
        middle, quoted = parts[1], parts[2]
        label = middle.split(" ")[0]
        if label not in COMPONENTS:
            continue
        if ";" in middle:
            # A discontinuous annotation has no single span to anchor against.
            dropped += 1
            continue
        begin, end = int(middle.split(" ")[1]), int(middle.split(" ")[2])
        if text[begin:end] != quoted:
            dropped += 1
            continue
        spans.append((begin, end, label))
    spans.sort()
    return text, spans, dropped


def build(corpus: Path, paper_id: str, out_dir: Path) -> None:
    text_path = corpus / f"{paper_id}.txt"
    if not text_path.is_file():
        raise SystemExit(f"{paper_id}: not in the corpus")
    text, spans, dropped = read_paper(text_path)
    if not spans:
        raise SystemExit(f"{paper_id}: no gold spans")
    low, high = spans[0][0], spans[-1][1]
    region = text[low:high]

    claims = []
    for index, (begin, end, label) in enumerate(spans, start=1):
        raw = text[begin:end]
        # The re-based span must quote the same characters, or recall would be
        # measured against text the document does not contain.
        assert region[begin - low : end - low] == raw
        claims.append(
            {
                "proposal_id": f"G{index:03d}",
                "raw_span": raw,
                "begin": begin - low,
                "end": end - low,
                "argument_type": label,
            }
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{paper_id}.txt").write_text(region, encoding="utf-8")
    (out_dir / f"{paper_id}.gold.json").write_text(
        json.dumps({"document_id": paper_id, "claims": claims}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    annotated = sum(claim["end"] - claim["begin"] for claim in claims)
    print(
        f"{paper_id}: {len(region)} Zeichen, {len(claims)} Gold-Spannen, "
        f"{annotated / len(region):.3f} der Region annotiert"
        + (f", {dropped} unbrauchbare Annotationen verworfen" if dropped else "")
    )


def catalogue(corpus: Path) -> None:
    """List papers by region size, so a document can be picked by length."""
    for text_path in sorted(corpus.glob("*.txt")):
        try:
            _, spans, dropped = read_paper(text_path)
        except ValueError as error:
            print(f"{text_path.stem}\t{error}")
            continue
        if not spans:
            print(f"{text_path.stem}\tempty")
            continue
        region = spans[-1][1] - spans[0][0]
        annotated = sum(end - begin for begin, end, _ in spans)
        print(
            f"{text_path.stem}\tregion={region}\tspans={len(spans)}\t"
            f"density={annotated / region:.3f}\tdropped={dropped}"
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
