"""Locked final defects: source limits are not new numerical business facts."""

from datetime import date

import pytest

from app.agent.evidence import bound_web_numeric_claims

TODAY = date(2026, 10, 9)
REQUEST = "Chuẩn bị báo cáo và tin 30 ngày gần đây."
SOURCE = {"evidence_kind": "page_text", "snippet": "Danh mục sản phẩm và thông tin chung."}


@pytest.mark.parametrize("statement", [
    "Trong khoảng từ 10/09/2026 đến 09/10/2026, chưa xác minh được tin mới [1].",
    "Trong khoảng thời gian yêu cầu từ 10/09/2026 đến 09/10/2026, hệ thống chưa "
    "xác minh được bản tin sự kiện mới nào do các nguồn chủ yếu là thông tin chung [1].",
    "Chưa tìm thấy tin trong khoảng 10/09/2026 đến 09/10/2026 từ nguồn đã đọc [1].",
    "Chưa kiểm chứng được thông tin cập nhật trong 30 ngày qua từ nguồn đã đọc [1].",
])
def test_calendar_search_limit_is_preserved_without_false_website_attribution(statement):
    result, count = bound_web_numeric_claims(statement, [SOURCE], request=REQUEST, today=TODAY)
    assert count == 1
    assert result == ("Chưa xác minh được tin trong khoảng 10/09/2026–09/10/2026 "
                      "từ các nguồn đã đọc.")
    assert bound_web_numeric_claims(result, [SOURCE], request=REQUEST, today=TODAY) == (result, 0)


@pytest.mark.parametrize("statement", [
    "Không có tin trong khoảng 10/09/2026 đến 09/10/2026 [1].",
    "Chưa xác minh được tin trong khoảng 01/09/2026 đến 09/10/2026 [1].",
    "Chưa xác minh được tin trong khoảng 10/09/2026 đến 09/10/2026, "
    "nhưng có 30 nhân viên [1].",
    "Chưa xác minh được tin 30 ngày gần đây về doanh thu tăng 30% [1].",
    "Có 30 chi nhánh [1]. Chưa xác minh được tin trong 30 ngày qua [1].",
    "Chưa xác minh được tin trong 30 ngày qua. Có 1000 khách hàng [1].",
    "Chưa xác minh được tin trong khoảng 31/09/2026 đến 09/10/2026 [1].",
])
def test_search_limitation_never_grants_unrequested_dates_or_business_assertions(statement):
    result, count = bound_web_numeric_claims(statement, [SOURCE], request=REQUEST, today=TODAY)
    assert count == 1
    assert "Chưa đủ bằng chứng" in result
    assert "Có 30" not in result and "1000" not in result


def test_repeated_incomplete_scale_counters_do_not_erase_supported_workforce_facts():
    source = {"evidence_kind": "page_text", "snippet": (
        "1+ Branches & Representative Offices 1+ Global Clients "
        "1+ Employees 1+ Countries & Territories. In 2025, 3,800 ideas and 32% women."
    )}
    answer = (
        "## Quy mô có căn cứ\n"
        "Nhân sự, chi nhánh và khách hàng đều bắt đầu bằng mốc một kèm dấu cộng [1]. "
        "Năm 2025 có hơn 3.800 ý tưởng và 32% nhân sự nữ [1]."
    )
    result, count = bound_web_numeric_claims(answer, [source])
    assert count == 1
    assert "số đếm chưa đầy đủ" in result
    assert "mốc một kèm dấu cộng" not in result
    assert "Năm 2025 có hơn 3.800 ý tưởng và 32% nhân sự nữ [1]." in result
    assert bound_web_numeric_claims(result, [source]) == (result, 0)


def test_one_small_count_or_normal_scale_is_not_a_placeholder_failure():
    for source_text, answer in [
        ("1+ Employees", "Có 1+ nhân viên [1]."),
        ("100+ Employees 10+ Branches 30+ Countries", "Có 100+ nhân viên [1]."),
    ]:
        source = {"evidence_kind": "page_text", "snippet": source_text}
        assert bound_web_numeric_claims(answer, [source]) == (answer, 0)


def test_placeholder_exception_never_applies_to_local_sources_or_uncited_claims():
    source = {"snippet": "1+ Employees 1+ Global Clients 1+ Countries & Territories"}
    answer = "Số nhân viên bắt đầu bằng mốc một kèm dấu cộng [1]."
    assert bound_web_numeric_claims(answer, [source]) == (answer, 0)
    assert bound_web_numeric_claims("Chưa xác minh được tin 30 ngày qua.", [SOURCE],
                                    request=REQUEST, today=TODAY)[1] == 0
