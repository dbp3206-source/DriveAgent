"""Native PostgreSQL vectors, committed atomically with their authoritative rows.

Generated columns avoid a second vector store/write transaction. Local SQLite
continues using its existing Qdrant/JSON paths. Cloud requires pgvector; missing
extension permissions fail startup rather than silently changing architecture.
"""

import json
import math

from sqlalchemy import bindparam, text

from app.services.embeddings import EMBEDDING_DIMENSION


def migrate_pgvector(connection) -> None:
    connection.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS extensions")
    connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions")
    namespace = connection.exec_driver_sql(
        "SELECT n.nspname FROM pg_extension e JOIN pg_namespace n "
        "ON n.oid=e.extnamespace WHERE e.extname='vector'"
    ).scalar_one()
    quoted = connection.dialect.identifier_preparer.quote_identifier(namespace)
    for table in ("document_chunks", "long_term_memories"):
        connection.exec_driver_sql(
            f"ALTER TABLE veridra_private.{table} ADD COLUMN IF NOT EXISTS "
            f"embedding_vector {quoted}.vector({EMBEDDING_DIMENSION}) GENERATED ALWAYS AS "
            "(CASE WHEN jsonb_array_length(embedding_json::jsonb) = "
            f"{EMBEDDING_DIMENSION} THEN embedding_json::{quoted}.vector"
            f"({EMBEDDING_DIMENSION}) ELSE NULL END) STORED"
        )


def is_postgres_session(db) -> bool:
    return db.get_bind().dialect.name == "postgresql"


async def rank_vectors(db, *, table: str, owner: str, vector: list[float], limit: int,
                       file_ids: list[str] | None = None, version_prefix: str | None = None,
                       kinds: list[str] | None = None) -> list[tuple[str, float]]:
    if table not in {"document_chunks", "long_term_memories"}:
        raise ValueError("Unknown vector source")
    if not owner or not 1 <= limit <= 1000:
        raise ValueError("Owner and bounded limit required")
    if len(vector) != EMBEDDING_DIMENSION or any(not math.isfinite(v) for v in vector):
        raise ValueError("Invalid query embedding")
    if not any(vector):
        return []
    namespace = db.info.get("pgvector_namespace")
    if namespace is None:
        namespace = await db.scalar(text(
            "SELECT n.nspname FROM pg_extension e JOIN pg_namespace n "
            "ON n.oid=e.extnamespace WHERE e.extname='vector'"
        ))
        if namespace is None:
            raise RuntimeError("pgvector extension is required for cloud retrieval")
        db.info["pgvector_namespace"] = namespace
    quoted = db.get_bind().dialect.identifier_preparer.quote_identifier(namespace)
    distance = (f"c.embedding_vector OPERATOR({quoted}.<=>) "
                f"CAST(:query_vector AS {quoted}.vector({EMBEDDING_DIMENSION}))")
    join = ""
    where = "c.user_id=:owner AND c.embedding_vector IS NOT NULL"
    params = {"owner": owner, "query_vector": json.dumps(vector), "limit": limit}
    expanding = []
    if table == "document_chunks":
        if not version_prefix:
            raise ValueError("Current index version required")
        join = (" JOIN veridra_private.drive_file_index i ON i.user_id=c.user_id "
                "AND i.drive_file_id=c.drive_file_id")
        where += " AND i.content_hash LIKE :version_prefix"
        params["version_prefix"] = version_prefix
        if file_ids:
            where += " AND c.drive_file_id IN :file_ids"
            params["file_ids"] = file_ids
            expanding.append(bindparam("file_ids", expanding=True))
    else:
        where += " AND c.is_archived=false"
        if kinds:
            where += " AND c.kind IN :kinds"
            params["kinds"] = kinds
            expanding.append(bindparam("kinds", expanding=True))
    statement = text(
        f"SELECT c.id, 1 - ({distance}) AS score FROM veridra_private.{table} c"
        f"{join} WHERE {where} ORDER BY ({distance}), c.id LIMIT :limit"
    ).bindparams(*expanding)
    result = await db.execute(statement, params)
    return [(identifier, float(score)) for identifier, score in result
            if score is not None and math.isfinite(float(score))]
