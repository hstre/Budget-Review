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
