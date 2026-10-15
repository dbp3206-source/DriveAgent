"""Real isolated SQLite age clocks; no Gemini, Google or production data."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db import models
from app.db.migrations import _content_clocks
from app.db.models import Base, CompanyProfile, LongTermMemory, SavedArtifact, User
from app.services.artifacts import ArtifactWrite, save_artifact
from app.services.retention_policy import utc
from app.tools.contracts import ToolContext

OLD = datetime(2026, 9, 1, 12, tzinfo=UTC)
NEW = OLD + timedelta(days=40)
NOW_TEXT = "2026-10-15T12:00:00+00:00"


@pytest.mark.parametrize("model,values,field,new_value", [
    (SavedArtifact, {"creation_key": "synthetic", "title": "Note", "content": "Old"},
     "content", "New"),
    (LongTermMemory, {"kind": "fact", "content": "Old", "normalized_hash": "synthetic"},
     "content", "New"),
    (LongTermMemory, {"kind": "fact", "content": "Old", "normalized_hash": "synthetic"},
     "tags_json", '["new-tag"]'),
    (CompanyProfile, {"name": "Synthetic", "normalized_name": "synthetic",
                      "domain": "example.invalid", "source_url": "https://example.invalid"},
     "notes", "New synthetic note"),
])
async def test_only_content_changes_extend_content_age(
    tmp_path, monkeypatch, model, values, field, new_value,
):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'age.db'}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            owner = User(email="retention@example.invalid", display_name="Synthetic owner")
            db.add(owner)
            await db.flush()
            row = model(user_id=owner.id, created_at=OLD, updated_at=OLD,
                        content_updated_at=OLD, **values)
            db.add(row)
            await db.commit()
            monkeypatch.setattr(models, "utc_now", lambda: NEW)
            await db.get(model, row.id)
            await db.commit()
            assert utc(row.content_updated_at) == OLD
            if model is CompanyProfile:
                row.last_verified_at = NEW
                row.updated_at = NEW
            else:
                row.is_archived = True
            await db.commit()
            assert utc(row.content_updated_at) == OLD
            setattr(row, field, getattr(row, field))
            await db.commit()
            assert utc(row.content_updated_at) == OLD
            setattr(row, field, new_value)
            await db.commit()
            assert utc(row.content_updated_at) == NEW
            row_id = row.id
        async with async_sessionmaker(engine)() as db:
            reopened = await db.get(model, row_id)
            assert utc(reopened.content_updated_at) == NEW
            assert getattr(reopened, field) == new_value
    finally:
        await engine.dispose()


async def test_fenced_artifact_bulk_write_does_not_extend_age_on_archive_or_same_text(
    tmp_path, monkeypatch,
):
    from app.services import artifacts

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'artifact-age.db'}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            owner = User(email="artifact-age@example.invalid", display_name="Synthetic")
            db.add(owner)
            await db.flush()
            row = SavedArtifact(
                user_id=owner.id, creation_key=str(uuid4()), title="Synthetic report",
                content="Synthetic content", content_updated_at=OLD,
                created_at=OLD, updated_at=OLD,
            )
            db.add(row)
            await db.commit()
            context = ToolContext(request_id="synthetic-age", user=owner, db=db,
                                  settings=Settings(_env_file=None))
            monkeypatch.setattr(artifacts, "utc_now", lambda: NEW)
            payload = ArtifactWrite(
                artifact_id=row.id, creation_key=row.creation_key, title=row.title,
                content=row.content, is_archived=True,
            )
            archived = await save_artifact(payload, context)
            await db.commit()
            assert archived.revision == 2 and archived.is_archived
            assert utc(row.content_updated_at) == OLD
            unchanged = payload.model_copy(update={"expected_revision": 2})
            await save_artifact(unchanged, context)
            await db.commit()
            assert utc(row.content_updated_at) == OLD
            changed = payload.model_copy(update={
                "expected_revision": 3, "title": "Updated synthetic report",
            })
            await save_artifact(changed, context)
            await db.commit()
            assert utc(row.content_updated_at) == NEW
            assert row.revision == 4 and row.title == changed.title
            assert (await db.scalars(select(SavedArtifact))).all() == [row]
    finally:
        await engine.dispose()


def test_legacy_clock_upgrade_preserves_content_and_known_dates_idempotently(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy-clocks.db'}")
    try:
        with engine.begin() as db:
            for table in ("saved_artifacts", "long_term_memories", "company_profiles"):
                db.exec_driver_sql(
                    f"CREATE TABLE {table} (id TEXT PRIMARY KEY, content TEXT, "
                    "created_at DATETIME, updated_at DATETIME)"
                )
                db.exec_driver_sql(
                    f"INSERT INTO {table} VALUES (?, ?, ?, ?)",
                    ("synthetic-old", "Synthetic content", OLD.isoformat(), NEW.isoformat()),
                )
            _content_clocks(db)
            _content_clocks(db)
            for table in ("saved_artifacts", "long_term_memories", "company_profiles"):
                content, age = db.exec_driver_sql(
                    f"SELECT content, content_updated_at FROM {table}"
                ).one()
                assert content == "Synthetic content"
                assert datetime.fromisoformat(age) == NEW
                # A later general timestamp must not overwrite the backfilled clock.
                db.exec_driver_sql(f"UPDATE {table} SET updated_at=?", (NOW_TEXT,))
            _content_clocks(db)
            for table in ("saved_artifacts", "long_term_memories", "company_profiles"):
                assert db.exec_driver_sql(
                    f"SELECT content_updated_at FROM {table}"
                ).scalar_one() == NEW.isoformat()
    finally:
        engine.dispose()
