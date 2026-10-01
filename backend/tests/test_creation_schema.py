import json

import pytest

from app.agent.creation import (
    WireAnswer,
    blank_unsourced_sheet_requested,
    ground_unsourced_spreadsheet_preview,
    preserve_explicit_literals,
)


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


def test_unsourced_sheet_preview_has_blank_input_and_a_real_sum_formula():
    generated = WireAnswer(
        answer="Đã chuẩn bị chi tiêu tháng trước với giao dịch Café 95000.",
        proposals=[
            {
                "kind": "spreadsheet",
                "spec_json": json.dumps(
                    {
                        "title": "Chi tiêu 2023",
                        "tabs": [
                            {
                                "title": "Giao dịch",
                                "headers": ["Nội dung", "So Tien (VND)"],
                                "rows": [["Café", 95000]],
                            }
                        ],
                    }
                ),
            }
        ],
    ).validate_artifacts()
    grounded = ground_unsourced_spreadsheet_preview(
        "Tạo bảng theo dõi chi tiêu.", generated, has_source_data=False
    )
    tab = grounded.proposals[0].spreadsheet.tabs[0]
    assert tab.rows[0] == [None, None]
    assert tab.rows[1][0] == "Tổng"
    assert tab.rows[1][1].function == "SUM"
    assert "2023" not in grounded.proposals[0].spreadsheet.title
    assert "95000" not in grounded.answer
    assert "=SUM(B2:B2)" in grounded.answer
    assert "| Nội dung | So Tien (VND) |\n| --- | --- |" in grounded.answer
    assert "Chưa tạo bảng" in grounded.answer


def test_unsourced_blank_template_discards_malformed_invented_rows_before_validation():
    envelope = WireAnswer(
        answer="Preview",
        proposals=[
            {
                "kind": "spreadsheet",
                "spec_json": json.dumps(
                    {
                        "title": "Theo dõi chi tiêu",
                        "tabs": [
                            {
                                "title": "Giao dịch",
                                "headers": ["Mục", "Số tiền"],
                                "rows": [["Café", 95000], {"PRIVATE_CANARY": 1000}],
                                "chart": {"title": "Sai dữ liệu", "value_column": 1},
                            }
                        ],
                    }
                ),
            }
        ],
    )
    assert blank_unsourced_sheet_requested(
        "Tạo bản xem trước Google Sheets theo dõi chi tiêu.", has_source_data=False
    )
    with pytest.raises(ValueError):
        envelope.validate_artifacts()
    with pytest.raises(ValueError):
        envelope.validate_artifacts(blank_unsourced_sheet=False)
    validated = envelope.validate_artifacts(blank_unsourced_sheet=True)
    assert validated.proposals[0].spreadsheet.tabs[0].rows == [[None, None]]
    grounded = ground_unsourced_spreadsheet_preview(
        "Tạo bản xem trước Google Sheets theo dõi chi tiêu.",
        validated,
        has_source_data=False,
    )
    assert "PRIVATE_CANARY" not in grounded.model_dump_json()
    assert grounded.proposals[0].spreadsheet.tabs[0].chart is None


def test_unsourced_blank_prevalidation_excludes_source_data_and_requested_samples():
    assert not blank_unsourced_sheet_requested("Tạo bảng theo dõi chi tiêu", has_source_data=True)
    assert not blank_unsourced_sheet_requested(
        "Tạo bảng với dữ liệu mẫu", has_source_data=False
    )
    assert not blank_unsourced_sheet_requested(
        "Tạo bảng: ăn trưa 95000 VND", has_source_data=False
    )
    assert not blank_unsourced_sheet_requested(
        "Tạo bảng có khoản Cà phê 95000", has_source_data=False
    )


