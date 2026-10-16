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


def test_legacy_adk_tables_deny_api_roles_without_removing_data():
    from app.db.framework_security import LEGACY_ADK_TABLES, protect_legacy_framework_tables

    url = os.environ.get("VERIDRA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("No isolated PostgreSQL test service; not proof of cloud readiness")
    parsed = make_url(url)
    if parsed.database != "veridra_ci" or parsed.drivername != "postgresql+psycopg":
        pytest.fail("PostgreSQL contract only permits the isolated veridra_ci database")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                for role in ("anon", "authenticated"):
                    if connection.exec_driver_sql(
                        f"SELECT 1 FROM pg_roles WHERE rolname = '{role}'"
                    ).scalar_one_or_none() is None:
                        connection.exec_driver_sql(f"CREATE ROLE {role} NOLOGIN")
                for table in LEGACY_ADK_TABLES:
                    assert connection.exec_driver_sql(
                        f"SELECT to_regclass('public.{table}')"
                    ).scalar_one_or_none() is None, "Fixture must not replace an existing table"
                    connection.exec_driver_sql(f"CREATE TABLE public.{table} (id integer)")
                    connection.exec_driver_sql(f"INSERT INTO public.{table} VALUES (1)")
                    connection.exec_driver_sql(
                        f"GRANT SELECT ON public.{table} TO PUBLIC, anon, authenticated"
                    )
                protect_legacy_framework_tables(connection)
                for table in LEGACY_ADK_TABLES:
                    assert connection.exec_driver_sql(
                        f"SELECT relrowsecurity FROM pg_class "
                        f"WHERE oid = 'public.{table}'::regclass"
                    ).scalar_one() is True
                    for role in ("anon", "authenticated"):
                        assert connection.exec_driver_sql(
                            f"SELECT has_table_privilege('{role}', 'public.{table}', 'SELECT')"
                        ).scalar_one() is False
                    assert connection.exec_driver_sql(
                        f"SELECT count(*) FROM public.{table}"
                    ).scalar_one() == 1
                # Repeat protection safely; owner access and rows remain intact.
                protect_legacy_framework_tables(connection)
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


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
        assert store.get_by_request_key(owner, "approval-one")["id"] == row["id"]
        assert store.get_by_request_key("other-" + owner, "approval-one") is None
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
        by_key = RelationalOperationStore(reopened).get_by_request_key(owner, "approval-one")
        assert by_key["digest"] == row["digest"]
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
            )).scalar_one() == 8
            assert db.execute(text(
                "SELECT column_default FROM information_schema.columns "
                "WHERE table_schema='veridra_private' AND table_name='users' "
                "AND column_name='auth_version'"
            )).scalar_one() is not None
            assert db.execute(text(
                "SELECT has_schema_privilege('public', 'veridra_private', 'USAGE')"
            )).scalar_one() is False
    finally:
        engine.dispose()


