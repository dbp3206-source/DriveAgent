import json
from types import SimpleNamespace

import pytest

from app.services.local_sources import extract_text
from app.tools.contracts import ToolError


def test_notebook_reads_source_not_outputs_or_executes():
    data = {
        "cells": [
            {
                "cell_type": "code",
                "source": ["print('hello')"],
                "outputs": [{"text": "DO NOT INCLUDE"}],
            }
        ]
    }
    text = extract_text("test.ipynb", json.dumps(data).encode())
    assert text == "print('hello')"
    assert "DO NOT INCLUDE" not in text


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("test.exe", b"MZ"),
        ("test.txt", b"\xff"),
        ("test.txt", b"\x00"),
        ("test.ipynb", b"[]"),
        ("test.txt", b""),
        ("test.txt", b"a" * 100001),
        ("test.txt", b"a" * 2000001),
    ],
    ids=[
        "unsupported",
        "non_utf8",
        "binary",
        "invalid_notebook",
        "empty",
        "text_limit",
        "size_limit",
    ],
)
def test_invalid_imports(name, data):
    with pytest.raises(ToolError):
        extract_text(name, data)


def test_utf8_bom_and_formula_are_inert_text():
    assert extract_text("test.md", b"\xef\xbb\xbfhello") == "hello"
    assert extract_text("test.csv", b"name,value\nx,=1+1") == "name,value\nx,=1+1"


async def test_query_read_reaches_later_pdf_page_without_embedding():
    from app.services.local_sources import LocalReadInput, read_local

    row = SimpleNamespace(id="source-a", name="sample.pdf", content_hash="native-hash",
                          content="<!-- page:1 -->\nIntroduction.\n\n"
                          "<!-- page:2 -->\nLoan growth risk and capital adequacy.")

    class Database:
        async def scalar(self, query):
            parameters = query.compile().params
            assert "owner-a" in parameters.values()
            assert "source-a" in parameters.values()
            return row

    context = SimpleNamespace(db=Database(), user=SimpleNamespace(id="owner-a"),
                              settings=SimpleNamespace(pdf_ocr_enabled=False,
                                                       public_base_url="http://localhost:8000"))
    result = await read_local(LocalReadInput(source_id="source-a", query="capital risk", limit=1),
                              context)
    assert result.data["citations"][0]["page_number"] == 2
    assert "capital adequacy" in result.data["text"]


async def test_exact_pdf_page_overrides_keyword_ranking_and_preserves_citation():
    from app.services.local_sources import LocalReadInput, read_local

    row = SimpleNamespace(
        id="source-a", name="sample.pdf", content_hash="native-hash",
        content="<!-- page:1 -->\nPublished 04/05/2026.\n"
        "<!-- page:3 -->\nNguồn: cậpnhậttới29/4/2026\n"
        "<!-- page:6 -->\nUpdated data keyword match.\n",
    )

    class Database:
        async def scalar(self, query):
            assert "owner-a" in query.compile().params.values()
            return row

    context = SimpleNamespace(
        db=Database(), user=SimpleNamespace(id="owner-a"),
        settings=SimpleNamespace(pdf_ocr_enabled=False, public_base_url="http://localhost:8000"),
    )
    result = await read_local(
        LocalReadInput(source_id="source-a", page_number=3, query="Updated data"), context
    )
    assert result.data["retrieval_method"] == "exact_page"
    assert result.data["citations"][0]["page_number"] == 3
    assert "29/4/2026" in result.data["text"]
    assert "keyword match" not in result.data["text"]
    assert result.data["next_offset"] is None
    with pytest.raises(ToolError) as error:
        await read_local(LocalReadInput(source_id="source-a", page_number=2), context)
    assert error.value.code == "source_page_not_found"

    row.content = "<!-- page:3 -->" + "x" * 12001 + "<!-- page:4 -->other"
    first = await read_local(LocalReadInput(source_id="source-a", page_number=3), context)
    assert len(first.data["text"]) == 12000
    assert first.data["next_offset"] == 12000
    rest = await read_local(
        LocalReadInput(source_id="source-a", page_number=3, offset=12000), context
    )
    assert rest.data["text"] == "x"
    assert rest.data["next_offset"] is None


async def test_search_preview_keeps_its_real_page_and_does_not_cross_pages():
    from app.services.local_sources import LocalSearchInput, search_local

    row = SimpleNamespace(
        id="source-a", name="sample.pdf", created_at=1,
        content="<!-- page:1 -->\nPublished 04/05/2026.\n"
        "<!-- page:3 -->\nNguồn cậpnhậttới29/4/2026\n"
        "<!-- page:4 -->\nUnrelated page.\n",
    )

    class Database:
        async def scalars(self, query):
            assert "owner-a" in query.compile().params.values()
            return [row]

    context = SimpleNamespace(
        db=Database(), user=SimpleNamespace(id="owner-a"),
        settings=SimpleNamespace(pdf_ocr_enabled=False, public_base_url="http://localhost:8000"),
    )
    result = await search_local(LocalSearchInput(query="sample.pdf"), context)
    assert result.data["sources"][0]["page_number"] == 1
    assert "29/4/2026" not in result.data["sources"][0]["snippet"]
    result = await search_local(LocalSearchInput(query="29/4/2026"), context)
    source = result.data["sources"][0]
    assert source["page_number"] == 3
    assert source["offset"] == row.content.index("<!-- page:3 -->")
    assert "04/05/2026" not in source["snippet"]
    assert "Unrelated" not in source["snippet"]

    row.content = "Plain text without page markers."
    result = await search_local(LocalSearchInput(query="sample.pdf"), context)
    assert result.data["sources"][0]["page_number"] is None
