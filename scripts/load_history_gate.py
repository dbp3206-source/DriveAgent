"""Quota-free history scale gate for the local SQLite/API pagination path.

The benchmark uses a temporary database and never touches ``data/`` or Google.
It deliberately measures the same FastAPI cursor endpoints used by the UI.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import tempfile
import time
import tracemalloc
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

SESSION_COUNT = 5_000
MESSAGE_COUNT = 50_000
PAGE_SAMPLES = 30


async def main() -> None:
    # Import app modules only after adding the backend package to sys.path.
    # Keeping this local avoids a module-level import-order exception in Ruff
    # while preserving the script's standalone invocation from the repo root.
    from app.api.chat import router
    from app.api.dependencies import get_current_user
    from app.db.models import Base, ChatSession, Message, User
    from app.db.session import get_db

    with tempfile.TemporaryDirectory(prefix="driveagent-history-gate-") as temp:
        database = Path(temp) / "load.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{database}")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        user_id = str(uuid4())
        now = datetime.now(UTC)
        session_rows: list[dict] = []
        message_rows: list[dict] = []
        tracemalloc.start()
        seed_started = time.perf_counter()
        for index in range(SESSION_COUNT):
            session_id = str(uuid4())
            at = now - timedelta(seconds=index)
            session_rows.append(
                {
                    "id": session_id,
                    "user_id": user_id,
                    "title": f"Scale session {index}",
                    "created_at": at,
                    "updated_at": at,
                }
            )
            for message_index in range(MESSAGE_COUNT // SESSION_COUNT):
                message_rows.append(
                    {
                        "id": str(uuid4()),
                        "session_id": session_id,
                        "user_id": user_id,
                        "role": "user" if message_index % 2 == 0 else "assistant",
                        "content": f"Message {message_index} in session {index}",
                        "citations_json": "[]",
                        "trace_json": "[]",
                        "status": "completed",
                        "created_at": at + timedelta(milliseconds=message_index),
                    }
                )

        async with engine.begin() as connection:
            await connection.execute(
                User.__table__.insert(),
                [{"id": user_id, "email": "scale@test.invalid", "display_name": "Scale"}],
            )
            await connection.execute(ChatSession.__table__.insert(), session_rows)
            await connection.execute(Message.__table__.insert(), message_rows)
        seed_seconds = time.perf_counter() - seed_started
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        app = FastAPI()
        app.include_router(router)

        async def current_user() -> User:
            async with factory() as db:
                user = await db.get(User, user_id)
                assert user is not None
                return user

        async def request_db():  # type: ignore[no-untyped-def]
            async with factory() as db:
                yield db

        app.dependency_overrides[get_current_user] = current_user
        app.dependency_overrides[get_db] = request_db

        latencies: list[float] = []
        seen: set[str] = set()
        cursor: str | None = None
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://scale.test"
        ) as client:
            for _ in range(PAGE_SAMPLES):
                started = time.perf_counter()
                response = await client.get(
                    "/api/chat/sessions-page",
                    params={"limit": 100, **({"cursor": cursor} if cursor else {})},
                )
                latencies.append((time.perf_counter() - started) * 1000)
                response.raise_for_status()
                page = response.json()
                ids = {item["id"] for item in page["items"]}
                if seen & ids:
                    raise RuntimeError("Cursor pagination returned duplicate sessions")
                seen |= ids
                cursor = page["next_cursor"]

            session_id = session_rows[0]["id"]
            messages = await client.get(
                f"/api/chat/sessions/{session_id}/messages-page", params={"limit": 6}
            )
            messages.raise_for_status()
            if len(messages.json()["items"]) != 6:
                raise RuntimeError("Message pagination returned an unexpected page")

        ordered = sorted(latencies)
        p95 = ordered[max(0, int(len(ordered) * 0.95 + 0.9999) - 1)]
        result = {
            "status": "pass",
            "database": "temporary",
            "sessions": SESSION_COUNT,
            "messages": MESSAGE_COUNT,
            "pages_sampled": PAGE_SAMPLES,
            "unique_sessions_seen": len(seen),
            "seed_seconds": round(seed_seconds, 3),
            "latency_p50_ms": round(statistics.median(latencies), 3),
            "latency_p95_ms": round(p95, 3),
            "python_peak_mib_during_seed": round(peak_bytes / 1024 / 1024, 2),
            "database_mib": round(database.stat().st_size / 1024 / 1024, 2),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
