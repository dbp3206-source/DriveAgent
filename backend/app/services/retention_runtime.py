"""Runtime store discovery and complete metadata inventories, never deletion.

Explicit existing files only. A missing optional store is recorded as absent;
an existing unrecognized/unavailable store never becomes an empty proof.
"""

import hashlib
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from pathlib import Path

import aiosqlite
from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import PROJECT_ROOT
from app.services.backup_retention import BACKUP_NAME, MIGRATION_ARCHIVE, MIGRATION_FOLDER
from app.services.retention_context import (
    adk_context_inventory,
    graph_context_inventory,
    langgraph_context_inventory,
    langgraph_context_oldest_at,
)
from app.services.retention_framework import adk_inventory
from app.services.retention_inventory import application_inventory
from app.services.retention_objects import object_inventory
from app.services.retention_policy import (
    RetentionCandidate,
    RetentionKind,
    RetentionPolicyError,
    StoreBinding,
)
from app.services.retention_selection import application_dependencies
from app.services.retention_state import ENTITIES, state_inventory
from app.services.retention_vectors import RetentionVectors


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def existing_file(path):
    """No read/create/open; reject aliases before any engine is constructed."""
    path = Path(path).absolute()
    try:
        if path.resolve() != path or path.is_symlink():
            raise RetentionPolicyError("retention_store_path_unsafe")
        if not path.exists():
            return False
        details = path.stat()
        if not path.is_file() or details.st_nlink != 1:
            raise RetentionPolicyError("retention_store_path_unsafe")
        return True
    except OSError:
        raise RetentionPolicyError("retention_store_unavailable") from None


@dataclass(frozen=True)
class RuntimeStore:
    name: str
    kind: str
    factory: object = None  # None means the caller's application transaction.
    namespace: str | None = None
    entities: frozenset[str] = frozenset()
    native: bool = False
    path: Path | None = None

    @asynccontextmanager
    async def session(self, application_db):
        if self.factory is None:
            yield application_db
        else:
            if self.path is not None and not existing_file(self.path):
                raise RetentionPolicyError("retention_store_disappeared")
            async with self.factory() as db:
                yield db


@dataclass(frozen=True)
class RuntimeInventory:
    candidates: tuple
    bindings: tuple
    stores: tuple
    contexts: dict
    dependencies: dict
    objects: object
    vectors: object
    busy: bool


