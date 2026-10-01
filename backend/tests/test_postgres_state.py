"""Real PostgreSQL contract, mandatory in CI; never uses a personal database."""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from app.services.relational_skills import RelationalSkillStore
from app.services.skills import SkillSpec
from app.tools.contracts import ToolError


def test_postgres_skills_owner_revision_concurrency_and_restart():
    url = os.environ.get("VERIDRA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("No isolated PostgreSQL test service; not proof of cloud readiness")
    parsed = make_url(url)
    if parsed.database != "veridra_ci" or parsed.drivername != "postgresql+psycopg":
        pytest.fail("PostgreSQL contract only permits the isolated veridra_ci database")
    engine = create_engine(url, pool_size=4, max_overflow=0)
    RelationalSkillStore.create_schema(engine)
    owner = f"test-{uuid4()}"
    spec = SkillSpec(name="daily_report", title="Daily report", description="Source report",
                     goal="Summarize {date}", procedure=["Read {date}", "Verify sources"],
                     output_format="Markdown")
    store = RelationalSkillStore(engine)
    try:
        created = store.save(owner, spec)
        with pytest.raises(ToolError):
            store.get("other-owner", created["id"])

        def edit(_):
            try:
                store.save(owner, spec, expected_revision=1)
                return "saved"
            except ToolError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(edit, range(4)))
        assert results.count("saved") == 1
        assert results.count("revision_conflict") == 3
        assert store.run(owner, spec.name, {"date": "2026-09-30"})["goal"] == (
            "Summarize 2026-09-30"
        )
    finally:
        engine.dispose()
    reopened = create_engine(url)
    try:
        store = RelationalSkillStore(reopened)
        assert store.get(owner, created["id"])["revision"] == 2
        assert store.archive(owner, created["id"])["active"] is False
        assert not store.list(owner)
    finally:
        reopened.dispose()


def test_postgres_queue_parallel_enqueue_claim_and_stale_worker():
    from app.services.durable_evaluation import LeaseLostError
    from app.services.relational_evaluation import RelationalEvaluationQueue

    url = os.environ.get("VERIDRA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("No isolated PostgreSQL test service; not proof of cloud readiness")
    parsed = make_url(url)
    if parsed.database != "veridra_ci" or parsed.drivername != "postgresql+psycopg":
        pytest.fail("PostgreSQL contract only permits the isolated veridra_ci database")
    engine = create_engine(url, pool_size=4, max_overflow=0)
    RelationalEvaluationQueue.create_schema(engine)
    queue = RelationalEvaluationQueue(engine)
    owner = f"queue-{uuid4()}"
    try:
        def enqueue(_):
            try:
                return queue.enqueue(owner, 1)
            except ValueError:
                return None

        with ThreadPoolExecutor(max_workers=4) as pool:
            identifiers = [value for value in pool.map(enqueue, range(4)) if value]
        assert len(identifiers) == 2
        assert queue.get("other-owner", identifiers[0]) is None
        with ThreadPoolExecutor(max_workers=4) as pool:
            claims = [value for value in pool.map(lambda _: queue.claim(2), range(4)) if value]
        assert {row["id"] for row in claims} == set(identifiers)
        assert len(claims) == 2
        first = claims[0]
        queue.checkpoint(first["id"], {"routing": {"pass_rate": 1}}, 3,
                         attempt=first["attempts"])
        # Finish the second job so recovery deterministically returns the first.
        queue.finish(claims[1]["id"], "completed", now=4, attempt=claims[1]["attempts"])
        recovered = queue.claim(124)
        assert recovered["id"] == first["id"]
        assert "routing" in recovered["checkpoint"]
        with pytest.raises(LeaseLostError):
            queue.finish(first["id"], "completed", now=125, attempt=first["attempts"])
        queue.finish(recovered["id"], "completed", now=126, attempt=recovered["attempts"])
    finally:
        engine.dispose()


def test_postgres_quota_serializes_reservations_across_guards():
    from app.services.relational_circuit import RelationalCircuitStore
    from app.services.relational_circuit import metadata as circuit_metadata
    from app.services.relational_quota import RelationalQuotaGuard

    url = os.environ.get("VERIDRA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("No isolated PostgreSQL test service; not proof of cloud readiness")
    parsed = make_url(url)
    if parsed.database != "veridra_ci" or parsed.drivername != "postgresql+psycopg":
        pytest.fail("PostgreSQL contract only permits the isolated veridra_ci database")
    engine = create_engine(url, pool_size=4, max_overflow=0)
    RelationalQuotaGuard.create_schema(engine)
    circuit_metadata.create_all(engine)
    credential = f"synthetic-{uuid4()}"
    try:
        def reserve(_):
            try:
                RelationalQuotaGuard(engine, credential=credential).reserve("flash", 10, now=100)
                return "reserved"
            except ToolError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(reserve, range(12)))
        assert results.count("reserved") == 5
        assert results.count("quota_minute_exhausted") == 7
        assert RelationalQuotaGuard(engine, credential=credential).daily_count(
            "flash", now=100
        ) == 5
        class Failure(Exception):
            code = 503

        circuit = RelationalCircuitStore(engine, credential)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: circuit.failure("generate", Failure(), now=100), range(4)))
        assert circuit.snapshot(now=101)[0]["consecutive_failures"] == 4
        with pytest.raises(ToolError):
            circuit.before_request("generate", now=101)
        circuit.success("generate", now=102)
        assert not circuit.snapshot(now=102)[0]["circuit_open"]
    finally:
        engine.dispose()


