"""Owner-fenced, resumable cleanup across actual runtime stores.

No model or Google calls. Manual requests require authenticated UI confirmation;
the internal scheduler may enqueue only items that have reached the expiry policy.
Both paths use the same strict inventory and snapshot checks; only the worker purges.
"""

import asyncio
import logging
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from time import time

from sqlalchemy import select

from app.db.models import CleanupJob, User
from app.services import cleanup_jobs as jobs
from app.services.cleanup_jobs import CleanupPlan, PurgeReference
from app.services.owner_admission import AdmissionError
from app.services.retention_application import application_purge_references, purge_application
from app.services.retention_context import (
    adk_context_inventory,
    graph_context_inventory,
    langgraph_context_inventory,
    reset_adk_context,
    reset_graph_context,
    reset_langgraph_context,
)
from app.services.retention_inventory import POLICIES
from app.services.retention_objects import object_inventory, validate_object_reference
from app.services.retention_policy import (
    CONTENT_RETENTION_DAYS,
    REQUIRED_INVENTORIES,
    RetentionPolicy,
    RetentionPolicyError,
    utc,
)
from app.services.retention_selection import select_batch
from app.services.retention_state import purge_state, state_inventory
from app.services.retention_vectors import VectorPoint

APPLICATION_NAMES = {model.__tablename__ for model, _kind, _clock in POLICIES}
CONTEXT_INVENTORY = {"graph": graph_context_inventory, "adk": adk_context_inventory,
                     "langgraph": langgraph_context_inventory}
CONTEXT_RESET = {"graph": reset_graph_context, "adk": reset_adk_context,
                 "langgraph": reset_langgraph_context}
AUTO_RETRY_SECONDS = 60 * 60
NOTICE_DAYS = 3


def _application(items):
    return tuple(item for item in items if item.record_id.split(":", 1)[0] in APPLICATION_NAMES)


def _state_items(items, store):
    return tuple(item for item in items if item.record_id.split(":", 1)[0] in store.entities)


