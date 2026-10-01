"""Test suite for Gmail tools, 2-phase human approval, and Morning Briefing service."""

import base64
from datetime import UTC, date, datetime, timedelta
from email import message_from_bytes, policy
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.tools.gmail as gmail_module
from app.api.gmail import router as gmail_router
from app.core.config import Settings
from app.db.models import Base, User, UserRole
from app.services.operations import OperationStore
from app.tools.contracts import ToolContext, ToolError
from app.tools.gmail import (
    EmailApprovalInput,
    EmailDraftSpec,
    EmailPrepareInput,
    GmailAttachmentInput,
    GmailCreateDraftInput,
    GmailDraftPrepareInput,
    GmailListInput,
    GmailReadMatchingInput,
    GmailReadThreadInput,
    _build_send_payload,
    _can_render_faithfully,
    _can_render_readably,
    _clean_snippet,
    _decode_body,
    _extract_html_body,
    _extract_message_content,
    _extract_plain_body_exact,
    _first_external_address,
    _presentation_for_message,
    _validate_summary_response,
    gmail_create_draft,
    gmail_get_attachment,
    gmail_list_messages,
    gmail_prepare_draft,
    gmail_prepare_native_draft,
    gmail_read_matching_messages,
    gmail_send,
    gmail_summarize_thread,
    gmail_tool_definitions,
    handle_gmail_http_error,
)


def test_gmail_snippet_unescapes_entities_and_removes_tracking_padding():
    assert _clean_snippet("A &#39;quote&#39;\u200b\ufeff") == "A 'quote'"
    assert (
        _clean_snippet("Bản tin\u034f\u034f  có\t nhiều\n khoảng cách")
        == "Bản tin có nhiều khoảng cách"
    )


def test_gmail_body_removes_tracking_padding_but_keeps_paragraphs():
    body, _ = _extract_message_content(
        {
            "mimeType": "text/plain",
            "body": {
                "data": _encoded(
                    "Mở đầu\u034f \u034f \u034f    bản tin.\n\n\nNội dung   chính."
                )
            },
        }
    )
    assert body == "Mở đầu bản tin.\n\nNội dung chính."


@pytest.mark.asyncio
async def test_gmail_list_batches_metadata_and_preserves_order(monkeypatch, tmp_path: Path):
    """The inbox list uses one read-only batch, with stable UI ordering."""

    class Request:
        def __init__(self, response):
            self.response = response
            self.execute_called = False

        def execute(self):
            self.execute_called = True
            return self.response

    class Batch:
        def __init__(self):
            self.requests: list[tuple[str, Request, object]] = []
            self.execute_called = False

        def add(self, request, callback=None, request_id=None):
            self.requests.append((request_id, request, callback))

        def execute(self):
            self.execute_called = True
            for request_id, request, callback in self.requests:
                callback(request_id, request.response, None)

    class Messages:
        def __init__(self, service):
            self.service = service

        def list(self, **kwargs):
            if "has:attachment" in kwargs["q"]:
                return Request({"messages": [{"id": "m2"}]})
            return Request(
                {
                    "messages": [{"id": "m1"}, {"id": "m2"}],
                    "resultSizeEstimate": 2,
                }
            )

        def get(self, **kwargs):
            message_id = kwargs["id"]
            return Request(
                {
                    "id": message_id,
                    "threadId": f"t-{message_id}",
                    "snippet": f"snippet-{message_id}",
                    "labelIds": ["UNREAD"],
                    "payload": {
                        "headers": [
                            {"name": "From", "value": f"{message_id}@example.com"},
                            {"name": "Subject", "value": f"Subject {message_id}"},
                            {"name": "Date", "value": "Thu, 11 Sep 2026 10:00:00 +0000"},
                        ]
                    },
                }
            )

    class Users:
        def __init__(self, service):
            self.service = service
            self._messages = Messages(service)

        def messages(self):
            return self._messages

    class Service:
        def __init__(self):
            self.batch = Batch()
            self._users = Users(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def users(self):
            return self._users

        def new_batch_http_request(self):
            return self.batch

    service = Service()
    monkeypatch.setattr(gmail_module, "build", lambda *args, **kwargs: service)

    async def fake_refresh(*args, **kwargs):
        return object()

    monkeypatch.setattr(gmail_module, "refresh_and_store_if_needed", fake_refresh)
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}", gemini_api_key=""
    )
    user = User(id="gmail-batch-user", email="user@example.com", display_name="User")
    context = ToolContext(
        request_id="gmail-batch-request", user=user, db=None, settings=settings
    )

    result = await gmail_list_messages(GmailListInput(max_results=2), context)

    assert service.batch.execute_called is True
    assert [item.id for item in result.messages] == ["m1", "m2"]
    assert [item.subject for item in result.messages] == ["Subject m1", "Subject m2"]
    assert [item.has_attachment for item in result.messages] == [False, True]
    assert all(not request.execute_called for _, request, _ in service.batch.requests)


