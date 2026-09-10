import json

import pytest

from app.agent.creation import WireAnswer


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        "null",
        "[]",
        '{"title":"Missing blocks"}',
        '{"title":"Bad","blocks":[{"text":"A"}],"execute_shell":"bad"}',
    ],
)
def test_shallow_envelope_never_bypasses_domain_validation(payload):
    envelope = WireAnswer(answer="Preview", proposals=[{"kind": "document", "spec_json": payload}])
    with pytest.raises(ValueError):
        envelope.validate_artifacts()


def test_provider_schema_stays_shallow_without_refs():
    schema = WireAnswer.provider_schema()
    encoded = json.dumps(schema)
    assert "$ref" not in encoded and "$defs" not in encoded
    assert "anyOf" not in encoded
    assert schema["additionalProperties"] is False
    assert schema["properties"]["proposals"]["maxItems"] == 4


def test_bundle_validates_presentation_and_visual_specs():
    envelope = WireAnswer(
        answer="Hai bản xem trước",
        proposals=[
            {
                "kind": "presentation",
                "spec_json": json.dumps(
                    {"title": "RAG", "slides": [{"title": "Mở đầu", "bullets": ["Ý chính"]}]}
                ),
            },
            {
                "kind": "visual",
                "spec_json": json.dumps(
                    {
                        "type": "flowchart",
                        "title": "Luồng RAG",
                        "sections": [{"title": "Tìm", "body": "Truy xuất"}],
                    }
                ),
            },
        ],
    ).validate_artifacts()
    assert [item.kind for item in envelope.proposals] == ["presentation", "visual"]


@pytest.mark.parametrize(
    "kind,spec",
    [
        (
            "document_edit",
            {"document_id": "document123", "old_text": "Cũ", "new_text": "Mới"},
        ),
        (
            "spreadsheet_edit",
            {
                "spreadsheet_id": "spreadsheet123",
                "sheet_title": "Data",
                "range_a1": "A1:B1",
                "new_values": [["Mới", 2]],
            },
        ),
        (
            "presentation_edit",
            {
                "presentation_id": "presentation123",
                "replacements": [{"old_text": "Cũ", "new_text": "Mới"}],
            },
        ),
    ],
)
def test_edit_proposals_are_typed_and_bounded(kind, spec):
    answer = WireAnswer(
        answer="Bản sửa để bạn kiểm tra",
        proposals=[{"kind": kind, "spec_json": json.dumps(spec)}],
    ).validate_artifacts()
    assert answer.proposals[0].kind == kind
