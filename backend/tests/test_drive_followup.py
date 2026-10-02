import json
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agent.orchestrator import AgentRunResult
from app.agent.routing import Route
from app.api.chat import _drive_followup_route, chat
from app.api.schemas import ChatRequest
from app.db.models import Base, ChatSession, Message, User


def assistant_with_drive(*file_ids: str):
    return SimpleNamespace(
        role="assistant",
        status="completed",
        citations_json=json.dumps(
            [
                {
                    "file_id": file_id,
                    "web_view_link": f"https://drive.google.com/file/d/{file_id}/view",
                }
                for file_id in file_ids
            ]
        ),
    )


def user_turn(content: str):
    return SimpleNamespace(role="user", content=content, citations_json="[]")


def failed_assistant():
    return SimpleNamespace(role="assistant", status="failed", citations_json="[]", content="")


def test_drive_followup_rereads_the_unique_cited_source():
    source_id = "drive-file-0123456789"
    prior = [assistant_with_drive(source_id), user_turn("Tóm tắt tệp PDF gần nhất trong Drive")]

    route = _drive_followup_route("Đào sâu nội dung file đó theo nguyên lý đầu tiên.", prior)

    assert route == Route("drive_read_file", {"file_id": source_id, "max_characters": 20_000})


def test_explicit_new_file_id_overrides_old_followup_source():
    prior = [assistant_with_drive("drive-file-0123456789")]
    assert (
        _drive_followup_route(
            "Phân tích sâu hơn file đó, nhưng dùng file_id: new-file-9876543210",
            prior,
        )
        is None
    )


def test_drive_followup_resolves_implicit_deepening_from_immediate_context():
    source_id = "drive-file-0123456789"
    prior = [
        assistant_with_drive(source_id),
        user_turn("Tóm tắt tệp PDF gần nhất trong Drive"),
    ]

    route = _drive_followup_route("Phân tích sâu hơn theo first principles.", prior)

    assert route == Route("drive_read_file", {"file_id": source_id, "max_characters": 20_000})


def test_drive_followup_survives_a_failed_uncited_assistant_turn():
    source_id = "drive-file-0123456789"
    prior = [
        failed_assistant(),
        user_turn("Đào sâu nội dung tài liệu đó"),
        assistant_with_drive(source_id, source_id),  # PDF page citations dedupe by file.
        user_turn("Tóm tắt tệp PDF gần nhất trong Drive"),
    ]

    route = _drive_followup_route("Mở rộng phần thứ hai trong tài liệu đó.", prior)

    assert route == Route("drive_read_file", {"file_id": source_id, "max_characters": 20_000})


def test_drive_followup_asks_when_previous_answer_cited_multiple_files():
    route = _drive_followup_route(
        "Phân tích sâu nội dung các tệp đó.",
        [assistant_with_drive("drive-file-0123456789", "drive-file-9876543210")],
    )

    assert route is not None
    assert route.direct
    assert route.required_sources == ("drive",)
    assert route.tool is None
    assert "nhiều tệp Drive" in (route.clarification or "")


def test_drive_followup_does_not_guess_after_a_topic_change_or_without_source():
    old_source = [
        SimpleNamespace(role="assistant", status="completed", citations_json="[]"),
        user_turn("Giải thích truy vấn SQL này"),
        assistant_with_drive("drive-file-0123456789"),
    ]

    assert _drive_followup_route("Đào sâu nội dung file đó.", old_source) is None
    assert (
        _drive_followup_route(
            "Giải thích khái niệm marketing này.",
            [assistant_with_drive("drive-file-0123456789")],
        )
        is None
    )
    assert _drive_followup_route("Đào sâu nội dung file đó.", [failed_assistant()]) is None


def test_drive_followup_ignores_non_google_or_malformed_citations():
    prior = [
        SimpleNamespace(
            role="assistant",
            status="completed",
            citations_json=json.dumps(
                [
                    {"file_id": "local:private-id", "web_view_link": "/local/private-id"},
                    {
                        "file_id": "attacker-controlled-id",
                        "web_view_link": "https://example.com/file/view",
                    },
                ]
            ),
        )
    ]

    assert _drive_followup_route("Đào sâu nội dung file đó.", prior) is None


class CapturingOrchestrator:
    def __init__(self):
        self.calls = []

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        return AgentRunResult(answer="Đã đọc lại đúng tệp.", plan=[], trace=[], citations=[])


async def test_chat_api_passes_persisted_drive_source_to_followup_orchestrator(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'drive-followup.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    orchestrator = CapturingOrchestrator()
    source_id = "drive-file-0123456789"
    async with factory() as db:
        user = User(
            email="drive-followup@example.com", display_name="Drive follow-up", role="editor"
        )
        db.add(user)
        await db.flush()
        session = ChatSession(user_id=user.id)
        db.add(session)
        await db.flush()
        db.add_all(
            [
                Message(
                    user_id=user.id,
                    session_id=session.id,
                    role="user",
                    content="Tóm tắt tệp PDF gần nhất trong Drive.",
                ),
                Message(
                    user_id=user.id,
                    session_id=session.id,
                    role="assistant",
                    content="Tệp nói về một chủ đề cụ thể.",
                    citations_json=json.dumps(
                        [
                            {
                                "file_id": source_id,
                                "file_name": "Private QA file",
                                "web_view_link": (
                                    f"https://drive.google.com/file/d/{source_id}/view"
                                ),
                                "chunk_index": 0,
                            }
                        ]
                    ),
                ),
            ]
        )
        await db.commit()
        request = SimpleNamespace(
            state=SimpleNamespace(request_id="drive-followup-request"),
            app=SimpleNamespace(state=SimpleNamespace(orchestrator=orchestrator)),
        )

        response = await chat(
            ChatRequest(
                message="Đào sâu nội dung file đó, đừng tìm một tệp khác.",
                session_id=session.id,
            ),
            request,
            user,
            db,
        )

        assert response.session_id == session.id
        assert len(orchestrator.calls) == 1
        assert orchestrator.calls[0]["route_override"] == Route(
            "drive_read_file", {"file_id": source_id, "max_characters": 20_000}
        )
    await engine.dispose()