def test_postgres_content_clock_upgrade_preserves_legacy_content():
    from datetime import UTC, datetime

    from sqlalchemy import insert, text

    from app.db.migrations import _content_clocks
    from app.db.models import Base, CompanyProfile, LongTermMemory, SavedArtifact, User
    from app.services.relational_state import prepare_state_schema

    url = os.environ.get("VERIDRA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("No isolated PostgreSQL test service; content clock upgrade not verified")
    parsed = make_url(url)
    if parsed.database != "veridra_ci" or parsed.drivername != "postgresql+psycopg":
        pytest.fail("Content clock upgrade only permits the isolated veridra_ci database")
    engine = create_engine(url).execution_options(
        schema_translate_map={None: "veridra_private"}
    )
    try:
        prepare_state_schema(engine)
        Base.metadata.create_all(engine)
        with engine.connect() as db:
            transaction = db.begin()
            try:
                owner_id = str(uuid4())
                changed_at = datetime(2026, 9, 10, 12, tzinfo=UTC)
                db.execute(insert(User).values(
                    id=owner_id, email=f"{owner_id}@example.invalid", display_name="Synthetic",
                ))
                rows = [
                    (SavedArtifact, {"creation_key": str(uuid4()), "title": "Synthetic",
                                     "content": "Synthetic legacy report"}),
                    (LongTermMemory, {"kind": "fact", "normalized_hash": "synthetic",
                                      "content": "Synthetic legacy note"}),
                    (CompanyProfile, {"name": "Synthetic", "normalized_name": "synthetic",
                                      "domain": f"{owner_id}.invalid",
                                      "source_url": "https://example.invalid"}),
                ]
                expected = {}
                for model, values in rows:
                    row_id = str(uuid4())
                    db.execute(insert(model).values(
                        id=row_id, user_id=owner_id, updated_at=changed_at, **values,
                    ))
                    expected[model.__tablename__] = row_id
                    # Transactional DDL is limited to the explicitly isolated CI DB.
                    db.execute(text(f"ALTER TABLE veridra_private.{model.__tablename__} "
                                    "DROP COLUMN content_updated_at"))
                _content_clocks(db)
                _content_clocks(db)
                for table, row_id in expected.items():
                    assert db.execute(text(
                        f"SELECT content_updated_at FROM veridra_private.{table} WHERE id=:id"
                    ), {"id": row_id}).scalar_one() == changed_at
                assert db.execute(text(
                    "SELECT content FROM veridra_private.saved_artifacts WHERE id=:id"
                ), {"id": expected["saved_artifacts"]}).scalar_one() == "Synthetic legacy report"
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def test_postgres_session_revocation_column_upgrade_preserves_legacy_user():
    from sqlalchemy import insert, text

    from app.db.migrations import _auth_version
    from app.db.models import Base, User
    from app.services.relational_state import prepare_state_schema

    url = os.environ.get("VERIDRA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("No isolated PostgreSQL test service; revocation upgrade not verified")
    parsed = make_url(url)
    if parsed.database != "veridra_ci" or parsed.drivername != "postgresql+psycopg":
        pytest.fail("Revocation upgrade only permits the isolated veridra_ci database")
    engine = create_engine(url).execution_options(
        schema_translate_map={None: "veridra_private"}
    )
    try:
        prepare_state_schema(engine)
        Base.metadata.create_all(engine)
        with engine.connect() as db:
            transaction = db.begin()
            try:
                db.execute(text("SET LOCAL lock_timeout='5s'"))
                owner = str(uuid4())
                db.execute(insert(User).values(
                    id=owner, email=f"{owner}@example.test", display_name="Legacy QA"
                ))
                # Simulate schema v5 only in the disposable CI database; roll back below.
                db.execute(text("ALTER TABLE veridra_private.users DROP COLUMN auth_version"))
                _auth_version(db)
                _auth_version(db)
                row = db.execute(text(
                    "SELECT display_name, auth_version FROM veridra_private.users WHERE id=:id"
                ), {"id": owner}).one()
                assert tuple(row) == ("Legacy QA", "")
            finally:
                transaction.rollback()
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
    from app.db.framework_sessions import framework_engine_options, protect_framework_engine
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
        ["sslmode", "options"]).render_as_string(hide_password=False)
    sync_engine = create_engine(url)
    try:
        prepare_state_schema(sync_engine)
    finally:
        sync_engine.dispose()
    session_id = f"adk-{uuid4()}"
    # Do not rely on startup search_path: a real cloud pooler ignored it.
    service = DatabaseSessionService(db_url=session_url, **framework_engine_options(session_url))
    protect_framework_engine(service.db_engine)
    try:
        await service.create_session(
            app_name="drive_agent", user_id="owner-a", session_id=session_id
        )
    finally:
        await service.close()
    reopened = DatabaseSessionService(db_url=session_url, **framework_engine_options(session_url))
    protect_framework_engine(reopened.db_engine)
    try:
        assert await reopened.get_session(
            app_name="drive_agent", user_id="owner-a", session_id=session_id
        ) is not None
        assert await reopened.get_session(
            app_name="drive_agent", user_id="owner-b", session_id=session_id
        ) is None
        async with reopened.db_engine.connect() as connection:
            schema_result = await connection.exec_driver_sql("SELECT current_schema()")
            assert schema_result.scalar_one() == "veridra_private"
            table_result = await connection.exec_driver_sql(
                "SELECT to_regclass('veridra_private.sessions') IS NOT NULL"
            )
            assert table_result.scalar_one() is True
    finally:
        await reopened.close()


def test_postgres_skill_retention_clock_and_legacy_insert(monkeypatch):
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace

    from sqlalchemy import text

    from app.services import relational_skills
    from app.services.relational_state import prepare_state_schema

    url = os.environ.get("VERIDRA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("No isolated PostgreSQL test service; skill retention not verified")
    parsed = make_url(url)
    if parsed.database != "veridra_ci" or parsed.drivername != "postgresql+psycopg":
        pytest.fail("Retention only permits the isolated veridra_ci database")
    engine = create_engine(url).execution_options(
        schema_translate_map={None: "veridra_private"}
    )
    try:
        prepare_state_schema(engine)
        RelationalSkillStore.create_schema(engine)
        store = RelationalSkillStore(engine)
        old = datetime(2026, 9, 1, 12, tzinfo=UTC)
        now = old + timedelta(days=40)
        owner = f"retention-{uuid4()}"
        row_id = str(uuid4())
        spec = SkillSpec(name="synthetic_retention", title="Synthetic report",
                         description="Synthetic notes", goal="Summarize selected sources",
                         procedure=["Check selected sources"], output_format="Short report")
        with engine.begin() as db:
            db.exec_driver_sql(
                "INSERT INTO veridra_private.skills VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (row_id, owner, spec.name, spec.model_dump_json(), 1, 1,
                 old.timestamp(), old.timestamp()),
            )
        assert store.retention_candidates(owner)[0].changed_at == old
        monkeypatch.setattr(relational_skills, "time",
                            SimpleNamespace(time=lambda: now.timestamp()))
        store.archive(owner, row_id)
        assert store.retention_candidates(owner)[0].changed_at == old
        assert store.retention_candidates("another-synthetic-owner") == []
        store.save(owner, spec.model_copy(update={"goal": "Compare selected sources"}),
                   expected_revision=1)
        assert store.retention_candidates(owner)[0].changed_at == now
        with engine.connect() as db:
            assert db.execute(text(
                "SELECT to_regclass('veridra_private.skill_content_clocks')"
            )).scalar_one() == "veridra_private.skill_content_clocks"
            assert db.execute(text(
                "SELECT has_schema_privilege('public', 'veridra_private', 'USAGE')"
            )).scalar_one() is False
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_postgres_application_retention_inventory_keeps_new_chat_content():
    from datetime import UTC, datetime, timedelta

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.db.models import Base, ChatSession, LongTermMemory, Message, User
    from app.services.relational_state import prepare_state_schema
    from app.services.retention_inventory import application_inventory

    url = os.environ.get("VERIDRA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("No isolated PostgreSQL test service; application inventory not verified")
    parsed = make_url(url)
    if parsed.database != "veridra_ci" or parsed.drivername != "postgresql+psycopg":
        pytest.fail("Retention only permits the isolated veridra_ci database")
    bootstrap = create_engine(url).execution_options(
        schema_translate_map={None: "veridra_private"}
    )
    try:
        prepare_state_schema(bootstrap)
        Base.metadata.create_all(bootstrap)
    finally:
        bootstrap.dispose()
    engine = create_async_engine(url, execution_options={
        "schema_translate_map": {None: "veridra_private"},
    })
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            old = datetime(2026, 9, 1, 12, tzinfo=UTC)
            now = old + timedelta(days=40)
            user = User(email=f"{uuid4()}@example.invalid", display_name="Synthetic")
            db.add(user)
            await db.flush()
            chat = ChatSession(user_id=user.id, title="Synthetic", created_at=old, updated_at=old)
            memory = LongTermMemory(user_id=user.id, kind="fact", content="Synthetic",
                                    normalized_hash="synthetic", is_archived=True,
                                    created_at=old, updated_at=now, content_updated_at=old)
            db.add_all([chat, memory])
            await db.flush()
            db.add(Message(user_id=user.id, session_id=chat.id, role="user",
                           content="Synthetic fresh turn", created_at=now))
            await db.flush()
            result = await application_inventory(db, user.id)
            rows = {item.record_id: item for item in result.candidates}
            assert len(rows) == 3 and not result.owner_busy
            assert rows[f"chat_sessions:{chat.id}"].changed_at == now
            assert rows[f"long_term_memories:{memory.id}"].changed_at == old
            assert result.policy_checks()["application"] is True
            assert any(ready is False for ready in result.policy_checks().values())
            await db.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_adk_retention_reads_private_and_legacy_public_without_touching_content():
    from google.adk.events import Event
    from google.adk.sessions import DatabaseSessionService
    from google.genai import types
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.framework_security import protect_legacy_framework_tables
    from app.db.framework_sessions import framework_engine_options, protect_framework_engine
    from app.services.relational_state import prepare_state_schema
    from app.services.retention_framework import adk_inventory

    url = os.environ.get("VERIDRA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("No isolated PostgreSQL test service; framework retention not verified")
    parsed = make_url(url)
    if parsed.database != "veridra_ci" or parsed.drivername != "postgresql+psycopg":
        pytest.fail("Retention only permits the isolated veridra_ci database")
    bootstrap = create_engine(url)
    try:
        prepare_state_schema(bootstrap)
    finally:
        bootstrap.dispose()
    owner = f"framework-retention-{uuid4()}"
    namespaces = {}
    for namespace in ("veridra_private", "public"):
        options = framework_engine_options(url) if namespace == "veridra_private" else {}
        service = DatabaseSessionService(db_url=url, **options)
        if namespace == "veridra_private":
            protect_framework_engine(service.db_engine)
        try:
            session = await service.create_session(
                app_name="drive_agent", user_id=owner, session_id=str(uuid4()),
                state={"case": "Synthetic context", "user:language": "Vietnamese"},
            )
            await service.append_event(session, Event(
                author="assistant", content=types.Content(role="model", parts=[
                    types.Part(text="SYNTHETIC_FRAMEWORK_SENTINEL"),
                ]),
            ))
            if namespace == "public":
                async with service.db_engine.begin() as db:
                    await db.run_sync(protect_legacy_framework_tables)
            async with async_sessionmaker(service.db_engine)() as db:
                result = await adk_inventory(db, owner, namespace=namespace)
                assert len(result.candidates) == 3
                assert "SYNTHETIC_FRAMEWORK_SENTINEL" not in repr(result)
                assert all(item.owner_id == owner for item in result.candidates)
                assert (await adk_inventory(db, "other-synthetic-owner",
                                            namespace=namespace)).candidates == ()
                namespaces[namespace] = {item.record_id for item in result.candidates}
            reopened = await service.get_session(
                app_name="drive_agent", user_id=owner, session_id=session.id,
            )
            assert reopened.state["case"] == "Synthetic context" and len(reopened.events) == 1
        finally:
            await service.close()
    assert namespaces["public"].isdisjoint(namespaces["veridra_private"])


@pytest.mark.asyncio
async def test_postgres_cleanup_claims_are_owner_isolated_and_old_worker_is_fenced():
    from sqlalchemy import select, text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from test_cleanup_jobs import STAMP, lease_args, plan

    from app.db.models import Base, CleanupJob, User
    from app.services import cleanup_jobs as jobs
    from app.services.relational_state import prepare_state_schema

    url = os.environ.get("VERIDRA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("No isolated PostgreSQL test service; cleanup queue not verified")
    parsed = make_url(url)
    if parsed.database != "veridra_ci" or parsed.drivername != "postgresql+psycopg":
        pytest.fail("Cleanup only permits the isolated veridra_ci database")
    bootstrap = create_engine(url).execution_options(
        schema_translate_map={None: "veridra_private"},
    )
    try:
        prepare_state_schema(bootstrap)
        Base.metadata.create_all(bootstrap)
    finally:
        bootstrap.dispose()
    engine = create_async_engine(url, execution_options={
        "schema_translate_map": {None: "veridra_private"},
    })
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            owner, other = (User(email=f"{uuid4()}@example.invalid", display_name="Synthetic")
                            for _ in range(2))
            db.add_all([owner, other])
            await db.commit()
        scope = plan(owner.id)
        same = await asyncio.gather(*(jobs.enqueue(factory, owner.id, scope, now=STAMP)
                                      for _ in range(4)))
        assert len(set(same)) == 1
        second_id = await jobs.enqueue(factory, other.id, plan(other.id), now=STAMP)
        with pytest.raises(jobs.CleanupStateError, match="already_open"):
            await jobs.enqueue(factory, owner.id, plan(owner.id), now=STAMP)
        claims = await asyncio.gather(*(jobs.claim(factory, now=STAMP) for _ in range(4)))
        taken = [item for item in claims if item is not None]
        assert len(taken) == 2 and {item["id"] for item in taken} == {same[0], second_id}
        first = next(item for item in taken if item["owner"] == owner.id)
        async with factory() as db:
            await jobs.mark_sql_done(db, *lease_args(first), now=STAMP)
            await jobs.record_purge(db, *lease_args(first), scope.external[0], now=STAMP)
            await db.commit()
        reclaimed = await asyncio.gather(*(jobs.claim(factory, now=STAMP + 121)
                                          for _ in range(4)))
        new = next(item for item in reclaimed if item and item["owner"] == owner.id)
        assert new["phase"] == "purging" and new["attempt"] == 2
        assert new["token"] != first["token"]
        async with factory() as db:
            with pytest.raises(jobs.CleanupLeaseLost):
                await jobs.mark_sql_done(db, *lease_args(first), now=STAMP)
            await db.rollback()
            await jobs.record_purge(db, *lease_args(new), scope.external[1], now=STAMP + 121)
            await jobs.finish(db, *lease_args(new), now=STAMP + 121)
            await db.commit()
            row = await db.scalar(select(CleanupJob).where(CleanupJob.id == same[0]))
            assert row.status == "succeeded"
            assert await db.scalar(text(
                "SELECT has_schema_privilege('public', 'veridra_private', 'USAGE')"
            )) is False
            assert await db.scalar(text(
                "SELECT count(*) FROM pg_indexes WHERE schemaname='veridra_private' "
                "AND tablename='cleanup_jobs' AND indexname='ux_cleanup_owner_open' "
                "AND indexdef LIKE '%UNIQUE%' AND indexdef LIKE '%WHERE%'"
            )) == 1
        assert await jobs.status(factory, other.id, same[0]) is None
    finally:
        await engine.dispose()
