"""Real FK-enabled SQL removal/checkpoints; external objects are NOT purged here."""

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import models as m
from app.services import cleanup_jobs
from app.services.retention_application import application_purge_references, purge_application
from app.services.retention_inventory import POLICIES, application_inventory
from app.services.retention_policy import (
    REQUIRED_INVENTORIES,
    RetentionPolicy,
    RetentionPolicyError,
)

OLD = datetime(2026, 9, 1, 12, tzinfo=UTC)
NOW = OLD + timedelta(days=45)
BODY = "SYNTHETIC_OLD_CONTENT_PRESENT_IN_EVERY_APPLICATION_STORE"


@pytest.fixture
async def data(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'application.db'}")

    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    try:
        async with engine.begin() as db:
            await db.run_sync(m.Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as db:
            user = m.User(email="application-a@example.invalid", display_name="Synthetic A")
            other = m.User(email="application-b@example.invalid", display_name="Synthetic B")
            db.add_all([user, other])
            await db.flush()
            chat = m.ChatSession(user_id=user.id, title=BODY, summary=BODY,
                                 created_at=OLD, updated_at=OLD)
            source = m.LocalSource(user_id=user.id, name="synthetic.txt", content=BODY,
                                   content_hash="d" * 64, created_at=OLD)
            db.add_all([chat, source])
            await db.flush()
            message = m.Message(user_id=user.id, session_id=chat.id, role="assistant",
                                content=BODY, created_at=OLD)
            db.add(message)
            await db.flush()
            rows = [
                chat, source, message,
                m.ChatTask(user_id=user.id, session_id=chat.id, client_key=str(uuid4()),
                           payload_json=json.dumps({"body": BODY}), result_json=json.dumps({
                               "body": BODY}), status="completed", created_at=OLD),
                m.ResponseFeedback(user_id=user.id, message_id=message.id, rating=1,
                                   comment=BODY, created_at=OLD, updated_at=OLD),
                m.CreationProposalRecord(user_id=user.id, message_id=message.id, ordinal=0,
                                           spec_json=json.dumps({"body": BODY}), created_at=OLD),
                m.PdfIngestionJob(user_id=user.id, name="synthetic.pdf", content_hash="e" * 64,
                                  size_bytes=1, status="completed", source_id=source.id,
                                  checkpoint_json=json.dumps([{"body": BODY}]),
                                  created_at=OLD, updated_at=OLD),
                m.DriveFileIndex(user_id=user.id, drive_file_id=f"local:{source.id}", name=BODY,
                                 mime_type="text/plain", content_hash="d" * 64, chunk_count=1,
                                 indexed_at=OLD),
                m.DocumentChunk(id=str(uuid4()), user_id=user.id,
                                drive_file_id=f"local:{source.id}", file_name=BODY,
                                mime_type="text/plain", chunk_index=0, content=BODY,
                                created_at=OLD),
                m.LongTermMemory(user_id=user.id, kind="fact", content=BODY,
                                 normalized_hash="d" * 64, is_archived=True,
                                 created_at=OLD, updated_at=OLD, content_updated_at=OLD),
                m.SavedArtifact(user_id=user.id, creation_key=str(uuid4()), title=BODY,
                                content=BODY, is_archived=True, content_updated_at=OLD,
                                created_at=OLD, updated_at=OLD),
                m.CompanyProfile(user_id=user.id, name=BODY, normalized_name="synthetic",
                                  domain="example.invalid", notes=BODY,
                                  source_url="https://example.invalid", last_verified_at=OLD,
                                  created_at=OLD, updated_at=OLD, content_updated_at=OLD),
                m.ScheduledJob(user_id=user.id, kind="synthetic", dedupe_key=str(uuid4()),
                                payload_json=json.dumps({"body": BODY}),
                                checkpoint_json=json.dumps({"body": BODY}), status="completed",
                                created_at=OLD, updated_at=OLD),
                m.AuditEvent(user_id=user.id, request_id=str(uuid4()), tool_name="synthetic",
                             arguments_json=json.dumps({"body": BODY}),
                             result_json=json.dumps({"body": BODY}), status="success",
                             created_at=OLD, completed_at=OLD),
                m.GraphCheckpoint(user_id=user.id, thread_id=f"{user.id}:{chat.id}",
                                   state_json=json.dumps({"body": BODY}), created_at=OLD),
            ]
            fresh = m.SavedArtifact(user_id=user.id, creation_key=str(uuid4()), title="Fresh",
                                   content="FRESH_SYNTHETIC_CANARY", content_updated_at=NOW,
                                   created_at=NOW, updated_at=NOW)
            foreign = m.SavedArtifact(user_id=other.id, creation_key=str(uuid4()), title="Other",
                                     content="OTHER_OWNER_CANARY", content_updated_at=OLD,
                                     created_at=OLD, updated_at=OLD)
            credential = m.ProviderCredential(user_id=user.id, display_name="Synthetic key",
                                                fingerprint="synthetic", encrypted_secret="FAKE")
            db.add_all([*rows, fresh, foreign, credential])
            await db.commit()
        yield factory, user.id, other.id, rows, fresh.id, foreign.id, credential.id
    finally:
        await engine.dispose()


async def snapshot(factory, owner):
    async with factory() as db:
        result = await application_inventory(db, owner)
    policy = RetentionPolicy("synthetic-application-retention-key-not-used-on-cloud")
    coverage = dict.fromkeys(REQUIRED_INVENTORIES, True)
    preview = policy.prepare(owner_id=owner, candidates=list(result.candidates),
                             inventories=coverage, now=NOW)
    return policy.validate(token=preview.token, owner_id=owner, current=list(result.candidates),
                           inventories=coverage, now=NOW)


async def old_count(factory, owner, rows):
    count = 0
    async with factory() as db:
        for row in rows:
            model = type(row)
            count += await db.scalar(select(func.count()).select_from(model).where(
                model.user_id == owner, model.id == row.id,
            ))
    return count


async def test_all_application_rows_remove_exactly_but_credentials_fresh_and_foreign_remain(data):
    factory, owner, other, rows, fresh, foreign, credential = data
    approved = await snapshot(factory, owner)
    assert len(approved.items) == len(POLICIES) == 15
    async with factory() as db:
        result = await purge_application(db, owner, approved.items, now=NOW.timestamp())
        await db.commit()
    assert result["deleted"] == 15
    assert {item.kind for item in result["external"]} == {"pdf", "drive_chunks", "agent_memories"}
    assert all(item.owner_id == owner for item in result["external"])
    assert len(result["chat_contexts"]) == 1
    assert await old_count(factory, owner, rows) == 0
    async with factory() as db:
        assert (await db.get(m.SavedArtifact, fresh)).content == "FRESH_SYNTHETIC_CANARY"
        assert (await db.get(m.SavedArtifact, foreign)).user_id == other
        assert (await db.get(m.ProviderCredential, credential)).encrypted_secret == "FAKE"
        assert await db.get(m.User, owner) is not None
        assert await db.get(m.User, other) is not None


async def test_content_and_durable_sql_checkpoint_commit_or_roll_back_together(data):
    factory, owner, _other, rows, _fresh, _foreign, _credential = data
    approved = await snapshot(factory, owner)
    async with factory() as db:
        refs = await application_purge_references(db, owner, approved.items)
    job_id = await cleanup_jobs.enqueue(factory, owner, cleanup_jobs.CleanupPlan(
        snapshot=approved, external=refs,
    ), now=NOW.timestamp())
    lease = await cleanup_jobs.claim(factory, now=NOW.timestamp())
    args = (job_id, lease["token"], lease["attempt"])
    async with factory() as db:
        await cleanup_jobs.mark_started(db, *args, now=NOW.timestamp())
        result = await purge_application(db, owner, approved.items, now=NOW.timestamp())
        assert result["external"] == refs
        await cleanup_jobs.mark_sql_done(db, *args, now=NOW.timestamp())
        await db.rollback()
    assert await old_count(factory, owner, rows) == 15
    assert not (await cleanup_jobs.status(factory, owner, job_id))["sql_completed"]
    async with factory() as db:
        await cleanup_jobs.mark_started(db, *args, now=NOW.timestamp())
        await purge_application(db, owner, approved.items, now=NOW.timestamp())
        await cleanup_jobs.mark_sql_done(db, *args, now=NOW.timestamp())
        await db.commit()
    assert await old_count(factory, owner, rows) == 0
    state = await cleanup_jobs.status(factory, owner, job_id)
    assert state["status"] == "purging" and state["remaining_count"] == 3
    assert state["sql_completed"] and state["completed_count"] == 0
    # SQL success is not physical-file/vector success.
    async with factory() as db:
        with pytest.raises(cleanup_jobs.CleanupStateError, match="not_finished"):
            await cleanup_jobs.finish(db, *args, now=NOW.timestamp())


@pytest.mark.parametrize("parent", [m.ChatSession, m.Message, m.LocalSource, m.DriveFileIndex])
async def test_missing_approved_dependencies_block_before_first_delete(data, parent):
    factory, owner, _other, rows, _fresh, _foreign, _credential = data
    approved = await snapshot(factory, owner)
    chosen = [item for item in approved.items
              if item.record_id.startswith(parent.__tablename__ + ":")]
    async with factory() as db:
        with pytest.raises(RetentionPolicyError, match="dependency_not_selected"):
            await purge_application(db, owner, chosen, now=NOW.timestamp())
        await db.rollback()
    assert await old_count(factory, owner, rows) == 15


async def test_foreign_cascade_dependency_is_not_silently_erased(data):
    factory, owner, other, rows, _fresh, _foreign, _credential = data
    message = next(row for row in rows if isinstance(row, m.Message))
    async with factory() as db:
        foreign = m.ResponseFeedback(user_id=other, message_id=message.id, rating=1,
                                     comment="FOREIGN_DEPENDENT_CANARY",
                                     created_at=OLD, updated_at=OLD)
        db.add(foreign)
        await db.commit()
        foreign_id = foreign.id
    approved = await snapshot(factory, owner)
    async with factory() as db:
        with pytest.raises(RetentionPolicyError, match="foreign_dependency"):
            await purge_application(db, owner, approved.items, now=NOW.timestamp())
        await db.rollback()
    assert await old_count(factory, owner, rows) == 15
    async with factory() as db:
        assert (await db.get(m.ResponseFeedback, foreign_id)).comment == "FOREIGN_DEPENDENT_CANARY"


async def test_wrong_owner_changed_payload_and_new_child_do_not_delete_any_rows(data):
    factory, owner, other, rows, _fresh, _foreign, _credential = data
    approved = await snapshot(factory, owner)
    async with factory() as db:
        with pytest.raises(RetentionPolicyError, match="preview_changed"):
            await purge_application(db, other, approved.items, now=NOW.timestamp())
        await db.rollback()
        feedback = next(row for row in rows if isinstance(row, m.ResponseFeedback))
        await db.execute(update(m.ResponseFeedback).where(
            m.ResponseFeedback.id == feedback.id,
        ).values(
            comment="SYNTHETIC_FRESH_REVIEW", updated_at=NOW,
        ))
        await db.commit()
    async with factory() as db:
        with pytest.raises(RetentionPolicyError, match="preview_changed"):
            await purge_application(db, owner, approved.items, now=NOW.timestamp())
        await db.rollback()
    assert await old_count(factory, owner, rows) == 15


async def test_active_chat_work_blocks_purge_and_reference_reads_have_no_side_effect(data):
    factory, owner, _other, rows, _fresh, _foreign, _credential = data
    approved = await snapshot(factory, owner)
    async with factory() as db:
        refs = await application_purge_references(db, owner, approved.items)
        assert len(refs) == 3 and not db.new and not db.dirty and not db.deleted
        task = next(row for row in rows if isinstance(row, m.ChatTask))
        await db.execute(update(m.ChatTask).where(m.ChatTask.id == task.id).values(status="queued"))
        await db.commit()
    async with factory() as db:
        with pytest.raises(RetentionPolicyError, match="owner_busy"):
            await purge_application(db, owner, approved.items, now=NOW.timestamp())
        await db.rollback()
    assert await old_count(factory, owner, rows) == 15
