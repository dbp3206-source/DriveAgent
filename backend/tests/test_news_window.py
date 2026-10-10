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


def test_shared_citation_publication_list_repairs_frame_and_moves_only_old_news():
    dates = ["28/09/2026", "22/09/2026", "21/09/2026", "17/09/2026",
             "14/09/2026", "11/09/2026", "10/09/2026", "08/09/2026",
             "07/09/2026", "27/08/2026"]
    items = "; ".join(f"ngày đăng {day} thông báo số {index}"
                      for index, day in enumerate(dates, start=1))
    answer = (
        "## Tin gần đây\nTrong khoảng thời gian từ ngày 10/09/2026 đến ngày "
        f"09/09/2026, các tin được ghi nhận gồm: {items} [1].\n\n"
        "## Cuộc hẹn\nHẹn từ 01/09/2026 đến 02/09/2026 theo đầu vào."
    )
    result, count = bound_recent_news(answer, SOURCES, request=REQUEST, today=TODAY)
    recent, background = result.split("### Mốc ngoài khoảng", 1)
    assert count == 3
    assert "đến ngày 09/10/2026" in recent
    assert "đến ngày 09/09/2026" not in result
    for day in dates[:7]:
        assert f"ngày đăng {day}" in recent
    for day in dates[7:]:
        assert day not in recent and f"ngày đăng {day}" in background
    assert result.count("[1]") == len(dates)
    assert "Hẹn từ 01/09/2026 đến 02/09/2026 theo đầu vào." in result
    assert bound_recent_news(result, SOURCES, request=REQUEST, today=TODAY) == (result, 0)


@pytest.mark.parametrize("publication", ["ngày đăng", "Đăng ngày", "ngày công bố",
                                         "công bố ngày"])
def test_shared_publication_attribution_is_not_company_specific(publication):
    answer = (
        f"Tin gần đây\nCác bài viết gồm: {publication} 29/09/2026 ra mắt sản phẩm; "
        f"và {publication} 05/09/2026 thay đổi bộ phận [S1]."
    )
    result, count = bound_recent_news(answer, SOURCES, request=REQUEST, today=TODAY)
    recent, background = result.split("### Mốc ngoài khoảng", 1)
    assert count == 1 and "29/09/2026" in recent and "05/09/2026" not in recent
    assert "05/09/2026" in background
    assert result.count("[S1]") == 2


def test_shared_multiple_references_preserve_all_source_attribution():
    answer = ("Tin gần đây\nNgày đăng 29/09/2026 tin mới; "
              "ngày đăng 01/08/2026 tin cũ [1, S2].")
    result, count = bound_recent_news(answer, SOURCES * 2, request=REQUEST, today=TODAY)
    assert count == 1 and result.count("[1, S2]") == 2
    assert bound_recent_news(result, SOURCES * 2, request=REQUEST, today=TODAY) == (result, 0)


@pytest.mark.parametrize("body", [
    "Ngày đăng 29/09/2026, nhắc sự kiện 01/08/2026; ngày đăng 02/08/2026 tin cũ [1].",
    "Trong khoảng từ ngày 01/08/2026 đến ngày 02/08/2026, triển lãm mở cửa [1].",
    "Bài viết so sánh 29/09/2026 với 01/08/2026; kết quả thay đổi [1].",
    "Các tin gồm: ngày đăng 31/02/2026 lỗi ngày; ngày đăng 29/09/2026 tin mới [1].",
    "Các tin gồm: ngày đăng 01/08/2026 tin cũ; ngày đăng 29/09/2026 tin mới [2].",
])
def test_shared_attribution_never_reinterprets_comparisons_invalid_dates_or_refs(body):
    answer = "## Tin gần đây\n" + body
    result, count = bound_recent_news(answer, SOURCES, request=REQUEST, today=TODAY)
    if body.startswith("Ngày đăng 29/09"):
        # The old, independently enumerated publication can move while the
        # article's current publication date and older event date stay together.
        assert count == 1
        assert "Ngày đăng 29/09/2026, nhắc sự kiện 01/08/2026" in result.split(
            "### Mốc ngoài khoảng", 1,
        )[0]
    else:
        assert (result, count) == (answer, 0)


@pytest.mark.parametrize("heading,body", [
    ("## Tin gần đây (từ 10/09/2026 đến 09/09/2026)", "Chưa có tin đã đối chiếu [1]."),
    ("Tin gần đây", "Trong khoảng thời gian từ ngày 10/09/2026 đến ngày 09/09/2026, "
     "chưa có tin đã đối chiếu [1]."),
])
def test_explicit_report_window_frame_is_corrected_without_moving_items(heading, body):
    result, count = bound_recent_news(heading + "\n" + body, SOURCES,
                                     request=REQUEST, today=TODAY)
    assert count == 0  # This counter records relocated items, not frame corrections.
    assert "09/10/2026" in result and "09/09/2026" not in result
    assert bound_recent_news(result, SOURCES, request=REQUEST, today=TODAY) == (result, 0)


def test_shared_publication_list_with_only_local_or_mixed_evidence_is_unchanged():
    answer = ("Tin gần đây\nNgày đăng 29/09/2026 tin mới; "
              "ngày đăng 01/08/2026 tin cũ [1,2].")
    assert bound_recent_news(answer, SOURCES + [{"evidence_kind": "local"}],
                             request=REQUEST, today=TODAY) == (answer, 0)


@pytest.mark.parametrize("prefix,separator", [("- ", "; "), ("", ", và ")])
def test_explicit_publication_enumeration_handles_bullets_and_commas(prefix, separator):
    answer = (f"Tin gần đây\n{prefix}Ngày đăng 29/09/2026 tin mới{separator}"
              "ngày đăng 01/08/2026 tin cũ [1].")
    result, count = bound_recent_news(answer, SOURCES, request=REQUEST, today=TODAY)
    assert count == 1
    recent, background = result.split("### Mốc ngoài khoảng", 1)
    assert "29/09/2026" in recent and "01/08/2026" not in recent
    assert "01/08/2026" in background and result.count("[1]") == 2


def test_news_event_range_is_preserved_even_if_later_sentence_mentions_news():
    answer = ("Tin gần đây\nTrong khoảng từ ngày 01/08/2026 đến ngày 02/08/2026, "
              "triển lãm mở cửa. Bài viết cũng cập nhật thông tin khách tham dự [1].")
    assert bound_recent_news(answer, SOURCES, request=REQUEST, today=TODAY) == (answer, 0)


@pytest.mark.parametrize("framing", [
    "trang web chính thức ghi nhận các thông tin được đăng tải gồm:",
    "nguồn chính thức đã liệt kê các bài viết sau:",
    "cổng thông tin tổng hợp tin tức gồm:",
])
def test_source_reporting_frame_corrects_window_before_shared_news_list(framing):
    answer = ("Tin gần đây\nTrong khoảng thời gian từ ngày 10/09/2026 đến ngày "
              f"09/09/2026, {framing} ngày đăng 28/09/2026 thông báo; "
              "và ngày đăng 27/08/2026 thông báo trước đó [1].")
    result, count = bound_recent_news(answer, SOURCES, request=REQUEST, today=TODAY)
    assert count == 1
    recent, background = result.split("### Mốc ngoài khoảng", 1)
    assert "đến ngày 09/10/2026" in recent and "đến ngày 09/09/2026" not in result
    assert "28/09/2026" in recent and "27/08/2026" not in recent
    assert "27/08/2026" in background and result.count("[1]") == 2
    assert bound_recent_news(result, SOURCES, request=REQUEST, today=TODAY) == (result, 0)
