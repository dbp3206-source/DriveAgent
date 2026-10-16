"""Reusable real-PG context contract; isolated veridra_ci database only."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.db.models import Base, ChatSession, GraphCheckpoint, Message, User
from app.services.relational_state import prepare_state_schema
from app.services.retention_context import graph_context_inventory, reset_graph_context


async def postgres_context_private_namespace_contract(url: str):
    """Root CI may await this from its existing PostgreSQL-only test entrypoint.

    Seeds only synthetic records and a deliberately incompatible public shadow
    table inside a rolled-back outer transaction. Never opens a personal DB.
    """
    parsed = make_url(url)
    if parsed.database != "veridra_ci" or parsed.drivername != "postgresql+psycopg":
        pytest.fail("Context reset contract only permits isolated veridra_ci")
    options = {"schema_translate_map": {None: "veridra_private"}}
    bootstrap = create_engine(url).execution_options(**options)
    try:
        prepare_state_schema(bootstrap)
        Base.metadata.create_all(bootstrap)
    finally:
        bootstrap.dispose()
    engine = create_async_engine(url, execution_options=options)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                assert await connection.scalar(text(
                    "SELECT to_regclass('public.graph_checkpoints')"
                )) is None, "Fixture must not replace an existing public table"
                await connection.execute(text(
                    "CREATE TABLE public.graph_checkpoints (id integer PRIMARY KEY, value text)"
                ))
                await connection.execute(text(
                    "INSERT INTO public.graph_checkpoints VALUES (1, 'PUBLIC_SHADOW_CANARY')"
                ))
                async with AsyncSession(bind=connection, expire_on_commit=False,
                                        join_transaction_mode="create_savepoint") as db:
                    owner, other, chat_id, message_id = (str(uuid4()) for _ in range(4))
                    db.add_all([
                        User(id=owner, email=f"{owner}@example.invalid", display_name="Synthetic"),
                        User(id=other, email=f"{other}@example.invalid", display_name="Synthetic"),
                    ])
                    await db.flush()
                    db.add(ChatSession(id=chat_id, user_id=owner, title="Canonical recent work"))
                    await db.flush()
                    db.add_all([
                        Message(id=message_id, session_id=chat_id, user_id=owner, role="user",
                                content="FRESH_CANONICAL_CANARY"),
                        GraphCheckpoint(user_id=owner, thread_id=f"{owner}:{chat_id}",
                                        state_json='{"canary":"OWN_PRIVATE_CONTEXT"}'),
                        GraphCheckpoint(user_id=other, thread_id=f"{other}:{uuid4()}",
                                        state_json='{"canary":"OTHER_PRIVATE_CONTEXT"}'),
                    ])
                    await db.commit()
                    inventory = await graph_context_inventory(db, owner)
                    assert inventory.row_count == 1
                    assert inventory.table_counts == (("graph_checkpoints", 1),)
                    assert await reset_graph_context(db, owner, inventory.digest) == 1
                    await db.rollback()
                    assert await graph_context_inventory(db, owner) == inventory
                    assert await reset_graph_context(db, owner, inventory.digest) == 1
                    await db.commit()
                    assert (await graph_context_inventory(db, owner)).row_count == 0
                    assert await db.scalar(select(func.count()).select_from(GraphCheckpoint).where(
                        GraphCheckpoint.user_id == other,
                    )) == 1
                    assert (await db.get(Message, message_id)).content == "FRESH_CANONICAL_CANARY"
                    assert await db.scalar(text(
                        "SELECT value FROM public.graph_checkpoints WHERE id=1"
                    )) == "PUBLIC_SHADOW_CANARY"
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_context_private_namespace_with_public_shadow():
    url = os.environ.get("VERIDRA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("No isolated PostgreSQL test service; not real-PG evidence")
    await postgres_context_private_namespace_contract(url)
