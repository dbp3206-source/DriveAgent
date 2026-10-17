"""Content-retention selection and approval contract, with no deletion side effects.

Storage adapters must finish the complete inventory and re-read selected records
under their write fence before using an approval. This module is not itself a
cleanup runner, an API, or evidence that the live product deletes old content.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4

from itsdangerous import BadData, URLSafeSerializer
from pydantic import BaseModel, ConfigDict, Field, ValidationError

CONTENT_RETENTION_DAYS = 30
APPROVAL_SECONDS = 600
MAX_APPROVAL_ITEMS = 200
# A successful ORM query alone cannot stand in for these independent stores.
REQUIRED_INVENTORIES = frozenset({
    "application", "framework", "vectors", "objects", "state", "backups",
})


class RetentionKind(StrEnum):
    CHAT = "chat"
    MEMORY = "memory"
    SOURCE = "source"
    INDEX = "index"
    ARTIFACT = "artifact"
    SKILL = "skill"
    COMPANY = "company"
    JOB = "job"
    OPERATION = "operation"
    AUDIT = "audit"
    FRAMEWORK = "framework"


class RetentionPolicyError(ValueError):
    """Stable error codes, never a rejected value or document in the message."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def utc(value: datetime) -> datetime:
    # SQLite returns the UTC ORM timestamps without timezone information.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return utc(value).isoformat()
    raise TypeError("unsupported_retention_fingerprint_value")


def content_fingerprint(*, owner_id: str, kind: RetentionKind, record_id: str,
                        changed_at: datetime, values: dict[str, Any]) -> str:
    """Hash an adapter's actual revision/content; never put it in an approval.

    Adapters must include all content, linkage and execution-state fields whose
    change could alter the deletion scope. A caller-provided revision number
    alone does not establish that the underlying content is still unchanged.
    """
    canonical = json.dumps(
        [owner_id, kind.value, record_id, utc(changed_at).isoformat(), values],
        ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
        default=_json_default,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True)
class RetentionCandidate:
    owner_id: str
    kind: RetentionKind
    record_id: str
    changed_at: datetime
    fingerprint: str
    active: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, RetentionKind):
            raise RetentionPolicyError("invalid_candidate_kind")
        if not isinstance(self.owner_id, str) or not self.owner_id or len(self.owner_id) > 200:
            raise RetentionPolicyError("invalid_candidate_identity")
        if not isinstance(self.record_id, str) or not self.record_id or len(self.record_id) > 200:
            raise RetentionPolicyError("invalid_candidate_identity")
        if (not isinstance(self.fingerprint, str) or len(self.fingerprint) != 64
                or any(c not in "0123456789abcdef" for c in self.fingerprint)):
            raise RetentionPolicyError("invalid_candidate_fingerprint")
        if not isinstance(self.changed_at, datetime) or type(self.active) is not bool:
            raise RetentionPolicyError("invalid_candidate_state")

    @property
    def key(self) -> tuple[str, str]:
        return self.kind.value, self.record_id


class SnapshotItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: RetentionKind
    record_id: str = Field(min_length=1, max_length=200)
    changed_at: datetime
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class StoreBinding(BaseModel):
    """Pin derived-store contents without putting private payloads in a token."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    count: int = Field(ge=0, le=1_000_000)


class ApprovalSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: int = 1
    approval_id: str = Field(min_length=36, max_length=36)
    owner_id: str = Field(min_length=1, max_length=200)
    issued_at: datetime
    cutoff: datetime
    items: tuple[SnapshotItem, ...] = Field(min_length=1, max_length=MAX_APPROVAL_ITEMS)
    bindings: tuple[StoreBinding, ...] = Field(default=(), max_length=16)


@dataclass(frozen=True)
class RetentionPreview:
    approval_id: str | None
    token: str | None
    selected_count: int
    due_count: int
    active_due_count: int
    has_more: bool
    counts: dict[str, int]
    expires_at: datetime | None
    cutoff: datetime


class RetentionPolicy:
    def __init__(self, secret: str):
        if len(secret) < 32:
            raise RetentionPolicyError("retention_signing_secret_too_short")
        self.serializer = URLSafeSerializer(
            secret, salt="veridra-content-retention-v1",
            signer_kwargs={"digest_method": hashlib.sha256},
        )

    @staticmethod
    def _complete_inventory(inventories: dict[str, bool]) -> None:
        if set(inventories) != REQUIRED_INVENTORIES or any(
            value is not True for value in inventories.values()
        ):
            raise RetentionPolicyError("retention_inventory_incomplete")

    @staticmethod
    def _owned(owner_id: str, candidates: list[RetentionCandidate]
               ) -> dict[tuple[str, str], RetentionCandidate]:
        if not isinstance(owner_id, str) or not owner_id or len(owner_id) > 200:
            raise RetentionPolicyError("invalid_retention_owner")
        owned = {}
        for candidate in candidates:
            if candidate.owner_id != owner_id:
                continue
            if candidate.key in owned:
                raise RetentionPolicyError("duplicate_retention_candidate")
            owned[candidate.key] = candidate
        return owned

    def prepare(self, *, owner_id: str, candidates: list[RetentionCandidate],
                inventories: dict[str, bool], now: datetime,
                bindings: tuple[StoreBinding, ...] = ()) -> RetentionPreview:
        """Read-only selection; neither viewing nor signing is deletion consent."""
        self._complete_inventory(inventories)
        stamp = utc(now)
        cutoff = stamp - timedelta(days=CONTENT_RETENTION_DAYS)
        due = [candidate for candidate in self._owned(owner_id, candidates).values()
               if utc(candidate.changed_at) <= cutoff]
        eligible = sorted((candidate for candidate in due if not candidate.active),
                          key=lambda item: (utc(item.changed_at), item.key))
        chosen = eligible[:MAX_APPROVAL_ITEMS]
        approval_id, token, expires_at = None, None, None
        if chosen:
            approval_id = str(uuid4())
            snapshot = ApprovalSnapshot(
                approval_id=approval_id, owner_id=owner_id, issued_at=stamp, cutoff=cutoff,
                items=tuple(SnapshotItem(
                    kind=item.kind, record_id=item.record_id, changed_at=utc(item.changed_at),
                    fingerprint=item.fingerprint,
                ) for item in chosen),
                bindings=bindings,
            )
            token = self.serializer.dumps(snapshot.model_dump(mode="json"))
            expires_at = stamp + timedelta(seconds=APPROVAL_SECONDS)
        return RetentionPreview(
            approval_id=approval_id, token=token, selected_count=len(chosen),
            due_count=len(due), active_due_count=sum(item.active for item in due),
            has_more=len(eligible) > len(chosen),
            counts=dict(Counter(item.kind.value for item in chosen)),
            expires_at=expires_at, cutoff=cutoff,
        )

    def validate(self, *, token: str, owner_id: str, current: list[RetentionCandidate],
                 inventories: dict[str, bool], now: datetime,
                 bindings: tuple[StoreBinding, ...] = ()) -> ApprovalSnapshot:
        """Revalidate under the runner's fence, before its first deletion.

        This authenticates a preview, not a user's click. Manual API calls must
        still require explicit confirmation and a trusted browser origin; the
        internal scheduler may use it only for records due under the expiry policy.
        Execution must claim approval_id in its durable ledger to prevent replay.
        """
        self._complete_inventory(inventories)
        if not isinstance(token, str) or len(token) > 100_000:
            raise RetentionPolicyError("invalid_retention_approval")
        try:
            snapshot = ApprovalSnapshot.model_validate(self.serializer.loads(token))
        except (BadData, ValidationError, TypeError, ValueError):
            raise RetentionPolicyError("invalid_retention_approval") from None
        if snapshot.version != 1 or snapshot.owner_id != owner_id:
            raise RetentionPolicyError("invalid_retention_approval")
        if (snapshot.bindings != bindings
                or len({item.name for item in bindings}) != len(bindings)):
            raise RetentionPolicyError("retention_preview_changed")
        stamp, issued_at = utc(now), utc(snapshot.issued_at)
        if stamp < issued_at or stamp >= issued_at + timedelta(seconds=APPROVAL_SECONDS):
            raise RetentionPolicyError("retention_approval_expired")
        if utc(snapshot.cutoff) != issued_at - timedelta(days=CONTENT_RETENTION_DAYS):
            raise RetentionPolicyError("invalid_retention_approval")
        owned = self._owned(owner_id, current)
        seen = set()
        for approved in snapshot.items:
            key = approved.kind.value, approved.record_id
            row = owned.get(key)
            if key in seen or row is None or row.active:
                raise RetentionPolicyError("retention_preview_changed")
            seen.add(key)
            if (row.fingerprint != approved.fingerprint
                    or utc(row.changed_at) != utc(approved.changed_at)
                    or utc(row.changed_at) > utc(snapshot.cutoff)):
                raise RetentionPolicyError("retention_preview_changed")
        # Newly eligible records are deliberately not added to this approval.
        return snapshot
