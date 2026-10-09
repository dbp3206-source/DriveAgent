from datetime import date

import pytest

from app.agent.news_window import bound_recent_news, news_window_context

TODAY = date(2026, 10, 9)
SOURCES = [{"evidence_kind": "page_text", "snippet": "Dữ liệu nguồn."}]
REQUEST = "Chuẩn bị báo cáo và tin 30 ngày gần đây."


def test_mixed_dated_news_moves_only_outside_items_and_preserves_other_sections():
    answer = (
        "Tổng quan và sản phẩm\nThành lập năm 2000 [1].\n\nTin gần đây\n"
        "Các thông tin được ghi nhận gần đây bao gồm thông báo 29/09/2026 [1], "
        "sản phẩm 10/09/2026 [1], bài viết 26/08/2026 [1], "
        "hạ tầng 12/08/2026 [1], và cuộc họp 19/03/2026 [1].\n\n"
        "Cuộc hẹn và bước tiếp theo\nHẹn ngày 12/08/2026 theo đầu vào."
    )
    result, count = bound_recent_news(answer, SOURCES, request=REQUEST, today=TODAY)
    recent, background = result.split("### Mốc ngoài khoảng", 1)
    assert count == 3
    assert "29/09/2026 [1]" in recent and "10/09/2026 [1]" in recent
    assert "26/08/2026" not in recent and "12/08/2026" not in recent
    assert "19/03/2026 [1]" in background and "26/08/2026 [1]" in background
    assert "Thành lập năm 2000 [1]." in recent
    assert "Hẹn ngày 12/08/2026 theo đầu vào." in result
    assert result.count("[1]") == answer.count("[1]")
    assert bound_recent_news(result, SOURCES, request=REQUEST, today=TODAY) == (result, 0)


@pytest.mark.parametrize("heading", ["Tin gần đây", "## Tin mới đã xác minh", "**Tin gần đây:**"])
def test_all_outside_news_keeps_content_as_dated_background(heading):
    answer = heading + "\nThông báo ngày 09/09/2026 [1]."
    result, count = bound_recent_news(answer, SOURCES, request=REQUEST, today=TODAY)
    assert count == 1
    assert "chưa có mục đã đối chiếu" in result
    assert "10/09/2026–09/10/2026" in result
    assert result.index("Mốc ngoài khoảng") < result.index("09/09/2026 [1]")


@pytest.mark.parametrize("body", [
    "Tin ngày 10/09/2026 [1].", "Tin ngày 09/10/2026 [1].",
    "Ngày đăng 08/10/2026, nhắc lại sự kiện 19/03/2026 [1].",
    "Tin không ghi ngày [1].", "Ngày chưa hợp lệ 31/02/2026 [1].",
    "Ngày 01/01/2026 nhưng chưa có nguồn.",
])
def test_boundary_does_not_infer_publication_dates_or_change_ambiguous_items(body):
    answer = "## Tin gần đây\n" + body
    assert bound_recent_news(answer, SOURCES, request=REQUEST, today=TODAY) == (answer, 0)


@pytest.mark.parametrize("user_request", ["", "Hẹn trong 30 ngày tới.",
    "Không tìm tin 30 ngày gần đây.", "Tin 7 ngày gần đây và tin 30 ngày gần đây."])
def test_no_unambiguous_requested_news_window_means_no_rewrite(user_request):
    answer = "Tin gần đây\nNgày 01/01/2026 [1]."
    assert bound_recent_news(answer, SOURCES, request=user_request, today=TODAY) == (answer, 0)


def test_local_sources_and_source_lists_are_not_filtered():
    answer = "Tin gần đây\nNgày 01/01/2026 [1]."
    assert bound_recent_news(answer, [{"snippet": "PDF"}], request=REQUEST,
                             today=TODAY) == (answer, 0)
    answer = "## Nguồn\nNgày 01/01/2026 [1]."
    assert bound_recent_news(answer, SOURCES, request=REQUEST, today=TODAY) == (answer, 0)


def test_calendar_window_is_explicit_and_inclusive():
    window = news_window_context(REQUEST, today=TODAY)
    assert window["start_date"] == "2026-09-10"
    assert window["end_date"] == "2026-10-09"
    assert window["days"] == 30
    window = news_window_context("Tin 7 ngày vừa qua", today=date(2026, 1, 3))
    assert window["start_date"] == "2025-12-28"


def test_future_date_is_outside_past_news_window():
    result, count = bound_recent_news("Tin gần đây\nThông báo 10/10/2026 [1].",
                                     SOURCES, request=REQUEST, today=TODAY)
    assert count == 1 and "Mốc ngoài khoảng" in result