def test_gmail_tool_definitions_registered():
    defs = gmail_tool_definitions()
    by_name = {d.name: d for d in defs}
    names = set(by_name)
    assert "gmail_list_messages" in names
    assert "gmail_read_thread" in names
    assert "gmail_read_matching_messages" in names
    assert "gmail_prepare_draft" in names
    assert "gmail_send" in names
    assert "gmail_prepare_native_draft" in names
    assert by_name["gmail_create_draft"].requires_user_action is True
    assert by_name["gmail_prepare_native_draft"].requires_user_action is True
    assert by_name["gmail_prepare_draft"].requires_user_action is True
    assert by_name["gmail_list_messages"].max_attempts == 3
    assert by_name["gmail_read_thread"].max_attempts == 3
    assert by_name["gmail_read_matching_messages"].external_write is False


@pytest.mark.asyncio
async def test_multi_email_read_filters_local_day_and_exact_sender_without_snippets(
    monkeypatch, tmp_path: Path
):
    class Request:
        def __init__(self, response):
            self.response = response

        def execute(self):
            return self.response

    class Messages:
        def list(self, **kwargs):
            assert kwargs["q"].startswith('subject:"Bản chi tiết" after:')
            assert " before:" in kwargs["q"]
            return Request(
                {
                    "messages": [{"id": "m1"}, {"id": "m2"}, {"id": "m3"}, {"id": "m4"}],
                    "nextPageToken": "next",
                }
            )

        def get(self, **kwargs):
            assert kwargs["format"] == "full"
            message_id = kwargs["id"]
            stamp = datetime(2026, 9, 24 if message_id != "m2" else 23, 1, tzinfo=UTC)
            sender = (
                '"Bảo Phúc Đinh" <dbp3206@gmail.com>'
                if message_id != "m3"
                else '"Người lạ" <impostor@example.com>'
            )
            return Request(
                {
                    "id": message_id,
                    "threadId": "t-" + message_id,
                    "internalDate": str(int(stamp.timestamp() * 1000)),
                    "snippet": "Không dùng đoạn này để tóm tắt",
                    "payload": {
                        "mimeType": "text/plain",
                        "headers": [
                            {"name": "From", "value": sender},
                            {"name": "Subject", "value": "Bản chi tiết 12h"},
                            {"name": "Date", "value": "Thu, 24 Sep 2026 08:00:00 +0700"},
                        ],
                        "body": {"data": _encoded("Toàn văn gồm bối cảnh, dữ kiện và kết luận.")},
                    },
                }
            )

    class Service:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def users(self):
            return self

        def messages(self):
            return Messages()

    monkeypatch.setattr(gmail_module, "build", lambda *args, **kwargs: Service())

    async def fake_refresh(*args, **kwargs):
        return object()

    monkeypatch.setattr(gmail_module, "refresh_and_store_if_needed", fake_refresh)
    context = ToolContext(
        request_id="multi-mail-test",
        user=User(id="reader", email="reader@example.com", display_name="Reader"),
        db=None,
        settings=Settings(data_dir=tmp_path, _env_file=None),
    )
    result = await gmail_read_matching_messages(
        GmailReadMatchingInput(
            query='subject:"Bản chi tiết"',
            local_date=date(2026, 9, 24),
            sender_address="dbp3206@gmail.com",
        ),
        context,
    )
    assert result.examined_count == 4
    assert result.next_page_token == "next"
    assert [message.id for message in result.messages] == ["m1", "m4"]
    # A subject's schedule label is not the Gmail receipt time; include it at 08:00.
    assert result.messages[0].subject == "Bản chi tiết 12h"
    assert result.messages[0].body == "Toàn văn gồm bối cảnh, dữ kiện và kết luận."
    assert result.messages[0].received_at_local.startswith("2026-09-24T08:00:00")
    assert "Không dùng đoạn này" not in result.messages[0].body
    assert result.unreadable_body_count == 0
    by_display_name = await gmail_read_matching_messages(
        GmailReadMatchingInput(
            query='subject:"Bản chi tiết"',
            local_date=date(2026, 9, 24),
            sender_name="Đinh Bảo Phúc",
        ),
        context,
    )
    # Two same-day emails with the same subject-hour label are both retained.
    assert [message.id for message in by_display_name.messages] == ["m1", "m4"]


