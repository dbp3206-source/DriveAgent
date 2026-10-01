from pathlib import Path

from app.services.pdf_parser import _append_text_recovery, parse_pdf_to_markdown


def test_pdf_parser_persists_and_rewrites_image_assets(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import opendataloader_pdf

    source = tmp_path / "fixture.pdf"
    source.write_bytes(b"not-a-real-pdf-for-fake-parser")

    def fake_convert(  # type: ignore[no-untyped-def]
        *, input_path, output_dir, format, markdown_page_separator
    ):
        image_dir = Path(output_dir) / "fixture_images"
        image_dir.mkdir()
        (image_dir / "figure 1.png").write_bytes(b"PNG")
        (Path(output_dir) / "fixture.md").write_text(
            "# Tài liệu\n\n![Sơ đồ](fixture_images/figure 1.png)\n"
            + markdown_page_separator.replace("%page-number%", "1"),
            encoding="utf-8",
        )

    monkeypatch.setattr(opendataloader_pdf, "convert", fake_convert)
    assets = tmp_path / "assets"
    result = parse_pdf_to_markdown(
        source,
        asset_dir=assets,
        asset_base_url="/api/drive/files/file-1/assets",
    )

    assert "/api/drive/files/file-1/assets/image-001.png" in result
    assert (assets / "image-001.png").read_bytes() == b"PNG"
    assert "DriveAgent assets:" not in result
    assert '"image-001.png"' in (assets / "manifest.json").read_text(encoding="utf-8")
    assert "<!-- page:1 -->" in result


def test_pdf_recovery_keeps_page_and_restores_broken_vietnamese_glyphs(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    import pdfplumber

    class FakePage:
        def extract_text(self) -> str:
            return "Tóm tắt đầy đủ các điều khoản chính\nDòng đã có trong nội dung"

    class FakePdf:
        pages = [FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(pdfplumber, "open", lambda _path: FakePdf())
    content = (
        "<!-- page:1 -->\n\n"
        "Tóm tắt đ y đủ các điều khoản chính\nDòng đã có trong nội dung\n\n"
        "<!-- page:2 -->\n\nTrang sau"
    )
    recovered = _append_text_recovery(content, tmp_path / "sample.pdf")

    assert "Tóm tắt đầy đủ các điều khoản chính" in recovered
    assert recovered.count("<!-- page:1 -->") == 1
    assert recovered.index("Tóm tắt đầy đủ các điều khoản chính") < recovered.index(
        "<!-- page:2 -->"
    )
    assert "Văn bản PDF bổ sung" not in recovered
    assert recovered.count("Dòng đã có trong nội dung") == 1
