from app.services.chunking import chunk_document


def test_chunking_keeps_content_and_overlap() -> None:
    text = "# Tiêu đề\n\n" + ("Đây là một câu có ý nghĩa. " * 120)

    chunks = chunk_document(text, "text/markdown")

    assert len(chunks) >= 2
    assert chunks[0].index == 0
    assert all(chunk.content.strip() for chunk in chunks)
    assert all(len(chunk.content) <= 1800 for chunk in chunks)


def test_empty_document_has_no_chunks() -> None:
    assert chunk_document(" \n\n ", "text/plain") == []


def test_markdown_table_with_spaced_delimiter_repeats_header() -> None:
    text = "| Mục | Số tiền |\n| --- | ---: |\n" + "\n".join(
        f"| Dòng {index} | {index} |" for index in range(120)
    )
    chunks = chunk_document(text, "text/markdown")
    assert len(chunks) >= 2
    assert all("| Mục | Số tiền |" in chunk.content for chunk in chunks)


def test_pdf_page_markers_keep_evidence_on_one_page() -> None:
    text = (
        "<!-- page:1 -->\n\n"
        "# Trang đầu\n\nMã bằng chứng A.\n\n"
        "<!-- page:2 -->\n\n"
        "# Trang sau\n\nMã bằng chứng B."
    )

    chunks = chunk_document(text, "application/pdf")

    assert [chunk.page_number for chunk in chunks] == [1, 2]
    assert "bằng chứng B" not in chunks[0].content
    assert "bằng chứng A" not in chunks[1].content


def test_pdf_image_noise_is_not_embedded_but_descriptive_alt_text_survives() -> None:
    chunks = chunk_document(
        "<!-- page:6 -->\n\n"
        "![](/api/drive/files/f/assets/image-001.png)\n\n"
        "![Biểu đồ tăng trưởng doanh thu](/api/drive/files/f/assets/chart.png)\n\n"
        "Doanh thu tăng 12%.",
        "application/pdf",
    )

    assert len(chunks) == 1
    assert "image-001" not in chunks[0].content
    assert "Hình: Biểu đồ tăng trưởng doanh thu" in chunks[0].content
    assert "Doanh thu tăng 12%." in chunks[0].content


def test_legacy_pdf_asset_inventory_is_never_embedded() -> None:
    chunks = chunk_document(
        "<!-- page:2 -->\n\nNội dung thật.\n\n"
        "<!-- DriveAgent assets: image-001.png, image-002.png -->",
        "application/pdf",
    )

    assert len(chunks) == 1
    assert chunks[0].content == "Nội dung thật."
