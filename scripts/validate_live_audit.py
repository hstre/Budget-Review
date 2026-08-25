"""Conservative live smoke assertion: structure exists, never assert truth."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    path = Path(sys.argv[1])
    dossier = json.loads(path.read_text(encoding="utf-8"))
    claims = dossier["semantic"]["claims"]
    if len(claims) < 10:
        print(f"live extraction admitted only {len(claims)} claims", file=sys.stderr)
        return 1
    if any(not claim["raw_span"] for claim in claims):
        print("live extraction contains an empty source span", file=sys.stderr)
        return 1
    html_path = path.with_name("dossier.html")
    if not html_path.is_file():
        print("live review did not create dossier.html", file=sys.stderr)
        return 1
    html = html_path.read_text(encoding="utf-8")
    if "Prüferdossier" not in html or "Prüfpunkte" not in html:
        print("live HTML dossier is incomplete", file=sys.stderr)
        return 1
    print(
        f"live audit valid: {len(claims)} admitted claims, "
        f"{len(dossier['semantic']['relations'])} relations"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
