"""Real local/native and relational-SQLite storage; no external service calls."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from app.services import relational_skills, skills
from app.services.relational_skills import RelationalSkillStore
from app.services.skills import SkillSpec, SkillStore, skill_content_hash
from app.tools.contracts import ToolError

OLD = datetime(2026, 9, 1, 12, tzinfo=UTC)
NEW = OLD + timedelta(days=40)
OWNER = "synthetic-owner-a"
OTHER = "synthetic-owner-b"


@pytest.fixture(params=["native", "relational-sqlite"])
def store(request, tmp_path):
    if request.param == "native":
        yield SkillStore(tmp_path)
        return
    engine = create_engine(f"sqlite:///{tmp_path / 'relational-skills.db'}")
    try:
        RelationalSkillStore.create_schema(engine)
        yield RelationalSkillStore(engine)
    finally:
        engine.dispose()


def stamp(monkeypatch, value):
    clock = SimpleNamespace(time=lambda: value.timestamp())
    monkeypatch.setattr(skills, "time", clock)
    monkeypatch.setattr(relational_skills, "time", clock)


def spec():
    return SkillSpec(name="synthetic_report", title="Synthetic report",
                     description="Synthetic notes only", goal="Summarize {topic}",
                     procedure=["Read selected sources", "Show missing facts"],
                     output_format="Short report")


def sql(store, statement, values=()):
    if isinstance(store, RelationalSkillStore):
        with store.engine.begin() as db:
            result = db.exec_driver_sql(statement, values)
            return result.fetchall() if result.returns_rows else []
    with store.connect() as db:
        result = db.execute(statement, values)
        return result.fetchall() if result.description else []


def test_read_archive_and_same_text_save_do_not_extend_skill_age(store, monkeypatch):
    stamp(monkeypatch, OLD)
    item = store.save(OWNER, spec())
    original = store.retention_candidates(OWNER)
    assert original[0].changed_at == OLD
    assert store.retention_candidates(OTHER) == []
    stamp(monkeypatch, NEW)
    store.get(OWNER, item["id"])
    store.list(OWNER)
    store.run(OWNER, item["name"], {"topic": "synthetic"})
    assert store.retention_candidates(OWNER) == original
    store.archive(OWNER, item["id"])
    archived = store.retention_candidates(OWNER)
    assert len(archived) == 1 and archived[0].changed_at == OLD
    assert archived[0].fingerprint != original[0].fingerprint
    same = store.save(OWNER, spec(), expected_revision=1)
    assert same["revision"] == 2
    assert store.retention_candidates(OWNER)[0].changed_at == OLD
    changed = spec().model_copy(update={"goal": "Compare selected sources for {topic}"})
    store.save(OWNER, changed, expected_revision=2)
    after = store.retention_candidates(OWNER)
    assert after[0].changed_at == NEW
    with pytest.raises(ToolError, match="Skill"):
        store.save(OWNER, spec(), expected_revision=1)
    assert store.retention_candidates(OWNER) == after
    with pytest.raises(ToolError):
        store.archive(OTHER, item["id"])
    assert store.retention_candidates(OTHER) == []


def test_legacy_positional_insert_and_rollback_edit_preserve_safest_known_age(
    store, monkeypatch,
):
    skill_id = str(uuid4())
    # Exactly the old eight-column INSERT: the companion does not break it.
    sql(store, "INSERT INTO skills VALUES (?,?,?,?,?,?,?,?)", (
        skill_id, OWNER, spec().name, spec().model_dump_json(), 1, 1,
        OLD.timestamp(), OLD.timestamp(),
    ))
    assert store.retention_candidates(OWNER)[0].changed_at == OLD
    stamp(monkeypatch, NEW)
    store.archive(OWNER, skill_id)
    assert store.retention_candidates(OWNER)[0].changed_at == OLD
    changed = spec().model_copy(update={"description": "Changed by a synthetic old release"})
    sql(store, "UPDATE skills SET spec=?,updated=? WHERE id=? AND user_id=?", (
        changed.model_dump_json(), NEW.timestamp(), skill_id, OWNER,
    ))
    original_clock = sql(store, "SELECT * FROM skill_content_clocks WHERE skill_id=?", (skill_id,))
    assert store.retention_candidates(OWNER)[0].changed_at == NEW
    assert sql(store, "SELECT * FROM skill_content_clocks WHERE skill_id=?", (skill_id,)) == (
        original_clock
    )  # A read does not repair/write metadata behind the user's back.
    stamp(monkeypatch, NEW + timedelta(days=1))
    store.archive(OWNER, skill_id)
    assert store.retention_candidates(OWNER)[0].changed_at == NEW
    clocks = sql(store, "SELECT content_hash FROM skill_content_clocks WHERE skill_id=?",
                 (skill_id,))
    assert clocks[0][0] == skill_content_hash(changed.model_dump_json())


@pytest.mark.parametrize("fault", ["owner", "negative-age", "infinite-age"])
def test_corrupt_clock_cannot_authorize_or_mutate_skill(store, monkeypatch, fault):
    stamp(monkeypatch, OLD)
    item = store.save(OWNER, spec())
    if fault == "owner":
        sql(store, "UPDATE skill_content_clocks SET user_id=? WHERE skill_id=?",
            (OTHER, item["id"]))
    else:
        sql(store, "UPDATE skill_content_clocks SET content_changed=? WHERE skill_id=?",
            (-1 if fault == "negative-age" else float("inf"), item["id"]))
    before = sql(store, "SELECT * FROM skills WHERE id=?", (item["id"],))
    with pytest.raises(ToolError):
        store.retention_candidates(OWNER)
    with pytest.raises(ToolError):
        store.archive(OWNER, item["id"])
    with pytest.raises(ToolError):
        store.save(OWNER, spec(), expected_revision=1)
    assert sql(store, "SELECT * FROM skills WHERE id=?", (item["id"],)) == before


def test_retention_output_contains_no_spec_text_or_other_owners(store, monkeypatch):
    stamp(monkeypatch, OLD)
    own = spec().model_copy(update={"description": "SYNTHETIC_PRIVATE_SENTINEL"})
    store.save(OWNER, own)
    store.save(OTHER, spec())
    result = store.retention_candidates(OWNER)
    assert len(result) == 1 and result[0].owner_id == OWNER
    assert "SYNTHETIC_PRIVATE_SENTINEL" not in repr(result)
    assert OTHER not in repr(result)