class RetentionCoordinator:
    def __init__(self, factory, gate, runtime, secret, *, clock=time):
        self.factory, self.gate, self.runtime = factory, gate, runtime
        self.policy = RetentionPolicy(secret)
        self.clock = clock

    @staticmethod
    def coverage(inventory):
        if inventory.busy:
            raise RetentionPolicyError("retention_owner_busy")
        # Only reached after every configured store completed its own strict
        # inventory. This is not a blanket readiness claim from one SQL query.
        return dict.fromkeys(REQUIRED_INVENTORIES, True)

    async def preview(self, owner):
        async with self.gate.exclusive(owner):
            async with self.factory() as db:
                if await db.scalar(select(CleanupJob.id).where(
                    CleanupJob.user_id == owner, CleanupJob.status.in_(jobs.OPEN),
                )) is not None:
                    raise RetentionPolicyError("cleanup_already_open")
                inventory = await self.runtime.inventory(db, owner)
                now = datetime.fromtimestamp(self.clock(), UTC)
                chosen = select_batch(inventory.candidates, inventory.dependencies, now=now)
                preview = self.policy.prepare(owner_id=owner, candidates=list(chosen),
                                              inventories=self.coverage(inventory), now=now,
                                              bindings=inventory.bindings)
                due = [item for item in inventory.candidates
                       if utc(item.changed_at) <= now - timedelta(days=CONTENT_RETENTION_DAYS)]
                warning_cutoff = now - timedelta(days=CONTENT_RETENTION_DAYS - NOTICE_DAYS)
                upcoming = [item for item in inventory.candidates
                            if now - timedelta(days=CONTENT_RETENTION_DAYS)
                            < utc(item.changed_at) <= warning_cutoff]
                next_due_at = min(
                    (utc(item.changed_at) + timedelta(days=CONTENT_RETENTION_DAYS)
                     for item in upcoming), default=None,
                )
                preview = replace(preview, due_count=len(due),
                                  active_due_count=sum(item.active for item in due),
                                  has_more=len(due) > len(chosen))
                result = asdict(preview)
                result.update(retention_days=CONTENT_RETENTION_DAYS,
                              upcoming_count=len(upcoming),
                              next_due_at=next_due_at.isoformat() if next_due_at else None,
                              reset_context_count=sum(item.row_count for item in
                                                      inventory.contexts.values()),
                              exclusions=["google_originals", "provider_backups", "user_downloads"])
                return result

    async def confirm(self, owner, token, *, automatic=False):
        """Revalidate a frozen scope from an explicit click or internal policy runner."""
        async with self.gate.exclusive(owner):
            async with self.factory() as db:
                inventory = await self.runtime.inventory(db, owner, lock=True)
                snapshot = self.policy.validate(token=token, owner_id=owner,
                                                current=list(inventory.candidates),
                                                inventories=self.coverage(inventory),
                                                now=datetime.fromtimestamp(self.clock(), UTC),
                                                bindings=inventory.bindings)
                # Verify closure against exactly these items, not a newly
                # expanded selection. Application purge repeats this guard.
                selected = {item.record_id for item in snapshot.items}
                selected_keys = {(item.kind.value, item.record_id) for item in snapshot.items}
                for key in selected_keys:
                    if not set(inventory.dependencies.get(key, ())).issubset(selected_keys):
                        raise RetentionPolicyError("retention_dependency_not_selected")
                references = await application_purge_references(
                    db, owner, _application(snapshot.items))
                refs = {(ref.kind, ref.object_id): ref for ref in references}
                for ref in inventory.objects.references:
                    key = (ref.kind, ref.object_id)
                    if key in refs or f"pdf_objects:{ref.object_id}" in selected:
                        refs[key] = ref
                points = {(point.collection, point.point_id): point
                          for point in inventory.vectors.points}
                for key, ref in tuple(refs.items()):
                    if ref.kind in {"drive_chunks", "agent_memories"}:
                        point = points.get(key)
                        refs[key] = ref.model_copy(update={
                            "fingerprint": point.fingerprint if point else None,
                        })
                for store in inventory.stores:
                    if store.factory is None:
                        continue
                    relevant = (_state_items(snapshot.items, store) if store.kind == "state"
                                else inventory.contexts[store.name].row_count)
                    if relevant:
                        binding = next(item for item in snapshot.bindings
                                       if item.name == store.name)
                        kind = {"state": "state", "adk": "adk_context",
                                "langgraph": "langgraph_context"}[store.kind]
                        refs[(kind, store.name)] = PurgeReference(
                            kind=kind, owner_id=owner, object_id=store.name,
                            fingerprint=binding.fingerprint,
                        )
                # Release read locks before the separate durable queue commit.
                # The exclusive in-process gate still prevents new owner work.
                await db.rollback()
            plan = CleanupPlan(snapshot=snapshot, external=tuple(sorted(
                refs.values(), key=lambda ref: (ref.kind, ref.object_id))))
            return await jobs.enqueue(self.factory, owner, plan, now=self.clock(),
                                      automatic=automatic)

    async def enqueue_due_retention(self):
        """Queue due owner-scoped work only; the existing worker performs verified deletion."""
        async with self.factory() as db:
            # Account suspension must not exempt retained content from its expiry date.
            owners = list(await db.scalars(select(User.id)))
        result = {"checked": len(owners), "enqueued": 0, "retried": 0,
                  "skipped": 0, "failed": 0}
        now = self.clock()
        retry_before = datetime.fromtimestamp(now - AUTO_RETRY_SECONDS, UTC)

        for owner in owners:
            try:
                async with self.factory() as db:
                    open_job = await db.scalar(select(CleanupJob).where(
                        CleanupJob.user_id == owner, CleanupJob.status.in_(jobs.OPEN),
                    ).order_by(CleanupJob.created_at.desc()).limit(1))
                if open_job is not None:
                    if open_job.automatic and open_job.status == "needs_attention":
                        async with self.gate.exclusive(owner):
                            retried = await jobs.retry_automatic(
                                self.factory, owner, open_job.id, before=retry_before,
                            )
                        result["retried" if retried else "skipped"] += 1
                    else:
                        result["skipped"] += 1
                    continue

                preview = await self.preview(owner)
                if preview["selected_count"] == 0 or not preview["token"]:
                    result["skipped"] += 1
                    continue
                await self.confirm(owner, preview["token"], automatic=True)
                result["enqueued"] += 1
            except (AdmissionError, RetentionPolicyError, jobs.CleanupStateError) as error:
                if getattr(error, "code", "") in {
                    "retention_owner_busy", "cleanup_already_open", "cleanup_approval_conflict",
                } or isinstance(error, AdmissionError):
                    result["skipped"] += 1
                else:
                    result["failed"] += 1
                    logging.getLogger(__name__).warning(
                        "Scheduled retention could not verify one owner; code=%s",
                        getattr(error, "code", "retention_schedule_failed"),
                    )
            except Exception:
                result["failed"] += 1
                logging.getLogger(__name__).warning(
                    "Scheduled retention could not verify one owner; "
                    "code=retention_schedule_failed",
                )
        return result

    async def _lease(self, claimed, function, *args):
        async with self.factory() as db:
            await function(db, claimed["id"], claimed["token"], claimed["attempt"],
                           *args, now=self.clock())
            await db.commit()

    @staticmethod
    def _context_kwargs(store):
        return {"namespace": store.namespace} if store.kind == "adk" else {}

    async def _reset_context(self, db, owner, store, fingerprint, *, resumable=False):
        kwargs = self._context_kwargs(store)
        current = await CONTEXT_INVENTORY[store.kind](db, owner, **kwargs)
        if resumable and current.row_count == 0:
            return  # Atomic foreign-store reset committed before its receipt.
        await CONTEXT_RESET[store.kind](db, owner, fingerprint, **kwargs)
        if (await CONTEXT_INVENTORY[store.kind](db, owner, **kwargs)).row_count:
            raise RetentionPolicyError("retention_context_reset_unverified")

    async def _critical(self, claimed, plan):
        owner = claimed["owner"]
        async with self.factory() as db:
            row = await jobs.leased_row(db, claimed["id"], claimed["token"],
                                        claimed["attempt"], now=self.clock())
            _stored, remaining, _done = jobs._progress(row)
            started = row.critical_started_at is not None
            if row.sql_completed_at is not None:
                return
            if not started:
                inventory = await self.runtime.inventory(db, owner, lock=True)
                # Consent was already consumed while unexpired at enqueue. A
                # queue delay must not silently alter/expand the approved list.
                self.policy.validate(token=self.policy.serializer.dumps(
                    plan.snapshot.model_dump(mode="json")), owner_id=owner,
                    current=list(inventory.candidates), inventories=self.coverage(inventory),
                    now=utc(plan.snapshot.issued_at), bindings=inventory.bindings)
                await jobs.mark_started(db, claimed["id"], claimed["token"],
                                        claimed["attempt"], now=self.clock())
                await db.commit()
            stores = await self.runtime.stores(db)
            await db.rollback()
        bindings = {item.name: item for item in plan.snapshot.bindings}
        external_stores = {store.name: store for store in stores if store.factory is not None}
        for ref in remaining:
            if ref.kind not in {"state", "adk_context", "langgraph_context"}:
                continue
            store = external_stores.get(ref.object_id)
            if store is None or ref.fingerprint != bindings[ref.object_id].fingerprint:
                raise RetentionPolicyError("retention_store_disappeared")
            await self._lease(claimed, jobs.renew)
            # RuntimeStore rechecks the physical path before opening; do not
            # turn a disappeared or aliased native DB into a new empty store.
            async with store.session(None) as db:
                if store.kind == "state":
                    inventory = await state_inventory(db, owner, entities=store.entities,
                                                      native=store.native, lock=True)
                    present = {item.key for item in inventory.candidates}
                    selected = [item for item in _state_items(plan.snapshot.items, store)
                                if (item.kind.value, item.record_id) in present]
                    await purge_state(db, owner, selected, entities=store.entities,
                                      native=store.native, now=self.clock())
                    after = await state_inventory(db, owner, entities=store.entities,
                                                  native=store.native)
                    if {item.key for item in after.candidates} & {
                        (item.kind.value, item.record_id) for item in selected
                    }:
                        raise RetentionPolicyError("retention_state_purge_unverified")
                else:
                    await self._reset_context(db, owner, store, ref.fingerprint, resumable=started)
                await db.commit()
            await self._lease(claimed, jobs.record_critical_step, ref)
        # Cloud state/context share the app DB; native foreign steps have their
        # own receipts above. Application rows + final checkpoint stay atomic.
        async with self.factory() as db:
            await jobs.renew(db, claimed["id"], claimed["token"], claimed["attempt"],
                             now=self.clock())
            for store in stores:
                if store.factory is not None:
                    continue
                if store.kind == "state":
                    await purge_state(db, owner, _state_items(plan.snapshot.items, store),
                                      entities=store.entities, now=self.clock())
                else:
                    await self._reset_context(db, owner, store, bindings[store.name].fingerprint)
            await purge_application(db, owner, _application(plan.snapshot.items), now=self.clock())
            await jobs.mark_sql_done(db, claimed["id"], claimed["token"], claimed["attempt"],
                                    now=self.clock())
            await db.commit()

    async def execute_one(self):
        claimed = await jobs.claim(self.factory, now=self.clock())
        if claimed is None:
            return False
        try:
            async with self.gate.exclusive(claimed["owner"]):
                plan = CleanupPlan.model_validate_json(claimed["plan_json"])
                await self._critical(claimed, plan)
                async with self.factory() as db:
                    row = await jobs.leased_row(db, claimed["id"], claimed["token"],
                                                claimed["attempt"], now=self.clock())
                    _plan, remaining, _done = jobs._progress(row)
                for ref in remaining:
                    await self._lease(claimed, jobs.renew)
                    if ref.kind == "pdf":
                        async with self.factory() as db:
                            objects = await object_inventory(
                                db, self.runtime.storage, claimed["owner"])
                        validate_object_reference(ref, objects)
                        await self.runtime.storage.delete_verified(ref.owner_id, ref.object_id)
                    else:
                        approved = (VectorPoint(ref.kind, ref.object_id, ref.owner_id,
                                                ref.fingerprint) if ref.fingerprint else None)
                        await self.runtime.vectors.delete_verified(ref, approved=approved)
                    await self._lease(claimed, jobs.record_purge, ref)
                await self._lease(claimed, jobs.finish)
        except asyncio.CancelledError:
            raise  # SQL rollback / external idempotent readback resumes the same job.
        except (jobs.CleanupLeaseLost, jobs.CleanupStateError):
            raise
        except Exception as error:
            code = ("owner_busy" if isinstance(error, AdmissionError)
                    else "storage_unavailable" if getattr(error, "code", "").startswith(
                        ("object_", "retention_object"))
                    else "vector_unavailable" if getattr(error, "code", "").startswith(
                        "retention_vector") else "approval_changed")
            await self._lease(claimed, jobs.fail, code)
            # Never log rejected source content, storage paths or provider text.
            logging.getLogger(__name__).warning("Cleanup requires attention; code=%s", code)
        return True

    async def worker(self):
        while True:
            try:
                worked = await self.execute_one()
            except Exception:
                worked = False
                logging.getLogger(__name__).warning("Cleanup worker will retry")
            await asyncio.sleep(0.2 if worked else 2)