def test_postgres_private_schema_translation_is_not_public():
    from sqlalchemy import text

    from app.services.relational_skills import metadata as skill_metadata
    from app.services.relational_state import prepare_state_schema

    url = os.environ.get("VERIDRA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("No isolated PostgreSQL test service; not proof of cloud readiness")
    parsed = make_url(url)
    if parsed.database != "veridra_ci" or parsed.drivername != "postgresql+psycopg":
        pytest.fail("PostgreSQL contract only permits the isolated veridra_ci database")
    engine = create_engine(url).execution_options(schema_translate_map={None: "veridra_private"})
    try:
        prepare_state_schema(engine)
        skill_metadata.create_all(engine)
        owner = f"private-{uuid4()}"
        store = RelationalSkillStore(engine)
        spec = SkillSpec(name="private_report", title="Private report", description="Private test",
                         goal="Report", procedure=["Read"], output_format="Markdown")
        created = store.save(owner, spec)
        with engine.connect() as db:
            assert db.execute(text(
                "SELECT count(*) FROM veridra_private.skills WHERE id=:id"
            ), {"id": created["id"]}).scalar_one() == 1
            if db.execute(text("SELECT to_regclass('public.skills')")).scalar_one() is not None:
                assert db.execute(text(
                    "SELECT count(*) FROM public.skills WHERE id=:id"
                ), {"id": created["id"]}).scalar_one() == 0
    finally:
        engine.dispose()


def test_postgres_operation_ledger_serializes_claim_and_survives_restart():
    from app.services.relational_operations import RelationalOperationStore

    url = os.environ.get("VERIDRA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("No isolated PostgreSQL test service; not proof of cloud readiness")
    parsed = make_url(url)
    if parsed.database != "veridra_ci" or parsed.drivername != "postgresql+psycopg":
        pytest.fail("PostgreSQL contract only permits the isolated veridra_ci database")
    engine = create_engine(url, pool_size=8, max_overflow=0)
    RelationalOperationStore.create_schema(engine)
    store = RelationalOperationStore(engine)
    owner = f"operation-{uuid4()}"
    row = store.prepare(owner, "approval-one", "docs_create", {"title": "Report"})
    try:
        def claim(_):
            try:
                RelationalOperationStore(engine).claim(owner, row["id"], row["digest"])
                return "claimed"
            except ToolError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(claim, range(8)))
        assert results.count("claimed") == 1
        assert results.count("operation_already_claimed") == 7
        store.checkpoint(owner, row["id"], "doc-id")
        store.uncertain(owner, row["id"], "readback_timeout")
    finally:
        engine.dispose()

    reopened = create_engine(url)
    try:
        restored = RelationalOperationStore(reopened).get(owner, row["id"])
        assert restored["state"] == "uncertain"
        assert restored["resource_id"] == "doc-id"
    finally:
        reopened.dispose()


def test_postgres_app_schema_and_migration_ledger_are_private():
    from sqlalchemy import text

    from app.db.migrations import apply_postgres_migrations
    from app.db.models import Base
    from app.services.relational_state import prepare_state_schema

    url = os.environ.get("VERIDRA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("No isolated PostgreSQL test service; not proof of cloud readiness")
    parsed = make_url(url)
    if parsed.database != "veridra_ci" or parsed.drivername != "postgresql+psycopg":
        pytest.fail("PostgreSQL contract only permits the isolated veridra_ci database")
    engine = create_engine(url).execution_options(
        schema_translate_map={None: "veridra_private"}
    )
    try:
        prepare_state_schema(engine)
        Base.metadata.create_all(engine)
        with engine.begin() as db:
            apply_postgres_migrations(db)
            assert db.execute(text(
                "SELECT to_regclass('veridra_private.users')"
            )).scalar_one() == "veridra_private.users"
            assert db.execute(text(
                "SELECT max(version) FROM veridra_private.schema_migrations"
            )).scalar_one() == 4
            assert db.execute(text(
                "SELECT has_schema_privilege('public', 'veridra_private', 'USAGE')"
            )).scalar_one() is False
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_postgres_native_vector_migration_ranking_and_atomic_update():
    import json

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.db.migrations import apply_postgres_migrations
    from app.db.models import Base, DocumentChunk, DriveFileIndex, LongTermMemory, User
    from app.services.embeddings import EMBEDDING_DIMENSION
    from app.services.pgvector import rank_vectors

    url = os.environ.get("VERIDRA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("No isolated pgvector PostgreSQL service; cloud gate not verified")
    parsed = make_url(url)
    if parsed.database != "veridra_ci" or parsed.drivername != "postgresql+psycopg":
        pytest.fail("Vector contract only permits isolated veridra_ci database")
    engine = create_async_engine(url, execution_options={
        "schema_translate_map": {None: "veridra_private"}
    })
    factory = async_sessionmaker(engine, expire_on_commit=False)
    owner, other = str(uuid4()), str(uuid4())
    x = [1.0] + [0.0] * (EMBEDDING_DIMENSION - 1)
    y = [0.0, 1.0] + [0.0] * (EMBEDDING_DIMENSION - 2)
    try:
        async with engine.begin() as db:
            await db.execute(text("CREATE SCHEMA IF NOT EXISTS veridra_private"))
            await db.run_sync(Base.metadata.create_all)
            await db.run_sync(apply_postgres_migrations)
            await db.run_sync(apply_postgres_migrations)
        async with factory() as db:
            db.add_all([User(id=owner, email=f"{owner}@example.test", display_name="Owner"),
                        User(id=other, email=f"{other}@example.test", display_name="Other")])
            await db.flush()
            for user, file, version, embedding in (
                (owner, "one", "current:1", x), (owner, "two", "current:2", y),
                (owner, "stale", "old:1", x), (other, "one", "current:1", x),
            ):
                db.add(DriveFileIndex(user_id=user, drive_file_id=file, name=file,
                                      mime_type="text/plain", content_hash=version,
                                      chunk_count=1))
                db.add(DocumentChunk(id=f"{user}-{file}", user_id=user,
                                     drive_file_id=file, file_name=file,
                                     mime_type="text/plain", chunk_index=0, content="sample",
                                     embedding_json=json.dumps(embedding)))
            db.add_all([
                LongTermMemory(id=str(uuid4()), user_id=user, kind=kind, content="sample",
                               normalized_hash=str(uuid4()), embedding_json=json.dumps(x),
                               is_archived=archived)
                for user, kind, archived in ((owner, "fact", False), (owner, "fact", True),
                                             (owner, "preference", False), (other, "fact", False))
            ])
            await db.commit()
            hits = await rank_vectors(db, table="document_chunks", owner=owner,
                                      vector=x, limit=12, version_prefix="current:%")
            assert [identifier for identifier, _ in hits] == [f"{owner}-one", f"{owner}-two"]
            assert hits[0][1] == pytest.approx(1.0)
            assert hits[1][1] == pytest.approx(0.0)
            assert len(await rank_vectors(db, table="document_chunks", owner=owner,
                                          vector=x, limit=12, version_prefix="current:%",
                                          file_ids=["two"])) == 1
            assert len(await rank_vectors(db, table="long_term_memories", owner=owner,
                                          vector=x, limit=12, kinds=["fact"])) == 1
            await db.execute(text("UPDATE veridra_private.document_chunks SET "
                                  "embedding_json=:embedding WHERE id=:id"),
                             {"embedding": json.dumps(y), "id": f"{owner}-one"})
            changed = await rank_vectors(db, table="document_chunks", owner=owner,
                                         vector=x, limit=12, version_prefix="current:%",
                                         file_ids=["one"])
            assert changed[0][1] == pytest.approx(0.0)
            await db.rollback()
            restored = await rank_vectors(db, table="document_chunks", owner=owner,
                                          vector=x, limit=12, version_prefix="current:%",
                                          file_ids=["one"])
            assert restored[0][1] == pytest.approx(1.0)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_chat_queue_duplicate_submit_parallel_claim_and_owner_isolation():
    from time import time

    from fastapi import HTTPException
    from sqlalchemy import delete, select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.api.chat_tasks import SubmitTask, enqueue, get_task
    from app.db.models import Base, ChatTask, User
    from app.services.chat_tasks import claim

    url = os.environ.get("VERIDRA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("No isolated PostgreSQL service; queue cloud gate not proven locally")
    parsed = make_url(url)
    if parsed.database != "veridra_ci" or parsed.drivername != "postgresql+psycopg":
        pytest.fail("PostgreSQL contract only permits the isolated veridra_ci database")
    engine = create_async_engine(url, pool_size=4, max_overflow=0).execution_options(
        schema_translate_map={None: "veridra_private"})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    owners = []
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as db:
            owners = [User(email=f"chat-{uuid4()}@example.com", display_name="CI", role="editor")
                      for _ in range(4)]
            db.add_all(owners)
            await db.commit()
        payloads = [SubmitTask(message="synthetic CI queue", client_key=str(uuid4()))
                    for _ in owners]

        async def submit(index):
            async with factory() as db:
                return await enqueue(payloads[index], owners[index], db)

        results = await asyncio.gather(*(submit(index) for index in range(4)))
        duplicates = await asyncio.gather(*(submit(0) for _ in range(4)))
        assert {row["id"] for row in duplicates} == {results[0]["id"]}
        claims = await asyncio.gather(*(claim(factory, now=time()) for _ in range(4)))
        assert len({row["id"] for row in claims if row}) == 4
        async with factory() as db:
            with pytest.raises(HTTPException) as error:
                await get_task(results[0]["id"], owners[1], db)
            assert error.value.status_code == 404
            rows = (await db.scalars(select(ChatTask).where(
                ChatTask.user_id.in_([owner.id for owner in owners])))).all()
            assert len(rows) == 4
    finally:
        if owners:
            async with factory() as db:
                await db.execute(delete(User).where(User.id.in_([owner.id for owner in owners])))
                await db.commit()
        await engine.dispose()


def test_postgres_remote_action_nonce_is_atomic():
    from app.services.relational_remote_actions import RelationalRemoteActionLedger

    url = os.environ.get("VERIDRA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("No isolated PostgreSQL test service; not proof of cloud readiness")
    parsed = make_url(url)
    if parsed.database != "veridra_ci" or parsed.drivername != "postgresql+psycopg":
        pytest.fail("PostgreSQL contract only permits the isolated veridra_ci database")
    engine = create_engine(url, pool_size=8, max_overflow=0)
    RelationalRemoteActionLedger.create_schema(engine)
    ledger = RelationalRemoteActionLedger(engine)
    nonce = uuid4().hex
    try:
        def consume(_):
            try:
                ledger.consume(nonce, 2_000_000_000)
                return "consumed"
            except ToolError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(consume, range(8)))
        assert results.count("consumed") == 1
        assert results.count("remote_action_replayed") == 7
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_postgres_scheduler_claim_is_atomic_and_persistent():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import Settings
    from app.db.models import Base, ScheduledJob, User
    from app.services.scheduled_jobs import _claim, _finish, enqueue_for_invited_users

    url = os.environ.get("VERIDRA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("No isolated PostgreSQL test service; not proof of cloud readiness")
    parsed = make_url(url)
    if parsed.database != "veridra_ci" or parsed.drivername != "postgresql+psycopg":
        pytest.fail("PostgreSQL contract only permits the isolated veridra_ci database")
    async_engine = create_async_engine(url).execution_options(
        schema_translate_map={None: "veridra_private"}
    )
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    owner = f"scheduled-{uuid4()}@example.com"
    try:
        async with async_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as db:
            db.add(
                User(
                    email=owner,
                    display_name="Scheduled",
                    encrypted_google_credentials="synthetic-ciphertext",
                )
            )
            await db.commit()
            settings = Settings(_env_file=None, environment="development")
            first = await enqueue_for_invited_users(
                db, settings, kind="morning", dedupe_key=f"slot-{uuid4()}"
            )
            assert first["created"] >= 1
        claims = await asyncio.gather(
            _claim(factory, now=2_000_000_000),
            _claim(factory, now=2_000_000_000),
        )
        claimed = [item for item in claims if item and item["user_id"]]
        assert len({item["id"] for item in claimed}) == len(claimed)
        own = next(item for item in claimed if item["kind"] == "morning")
        await _finish(factory, own, result={"verified": True}, error=None)
        async with factory() as db:
            row = await db.get(ScheduledJob, own["id"])
            assert row.status == "completed"
            assert "verified" in row.checkpoint_json
    finally:
        await async_engine.dispose()


@pytest.mark.asyncio
async def test_adk_sessions_persist_in_private_postgres_schema():
    from google.adk.sessions import DatabaseSessionService

    from app.core.config import Settings
    from app.services.relational_state import prepare_state_schema

    url = os.environ.get("VERIDRA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("No isolated PostgreSQL test service; not proof of cloud readiness")
    parsed = make_url(url)
    if parsed.database != "veridra_ci" or parsed.drivername != "postgresql+psycopg":
        pytest.fail("PostgreSQL contract only permits the isolated veridra_ci database")
    # Production config must retain TLS validation. The disposable CI service
    # has no TLS certificate: exercise ADK persistence/schema isolation there,
    # not cloud transport security (covered by config tests and staging smoke).
    settings = Settings(_env_file=None, database_url=parsed.update_query_dict(
        {"sslmode": "require"}).render_as_string(hide_password=False))
    session_url = make_url(settings.framework_session_database_url).difference_update_query(
        ["sslmode"]).render_as_string(hide_password=False)
    sync_engine = create_engine(url)
    try:
        prepare_state_schema(sync_engine)
    finally:
        sync_engine.dispose()
    session_id = f"adk-{uuid4()}"
    service = DatabaseSessionService(db_url=session_url)
    try:
        await service.create_session(
            app_name="drive_agent", user_id="owner-a", session_id=session_id
        )
    finally:
        await service.close()
    reopened = DatabaseSessionService(db_url=session_url)
    try:
        assert await reopened.get_session(
            app_name="drive_agent", user_id="owner-a", session_id=session_id
        ) is not None
        assert await reopened.get_session(
            app_name="drive_agent", user_id="owner-b", session_id=session_id
        ) is None
    finally:
        await reopened.close()