@pytest.mark.asyncio
async def test_multi_email_read_today_scope_uses_runtime_day_not_supplied_date(
    monkeypatch, tmp_path: Path
):
    received = datetime.now(UTC) - timedelta(seconds=1)
    local_today = received.astimezone(ZoneInfo("Asia/Bangkok")).date()

    class Request:
        def __init__(self, response):
            self.response = response

        def execute(self):
            return self.response

    class Service:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def users(self):
            return self

        def messages(self):
            return self

        def list(self, **kwargs):
            return Request({"messages": [{"id": "m1"}, {"id": "m2"}]})

        def get(self, **kwargs):
            sender = (
                '"Bảo Phúc Đinh" <verified@example.com>'
                if kwargs["id"] == "m1"
                else '"Người khác" <other@example.com>'
            )
            return Request(
                {
                    "id": kwargs["id"],
                    "internalDate": str(int(received.timestamp() * 1000)),
                    "payload": {
                        "mimeType": "text/plain",
                        "headers": [
                            {"name": "From", "value": sender},
                            {"name": "Subject", "value": "Bản chi tiết 15h"},
                        ],
                        "body": {"data": _encoded("Nội dung đầy đủ")},
                    },
                }
            )

    monkeypatch.setattr(gmail_module, "build", lambda *args, **kwargs: Service())

    async def fake_refresh(*args, **kwargs):
        return object()

    monkeypatch.setattr(gmail_module, "refresh_and_store_if_needed", fake_refresh)
    context = ToolContext(
        request_id="multi-mail-today",
        user=User(id="reader", email="reader@example.com", display_name="Reader"),
        db=None,
        settings=Settings(data_dir=tmp_path, _env_file=None),
    )
    result = await gmail_read_matching_messages(
        GmailReadMatchingInput(
            query='subject:"Bản chi tiết"',
            local_date=local_today - timedelta(days=1),
            day_scope="today",
            timezone="Asia/Bangkok",
            sender_name="Đinh Bảo Phúc",
        ),
        context,
    )
    assert [message.id for message in result.messages] == ["m1"]
    assert result.sender_mismatch_count == 1
    assert result.local_day_mismatch_count == 0
    assert result.messages[0].received_at_local[:10] == local_today.isoformat()