def test_unsourced_sheet_explicit_sample_is_labelled_not_silently_passed_as_real():
    generated = WireAnswer(
        answer="Có một giao dịch Café 95000.",
        proposals=[
            {
                "kind": "spreadsheet",
                "spec_json": json.dumps(
                    {
                        "title": "Theo dõi chi tiêu",
                        "tabs": [
                            {
                                "title": "Chi tiêu",
                                "headers": ["Nội dung", "Số tiền"],
                                "rows": [["Café", 95000]],
                            }
                        ],
                    }
                ),
            }
        ],
    ).validate_artifacts()
    sample = ground_unsourced_spreadsheet_preview(
        "Cho ví dụ một bảng chi tiêu với dữ liệu mẫu.", generated, has_source_data=False
    )
    assert sample.proposals[0].spreadsheet.tabs[0].rows[0] == ["Café", 95000]
    assert "Dữ liệu minh họa" in sample.proposals[0].spreadsheet.title
    assert "không phải giao dịch thật" in sample.answer
    explicit_sample = ground_unsourced_spreadsheet_preview(
        "Cho ví dụ dữ liệu mẫu: Café 95000 VND.", generated, has_source_data=False
    )
    assert "Dữ liệu minh họa" in explicit_sample.proposals[0].spreadsheet.title
    template = ground_unsourced_spreadsheet_preview(
        "Tạo mẫu theo dõi chi tiêu.", generated, has_source_data=False
    )
    assert template.proposals[0].spreadsheet.tabs[0].rows[0] == [None, None]
    assert "Mẫu trống" in template.proposals[0].spreadsheet.title
    assert (
        ground_unsourced_spreadsheet_preview(
            "Tạo bảng từ nguồn đã chọn.", generated, has_source_data=True
        )
        == generated
    )


def test_bundle_validates_document_and_spreadsheet_specs():
    envelope = WireAnswer(
        answer="Hai bản xem trước",
        proposals=[
            {
                "kind": "document",
                "spec_json": json.dumps(
                    {"title": "RAG", "blocks": [{"text": "Ý chính", "style": "HEADING_1"}]}
                ),
            },
            {
                "kind": "spreadsheet",
                "spec_json": json.dumps(
                    {
                        "title": "Theo dõi RAG",
                        "tabs": [
                            {"title": "Tiến độ", "headers": ["Việc"], "rows": [["Truy xuất"]]}
                        ],
                    }
                ),
            },
        ],
    ).validate_artifacts()
    assert [item.kind for item in envelope.proposals] == ["document", "spreadsheet"]


def test_explicit_quoted_literals_restore_only_equivalent_generated_strings():
    generated = WireAnswer(
        answer="Bản xem trước",
        proposals=[
            {
                "kind": "document",
                "spec_json": json.dumps(
                    {
                        "title": "DriveAgent Production QA",
                        "blocks": [
                            {"text": "Kế hoach nghiệm thu", "style": "HEADING_1"},
                            {"text": "Dối chiếu", "style": "NORMAL_TEXT"},
                            {"text": "Nội dung khác nghĩa", "style": "NORMAL_TEXT"},
                        ],
                    }
                ),
            }
        ],
    ).validate_artifacts()

    restored = preserve_explicit_literals(
        'Tạo file "DriveAgent Production QA" với tiêu đề “Kế hoạch nghiệm thu”, '
        'gồm bước Đối chiếu và mã "DA-1".',
        generated,
    )

    document = restored.proposals[0].document
    assert document.title == "DriveAgent Production QA"
    assert document.blocks[0].text == "Kế hoạch nghiệm thu"
    assert document.blocks[1].text == "Đối chiếu"
    # An absent or semantically different quoted literal is never invented.
    assert document.blocks[2].text == "Nội dung khác nghĩa"


def test_provider_mojibake_is_repaired_from_request_or_rejected():
    def proposal(text: str):
        return WireAnswer(
            answer="Preview",
            proposals=[
                {
                    "kind": "document",
                    "spec_json": json.dumps(
                        {"title": "QA", "blocks": [{"text": text, "style": "NORMAL_TEXT"}]}
                    ),
                }
            ],
        ).validate_artifacts()

    repaired = preserve_explicit_literals(
        "Danh sách gồm Chuẩn bị, Thực hiện, Đối chiếu và trạng thái Đạt.",
        proposal("Thực hi峄噉"),
    )
    assert repaired.proposals[0].document.blocks[0].text == "Thực hiện"

    with pytest.raises(ValueError, match="unrecoverable text encoding"):
        preserve_explicit_literals("Tạo ghi chú bình thường.", proposal("未知岷\ue167"))


