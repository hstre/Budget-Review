from __future__ import annotations

import zipfile

import pytest

from budget_review.ingest import IngestError, ingest, read_source


def test_single_text_is_not_wrapped(tmp_path) -> None:
    source = tmp_path / "proposal.md"
    source.write_text("Exact source span.", encoding="utf-8")
    bundle = ingest([source])
    assert bundle.text == "Exact source span."
    assert bundle.document_id == "proposal"


def test_multiple_sources_have_visible_boundaries(tmp_path) -> None:
    proposal = tmp_path / "proposal.md"
    budget = tmp_path / "budget.csv"
    proposal.write_text("Target: 10 people.", encoding="utf-8")
    budget.write_text("Item,EUR\nStaff,1000\n", encoding="utf-8")
    bundle = ingest([proposal, budget])
    assert "[[SOURCE: proposal.md]]" in bundle.text
    assert "[[SOURCE: budget.csv]]" in bundle.text
    assert "A2=Staff" in bundle.text
    assert "B2=1000" in bundle.text


def test_minimal_docx_is_read(tmp_path) -> None:
    path = tmp_path / "proposal.docx"
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>Budget claim</w:t></w:r></w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    assert read_source(path) == "Budget claim"


def test_unsupported_format_fails(tmp_path) -> None:
    path = tmp_path / "proposal.pages"
    path.write_text("text", encoding="utf-8")
    with pytest.raises(IngestError, match="unsupported"):
        ingest([path])


def test_missing_input_fails(tmp_path) -> None:
    with pytest.raises(IngestError, match="does not exist"):
        ingest([tmp_path / "missing.md"])


