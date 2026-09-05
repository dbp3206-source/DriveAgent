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