@pytest.mark.asyncio
async def test_multi_email_read_today_collects_pages_without_duplicate_messages(
    monkeypatch, tmp_path: Path
):
    received = datetime.now(UTC) - timedelta(seconds=2)
    queries: list[str] = []

    class Request:
        def __init__(self, response):
            self.response = response

        def execute(self):
            return self.response

    class Service:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def users(self):
            return self

        def messages(self):
            return self

        def list(self, **kwargs):
            queries.append(kwargs["q"])
            if kwargs["pageToken"] is None:
                return Request({
                    "messages": [{"id": "m1"}, {"id": "m2"}],
                    "nextPageToken": "page-two",
                })
            assert kwargs["pageToken"] == "page-two"
            return Request({"messages": [{"id": "m2"}, {"id": "m3"}]})

        def get(self, **kwargs):
            return Request({
                "id": kwargs["id"],
                "internalDate": str(int(received.timestamp() * 1000)),
                "payload": {
                    "mimeType": "text/plain",
                    "headers": [
                        {"name": "From", "value": '"Sender" <sender@example.com>'},
                        {"name": "Subject", "value": "Bản chi tiết"},
                    ],
                    "body": {"data": _encoded(f"Nội dung {kwargs['id']}")},
                },
            })

    monkeypatch.setattr(gmail_module, "build", lambda *args, **kwargs: Service())

    async def fake_refresh(*args, **kwargs):
        return object()

    monkeypatch.setattr(gmail_module, "refresh_and_store_if_needed", fake_refresh)
    context = ToolContext(
        request_id="multi-page-today",
        user=User(id="reader", email="reader@example.com", display_name="Reader"),
        db=None,
        settings=Settings(data_dir=tmp_path, _env_file=None),
    )
    result = await gmail_read_matching_messages(
        GmailReadMatchingInput(
            query='subject:"Bản chi tiết"',
            day_scope="today",
            timezone="Asia/Bangkok",
            max_results=2,
        ),
        context,
    )

    assert [message.id for message in result.messages] == ["m1", "m2", "m3"]
    assert result.examined_count == 3
    assert result.next_page_token is None
    assert len(queries) == 2
    assert queries[0] == queries[1]
    assert "after:" in queries[0] and "before:" in queries[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("body_size", [0, -1, 90_001])
async def test_multi_email_read_unverified_date_and_oversize_fail_closed(
    monkeypatch, tmp_path: Path, body_size: int
):
    class Request:
        def __init__(self, response):
            self.response = response

        def execute(self):
            return self.response

    class Service:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def users(self):
            return self

        def messages(self):
            return self

        def list(self, **kwargs):
            return Request({"messages": [{"id": "m1"}]})

        def get(self, **kwargs):
            if body_size == 0:
                internal_date = None
            elif body_size == -1:
                internal_date = str(
                    int((datetime.now(UTC) + timedelta(hours=1)).timestamp() * 1000)
                )
            else:
                internal_date = "1790211600000"
            return Request(
                {
                    "id": "m1",
                    "internalDate": internal_date,
                    "payload": {
                        "mimeType": "text/plain",
                        "headers": [{"name": "From", "value": "Sender <sender@example.com>"}],
                        "body": {"data": _encoded("x" * max(0, body_size))},
                    },
                }
            )

    monkeypatch.setattr(gmail_module, "build", lambda *args, **kwargs: Service())

    async def fake_refresh(*args, **kwargs):
        return object()

    monkeypatch.setattr(gmail_module, "refresh_and_store_if_needed", fake_refresh)
    context = ToolContext(
        request_id="multi-mail-boundary",
        user=User(id="reader", email="reader@example.com", display_name="Reader"),
        db=None,
        settings=Settings(data_dir=tmp_path, _env_file=None),
    )
    payload = GmailReadMatchingInput(
        query="subject:daily",
        local_date=date(2026, 9, 24) if body_size == 0 else None,
    )
    if body_size == 0:
        result = await gmail_read_matching_messages(payload, context)
        assert result.messages == []
        assert result.date_unverified_count == 1
    elif body_size == -1:
        result = await gmail_read_matching_messages(payload, context)
        assert result.messages == []
        assert result.future_excluded_count == 1
    else:
        with pytest.raises(ToolError, match="quá dài") as exc:
            await gmail_read_matching_messages(payload, context)
        assert exc.value.code == "gmail_multi_read_too_large"


@pytest.mark.parametrize(
    ("status", "retryable"),
    [(408, True), (429, True), (500, True), (503, True), (401, False), (403, False), (404, False)],
)
def test_gmail_transient_http_errors_are_retryable_but_auth_and_missing_are_not(
    status: int, retryable: bool
):
    error = handle_gmail_http_error(
        SimpleNamespace(status_code=status), "tìm kiếm email"
    )

    assert error.retryable is retryable
    assert error.code == f"gmail_{status}"


def _encoded(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def test_html_email_is_cleaned_and_attachments_are_retained():
    body, attachments = _extract_message_content(
        {
            "mimeType": "multipart/mixed",
            "parts": [
                {
                    "mimeType": "text/html",
                    "body": {
                        "data": _encoded(
                            "<style>.hidden{display:none}</style><p>Xin <b>chào</b></p>"
                            "<script>steal()</script><div>Lịch họp: thứ Sáu</div>"
                        )
                    },
                },
                {
                    "mimeType": "application/pdf",
                    "filename": "ke-hoach.pdf",
                    "body": {"attachmentId": "att-1", "size": 2400},
                },
            ],
        }
    )
    assert body == "Xin chào\nLịch họp: thứ Sáu"
    assert "steal" not in body
    assert attachments == [
        {
            "filename": "ke-hoach.pdf",
            "mime_type": "application/pdf",
            "size": 2400,
            "attachment_id": "att-1",
        }
    ]


def test_presentation_fidelity_is_claimed_only_for_plain_text():
    plain = {"mimeType": "text/plain", "body": {"data": _encoded("Nội dung nguyên bản")}}
    mixed = {
        "mimeType": "multipart/alternative",
        "parts": [
            plain,
            {"mimeType": "text/html", "body": {"data": _encoded("<p>Nội dung</p>")}},
        ],
    }
    assert _can_render_faithfully(plain) is True
    assert _can_render_faithfully(mixed) is False


def test_faithful_plain_body_is_not_rewritten():
    original = "  Dòng đầu\r\n\r\n<https://example.com/?utm_source=mail>  \n"
    payload = {"mimeType": "text/plain", "body": {"data": _encoded(original)}}
    assert _extract_plain_body_exact(payload) == original


def test_plain_only_email_uses_faithful_text_mode():
    original = "  Dòng đầu\r\n\r\nNội dung đầy đủ.  \n"
    payload = {"mimeType": "text/plain", "body": {"data": _encoded(original)}}

    assert _presentation_for_message(payload, original, original) == (
        "faithful_text",
        original,
    )


def test_multipart_and_html_mail_with_text_is_read_directly():
    multipart = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": _encoded("Nội dung chữ đầy đủ")}},
            {"mimeType": "text/html", "body": {"data": _encoded("<p>Nội dung chữ đầy đủ</p>")}},
        ],
    }
    mode, body = _presentation_for_message(
        multipart, "Nội dung chữ đầy đủ", "Nội dung chữ đầy đủ", "<p>Nội dung chữ đầy đủ</p>"
    )
    assert mode == "safe_html"
    assert body == "Nội dung chữ đầy đủ"

    html_only = {"mimeType": "text/html", "body": {"data": _encoded("<p>Lịch họp lúc 9 giờ</p>")}}
    mode, body = _presentation_for_message(
        html_only, "Lịch họp lúc 9 giờ", "", "<p>Lịch họp lúc 9 giờ</p>"
    )
    assert mode == "safe_html"
    assert body == "Lịch họp lúc 9 giờ"


