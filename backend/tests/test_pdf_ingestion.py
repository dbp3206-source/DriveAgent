import json
from types import SimpleNamespace

import pytest

from app.services.pdf_ingestion import (
    PageExtraction,
    extract_page,
    native_page_text,
    parse_ocr_tsv,
    table_markdown,
)


def test_page_markers_and_low_confidence_not_indexed():
    assert PageExtraction(12, "text", "Verified text").markdown().startswith("<!-- page:12 -->")
    assert PageExtraction(2, "low_confidence", "uncertain 123", 20).markdown() == ""
    assert not PageExtraction(3, "needs_ocr", "tiny").indexable
    assert not PageExtraction(4, "text", "").indexable
    assert "đối chiếu ảnh gốc" in PageExtraction(5, "ocr", "recognized 100", 90).markdown()


def test_table_escapes_pipes_and_pads_rows():
    text = table_markdown([["Hạng mục", "Giá"], ["A|B", 120], ["Chưa có"]])
    assert "A\\|B" in text and "120" in text
    assert "| Chưa có |  |" in text


def test_tsv_ignores_nonwords_and_weights_confidence():
    raw = ("level\tblock_num\tpar_num\tline_num\tconf\ttext\n"
           "1\t0\t0\t0\t-1\tpage\n5\t1\t1\t1\t90\tViệt\n"
           "5\t1\t1\t1\t80\tNam\n5\t1\t1\t2\tbad\t?\n")
    text, confidence = parse_ocr_tsv(raw)
    assert text == "Việt Nam\n?"
    assert confidence == 75


def test_nonfinite_ocr_confidence_is_never_trusted():
    raw = "level\tblock_num\tpar_num\tline_num\tconf\ttext\n5\t1\t1\t1\tnan\t123\n"
    assert parse_ocr_tsv(raw) == ("123", 0)


def test_literal_quote_does_not_swallow_subsequent_tsv_records():
    raw = ("level\tblock_num\tpar_num\tline_num\tconf\ttext\n"
           '5\t1\t1\t1\t90\t"\n5\t1\t1\t1\t90\tVerified\n'
           '5\t1\t1\t1\t90\t"\n')
    assert parse_ocr_tsv(raw) == ('" Verified "', 90)


def test_historical_pdf_ocr_is_quarantined_without_deleting_source():
    from app.services.local_sources import excluded_ocr_source

    source = SimpleNamespace(name="scan.pdf",
                             content="<!-- page:1 -->\nVăn bản OCR: cần đối chiếu ảnh gốc "
                                     "khi sử dụng số liệu.\nHistorical data")
    assert excluded_ocr_source(source, SimpleNamespace(pdf_ocr_enabled=False))
    assert not excluded_ocr_source(source, SimpleNamespace(pdf_ocr_enabled=True))
    assert "Historical data" in source.content
    source.content = "<!-- page:1 -->\nNative text only"
    assert not excluded_ocr_source(source, SimpleNamespace(pdf_ocr_enabled=False))


def test_native_text_and_table_share_original_page(monkeypatch, tmp_path):
    page = SimpleNamespace(extract_text=lambda **kwargs: "Native document " * 8,
                           extract_tables=lambda: [[["Metric", "Value"], ["Revenue", "100"]]])

    class Pdf:
        pages = [page]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("pdfplumber.open", lambda _path: Pdf())
    result = extract_page(tmp_path / "source.pdf", 1)
    assert result.status == "text" and "Revenue" in result.text
    assert "<!-- page:1 -->" in result.markdown()
    assert extract_page(tmp_path / "source.pdf", 0).error_code == "page_out_of_range"
    assert json.loads(json.dumps(result.__dict__))["page"] == 1


def test_empty_page_does_not_become_success_without_ocr(monkeypatch, tmp_path):
    class Pdf:
        pages = [SimpleNamespace(extract_text=lambda **kwargs: "", extract_tables=lambda: [])]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("pdfplumber.open", lambda _path: Pdf())
    result = extract_page(tmp_path / "source.pdf", 1,
                          tesseract=str(tmp_path / "missing"), pdftoppm=str(tmp_path / "missing"))
    assert result.status == "needs_ocr" and not result.indexable
    monkeypatch.setattr("app.services.pdf_ingestion._binary",
                        lambda *_args: pytest.fail("Excluded OCR must not inspect binaries"))
    excluded = extract_page(tmp_path / "source.pdf", 1, ocr_enabled=False)
    assert excluded.status == "unsupported_scan" and not excluded.indexable
    assert excluded.error_code == "pdf_ocr_excluded"


