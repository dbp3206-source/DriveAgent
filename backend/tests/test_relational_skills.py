from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.services.relational_skills import RelationalSkillStore, skills
from app.services.skills import SkillSpec
from app.tools.contracts import ToolError


def example():
    return SkillSpec(name="daily_report", title="Báo cáo hàng ngày",
                     description="Tổng hợp nguồn đã chọn", goal="Báo cáo {date}",
                     procedure=["Đọc nguồn cho {date}", "Kiểm tra nguồn"],
                     preferred_capabilities=["gmail"], output_format="Markdown")


@pytest.fixture
def store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'portable.db'}")
    RelationalSkillStore.create_schema(engine)
    yield RelationalSkillStore(engine)
    engine.dispose()


def test_owner_revision_archive_and_fresh_input(store):
    first = store.save("alice", example())
    store.save("bob", example())
    assert len(store.list("alice")) == 1
    assert store.run("alice", "daily_report", {"date": "2026-09-30"})["goal"] == (
        "Báo cáo 2026-09-30"
    )
    with pytest.raises(ToolError, match="Thiếu đầu vào"):
        store.run("alice", "daily_report", {})
    with pytest.raises(ToolError) as denied:
        store.get("bob", first["id"])
    assert denied.value.code == "skill_not_found"
    second = store.save("alice", example(), expected_revision=1)
    assert second["revision"] == 2
    with pytest.raises(ToolError) as stale:
        store.save("alice", example(), expected_revision=1)
    assert stale.value.code == "revision_conflict"
    with pytest.raises(ToolError):
        store.archive("bob", first["id"])
    store.archive("alice", first["id"])
    assert not store.list("alice")
    assert len(store.list("alice", include_archived=True)) == 1


def test_simultaneous_revision_has_one_winner(store):
    store.save("alice", example())

    def edit(_):
        try:
            store.save("alice", example(), expected_revision=1)
            return "saved"
        except ToolError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(edit, range(4)))
    assert results.count("saved") == 1
    assert results.count("revision_conflict") == 3
    assert store.get("alice", "daily_report")["revision"] == 2


def test_portable_schema_compiles_for_postgres():
    ddl = str(CreateTable(skills).compile(dialect=postgresql.dialect()))
    assert "uq_skills_user_name" in ddl
    assert "PRAGMA" not in ddl
    assert "user_id" in ddl


def test_reopen_preserves_state(tmp_path):
    url = f"sqlite:///{tmp_path / 'persistent.db'}"
    engine = create_engine(url)
    RelationalSkillStore.create_schema(engine)
    created = RelationalSkillStore(engine).save("alice", example())
    engine.dispose()
    reopened = create_engine(url)
    try:
        assert RelationalSkillStore(reopened).get("alice", created["id"])["revision"] == 1
    finally:
        reopened.dispose()


def test_factory_has_explicit_bootstrap_and_no_local_copy(tmp_path):
    from app.core.config import Settings
    from app.services.relational_skills import (
        close_state_engines,
        initialize_skill_store,
        skill_store,
    )
    from app.services.skills import SkillStore

    # Use isolated local root, not the repository's real private Skills.
    class Profile:
        data_dir = tmp_path
        relational_state_url = None

    SkillStore(tmp_path).save("alice", example())
    assert len(skill_store(Profile()).list("alice")) == 1
    cloud = Settings(_env_file=None, relational_state_url=f"sqlite:///{tmp_path / 'cloud.db'}")
    try:
        initialize_skill_store(cloud)
        assert skill_store(cloud).list("alice") == []
        skill_store(cloud).save("bob", example())
        assert SkillStore(tmp_path).list("bob") == []
    finally:
        close_state_engines()