def _minimal_pdf(*pages: str) -> bytes:
    """A hand-built PDF, so the PDF path is exercised without a fixture binary."""
    objects: list[tuple[int, bytes]] = []
    kids: list[str] = []
    for index, text in enumerate(pages):
        page_id = 3 + index * 2
        stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode("latin-1")
        kids.append(f"{page_id} 0 R")
        objects.append(
            (
                page_id,
                (
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
                    f"/Contents {page_id + 1} 0 R /Resources << /Font << /F1 999 0 R >> >> >>"
                ).encode("latin-1"),
            )
        )
        objects.append(
            (
                page_id + 1,
                b"<< /Length "
                + str(len(stream)).encode()
                + b" >>\nstream\n"
                + stream
                + b"\nendstream",
            )
        )
    objects.append((1, b"<< /Type /Catalog /Pages 2 0 R >>"))
    objects.append(
        (2, ("<< /Type /Pages /Kids [" + " ".join(kids) + f"] /Count {len(pages)} >>").encode())
    )
    objects.append((999, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"))
    objects.sort()

    out = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for number, body in objects:
        offsets[number] = len(out)
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    highest = max(offsets) + 1
    xref_at = len(out)
    out += f"xref\n0 {highest}\n".encode() + b"0000000000 65535 f \n"
    for number in range(1, highest):
        out += (
            f"{offsets[number]:010d} 00000 n \n".encode()
            if number in offsets
            else b"0000000000 65535 f \n"
        )
    out += f"trailer\n<< /Size {highest} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    return bytes(out)


def test_csv_cells_carry_their_coordinates(tmp_path) -> None:
    path = tmp_path / "budget.csv"
    path.write_text("Position,Betrag\nPersonal,60000\n", encoding="utf-8")

    text = read_source(path)

    assert text.splitlines() == ["A1=Position | B1=Betrag", "A2=Personal | B2=60000"]


def test_tsv_uses_the_tab_delimiter(tmp_path) -> None:
    path = tmp_path / "budget.tsv"
    path.write_text("Position\tBetrag\nPersonal\t60000\n", encoding="utf-8")

    assert read_source(path).splitlines()[0] == "A1=Position | B1=Betrag"


def test_a_byte_order_mark_does_not_leak_into_the_first_cell(tmp_path) -> None:
    path = tmp_path / "budget.csv"
    path.write_bytes("Position,Betrag\n".encode("utf-8-sig"))

    assert read_source(path).startswith("A1=Position")


def test_quoted_csv_fields_stay_one_cell(tmp_path) -> None:
    path = tmp_path / "budget.csv"
    path.write_text('Position,Notiz\nPersonal,"erst A, dann B"\n', encoding="utf-8")

    assert 'B2=erst A, dann B' in read_source(path)


def test_column_names_continue_past_z(tmp_path) -> None:
    path = tmp_path / "wide.csv"
    path.write_text(",".join(str(index) for index in range(1, 29)) + "\n", encoding="utf-8")

    cells = read_source(path).split(" | ")

    assert cells[25] == "Z1=26"
    assert cells[26] == "AA1=27"
    assert cells[27] == "AB1=28"


def test_xlsx_sheets_are_labelled_and_empty_cells_dropped(tmp_path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Kosten"
    sheet["A1"] = "Personal"
    sheet["C1"] = 60000
    sheet["A3"] = "Sachmittel"
    workbook.create_sheet("Leer")
    workbook.save(tmp_path / "budget.xlsx")

    text = read_source(tmp_path / "budget.xlsx")

    assert "[SHEET Kosten]" in text
    assert "[SHEET Leer]" in text
    assert "A1=Personal | C1=60000" in text
    assert "A3=Sachmittel" in text
    assert "B1=" not in text, "empty cells must not become empty coordinates"


def test_pdf_pages_are_numbered(tmp_path) -> None:
    pytest.importorskip("pypdf")
    path = tmp_path / "proposal.pdf"
    path.write_bytes(_minimal_pdf("Budget line one", "Budget line two"))

    text = read_source(path)

    assert "[PAGE 1]" in text and "[PAGE 2]" in text
    assert "Budget line one" in text
    assert text.index("[PAGE 1]") < text.index("[PAGE 2]")


def test_suffix_matching_ignores_case(tmp_path) -> None:
    path = tmp_path / "notes.MD"
    path.write_text("A claim.", encoding="utf-8")

    assert read_source(path) == "A claim."


def test_a_corrupt_docx_is_reported_as_such(tmp_path) -> None:
    path = tmp_path / "broken.docx"
    path.write_bytes(b"not a zip archive at all")

    with pytest.raises(IngestError, match="invalid DOCX"):
        read_source(path)


def test_a_whitespace_only_input_is_refused(tmp_path) -> None:
    path = tmp_path / "blank.txt"
    path.write_text("   \n\t\n", encoding="utf-8")

    with pytest.raises(IngestError, match="no extractable text"):
        ingest([path])


def test_the_document_id_is_inferred_from_the_first_file_name(tmp_path) -> None:
    path = tmp_path / "Antrag 2026 (final).md"
    path.write_text("A claim.", encoding="utf-8")

    assert ingest([path]).document_id == "Antrag-2026-final"


def test_an_unusable_file_name_still_yields_a_document_id(tmp_path) -> None:
    path = tmp_path / "###.md"
    path.write_text("A claim.", encoding="utf-8")

    assert ingest([path]).document_id == "document"


def test_an_explicit_document_id_wins_over_the_file_name(tmp_path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("A claim.", encoding="utf-8")

    assert ingest([path], document_id="chosen").document_id == "chosen"


def test_mixed_formats_are_combined_with_visible_boundaries(tmp_path) -> None:
    markdown = tmp_path / "proposal.md"
    markdown.write_text("The programme serves 300 participants.", encoding="utf-8")
    table = tmp_path / "budget.csv"
    table.write_text("Position,Betrag\nPersonal,60000\n", encoding="utf-8")

    bundle = ingest([markdown, table])

    assert "[[SOURCE: proposal.md]]" in bundle.text
    assert "[[SOURCE: budget.csv]]" in bundle.text
    assert "A2=Personal | B2=60000" in bundle.text
    assert bundle.source_files == (str(markdown), str(table))
