from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.services.document_creator import (
    DocumentCreator,
    DocumentPatchSpec,
    DocumentSpec,
    create_requests,
    utf16_length,
)
from app.tools.contracts import ToolError


def document(text, revision="r1"):
    return {
        "title": "Report",
        "revisionId": revision,
        "tabs": [
            {
                "tabProperties": {"tabId": "tab1"},
                "documentTab": {
                    "body": {
                        "content": [
                            {"sectionBreak": {}, "endIndex": 1},
                            {
                                "startIndex": 1,
                                "paragraph": {"elements": [{"textRun": {"content": text}}]},
                            },
                        ]
                    }
                },
            }
        ],
    }


def table_document(rows, revision="r1"):
    table_rows = []
    table_start = 14
    next_index = table_start + 3
    for row in rows:
        cells = []
        for value in row:
            content = value + "\n"
            end_index = next_index + utf16_length(content)
            paragraph = {
                "startIndex": next_index,
                "endIndex": end_index,
                "paragraph": {
                    "elements": [{
                        "startIndex": next_index,
                        "endIndex": end_index,
                        "textRun": {"content": content},
                    }]
                },
            }
            cells.append({"content": [paragraph]})
            next_index = end_index + 1
        table_rows.append({"tableCells": cells})
        next_index += 1
    table_end = next_index - 1
    return {
        "title": "Report",
        "revisionId": revision,
        "tabs": [
            {
                "tabProperties": {"tabId": "tab1"},
                "documentTab": {
                    "body": {
                        "content": [
                            {"sectionBreak": {}, "startIndex": 0, "endIndex": 1},
                            {
                                "startIndex": 1,
                                "paragraph": {"elements": [{"textRun": {"content": "Report\n"}}]},
                            },
                            {
                                "startIndex": 8,
                                "paragraph": {"elements": [{"textRun": {"content": "Intro\n"}}]},
                            },
                            {
                                "startIndex": table_start,
                                "endIndex": table_end,
                                "table": {"tableRows": table_rows},
                            },
                            {
                                "startIndex": table_end,
                                "paragraph": {"elements": [{"textRun": {"content": "After\n"}}]},
                            },
                        ]
                    }
                },
            }
        ],
    }


class FakeDocs:
    def __init__(self, reads):
        self.reads = iter(reads)
        self.writes = []

    def response(self, value):
        def execute(num_retries):
            assert num_retries == 0
            return value

        return SimpleNamespace(execute=execute)

    def documents(self):
        return self

    def create(self, **kwargs):
        self.writes.append(kwargs)
        return self.response({"documentId": "doc123"})

    def get(self, **kwargs):
        assert kwargs["includeTabsContent"]
        return self.response(next(self.reads))

    def batchUpdate(self, **kwargs):
        self.writes.append(kwargs)
        return self.response({})


def test_create_formats_and_verifies_unicode():
    spec = DocumentSpec(title="Report", blocks=[{"text": "😀 lesson", "style": "HEADING_1"}])
    text, requests = create_requests(spec)
    paragraph_requests = [item for item in requests if "updateParagraphStyle" in item]
    expected_end = 1 + utf16_length(text)
    assert paragraph_requests[-1]["updateParagraphStyle"]["range"]["endIndex"] == expected_end
    fake = FakeDocs([document(text + "\n")])
    saved = []
    result = DocumentCreator(fake).create(spec, saved.append)
    assert saved == ["doc123"] and result["verified"]
    assert len(fake.writes) == 2


def test_create_deduplicates_repeated_title_block():
    spec = DocumentSpec(
        title="Báo cáo quý",
        blocks=[
            {"text": "Báo cáo quý", "style": "HEADING_1"},
            {"text": "Kết luận", "style": "HEADING_1"},
        ],
    )
    text, requests = create_requests(spec)
    assert text == "Báo cáo quý\nKết luận\n"
    paragraphs = [
        item["updateParagraphStyle"]
        for item in requests
        if "updateParagraphStyle" in item
    ]
    assert len(paragraphs) == 2


def test_failed_verification_preserves_created_id():
    fake = FakeDocs([document("unexpected\n")])
    saved = []
    with pytest.raises(ToolError) as failure:
        DocumentCreator(fake).create(
            DocumentSpec(title="Report", blocks=[{"text": "A"}]), saved.append
        )
    assert failure.value.code == "verification_failed"
    assert saved == ["doc123"]