def test_image_only_html_mail_can_render_without_text_extraction():
    image_only = {"mimeType": "text/html", "body": {"data": _encoded('<img src="cid:hero">')}}
    assert _presentation_for_message(
        image_only, "", "", '<img src="cid:hero">'
    ) == ("safe_html", "")


def test_calendar_invitation_is_extracted_as_readable_event_fields():
    invitation = "\r\n".join([
        "BEGIN:VCALENDAR", "BEGIN:VEVENT", "SUMMARY:Demo\\, review",
        "DTSTART:20260923T121500Z", "DTEND:20260923T130000Z",
        "LOCATION:Room 4", "DESCRIPTION:Discuss roadmap\\nReview owners",
        "ATTENDEE;CN=Bao:mailto:bao@example.com", "END:VEVENT", "END:VCALENDAR",
    ])
    payload = {"mimeType": "text/calendar", "body": {"data": _encoded(invitation)}}
    body, _ = _extract_message_content(payload)
    mode, display = _presentation_for_message(payload, body, "")
    assert mode == "calendar_text"
    assert "Tiêu đề: Demo, review" in display
    assert "Bắt đầu: 23/09/2026 12:15:00 UTC" in display
    assert "Kết thúc: 23/09/2026 13:00:00 UTC" in display
    assert "Địa điểm: Room 4" in display
    assert "Mô tả: Discuss roadmap\nReview owners" in display
    assert "Người tham dự: mailto:bao@example.com" in display


def test_rich_html_with_images_and_links_is_presented_as_sanitizable_html():
    with_image = {
        "mimeType": "multipart/related",
        "parts": [
            {
                "mimeType": "text/html",
                "body": {"data": _encoded("<p>Thông báo</p><img src='cid:hero'>")},
            },
            {"mimeType": "image/png", "body": {"attachmentId": "inline-image"}},
        ],
    }
    with_link = {
        "mimeType": "text/html",
        "body": {"data": _encoded("<p>Đọc <a href='https://example.com/detail'>chi tiết</a></p>")},
    }
    for payload in (with_image, with_link):
        html = _extract_html_body(payload)
        mode, body = _presentation_for_message(payload, "Thông báo chi tiết", "", html)
        assert mode == "safe_html"
        assert body == "Thông báo chi tiết"
        assert _can_render_readably(payload) is True


def test_inline_cid_images_are_collected_with_metadata_without_fetching_bytes():
    body, attachments = _extract_message_content({
        "mimeType": "multipart/related",
        "parts": [
            {"mimeType": "text/html", "body": {"data": _encoded('<img src="cid:hero">')}},
            {
                "mimeType": "image/png",
                "headers": [
                    {"name": "Content-ID", "value": "<hero>"},
                    {"name": "Content-Disposition", "value": "inline"},
                ],
                "body": {"attachmentId": "image-1", "size": 128},
            },
        ],
    })
    assert body == ""
    assert attachments == [{
        "filename": "hero",
        "mime_type": "image/png",
        "size": 128,
        "attachment_id": "image-1",
        "content_id": "hero",
        "inline": True,
    }]


def test_summary_contract_requires_three_synthesized_bullets():
    assert _validate_summary_response('{"bullets":[" Ý một ","Ý hai","Ý ba"]}') == [
        "Ý một", "Ý hai", "Ý ba"
    ]
    with pytest.raises(ToolError, match="đúng 3 ý"):
        _validate_summary_response('{"bullets":["Chỉ có một ý"]}')


def test_summary_endpoint_accepts_post_requests():
    route = next(
        item for item in gmail_router.routes
        if getattr(item, "path", "") == "/api/gmail/threads/{thread_id}/summary"
    )
    assert route.methods == {"POST"}


def test_attachment_endpoint_is_read_only_get():
    route = next(
        item for item in gmail_router.routes
        if getattr(item, "path", "")
        == "/api/gmail/messages/{message_id}/attachments/{attachment_id}"
    )
    assert route.methods == {"GET"}


