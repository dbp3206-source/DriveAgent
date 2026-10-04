"""Read-only W1 morning briefing tests with a governed-tool double."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.models import Base, Message, User, UserRole
from app.services.morning_briefing import MorningBriefingService
from app.tools.contracts import ToolError


class RecordingRegistry:
    """A local tool-harness double; it never contacts Google or another provider."""

    def __init__(self, messages, threads, *, failures=(), next_page_token=None):
        self.messages = messages
        self.threads = threads
        self.failures = set(failures)
        self.next_page_token = next_page_token
        self.calls: list[tuple[str, dict, object]] = []

    async def execute(self, name, arguments, context):
        self.calls.append((name, arguments, context))
        assert context.source == "morning_briefing"
        assert context.user.id == "w1-owner"
        if name == "gmail_list_messages":
            return SimpleNamespace(
                total_found=len(self.messages),
                messages=self.messages,
                next_page_token=self.next_page_token,
            )
        if name == "gmail_read_thread":
            thread_id = arguments["thread_id"]
            if thread_id in self.failures:
                raise ToolError("thread read failed", code="gmail_500")
            return self.threads.get(
                thread_id,
                SimpleNamespace(thread_id=thread_id, subject="Unknown", messages=[]),
            )
        if name == "drive_list_files":
            return SimpleNamespace(files=[])
        raise AssertionError(f"W1 attempted an out-of-scope tool: {name}")


@pytest.fixture
async def w1_db(tmp_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'w1.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    user = User(
        id="w1-owner",
        email="w1-owner@example.test",
        display_name="W1 Owner",
        role=UserRole.EDITOR.value,
    )
    async with factory() as db:
        db.add(user)
        await db.commit()
        yield db, user
    await engine.dispose()


def _header(index: int):
    return SimpleNamespace(
        id=f"message-{index}",
        thread_id=f"thread-{index}",
        sender=f"sender-{index}@example.test",
        subject=f"Request {index}",
        date="Fri, 02 Oct 2026 09:00:00 +0700",
        snippet=f"metadata snippet {index}",
    )


def _thread(index: int, body: str):
    return SimpleNamespace(
        thread_id=f"thread-{index}",
        subject=f"Request {index}",
        messages=[
            SimpleNamespace(
                id=f"message-{index}",
                sender=f"sender-{index}@example.test",
                date="Fri, 02 Oct 2026 09:00:00 +0700",
                body=body,
                plain_body="",
                attachments=[],
            )
        ],
    )


def _settings(tmp_path: Path) -> Settings:
    return Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'w1.db'}")


@pytest.mark.asyncio
async def test_morning_briefing_reads_bodies_and_persists_sources(w1_db, tmp_path: Path):
    db, user = w1_db
    messages = [_header(index) for index in range(1, 6)]
    threads = {
        f"thread-{index}": _thread(index, f"BODY_EVIDENCE_{index}: yêu cầu cần xử lý")
        for index in range(1, 6)
    }
    registry = RecordingRegistry(messages, threads)

    result = await MorningBriefingService(_settings(tmp_path), registry).generate_brief(
        user, db, request_id="w1-body"
    )

    assert result["read_email_count"] == 5
    assert result["body_failure_count"] == 0
    assert "BODY_EVIDENCE_1" in result["summary"]
    assert "Request 1" in result["summary"]  # metadata remains visible with body context

    names = [name for name, _arguments, _context in registry.calls]
    assert names[0] == "gmail_list_messages"
    assert names.count("gmail_read_thread") == 5
    assert names.count("drive_list_files") == 1
    assert not {"gmail_send", "gmail_create_draft", "docs_execute", "sheets_execute"} & set(
        names
    )
    assert all(context.user.id == user.id for _name, _args, context in registry.calls)

    message = await db.scalar(select(Message).where(Message.id == result["message_id"]))
    citations = json.loads(message.citations_json)
    assert len(citations) == 5
    assert {
        "file_id",
        "file_name",
        "chunk_index",
        "snippet",
        "web_view_link",
        "score",
    }.issubset(citations[0])
    assert citations[0]["file_id"] == "thread-1"
    assert citations[0]["file_name"] == "Request 1"
    assert "BODY_EVIDENCE_1" in citations[0]["snippet"]
    assert citations[0]["web_view_link"].endswith("#all/thread-1")


@pytest.mark.asyncio
async def test_morning_briefing_caps_reads_and_keeps_partial_body_failures_visible(
    w1_db, tmp_path: Path
):
    db, user = w1_db
    # The sixth result is deliberately present to prove that the unattended job does
    # not follow the next page or read beyond its five-thread budget.
    messages = [_header(index) for index in range(1, 7)]
    threads = {
        "thread-1": _thread(1, "BODY_OK_1"),
        "thread-3": SimpleNamespace(thread_id="thread-3", subject="Request 3", messages=[]),
        "thread-4": _thread(4, "BODY_OK_4"),
        "thread-5": _thread(5, "BODY_OK_5"),
    }
    registry = RecordingRegistry(messages, threads, failures={"thread-2"}, next_page_token="next")

    result = await MorningBriefingService(_settings(tmp_path), registry).generate_brief(
        user, db, request_id="w1-partial"
    )

    read_calls = [
        arguments["thread_id"]
        for name, arguments, _context in registry.calls
        if name == "gmail_read_thread"
    ]
    assert read_calls == [f"thread-{index}" for index in range(1, 6)]
    assert "thread-6" not in read_calls
    assert result["read_email_count"] == 3
    assert result["body_failure_count"] == 2
    assert "BODY_OK_1" in result["summary"]
    assert "BODY_OK_4" in result["summary"]
    assert "chưa đọc được nội dung" in result["summary"]
    assert "Còn trang thư tiếp theo" in result["summary"]
    # A failed body read must not cause a draft/send or stop Drive's independent read.
    assert any(name == "drive_list_files" for name, _args, _context in registry.calls)


@pytest.mark.asyncio
async def test_morning_briefing_marks_exact_boundary_truncation_and_omitted_messages(
    w1_db, tmp_path: Path
):
    db, user = w1_db
    header = _header(1)
    long_body = "A" * (MorningBriefingService.MAX_BODY_CHARS_PER_THREAD + 1)
    long_thread = SimpleNamespace(
        thread_id="thread-1",
        subject="Request 1",
        messages=[
            SimpleNamespace(
                sender="sender-1@example.test",
                date="Fri, 02 Oct 2026 09:00:00 +0700",
                body=long_body,
                plain_body="",
                attachments=[],
            ),
            SimpleNamespace(
                sender="sender-1@example.test",
                date="Fri, 02 Oct 2026 09:05:00 +0700",
                body="SECOND_MESSAGE_MUST_BE_EXPLICITLY_OMITTED",
                plain_body="",
                attachments=[],
            ),
        ],
    )
    registry = RecordingRegistry([header], {"thread-1": long_thread})

    result = await MorningBriefingService(_settings(tmp_path), registry).generate_brief(
        user, db, request_id="w1-boundary"
    )

    body_lines = [line[6:] for line in result["summary"].splitlines() if line.startswith("    > ")]
    assert len(body_lines) == 1
    assert len(body_lines[0]) == MorningBriefingService.MAX_BODY_CHARS_PER_THREAD
    assert body_lines[0].endswith("…")
    assert "Nội dung đã rút gọn theo giới hạn bản tin" in result["summary"]
    assert "Còn 1 thư trong cuộc trao đổi chưa được đưa vào bản tin" in result["summary"]
    assert result["body_failure_count"] == 1