def test_language_only_tessdata_uses_renderer_flag_and_rejects_plain_text(monkeypatch, tmp_path):
    class Pdf:
        pages = [SimpleNamespace(extract_text=lambda **kwargs: "", extract_tables=lambda: [])]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("pdfplumber.open", lambda _path: Pdf())
    monkeypatch.setattr("app.services.pdf_ingestion._binary", lambda *_args: "binary")
    calls = []
    output = [b"plain text instead of TSV"]

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout=output[0])

    monkeypatch.setattr("app.services.pdf_ingestion.subprocess.run", run)
    result = extract_page(tmp_path / "scan.pdf", 1, tessdata=str(tmp_path))
    assert result.error_code == "ocr_invalid_output" and not result.indexable
    assert calls[-1][-2:] == ["-c", "tessedit_create_tsv=1"]
    assert "tsv" not in calls[-1]
    output[0] = (b"level\tpage_num\tblock_num\tpar_num\tline_num\tconf\ttext\n"
                 b"5\t1\t1\t1\t1\t95\tVerified\n")
    result = extract_page(tmp_path / "scan.pdf", 1, tessdata=str(tmp_path))
    assert result.status == "ocr" and result.text == "Verified" and result.confidence == 95


def test_real_two_column_pdf_keeps_reading_order(tmp_path):
    import pdfplumber
    from reportlab.pdfgen.canvas import Canvas

    path = tmp_path / "columns.pdf"
    canvas = Canvas(str(path), pagesize=(600, 800))
    canvas.setFont("Helvetica", 10)
    for row in range(16):
        canvas.drawString(25, 750 - row * 18, f"LEFT{row:02} evidence belongs to left column only")
        canvas.drawString(330, 750 - row * 18, f"RIGHT{row:02} evidence belongs to right column")
    canvas.save()
    with pdfplumber.open(path) as pdf:
        text = native_page_text(pdf.pages[0], has_tables=False)
        assert text.index("LEFT15") < text.index("RIGHT00")
        table_text = native_page_text(pdf.pages[0], has_tables=True)
        assert table_text.index("RIGHT00") < table_text.index("LEFT15")


def test_single_column_pdf_is_not_split(tmp_path):
    import pdfplumber
    from reportlab.pdfgen.canvas import Canvas

    path = tmp_path / "single.pdf"
    canvas = Canvas(str(path), pagesize=(600, 800))
    for row in range(16):
        canvas.drawString(25, 750 - row * 18,
                          f"ROW{row:02} single paragraph spans the middle of this page reliably")
    canvas.save()
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[0]
        assert native_page_text(page, has_tables=False) == page.extract_text(layout=False)


def test_prominent_lines_keep_cover_title_separate_from_column_labels(tmp_path):
    import pdfplumber
    from reportlab.pdfgen.canvas import Canvas

    from app.services.pdf_ingestion import prominent_text_lines

    path = tmp_path / "cover.pdf"
    canvas = Canvas(str(path), pagesize=(600, 800))
    canvas.setFont("Helvetica", 32)
    canvas.drawString(50, 700, "Quarterly review")
    canvas.drawString(50, 650, "Outlook and priorities")
    canvas.setFont("Helvetica", 10)
    canvas.drawString(50, 550, "Current events and details unrelated to the report title")
    canvas.drawString(50, 520, "Department one")
    canvas.drawString(330, 520, "Department two")
    canvas.save()
    with pdfplumber.open(path) as pdf:
        lines = prominent_text_lines(pdf.pages[0])
        assert "- Quarterly review\n- Outlook and priorities" in lines
        assert "Department" not in lines
        assert "không tự xác định" in lines
    result = extract_page(path, 1, ocr_enabled=False)
    assert "Department one" in result.text
    assert lines in result.text
