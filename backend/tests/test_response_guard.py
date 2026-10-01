from app.agent.response_guard import (
    categorical_claim_lines,
    enforce_explicit_source_restriction,
    explicit_source_restriction,
    source_restriction_instruction,
)


def test_detects_explicit_unsourced_claim_restriction():
    assert explicit_source_restriction(
        "Không đưa ra con số hay khẳng định khoa học cụ thể nếu không có nguồn."
    )
    assert not explicit_source_restriction("So sánh hai cách học giúp tôi.")
    instruction = source_restriction_instruction(
        "Không đưa ra khẳng định khoa học nếu không có nguồn."
    )
    assert "chỉ mô tả thao tác có thể quan sát" in instruction
    assert "bỏ hẳn tiêu chí không có bằng chứng" in instruction
    assert source_restriction_instruction("So sánh hai cách học giúp tôi.") == ""


def test_fail_closed_guard_omits_uncited_claims_without_placeholder_noise():
    answer = """### So sánh
| Tiêu chí | Flashcard | Đọc lại |
|---|---|---|
| Ghi nhớ dài hạn | Cao, bền vững | Thấp, dễ quên nhanh |
| Cách dùng | Tự kiểm tra | Đọc để xem lại cấu trúc |

- Ưu điểm: Hiệu quả cao trong việc chống lại hiện tượng quên.
- Có thể thử cả hai cách và tự theo dõi kết quả.
"""

    guarded, affected = enforce_explicit_source_restriction(
        "Không đưa khẳng định khoa học nếu không có nguồn.",
        answer,
        has_citations=False,
    )

    assert affected == 2
    assert categorical_claim_lines(guarded) == []
    assert "| Cách dùng |" in guarded
    assert "| Ghi nhớ dài hạn |" not in guarded
    assert "- Ưu điểm:" not in guarded
    assert "Có thể thử cả hai cách" in guarded
    assert "đã lược bỏ" in guarded
    assert "Chưa kết luận" not in guarded


def test_guard_requires_inline_citation_instead_of_any_citation_elsewhere():
    answer = "| Chi phí | Cao | Thấp |\n\nNguồn tham khảo [1]"

    guarded, affected = enforce_explicit_source_restriction(
        "Không đưa khẳng định nếu không có nguồn.", answer, has_citations=True
    )
    assert affected == 1
    assert "| Chi phí |" not in guarded


def test_guard_preserves_risky_line_with_inline_server_citation():
    answer = "| Ghi nhớ | Cao [1] | Thấp [1] |"

    assert enforce_explicit_source_restriction(
        "Không đưa khẳng định nếu không có nguồn.", answer, has_citations=True
    ) == (answer, 0)


def test_guard_does_not_rewrite_unrestricted_answers():
    answer = "| Chi phí | Cao | Thấp |"

    assert enforce_explicit_source_restriction(
        "Hãy so sánh chi phí.", answer, has_citations=False
    ) == (answer, 0)


def test_live_flashcard_regression_redacts_scientific_claims_and_keeps_sections():
    answer = """### Bảng so sánh
| Tiêu chí | Flashcard | Đọc lại ghi chú |
|---|---|---|
| Bản chất | Truy xuất chủ động kết hợp lặp lại ngắt quãng. | Tiếp thu thụ động. |
| Mức độ tương tác | Buộc não bộ phải tự tái tạo thông tin. | Dễ dẫn đến nhận diện mặt chữ. |

### Trade-off
- Ưu điểm: Giúp nhận diện nhanh các lỗ hổng và tối ưu hóa thời gian ôn tập.
- Nhược điểm: Tốn thời gian chuẩn bị bộ thẻ.

### Khuyến nghị
Nếu tự diễn giải được, phương pháp có thể phát huy tác dụng.
"""

    guarded, affected = enforce_explicit_source_restriction(
        "Không đưa ra con số hay khẳng định khoa học cụ thể nếu không có nguồn.",
        answer,
        has_citations=False,
    )

    assert affected == 4
    assert categorical_claim_lines(guarded) == []
    assert "| Bản chất |" not in guarded
    assert "| Mức độ tương tác |" not in guarded
    assert "- Ưu điểm:" not in guarded
    assert "- Nhược điểm: Tốn thời gian chuẩn bị bộ thẻ." in guarded
    assert "### Khuyến nghị" in guarded
    assert "Chưa kết luận" not in guarded


def test_guard_preserves_action_before_unsupported_effect_clause():
    answer = """- Đọc lại ghi chú và gạch chân ý chính để củng cố khả năng ghi nhớ.
- Nhược điểm: Có thêm bước tạo thẻ; dễ làm đứt gãy bối cảnh.
- Tự trả lời trước khi lật thẻ để rèn luyện khả năng gợi nhớ.
"""

    guarded, affected = enforce_explicit_source_restriction(
        "Không đưa khẳng định khoa học nếu không có nguồn.",
        answer,
        has_citations=False,
    )

    assert affected == 3
    assert "- Đọc lại ghi chú và gạch chân ý chính." in guarded
    assert "- Nhược điểm: Có thêm bước tạo thẻ." in guarded
    assert "- Tự trả lời trước khi lật thẻ." in guarded
    assert categorical_claim_lines(guarded) == []


def test_guard_does_not_erase_generic_helpful_operational_guidance():
    answer = """- Cách làm này giúp chia lịch học thành từng buổi nhỏ.
- Bảng theo dõi hỗ trợ bạn đánh dấu phần đã hoàn thành.
| Cách thực hiện | Viết câu hỏi ở mặt trước | Đọc lại ghi chú theo đề mục |
"""

    assert enforce_explicit_source_restriction(
        "Không đưa khẳng định khoa học nếu không có nguồn.",
        answer,
        has_citations=False,
    ) == (answer, 0)
