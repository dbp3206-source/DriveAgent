import pytest

from app.services.skills import SkillSpec, SkillStore
from app.tools.contracts import ToolError


def skill():
    return SkillSpec(
        name="project_report",
        title="Tạo báo cáo project",
        description="Quy trình báo cáo có nguồn",
        goal="Báo cáo cho {project}",
        procedure=["Tìm tài liệu {project}", "Đọc bằng chứng", "Soạn báo cáo"],
        constraints=["Không bịa nguồn"],
        preferred_capabilities=["drive", "rag", "docs"],
        output_format="Google Docs",
    )


def test_skill_lifecycle_is_user_scoped_and_versioned(tmp_path):
    store = SkillStore(tmp_path)
    created = store.save("alice", skill())
    assert created["revision"] == 1
    assert store.run("alice", "project_report", {"project": "RAG"})["goal"] == "Báo cáo cho RAG"
    updated_spec = skill().model_copy(update={"description": "Báo cáo ngắn gọn"})
    updated = store.save("alice", updated_spec, expected_revision=1)
    assert updated["revision"] == 2
    with pytest.raises(ToolError) as conflict:
        store.save("alice", updated_spec, expected_revision=1)
    assert conflict.value.code == "revision_conflict"
    with pytest.raises(ToolError):
        store.get("bob", created["id"])
    assert store.archive("alice", created["id"])["active"] is False


def test_skill_requires_fresh_placeholder_inputs(tmp_path):
    store = SkillStore(tmp_path)
    store.save("alice", skill())
    with pytest.raises(ToolError) as missing:
        store.run("alice", "project_report", {})
    assert missing.value.code == "skill_input_missing"