@pytest.mark.asyncio
async def test_gmail_attachment_is_verified_against_message_and_decoded(monkeypatch):
    image_bytes = b"\x89PNG\r\n\x1a\nsmall-test-image"
    encoded = base64.urlsafe_b64encode(image_bytes).decode().rstrip("=")

    class FakeRequest:
        def __init__(self, value):
            self.value = value
        def execute(self):
            return self.value

    class FakeAttachments:
        def get(self, **kwargs):
            assert kwargs["messageId"] == "message-123"
            assert kwargs["id"] == "image-123"
            return FakeRequest({"data": encoded})

    class FakeMessages:
        def get(self, **kwargs):
            assert kwargs["id"] == "message-123"
            return FakeRequest({"payload": {
                "mimeType": "multipart/related",
                "parts": [{
                    "mimeType": "image/png",
                    "filename": "pixel.png",
                    "body": {"attachmentId": "image-123", "size": len(image_bytes)},
                }],
            }})
        def attachments(self):
            return FakeAttachments()

    class FakeUsers:
        def messages(self):
            return FakeMessages()

    class FakeService:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return None
        def users(self):
            return FakeUsers()

    async def fake_refresh(*_args, **_kwargs):
        return object()

    monkeypatch.setattr(gmail_module, "refresh_and_store_if_needed", fake_refresh)
    monkeypatch.setattr(gmail_module, "build", lambda *_args, **_kwargs: FakeService())
    user = User(id="attachment-user", email="user@example.com", role=UserRole.SUPER_ADMIN.value)
    context = ToolContext(request_id="attachment-request", user=user, db=None, settings=Settings())  # type: ignore[arg-type]
    result = await gmail_get_attachment(
        GmailAttachmentInput(message_id="message-123", attachment_id="image-123"), context
    )
    assert result.mime_type == "image/png"
    assert result.filename == "pixel.png"
    assert base64.b64decode(result.data_base64) == image_bytes


@pytest.mark.asyncio
async def test_gmail_attachment_stable_part_id_resolves_fresh_opaque_id(monkeypatch):
    """threads.get IDs may differ from messages.get IDs for one MIME part."""
    image_bytes = b"\x89PNG\r\n\x1a\nimage-from-current-message"
    encoded = base64.urlsafe_b64encode(image_bytes).decode().rstrip("=")

    class FakeRequest:
        def __init__(self, value):
            self.value = value

        def execute(self):
            return self.value

    class FakeAttachments:
        def get(self, **kwargs):
            assert kwargs["messageId"] == "message-123"
            assert kwargs["id"] == "fresh-id-from-messages-get"
            return FakeRequest({"data": encoded})

    class FakeMessages:
        def get(self, **kwargs):
            assert kwargs["id"] == "message-123"
            return FakeRequest({"payload": {
                "mimeType": "multipart/related",
                "parts": [{
                    "partId": "1.2",
                    "mimeType": "image/png",
                    "filename": "image.png",
                    "body": {"attachmentId": "fresh-id-from-messages-get"},
                }],
            }})

        def attachments(self):
            return FakeAttachments()

    class FakeUsers:
        def messages(self):
            return FakeMessages()

    class FakeService:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def users(self):
            return FakeUsers()

    async def fake_refresh(*_args, **_kwargs):
        return object()

    monkeypatch.setattr(gmail_module, "refresh_and_store_if_needed", fake_refresh)
    monkeypatch.setattr(gmail_module, "build", lambda *_args, **_kwargs: FakeService())
    user = User(id="attachment-user", email="user@example.com", role=UserRole.SUPER_ADMIN.value)
    context = ToolContext(request_id="stable-part", user=user, db=None, settings=Settings())  # type: ignore[arg-type]
    result = await gmail_get_attachment(
        GmailAttachmentInput(message_id="message-123", attachment_id="part:1.2"), context
    )
    assert base64.b64decode(result.data_base64) == image_bytes


@pytest.mark.asyncio
async def test_summary_reads_complete_message_and_returns_three_bullets(monkeypatch):
    captured: dict[str, str] = {}
    payload = {
        "messages": [{
            "id": "message-1",
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Subject", "value": "Kế hoạch"},
                ],
                "body": {
                    "data": _encoded(
                        "Mở đầu. Nội dung quyết định ở cuối thư: họp lúc 9 giờ sáng thứ Hai."
                    )
                },
            },
        }]
    }

    class FakeRequest:
        def execute(self):
            return payload

    class FakeThreads:
        def get(self, **_kwargs):
            return FakeRequest()

    class FakeUsers:
        def threads(self):
            return FakeThreads()

    class FakeService:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return None
        def users(self):
            return FakeUsers()

    class FakeModels:
        async def generate_content(self, **kwargs):
            captured["prompt"] = kwargs["contents"]
            return SimpleNamespace(
                text='{"bullets":["Nêu kế hoạch","Họp lúc 9 giờ","Thời gian là thứ Hai"]}'
            )

    class FakeAsyncClient:
        def __init__(self):
            self.models = FakeModels()
        async def aclose(self):
            return None

    class FakeClient:
        def __init__(self, **_kwargs):
            self.aio = FakeAsyncClient()

    async def fake_refresh(*_args, **_kwargs):
        return object()

    monkeypatch.setattr(gmail_module, "refresh_and_store_if_needed", fake_refresh)
    monkeypatch.setattr(gmail_module, "build", lambda *_args, **_kwargs: FakeService())
    monkeypatch.setattr(gmail_module.genai, "Client", FakeClient)
    settings = Settings(gemini_api_key="fake-key")
    user = User(id="summary-user", email="user@example.com", role=UserRole.SUPER_ADMIN.value)
    context = ToolContext(request_id="summary-request", user=user, db=None, settings=settings)  # type: ignore[arg-type]

    result = await gmail_summarize_thread(GmailReadThreadInput(thread_id="thread-123"), context)
    assert len(result.bullets) == 3
    assert "họp lúc 9 giờ sáng thứ Hai" in captured["prompt"]


