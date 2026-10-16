"""Real isolated SQL reads: inventory/age/ownership, never proof of deletion."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Column, String, Table
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import models as m
from app.services.retention_inventory import (
    POLICIES,
    application_inventory,
    validate_application_catalog,
)
from app.services.retention_policy import RetentionPolicy, RetentionPolicyError, utc

OLD = datetime(2026, 9, 1, 12, tzinfo=UTC)
NOW = OLD + timedelta(days=40)


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'inventory.db'}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(m.Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            yield session
    finally:
        await engine.dispose()


async def owner(db, suffix="a"):
    row = m.User(email=f"{suffix}@example.invalid", display_name="Synthetic")
    db.add(row)
    await db.flush()
    return row


async def test_all_application_tables_are_explicitly_classified_and_unknown_table_blocks(db):
    validate_application_catalog()
    unknown = Table("synthetic_unclassified_content", m.Base.metadata,
                    Column("id", String, primary_key=True))
    try:
        with pytest.raises(RetentionPolicyError, match="catalog_incomplete"):
            await application_inventory(db, "synthetic-owner")
    finally:
        m.Base.metadata.remove(unknown)
    validate_application_catalog()


async def test_read_includes_archived_rows_not_identity_keys_or_other_owners(db):
    own, other = await owner(db), await owner(db, "b")
    for user in (own, other):
        db.add_all([
            m.LongTermMemory(user_id=user.id, kind="fact", content="PRIVATE_SYNTHETIC_SENTINEL",
                             normalized_hash="synthetic", is_archived=True,
                             content_updated_at=OLD, created_at=OLD, updated_at=NOW),
            m.SavedArtifact(user_id=user.id, creation_key=str(uuid4()), title="Synthetic",
                            content="PRIVATE_SYNTHETIC_SENTINEL", is_archived=True,
                            content_updated_at=OLD, created_at=OLD, updated_at=NOW),
            m.ProviderCredential(user_id=user.id, display_name="Synthetic key",
                                 fingerprint=user.id, encrypted_secret="not-a-real-credential"),
        ])
    await db.commit()
    result = await application_inventory(db, own.id)
    assert len(result.candidates) == 2 and not result.owner_busy
    assert all(item.owner_id == own.id and item.changed_at == OLD for item in result.candidates)
    assert "PRIVATE_SYNTHETIC_SENTINEL" not in repr(result)
    assert "not-a-real-credential" not in repr(result)
    assert other.id not in repr(result)
    assert result.policy_checks()["application"] is True
    with pytest.raises(RetentionPolicyError, match="inventory_incomplete"):
        RetentionPolicy("synthetic-key-long-enough-for-inventory-tests").prepare(
            owner_id=own.id, candidates=list(result.candidates),
            inventories=result.policy_checks(), now=NOW,
        )
    assert not db.new and not db.dirty and not db.deleted


async def test_new_message_in_old_chat_protects_parent_but_keeps_old_turn_visible(db):
    user = await owner(db)
    chat = m.ChatSession(user_id=user.id, title="Synthetic", created_at=OLD, updated_at=OLD)
    db.add(chat)
    await db.flush()
    old = m.Message(user_id=user.id, session_id=chat.id, role="user", content="Old synthetic",
                    created_at=OLD)
    fresh = m.Message(user_id=user.id, session_id=chat.id, role="assistant",
                      content="Fresh synthetic", created_at=NOW)
    db.add_all([old, fresh])
    await db.commit()
    result = await application_inventory(db, user.id)
    rows = {item.record_id: item for item in result.candidates}
    assert rows[f"chat_sessions:{chat.id}"].changed_at == NOW
    assert rows[f"messages:{old.id}"].changed_at == OLD
    assert rows[f"messages:{fresh.id}"].changed_at == NOW
    assert len(rows) == 3


@pytest.mark.parametrize("kind", ["feedback", "proposal", "task"])
async def test_fresh_dependent_content_protects_older_chat_and_message(db, kind):
    user = await owner(db)
    chat = m.ChatSession(user_id=user.id, title="Synthetic", created_at=OLD, updated_at=OLD)
    db.add(chat)
    await db.flush()
    message = m.Message(user_id=user.id, session_id=chat.id, role="assistant",
                        content="Synthetic old answer", created_at=OLD)
    db.add(message)
    await db.flush()
    related = {
        "feedback": m.ResponseFeedback(user_id=user.id, message_id=message.id, rating=1,
                                       comment="Synthetic fresh review",
                                       created_at=NOW, updated_at=NOW),
        "proposal": m.CreationProposalRecord(user_id=user.id, message_id=message.id,
                                              ordinal=0, spec_json="{}", created_at=NOW),
        "task": m.ChatTask(user_id=user.id, session_id=chat.id, client_key=str(uuid4()),
                           payload_json="{}", status="completed", created_at=NOW),
    }[kind]
    db.add(related)
    await db.commit()
    result = await application_inventory(db, user.id)
    rows = {item.record_id: item for item in result.candidates}
    assert rows[f"chat_sessions:{chat.id}"].changed_at == NOW
    assert rows[f"messages:{message.id}"].changed_at == (OLD if kind == "task" else NOW)
    policy = RetentionPolicy("synthetic-parent-protection-key-not-used-on-cloud")
    preview = policy.prepare(owner_id=user.id, candidates=list(result.candidates),
                             inventories=dict.fromkeys(result.policy_checks(), True), now=NOW)
    assert preview.selected_count == (1 if kind == "task" else 0)


async def test_foreign_child_reference_does_not_refresh_another_owners_content(db):
    user, other = await owner(db), await owner(db, "b")
    chat = m.ChatSession(user_id=user.id, title="Synthetic", created_at=OLD, updated_at=OLD)
    db.add(chat)
    await db.flush()
    message = m.Message(user_id=user.id, session_id=chat.id, role="assistant",
                        content="Synthetic old answer", created_at=OLD)
    db.add(message)
    await db.flush()
    db.add(m.ResponseFeedback(user_id=other.id, message_id=message.id, rating=1,
                              created_at=NOW, updated_at=NOW))
    await db.commit()
    result = await application_inventory(db, user.id)
    assert len(result.candidates) == 2
    assert all(row.changed_at == OLD for row in result.candidates)


@pytest.mark.parametrize("model,values", [
    (m.ChatTask, {"client_key": "synthetic", "payload_json": "{}", "status": "queued"}),
    (m.ScheduledJob, {"kind": "synthetic", "dedupe_key": "synthetic", "status": "running"}),
    (m.PdfIngestionJob, {"name": "synthetic.pdf", "content_hash": "synthetic", "size_bytes": 1,
                         "status": "queued"}),
])
async def test_inflight_work_blocks_application_readiness(db, model, values):
    user = await owner(db)
    if model is m.ChatTask:
        chat = m.ChatSession(user_id=user.id)
        db.add(chat)
        await db.flush()
        values = values | {"session_id": chat.id}
    db.add(model(user_id=user.id, created_at=OLD, **values))
    await db.commit()
    result = await application_inventory(db, user.id)
    assert result.owner_busy and result.policy_checks()["application"] is False
    assert any(item.active for item in result.candidates)


async def test_fresh_reads_change_no_clock_but_content_change_invalidates_fingerprint(db):
    user = await owner(db)
    row = m.LongTermMemory(user_id=user.id, kind="fact", content="Synthetic old note",
                           normalized_hash="synthetic", created_at=OLD, updated_at=OLD,
                           content_updated_at=OLD)
    db.add(row)
    await db.commit()
    original = await application_inventory(db, user.id)
    assert await application_inventory(db, user.id) == original
    row.content = "Synthetic changed note"
    await db.commit()
    changed = await application_inventory(db, user.id)
    assert changed.candidates[0].fingerprint != original.candidates[0].fingerprint
    assert changed.candidates[0].changed_at > OLD
    assert not db.new and not db.dirty and not db.deleted


async def test_every_content_table_is_read_without_ui_page_truncation(db):
    user = await owner(db)
    shared_id = str(uuid4())
    chat = m.ChatSession(id=shared_id, user_id=user.id, title="Synthetic")
    rows = [
        chat,
        m.Message(id=shared_id, user_id=user.id, session_id=shared_id, role="user",
                  content="Synthetic old turn"),
        m.ChatTask(id=shared_id, user_id=user.id, session_id=shared_id,
                   client_key=str(uuid4()), payload_json="{}", status="completed"),
        m.ResponseFeedback(id=shared_id, user_id=user.id, message_id=shared_id, rating=1),
        m.CreationProposalRecord(id=shared_id, user_id=user.id, message_id=shared_id,
                                 ordinal=0, spec_json="{}"),
        m.LocalSource(id=shared_id, user_id=user.id, name="synthetic.txt",
                      content="Synthetic source", content_hash="synthetic"),
        m.PdfIngestionJob(id=shared_id, user_id=user.id, name="synthetic.pdf",
                          content_hash="synthetic", size_bytes=1, status="completed",
                          source_id=shared_id),
        m.DriveFileIndex(id=shared_id, user_id=user.id, drive_file_id="synthetic-file",
                         name="Synthetic", mime_type="text/plain", content_hash="synthetic"),
        m.DocumentChunk(id=shared_id, user_id=user.id, drive_file_id="synthetic-file",
                        file_name="Synthetic", mime_type="text/plain", chunk_index=0,
                        content="Synthetic chunk"),
        m.LongTermMemory(id=shared_id, user_id=user.id, kind="fact", content="Synthetic note",
                         normalized_hash="synthetic"),
        m.SavedArtifact(id=shared_id, user_id=user.id, creation_key=str(uuid4()),
                        title="Synthetic", content="Synthetic artifact"),
        m.CompanyProfile(id=shared_id, user_id=user.id, name="Synthetic",
                         normalized_name="synthetic", domain="example.invalid",
                         source_url="https://example.invalid"),
        m.ScheduledJob(id=shared_id, user_id=user.id, kind="morning", dedupe_key="synthetic",
                       status="completed"),
        m.AuditEvent(id=shared_id, user_id=user.id, request_id="synthetic", tool_name="synthetic",
                     status="success"),
        m.GraphCheckpoint(id=shared_id, user_id=user.id, thread_id="synthetic", state_json="{}"),
    ]
    for row in rows:
        for field in ("created_at", "updated_at", "content_updated_at", "indexed_at"):
            if hasattr(type(row), field):
                setattr(row, field, OLD)
    db.add_all(rows)
    for index in range(205):
        db.add(m.LocalSource(user_id=user.id, name=f"synthetic-{index}.txt",
                             content="Synthetic", content_hash=f"synthetic-{index}",
                             created_at=OLD))
    await db.commit()
    result = await application_inventory(db, user.id)
    assert len(rows) == len(POLICIES)
    assert len(result.candidates) == len(POLICIES) + 205
    assert len({item.key for item in result.candidates}) == len(result.candidates)
    assert all(item.changed_at == OLD for item in result.candidates)
    assert not result.owner_busy and not db.new and not db.dirty and not db.deleted


async def test_replaced_source_uses_its_own_publication_not_creation_or_other_owner(db):
    user, other = await owner(db), await owner(db, "b")
    source = m.LocalSource(user_id=user.id, name="synthetic.pdf", content="Synthetic original",
                           content_hash="original", created_at=OLD)
    db.add(source)
    await db.flush()
    job = m.PdfIngestionJob(user_id=user.id, name="synthetic.pdf", content_hash="synthetic",
                            size_bytes=1, status="completed", source_id=source.id,
                            created_at=OLD, updated_at=OLD)
    # A malformed cross-owner reference must neither leak nor extend the source age.
    foreign = m.PdfIngestionJob(user_id=other.id, name="foreign-synthetic.pdf",
                                content_hash="foreign", size_bytes=1, status="completed",
                                source_id=source.id, created_at=NOW, updated_at=NOW)
    db.add_all([job, foreign])
    await db.commit()
    original = await application_inventory(db, user.id)
    before = next(item for item in original.candidates
                  if item.record_id == f"local_sources:{source.id}")
    assert before.changed_at == OLD
    # Mirror the actual worker's one-transaction publish to an existing source.
    source.content, source.content_hash, job.updated_at = "Synthetic replacement", "changed", NOW
    await db.commit()
    updated = await application_inventory(db, user.id)
    after = next(item for item in updated.candidates
                 if item.record_id == f"local_sources:{source.id}")
    assert utc(source.created_at) == OLD and after.changed_at == NOW
    assert after.fingerprint != before.fingerprint
    assert len(updated.candidates) == 2 and not updated.owner_busy