def test_real_vietnamese_provider_corruption_is_repaired_across_document_fields():
    generated = WireAnswer(
        answer="Preview",
        proposals=[
            {
                "kind": "document",
                "spec_json": json.dumps(
                    {
                        "title": "QA",
                        "blocks": [
                            {"text": "Kế ho岷ch nghi峄僲 thu", "style": "HEADING_1"},
                            {"text": "Thực hi峄噉", "style": "NORMAL_TEXT"},
                            {
                                "kind": "table",
                                "rows": [
                                    ["H岷1ng mục", "Chủ sở hữu", "Tr岷1ng thái"],
                                    ["Google Drive", "Bảo Phúc", "膽岷1t"],
                                ],
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
            }
        ],
    ).validate_artifacts()
    request = (
        'Tạo Google Docs tên "QA", tiêu đề "Kế hoạch nghiệm thu", gồm bước Thực hiện '
        "và bảng Hạng mục | Chủ sở hữu | Trạng thái, dòng Google Drive | Bảo Phúc | Đạt."
    )

    repaired = preserve_explicit_literals(request, generated).proposals[0].document

    assert repaired.blocks[0].text == "Kế hoạch nghiệm thu"
    assert repaired.blocks[1].text == "Thực hiện"
    assert repaired.blocks[2].rows == [
        ["Hạng mục", "Chủ sở hữu", "Trạng thái"],
        ["Google Drive", "Bảo Phúc", "Đạt"],
    ]


def test_short_spreadsheet_labels_preserve_case_and_repair_unique_one_character_typo():
    generated = WireAnswer(
        answer="Bản xem trước",
        proposals=[
            {
                "kind": "spreadsheet",
                "spec_json": json.dumps(
                    {
                        "title": "DriveAgent Budget QA 2026-09-12",
                        "tabs": [
                            {
                                "title": "Budget",
                                "headers": ["Hạng mục", "Ngân sách", "Thực tế", "Chêh lệch"],
                                "rows": [
                                    ["sách", 500000, 450000, 50000],
                                    ["Đi lại", 300000, 320000, -20000],
                                ],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
            }
        ],
    ).validate_artifacts()
    request = (
        'Tạo Google Sheets tên "DriveAgent Budget QA 2026-09-12" với cột Hạng mục, '
        "Ngân sách, Thực tế, Chênh lệch. Có hai hàng Sách 500000 450000 và Đi lại "
        "300000 320000, thêm hàng Tổng bằng công thức."
    )

    repaired = preserve_explicit_literals(request, generated).proposals[0].spreadsheet

    assert repaired.tabs[0].headers == ["Hạng mục", "Ngân sách", "Thực tế", "Chênh lệch"]
    assert repaired.tabs[0].rows[0][0] == "Sách"
    assert repaired.tabs[0].rows[1][0] == "Đi lại"


def test_short_literal_guard_does_not_rewrite_merely_similar_generated_prose():
    generated = WireAnswer(
        answer="Bản xem trước",
        proposals=[
            {
                "kind": "document",
                "spec_json": json.dumps(
                    {"title": "QA", "blocks": [{"text": "Kế hoạch khác", "style": "NORMAL_TEXT"}]}
                ),
            }
        ],
    ).validate_artifacts()

    repaired = preserve_explicit_literals(
        "Hãy tạo kế hoạch học và phần đánh giá.", generated
    ).proposals[0].document

    assert repaired.blocks[0].text == "Kế hoạch khác"


@pytest.mark.parametrize("kind", ["presentation", "presentation_edit", "visual"])
def test_retired_creative_outputs_are_rejected_at_provider_boundary(kind):
    with pytest.raises(ValueError):
        WireAnswer(answer="Không còn hỗ trợ", proposals=[{"kind": kind, "spec_json": "{}"}])


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
    ],
)
def test_edit_proposals_are_typed_and_bounded(kind, spec):
    answer = WireAnswer(
        answer="Bản sửa để bạn kiểm tra",
        proposals=[{"kind": kind, "spec_json": json.dumps(spec)}],
    ).validate_artifacts()
    assert answer.proposals[0].kind == kind