def test_plain_text_wins_over_html_fallback():
    body, _ = _extract_message_content(
        {
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _encoded("Bản rõ")}},
                {"mimeType": "text/html", "body": {"data": _encoded("<p>Bản HTML</p>")}},
            ],
        }
    )
    assert body == "Bản rõ"


def test_mime_charset_and_attachment_backed_body_are_decoded():
    encoded = base64.urlsafe_b64encode("Xin chào từ email".encode("utf-16-le")).decode().rstrip("=")
    assert _decode_body(encoded, "utf-16-le") == "Xin chào từ email"
    requested: list[str] = []
    body, _ = _extract_message_content(
        {
            "mimeType": "text/plain",
            "headers": [{"name": "Content-Type", "value": "text/plain; charset=utf-16-le"}],
            "body": {"attachmentId": "body-1"},
        },
        attachment_loader=lambda attachment_id: requested.append(attachment_id) or encoded,
    )
    assert requested == ["body-1"]
    assert body == "Xin chào từ email"


def test_reply_target_never_selects_authenticated_user():
    assert _first_external_address(
        "Me <student@example.com>", "Teacher <teacher@example.com>", own_email="student@example.com"
    ) == "Teacher <teacher@example.com>"
    assert _first_external_address("student@example.com", own_email="student@example.com") == ""


def test_richer_html_wins_when_plain_part_is_only_a_footer():
    article = " ".join(["Nội dung bài viết hữu ích cho người đọc."] * 20)
    body, _ = _extract_message_content(
        {
            "mimeType": "multipart/alternative",
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": _encoded("Unsubscribe: https://tracking.example/a-long-id")},
                },
                {
                    "mimeType": "text/html",
                    "body": {
                        "data": _encoded(
                            f"<article><h1>Bản tin</h1><p>{article}</p></article>"
                        )
                    },
                },
            ],
        }
    )
    assert body.startswith("Bản tin")
    assert "Nội dung bài viết" in body


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("recipient", "victim@example.com\nBcc: attacker@example.com"),
        ("subject", "Báo cáo\r\nBcc: attacker@example.com"),
        ("cc", "khong-phai-email"),
    ],
)
def test_email_headers_reject_injection_and_bad_addresses(field, value):
    kwargs = {
        "recipient": "student@example.com",
        "subject": "Báo cáo",
        "body": "Nội dung",
        field: value,
    }
    with pytest.raises(ValueError):
        EmailDraftSpec(**kwargs)


def test_reply_metadata_is_part_of_approved_digest_payload():
    draft = EmailDraftSpec(
        recipient="Giảng viên <teacher@example.com>",
        cc="team@example.com",
        subject="Re: Lịch học",
        body="Em đã nhận thông tin.",
        thread_id="thread-123",
        in_reply_to="<message-1@example.com>",
        references="<message-0@example.com> <message-1@example.com>",
    )
    assert draft.thread_id == "thread-123"
    assert draft.in_reply_to == "<message-1@example.com>"
    payload, attachments = _build_send_payload(draft, credentials=None)
    message = message_from_bytes(base64.urlsafe_b64decode(payload["raw"]), policy=policy.default)
    assert payload["threadId"] == "thread-123"
    assert message["To"] == "Giảng viên <teacher@example.com>"
    assert message["Cc"] == "team@example.com"
    assert message["In-Reply-To"] == "<message-1@example.com>"
    assert attachments == []


@pytest.mark.asyncio
async def test_gmail_prepare_and_approve_two_phase_flow(tmp_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}", gemini_api_key=""
    )
    user = User(
        id="user-gmail-qa",
        email="dbp3206@gmail.com",
        display_name="QA User",
        role=UserRole.SUPER_ADMIN.value,
    )

    async with factory() as db:
        context = ToolContext(request_id="req-gmail-1", user=user, db=db, settings=settings)

        # 1. Prepare draft
        prep_input = EmailPrepareInput(
            request_key="req-gmail-test-1",
            draft=EmailDraftSpec(
                recipient="test@example.com",
                subject="Báo cáo tiến độ",
                body="Xin chào, đây là nội dung email tiến độ.",
            ),
        )
        prep_res = await gmail_prepare_draft(prep_input, context)
        assert prep_res.data["state"] == "pending"
        assert len(prep_res.data["digest"]) == 64  # SHA-256 hex string
        operation_id = prep_res.data["operation_id"]

        # Check operations.db recorded the pending draft
        store = OperationStore(tmp_path / "operations.db")
        op = store.get(user.id, operation_id)
        assert op["state"] == "pending"
        assert op["digest"] == prep_res.data["digest"]

        # 2. Tampered digest must fail
        with pytest.raises(ToolError, match="không khớp"):
            await gmail_send(
                EmailApprovalInput(
                    operation_id=operation_id,
                    approved_digest="0" * 64,
                ),
                context,
            )

    await engine.dispose()