class RetentionRuntime:
    def __init__(self, settings, storage, vector_store, *, backup_root=None):
        self.settings = settings
        self.storage = storage
        self.vectors = RetentionVectors(vector_store)
        self.backup_root = Path(backup_root) if backup_root is not None else (
            PROJECT_ROOT / ".local-backups")
        self._engines = {}

    def _local(self, name, kind, path, *, entities=frozenset(), native=False):
        if not existing_file(path):
            return None
        path = Path(path).absolute()
        engine = self._engines.get(path)
        if engine is None:
            # mode=rw also closes the race between checking and opening a file.
            async def connect():
                return await aiosqlite.connect(path.as_uri() + "?mode=rw", uri=True)

            url = make_url("sqlite+aiosqlite://").set(database=path.as_posix())
            engine = create_async_engine(url, async_creator=connect)
            self._engines[path] = engine
        return RuntimeStore(name, kind, async_sessionmaker(engine, expire_on_commit=False),
                            entities=entities, native=native, path=path)

    async def close(self):
        for engine in self._engines.values():
            await engine.dispose()
        self._engines.clear()

    async def stores(self, db):
        stores = [RuntimeStore("graph", "graph")]
        legacy_states = ("skills.db", "operations.db", "evaluation_jobs.db")
        if db.bind.dialect.name == "postgresql":
            if any(existing_file(self.settings.data_dir / name)
                   for name in (*legacy_states, "adk_sessions.db")):
                # Inactive legacy stores must not disappear from coverage.
                # Do not ambiguously merge copies with migrated identical IDs.
                raise RetentionPolicyError("retention_legacy_store_not_reconciled")
            stores.append(RuntimeStore("state", "state", entities=ENTITIES))
            for namespace in ("veridra_private", "public"):
                names = await db.run_sync(lambda session, ns=namespace: set(inspect(
                    session.connection()).get_table_names(schema=ns)))
                framework = {"sessions", "events", "user_states", "app_states",
                             "adk_internal_metadata"}
                if names & framework:
                    stores.append(RuntimeStore(f"adk_{namespace}", "adk", namespace=namespace))
                elif namespace == "veridra_private":
                    raise RetentionPolicyError("retention_framework_store_missing")
            # Even an inactive alternate local saver may retain prior contents.
            local = self._local("langgraph", "langgraph",
                                self.settings.data_dir / "langgraph_checkpoints.db")
            if local:
                stores.append(local)
        else:
            if self.settings.relational_state_url is not None:
                url = make_url(self.settings.relational_state_url.get_secret_value())
                if url.drivername != "sqlite" or not url.database:
                    raise RetentionPolicyError("retention_state_profile_unknown")
                current_path = Path(url.database).absolute()
                if any(existing_file(self.settings.data_dir / name)
                       for name in legacy_states
                       if (self.settings.data_dir / name).absolute() != current_path):
                    raise RetentionPolicyError("retention_legacy_store_not_reconciled")
                local = self._local("state", "state", Path(url.database).absolute(),
                                    entities=ENTITIES)
                if local:
                    stores.append(local)
            else:
                for name, entity, filename in (("skills", "skills", "skills.db"),
                                                ("operations", "operations", "operations.db"),
                                                ("evaluation", "evaluation_jobs",
                                                 "evaluation_jobs.db")):
                    local = self._local(name, "state", self.settings.data_dir / filename,
                                        entities=frozenset({entity}), native=True)
                    if local:
                        stores.append(local)
            for name, filename in (("adk_local", "adk_sessions.db"),
                                   ("langgraph", "langgraph_checkpoints.db")):
                local = self._local(name, "adk" if name == "adk_local" else "langgraph",
                                    self.settings.data_dir / filename)
                if local:
                    stores.append(local)
        return tuple(stores)

    def _backup_binding(self):
        root = self.backup_root.absolute()
        if not root.exists():
            return StoreBinding(name="backups", fingerprint=digest(["operator-backups-absent"]),
                                count=0)
        if root.resolve() != root or root.is_symlink():
            raise RetentionPolicyError("retention_backup_path_unsafe")
        # These encrypted snapshots can contain multiple owners. We must not
        # silently erase them for one user's approval, or call them covered.
        for item in root.iterdir():
            if BACKUP_NAME.fullmatch(item.name):
                raise RetentionPolicyError("retention_shared_backup_present")
            if MIGRATION_FOLDER.fullmatch(item.name):
                if item.resolve() != item or not item.is_dir():
                    raise RetentionPolicyError("retention_backup_path_unsafe")
                if any(MIGRATION_ARCHIVE.fullmatch(child.name) for child in item.iterdir()):
                    raise RetentionPolicyError("retention_shared_backup_present")
        return StoreBinding(name="backups", fingerprint=digest(["operator-snapshots-absent"]),
                            count=0)

    async def inventory(self, db, owner, *, lock=False):
        app = await application_inventory(db, owner, lock=lock)
        graph_rows = [item for item in app.candidates
                      if item.record_id.startswith("graph_checkpoints:")]
        candidates = [item for item in app.candidates if item not in graph_rows]
        dependencies = await application_dependencies(db, owner)
        bindings, contexts = [], {}
        busy = app.owner_busy
        stores = await self.stores(db)
        for store in stores:
            async with store.session(db) as session:
                if store.kind == "state":
                    state = await state_inventory(session, owner, entities=store.entities,
                                                  native=store.native, lock=lock)
                    candidates.extend(state.candidates)
                    busy = busy or state.owner_busy
                    bindings.append(StoreBinding(name=store.name, fingerprint=digest(sorted(
                        (item.key, item.fingerprint) for item in state.candidates)),
                        count=len(state.candidates)))
                    continue
                if store.kind == "adk":
                    context = await adk_context_inventory(session, owner,
                                                          namespace=store.namespace, lock=lock)
                    aged = [item.changed_at for item in (await adk_inventory(
                        session, owner, namespace=store.namespace, lock=lock)).candidates]
                elif store.kind == "graph":
                    context = await graph_context_inventory(session, owner, lock=lock)
                    aged = [item.changed_at for item in graph_rows]
                else:
                    context = await langgraph_context_inventory(session, owner, lock=lock)
                    # Checkpoint IDs are owner-scoped UUIDv6 timestamps. A
                    # shared database/WAL mtime lets one owner's activity
                    # postpone retention for every other owner indefinitely.
                    changed = await langgraph_context_oldest_at(session, owner, lock=lock)
                    aged = [changed] if changed is not None else []
                contexts[store.name] = context
                bindings.append(StoreBinding(name=store.name, fingerprint=context.digest,
                                             count=context.row_count))
                if aged and context.row_count:
                    candidates.append(RetentionCandidate(
                        owner_id=owner, kind=RetentionKind.FRAMEWORK,
                        record_id=f"derived_context:{store.name}",
                        changed_at=min(aged),
                        fingerprint=context.digest,
                    ))
        objects = await object_inventory(db, self.storage, owner)
        # A PDF's physical copy cannot be separated from a still-fresh SQL job.
        jobs = {item.record_id.split(":", 1)[1]: item for item in candidates
                if item.record_id.startswith("pdf_ingestion_jobs:")}
        for item in objects.candidates:
            identity = item.record_id.split(":", 1)[1]
            if identity in jobs:
                job = jobs[identity]
                dependencies.setdefault(job.key, frozenset())
                dependencies[job.key] |= {item.key}
                # A physical-only orphan may age on its metadata; a known job
                # and its PDF are one logical input. Fresh jobs protect PDFs.
                item = replace(item, changed_at=max(item.changed_at, job.changed_at))
            candidates.append(item)
        vectors = await self.vectors.inventory(owner)
        canonical = {("agent_memories" if item.record_id.startswith("long_term_memories:")
                      else "drive_chunks", item.record_id.split(":", 1)[1])
                     for item in app.candidates if item.record_id.startswith(
                         ("long_term_memories:", "document_chunks:"))}
        if any((point.collection, point.point_id) not in canonical for point in vectors.points):
            raise RetentionPolicyError("retention_orphan_vector_age_unknown")
        bindings.append(StoreBinding(name="vectors", fingerprint=vectors.digest,
                                     count=len(vectors.points)))
        bindings.append(self._backup_binding())
        return RuntimeInventory(tuple(candidates), tuple(sorted(bindings, key=lambda x: x.name)),
                                stores, contexts, dependencies, objects, vectors, busy)
