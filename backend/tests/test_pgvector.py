import math
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.services.embeddings import EMBEDDING_DIMENSION
from app.services.pgvector import rank_vectors


def session():
    return SimpleNamespace(
        info={}, scalar=AsyncMock(return_value="extensions"),
        execute=AsyncMock(return_value=[("allowed", 0.9)]),
        get_bind=lambda: SimpleNamespace(dialect=postgresql.dialect()),
    )


@pytest.mark.asyncio
async def test_rank_keeps_owner_files_version_and_archive_in_sql():
    db = session()
    vector = [1.0] + [0.0] * (EMBEDDING_DIMENSION - 1)
    assert await rank_vectors(db, table="document_chunks", owner="owner",
                              vector=vector, limit=12, file_ids=["one"],
                              version_prefix="current:%") == [("allowed", 0.9)]
    statement, params = db.execute.call_args.args
    sql = str(statement)
    assert "c.user_id=:owner" in sql
    assert "drive_file_index" in sql
    assert "i.content_hash LIKE :version_prefix" in sql
    assert "OPERATOR(\"extensions\".<=>)" in sql
    assert params["owner"] == "owner" and params["file_ids"] == ["one"]
    await rank_vectors(db, table="long_term_memories", owner="owner", vector=vector,
                       limit=20, kinds=["fact"])
    assert "c.is_archived=false" in str(db.execute.call_args.args[0])
    assert db.execute.call_args.args[1]["kinds"] == ["fact"]
    db.scalar.assert_awaited_once()


@pytest.mark.asyncio
async def test_rank_rejects_invalid_embeddings_and_untrusted_identifiers():
    db = session()
    vector = [1.0] + [0.0] * (EMBEDDING_DIMENSION - 1)
    for override in ({"table": "users; DROP TABLE users"}, {"owner": ""},
                     {"limit": 1001}, {"vector": [math.nan] * EMBEDDING_DIMENSION},
                     {"vector": [1.0]}, {"version_prefix": None}):
        args = dict(table="document_chunks", owner="owner", vector=vector,
                    limit=12, version_prefix="current:%")
        args.update(override)
        with pytest.raises(ValueError):
            await rank_vectors(db, **args)
    db.execute.assert_not_awaited()
    assert await rank_vectors(db, table="long_term_memories", owner="owner",
                              vector=[0.0] * EMBEDDING_DIMENSION, limit=1) == []


@pytest.mark.asyncio
async def test_missing_cloud_extension_does_not_silently_use_json_cosine():
    db = session()
    db.scalar.return_value = None
    with pytest.raises(RuntimeError, match="pgvector extension is required"):
        await rank_vectors(db, table="long_term_memories", owner="owner",
                           vector=[1.0] * EMBEDDING_DIMENSION, limit=1)
    db.execute.assert_not_awaited()
