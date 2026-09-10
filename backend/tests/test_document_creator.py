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
    assert requests[-1]["updateParagraphStyle"]["range"]["endIndex"] == 1 + utf16_length(text)
    fake = FakeDocs([document(text + "\n")])
    saved = []
    result = DocumentCreator(fake).create(spec, saved.append)
    assert saved == ["doc123"] and result["verified"]
    assert len(fake.writes) == 2


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