def test_targeted_patch_uses_utf16_and_revision_lock():
    fake = FakeDocs([document("😀 old rest\n"), document("😀 new rest\n", "r2")])
    spec = DocumentPatchSpec(
        document_id="doc123", tab_id="tab1", revision_id="r1", old_text="old", new_text="new"
    )
    assert DocumentCreator(fake).apply_patch(spec)["verified"]
    body = fake.writes[0]["body"]
    assert body["writeControl"] == {"requiredRevisionId": "r1"}
    assert body["requests"][0]["deleteContentRange"]["range"]["startIndex"] == 4


@pytest.mark.parametrize(
    "text,revision,code",
    [
        ("old\n", "r2", "revision_conflict"),
        ("old old\n", "r1", "ambiguous_patch"),
        ("missing\n", "r1", "ambiguous_patch"),
    ],
)
def test_patch_rejected_before_write(text, revision, code):
    fake = FakeDocs([document(text, revision)])
    spec = DocumentPatchSpec(
        document_id="doc123", tab_id="tab1", revision_id="r1", old_text="old", new_text="new"
    )
    with pytest.raises(ToolError) as failure:
        DocumentCreator(fake).apply_patch(spec)
    assert failure.value.code == code
    assert not fake.writes


def test_invalid_specs_reject_controls_and_unknown_fields():
    with pytest.raises(ValidationError):
        DocumentSpec(title="Report", blocks=[{"text": "bad\x00text"}])
    with pytest.raises(ValidationError):
        DocumentSpec(title="Report", blocks=[{"text": "good"}], execute_shell="bad")


def test_document_theme_and_lists_produce_native_formatting_requests():
    spec = DocumentSpec(
        title="Kế hoạch",
        theme="study",
        blocks=[{"text": "Ôn chương 1", "list_style": "numbered"}],
    )
    _, requests = create_requests(spec)
    assert any("updateDocumentStyle" in item for item in requests)
    bullet = next(
        item["createParagraphBullets"]
        for item in requests
        if "createParagraphBullets" in item
    )
    assert bullet["bulletPreset"] == "NUMBERED_DECIMAL_ALPHA_ROMAN"
    text_styles = [item["updateTextStyle"] for item in requests if "updateTextStyle" in item]
    assert text_styles[0]["textStyle"]["weightedFontFamily"]["fontFamily"] == "Arial"


def test_document_table_blocks_are_rectangular_and_bounded():
    spec = DocumentSpec(
        title="Report",
        blocks=[{"kind": "table", "rows": [["Metric", "Value"], ["Hours", "12"]]}],
    )
    assert spec.blocks[0].kind == "table"
    assert spec.blocks[0].rows == [["Metric", "Value"], ["Hours", "12"]]
    with pytest.raises(ValidationError):
        DocumentSpec(title="Report", blocks=[{"kind": "table", "rows": [["A", "B"], ["C"]]}])
    with pytest.raises(ValidationError):
        DocumentSpec(title="Report", blocks=[{"kind": "table", "rows": []}])


def test_create_inserts_fills_and_readback_verifies_native_table():
    empty_table = table_document([["", ""], ["", ""]])
    expected = table_document([["Category", "Amount"], ["Books", "120"]])
    fake = FakeDocs([empty_table, expected])
    saved = []
    result = DocumentCreator(fake).create(
        DocumentSpec(
            title="Report",
            blocks=[
                {"text": "Intro"},
                {"kind": "table", "rows": [["Category", "Amount"], ["Books", "120"]]},
                {"text": "After"},
            ],
        ),
        saved.append,
    )
    assert result["verified"] and saved == ["doc123"]
    writes = [entry for entry in fake.writes if "requests" in entry.get("body", {})]
    requests = [request for write in writes for request in write["body"]["requests"]]
    table_request = next(request["insertTable"] for request in requests if "insertTable" in request)
    assert (table_request["rows"], table_request["columns"]) == (2, 2)
    cell_inserts = [
        request["insertText"]
        for request in requests
        if "insertText" in request
        and "location" in request["insertText"]
        and request["insertText"].get("text") in {"Category", "Amount", "Books", "120"}
    ]
    assert [item["text"] for item in cell_inserts] == ["120", "Books", "Amount", "Category"]
    assert [item["location"]["index"] for item in cell_inserts] == sorted(
        (item["location"]["index"] for item in cell_inserts), reverse=True
    )
