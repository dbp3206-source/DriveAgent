"""No network/filesystem/DB: selection contract, not proof of an end-to-end purge."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.services.retention_policy import (
    APPROVAL_SECONDS,
    MAX_APPROVAL_ITEMS,
    REQUIRED_INVENTORIES,
    RetentionCandidate,
    RetentionKind,
    RetentionPolicy,
    RetentionPolicyError,
    content_fingerprint,
)

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
SECRET = "synthetic-retention-signing-key-not-used-on-cloud"
OWNER = "synthetic-owner-a"


def candidate(*, record_id="synthetic-one", owner_id=OWNER, kind=RetentionKind.MEMORY,
              age=31, content="Synthetic note, not production data", active=False):
    changed_at = NOW - timedelta(days=age)
    return RetentionCandidate(
        owner_id=owner_id, kind=kind, record_id=record_id, changed_at=changed_at,
        fingerprint=content_fingerprint(
            owner_id=owner_id, kind=kind, record_id=record_id, changed_at=changed_at,
            values={"content": content, "revision": 1},
        ), active=active,
    )


def inventories():
    return dict.fromkeys(REQUIRED_INVENTORIES, True)


def prepare(policy, rows, **kwargs):
    return policy.prepare(owner_id=OWNER, candidates=rows, inventories=inventories(),
                          now=NOW, **kwargs)


def validate(policy, token, rows, *, now=NOW, owner_id=OWNER):
    return policy.validate(token=token, owner_id=owner_id, current=rows,
                           inventories=inventories(), now=now)


def test_age_boundary_timezone_and_future_preserve_original_candidates():
    policy = RetentionPolicy(SECRET)
    rows = [candidate(record_id="before", age=29), candidate(record_id="exact", age=30),
            candidate(record_id="after", age=31), candidate(record_id="future", age=-1)]
    originals = tuple(rows)
    preview = prepare(policy, rows)
    approved = validate(policy, preview.token, rows)
    assert {item.record_id for item in approved.items} == {"exact", "after"}
    assert preview.due_count == preview.selected_count == 2
    assert tuple(rows) == originals  # No viewing-time mutation or implied deletion.
    shifted = [replace(item, changed_at=item.changed_at.astimezone(
        timezone(timedelta(hours=7)))) for item in rows]
    assert validate(policy, preview.token, shifted).approval_id == preview.approval_id
    naive = [replace(item, changed_at=item.changed_at.replace(tzinfo=None)) for item in rows]
    assert validate(policy, preview.token, naive).approval_id == preview.approval_id


def test_owner_isolation_no_empty_approval_and_active_records_are_not_selected():
    policy = RetentionPolicy(SECRET)
    rows = [candidate(owner_id="synthetic-owner-b"), candidate(active=True)]
    preview = prepare(policy, rows)
    assert preview.token is None and preview.approval_id is None
    assert preview.selected_count == 0 and preview.due_count == 1
    assert preview.active_due_count == 1 and preview.counts == {}
    old = candidate()
    token = prepare(policy, [old]).token
    with pytest.raises(RetentionPolicyError, match="invalid_retention_approval"):
        validate(policy, token, [old], owner_id="synthetic-owner-b")


@pytest.mark.parametrize("inventory", sorted(REQUIRED_INVENTORIES))
def test_missing_or_failed_store_blocks_prepare_and_confirm(inventory):
    policy = RetentionPolicy(SECRET)
    rows = [candidate()]
    token = prepare(policy, rows).token
    for missing in (False, None):
        coverage = inventories()
        if missing is None:
            coverage.pop(inventory)
        else:
            coverage[inventory] = False
        with pytest.raises(RetentionPolicyError, match="retention_inventory_incomplete"):
            policy.prepare(owner_id=OWNER, candidates=rows, inventories=coverage, now=NOW)
        with pytest.raises(RetentionPolicyError, match="retention_inventory_incomplete"):
            policy.validate(token=token, owner_id=OWNER, current=rows,
                            inventories=coverage, now=NOW)


@pytest.mark.parametrize("change", ["content", "date", "active", "gone", "owner", "kind"])
def test_changed_snapshot_cannot_be_confirmed(change):
    policy = RetentionPolicy(SECRET)
    old = candidate()
    token = prepare(policy, [old]).token
    current = {
        "content": [candidate(content="Changed synthetic note")],
        "date": [replace(old, changed_at=NOW - timedelta(days=30))],
        "active": [replace(old, active=True)],
        "gone": [],
        "owner": [replace(old, owner_id="synthetic-owner-b")],
        "kind": [replace(old, kind=RetentionKind.ARTIFACT)],
    }[change]
    with pytest.raises(RetentionPolicyError, match="retention_preview_changed"):
        validate(policy, token, current)


def test_newly_due_items_are_not_silently_added_to_old_approval():
    policy = RetentionPolicy(SECRET)
    old = candidate()
    token = prepare(policy, [old]).token
    result = validate(policy, token, [candidate(record_id="newly-eligible"), old])
    assert [item.record_id for item in result.items] == [old.record_id]


@pytest.mark.parametrize("seconds", [-1, APPROVAL_SECONDS, APPROVAL_SECONDS + 1])
def test_expired_or_future_approvals_are_rejected(seconds):
    policy = RetentionPolicy(SECRET)
    rows = [candidate()]
    token = prepare(policy, rows).token
    with pytest.raises(RetentionPolicyError, match="retention_approval_expired"):
        validate(policy, token, rows, now=NOW + timedelta(seconds=seconds))


def test_tampering_bad_shape_wrong_key_and_wrong_purpose_are_rejected():
    policy = RetentionPolicy(SECRET)
    rows = [candidate()]
    token = prepare(policy, rows).token
    for value in ("invalid", token + "bad", policy.serializer.dumps({}), "x" * 100_001):
        with pytest.raises(RetentionPolicyError, match="invalid_retention_approval"):
            validate(policy, value, rows)
    with pytest.raises(RetentionPolicyError, match="invalid_retention_approval"):
        validate(RetentionPolicy(SECRET + "-changed"), token, rows)
    from itsdangerous import URLSafeSerializer

    wrong_purpose = URLSafeSerializer(SECRET, salt="google-document-approval")
    foreign = wrong_purpose.dumps(policy.serializer.loads(token))
    with pytest.raises(RetentionPolicyError, match="invalid_retention_approval"):
        validate(policy, foreign, rows)


def test_payload_contains_no_note_text_and_duplicates_fail_closed():
    policy = RetentionPolicy(SECRET)
    content = "PRIVATE_TEST_SENTINEL_not_a_real_person_or_document"
    row = candidate(content=content)
    preview = prepare(policy, [row])
    payload = policy.serializer.loads(preview.token)
    assert content not in str(payload)
    assert set(payload["items"][0]) == {"kind", "record_id", "changed_at", "fingerprint"}
    with pytest.raises(RetentionPolicyError, match="duplicate_retention_candidate"):
        prepare(policy, [row, row])
    forged = dict(payload)
    forged["items"] *= 2
    with pytest.raises(RetentionPolicyError, match="retention_preview_changed"):
        validate(policy, policy.serializer.dumps(forged), [row])


def test_bounded_selection_all_kinds_and_separate_approvals():
    policy = RetentionPolicy(SECRET)
    rows = [candidate(record_id=f"item-{index:04d}",
                      kind=list(RetentionKind)[index % len(RetentionKind)])
            for index in range(MAX_APPROVAL_ITEMS + 1)]
    preview = prepare(policy, rows)
    result = validate(policy, preview.token, rows)
    assert preview.has_more and preview.due_count == MAX_APPROVAL_ITEMS + 1
    assert len(result.items) == preview.selected_count == MAX_APPROVAL_ITEMS
    assert set(preview.counts) == {kind.value for kind in RetentionKind}
    assert prepare(policy, rows).approval_id != result.approval_id


def test_fingerprint_is_stable_but_bound_to_owner_identity_content_and_time():
    args = dict(owner_id=OWNER, kind=RetentionKind.MEMORY, record_id="synthetic-one",
                changed_at=NOW, values={"content": "Synthetic note", "revision": 1})
    expected = content_fingerprint(**args)
    assert content_fingerprint(**(args | {"values": {
        "revision": 1, "content": "Synthetic note"}})) == expected
    for key, value in [("owner_id", "other"), ("kind", RetentionKind.ARTIFACT),
                       ("record_id", "different"), ("changed_at", NOW - timedelta(seconds=1)),
                       ("values", {"content": "Different note", "revision": 1})]:
        assert content_fingerprint(**(args | {key: value})) != expected
    with pytest.raises(ValueError):
        content_fingerprint(**(args | {"values": {"value": float("nan")}}))


def test_invalid_candidates_and_weak_signing_key_are_not_accepted():
    with pytest.raises(RetentionPolicyError, match="retention_signing_secret_too_short"):
        RetentionPolicy("short")
    old = candidate()
    for key, value in [("kind", "account"), ("record_id", ""), ("owner_id", ""),
                       ("fingerprint", "not-a-digest")]:
        with pytest.raises(RetentionPolicyError):
            replace(old, **{key: value})
