import json
from types import SimpleNamespace

import pytest

from app.api.chat import _gmail_followup_route


@pytest.mark.parametrize(
    "message",
    [
        "Phân tích 5 email gần nhất trong Gmail của tôi",
        "Phân tích 2 thư mới nhất",
        "Đào sâu email từ Khách Hàng B",
        "Phân tích email hôm nay",
        "Phân tích mail ngày 02/10/2026",
        "Phân tích thư trong 7 ngày qua",
        "Phân tích email, bỏ giới hạn người gửi cũ",
        'Phân tích thư tiêu đề "Cuộc hẹn mới"',
    ],
)
def test_new_explicit_scope_is_not_pinned_to_previous_thread(message):
    assert _gmail_followup_route(message, [assistant_with_thread("thread-123456")]) is None


def assistant_with_thread(thread_id: str):
    return SimpleNamespace(
        role="assistant",
        content="",
        citations_json=json.dumps(
            [{"web_view_link": f"https://mail.google.com/mail/u/0/#all/{thread_id}"}]
        ),
    )


def assistant_with_threads(*thread_ids: str):
    return SimpleNamespace(
        role="assistant",
        content="",
        citations_json=json.dumps(
            [
                {"web_view_link": f"https://mail.google.com/mail/u/0/#all/{thread_id}"}
                for thread_id in thread_ids
            ]
        ),
    )


def user_turn(content: str):
    return SimpleNamespace(role="user", content=content, citations_json="[]")


def assistant_without_source():
    return SimpleNamespace(role="assistant", content="", citations_json="[]", status="failed")


def test_followup_survives_an_uncited_failed_assistant_turn():
    prior = [
        assistant_without_source(),
        user_turn("đào sâu ý thứ hai trong email vừa tóm tắt"),
        assistant_with_thread("thread-123456"),
        user_turn("tóm tắt email gần nhất"),
    ]

    route = _gmail_followup_route("đào sâu ý thứ hai", prior)

    assert route is not None
    assert route.tool == "gmail_read_thread"
    assert route.arguments == {"thread_id": "thread-123456"}


def test_followup_does_not_reuse_old_email_after_topic_change():
    prior = [
        assistant_without_source(),
        user_turn("giải thích truy vấn SQL này"),
        assistant_with_thread("thread-123456"),
        user_turn("tóm tắt email gần nhất"),
    ]

    assert _gmail_followup_route("mở rộng thêm", prior) is None


def test_followup_without_any_gmail_source_does_not_guess_a_thread():
    prior = [
        assistant_without_source(),
        user_turn("giải thích thêm về tài liệu"),
    ]

    assert _gmail_followup_route("đào sâu ý thứ hai", prior) is None


def test_explicit_latest_email_can_refer_to_a_recent_cited_thread():
    prior = [assistant_without_source(), assistant_with_thread("thread-abcdef")]

    route = _gmail_followup_route("mở rộng email gần nhất đó", prior)

    assert route is not None
    assert route.arguments == {"thread_id": "thread-abcdef"}


def test_followup_asks_which_email_when_previous_answer_cited_multiple_threads():
    route = _gmail_followup_route(
        "đào sâu thêm nội dung đó",
        [assistant_with_threads("thread-123456", "thread-abcdef")],
    )

    assert route is not None
    assert route.direct is True
    assert route.required_sources == ("gmail",)
    assert "nhiều email khác nhau" in (route.clarification or "")


def test_followup_time_request_reopens_previous_gmail_source():
    route = _gmail_followup_route(
        "ghi rõ mốc thời gian cho tôi",
        [assistant_with_thread("thread-123456")],
    )

    assert route is not None
    assert route.tool == "gmail_read_thread"
    assert route.arguments == {"thread_id": "thread-123456"}


def test_followup_time_request_reads_all_previously_cited_threads():
    route = _gmail_followup_route(
        "ghi rõ mốc thời gian cho tôi",
        [assistant_with_threads("thread-123456", "thread-abcdef")],
    )

    assert route is not None
    assert [source.arguments for source in route.sources] == [
        {"thread_id": "thread-123456"},
        {"thread_id": "thread-abcdef"},
    ]


def test_repeated_citations_to_the_same_thread_are_not_ambiguous():
    route = _gmail_followup_route(
        "đào sâu email gần nhất đó",
        [assistant_with_threads("thread-123456", "thread-123456")],
    )

    assert route is not None
    assert route.tool == "gmail_read_thread"
    assert route.arguments == {"thread_id": "thread-123456"}


def test_gmail_followup_rejects_lookalike_hosts_and_wrong_paths():
    prior = [
        SimpleNamespace(
            role="assistant",
            content="",
            status="completed",
            citations_json=json.dumps(
                [
                    {
                        "web_view_link": "https://mail.google.com.evil.example/mail/u/0/#all/thread-123456"
                    },
                    {"web_view_link": "https://mail.google.com/evil/#all/thread-abcdef"},
                ]
            ),
        )
    ]

    assert _gmail_followup_route("đào sâu email gần nhất đó", prior) is None