@pytest.mark.asyncio
async def test_morning_briefing_generates_and_updates_session(tmp_path: Path):
    from app.services.morning_briefing import MorningBriefingService
    from app.tools.registry import ToolRegistry

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test_brief.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test_brief.db'}", gemini_api_key=""
    )
    user = User(
        id="user-brief-test",
        email="user@example.com",
        display_name="Brief User",
        role=UserRole.EDITOR.value,
    )

    registry = ToolRegistry()
    service = MorningBriefingService(settings=settings, registry=registry)

    async with factory() as db:
        db.add(user)
        await db.commit()

        # First run: should create a new session and assistant message
        res1 = await service.generate_brief(user=user, db=db, request_id="brief-req-1")
        assert "session_id" in res1
        assert "message_id" in res1
        assert "summary" in res1
        assert "answer" in res1
        assert res1["summary"] == res1["answer"]
        assert "☀️ Bản tin buổi sáng" in res1["summary"]
        assert "Hộp thư Gmail" in res1["summary"]
        assert "Google Drive cập nhật" in res1["summary"]

        session_id_1 = res1["session_id"]
        msg_id_1 = res1["message_id"]

        # Second run on same day: should update existing session and message idempotently
        res2 = await service.generate_brief(user=user, db=db, request_id="brief-req-2")
        assert res2["session_id"] == session_id_1
        assert res2["message_id"] == msg_id_1
        assert res2["answer"] is not None

    await engine.dispose()


@pytest.mark.asyncio
async def test_gmail_create_draft_native_flow(monkeypatch, tmp_path: Path):
    """A native draft is inert until the exact stored preview is approved."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test_draft.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test_draft.db'}", gemini_api_key=""
    )
    user = User(
        id="user-draft-test",
        email="testuser@example.com",
        display_name="Draft User",
        role=UserRole.EDITOR.value,
    )

    created_draft_payload = {}

    class MockDrafts:
        def create(self, userId, body):
            created_draft_payload["userId"] = userId
            created_draft_payload["body"] = body
            class Exec:
                def execute(self):
                    return {
                        "id": "draft_abc123",
                        "message": {"id": "msg_xyz789", "threadId": "thread_001"},
                    }
            return Exec()

    class MockUsers:
        def drafts(self):
            return MockDrafts()

    class MockService:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def users(self):
            return MockUsers()

    monkeypatch.setattr(gmail_module, "build", lambda *args, **kwargs: MockService())

    async def mock_refresh(*args, **kwargs):
        return None

    monkeypatch.setattr(gmail_module, "refresh_and_store_if_needed", mock_refresh)

    async with factory() as db:
        context = ToolContext(request_id="draft-req-1", user=user, db=db, settings=settings)
        payload = GmailDraftPrepareInput(
            request_key="chat-draft-test-1",
            draft=GmailCreateDraftInput(
                recipient="ceo@example.com",
                subject="Báo cáo tuần",
                body="Kính gửi CEO, đây là báo cáo tóm tắt...",
            ),
        )
        prepared = await gmail_prepare_native_draft(payload, context)
        assert prepared.data["state"] == "pending"
        assert created_draft_payload == {}
        with pytest.raises(ToolError, match="không khớp"):
            await gmail_create_draft(
                EmailApprovalInput(
                    operation_id=prepared.data["operation_id"],
                    approved_digest="0" * 64,
                ),
                context,
            )

        res = await gmail_create_draft(
            EmailApprovalInput(
                operation_id=prepared.data["operation_id"],
                approved_digest=prepared.data["digest"],
            ),
            context,
        )
        assert res.draft_id == "draft_abc123"
        assert res.message_id == "msg_xyz789"
        assert res.thread_id == "thread_001"
        assert res.gmail_draft_url == "https://mail.google.com/mail/u/0/#drafts"
        assert "ceo@example.com" in res.recipient
        assert "draft_abc123" in res.message
        assert created_draft_payload["userId"] == "me"
        store = OperationStore(tmp_path / "operations.db")
        operation = store.get(user.id, prepared.data["operation_id"])
        assert operation["state"] == "succeeded"
        assert operation["resource_id"] == "draft_abc123"
        with pytest.raises(ToolError, match="đã được nhận"):
            await gmail_create_draft(
                EmailApprovalInput(
                    operation_id=prepared.data["operation_id"],
                    approved_digest=prepared.data["digest"],
                ),
                context,
            )

    await engine.dispose()
