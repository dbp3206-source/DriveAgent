from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api import admin, protocols, skills, system
from app.core.config import Settings
from app.db.models import User, UserRole
from app.services.skills import SkillSpec
from app.tools.contracts import ToolContext, ToolError
from app.tools.skills import SkillArchive, SkillList, SkillRun, SkillSave, skill_tool_definitions


def _user(user_id: str = "user-1", role: str = "super_admin") -> User:
    return User(id=user_id, email=f"{user_id}@example.test", display_name=user_id, role=role)


def _request(**state):
    app_state = SimpleNamespace(**state)
    return SimpleNamespace(
        app=SimpleNamespace(state=app_state),
        state=SimpleNamespace(request_id="req-1"),
        headers={"origin": "http://localhost:8000"},
        url=SimpleNamespace(scheme="http", netloc="localhost:8000"),
    )


@pytest.mark.asyncio
async def test_admin_role_management_success_and_guards():
    admin_user = _user("admin")
    member = _user("member", "viewer")
    db = AsyncMock()
    scalars = MagicMock()
    scalars.all.return_value = [admin_user, member]
    db.scalars.return_value = scalars

    listed = await admin.list_users(db, admin_user)
    assert [item.email for item in listed] == [admin_user.email, member.email]
    roles = await admin.list_roles(admin_user)
    assert "super_admin" in roles and roles["super_admin"]

    db.get.return_value = None
    with pytest.raises(HTTPException) as missing:
        await admin.update_role("missing", admin.RoleUpdate(role=UserRole.EDITOR), db, admin_user)
    assert missing.value.status_code == 404

    db.get.return_value = admin_user
    with pytest.raises(HTTPException) as self_demotion:
        await admin.update_role(
            admin_user.id, admin.RoleUpdate(role=UserRole.EDITOR), db, admin_user
        )
    assert self_demotion.value.status_code == 400

    db.get.return_value = member
    updated = await admin.update_role(
        member.id, admin.RoleUpdate(role=UserRole.EDITOR), db, admin_user
    )
    assert updated.role == "editor"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_protocol_token_origin_guard_and_cache_headers():
    settings = Settings(_env_file=None, app_secret="x" * 32)
    request = _request()
    with (
        patch.object(protocols, "get_settings", return_value=settings),
        patch.object(protocols, "is_trusted_ui_origin", return_value=False),
    ):
        with pytest.raises(HTTPException) as blocked:
            await protocols.issue_token(request, _user())
    assert blocked.value.status_code == 403

    with (
        patch.object(protocols, "get_settings", return_value=settings),
        patch.object(protocols, "is_trusted_ui_origin", return_value=True),
    ):
        response = await protocols.issue_token(request, _user())
    assert response.headers["cache-control"] == "no-store"
    assert b'"scope":"knowledge:read"' in response.body


@pytest.mark.asyncio
async def test_skill_handlers_and_api_delegate_to_governed_registry(tmp_path):
    user = _user()
    settings = Settings(_env_file=None, data_dir=tmp_path)
    context = ToolContext(
        request_id="req-1", user=user, db=AsyncMock(), settings=settings, source="test"
    )
    skill_name = f"study_plan_{uuid4().hex[:8]}"
    spec = SkillSpec(
        name=skill_name,
        title="Study plan",
        description="Create a plan",
        goal="Create a plan for {project}",
        procedure=["Read {project}", "Write plan"],
        constraints=["Use current context"],
        output_format="Markdown checklist",
    )
    saved = await skill_tool_definitions()[0].handler(SkillSave(skill=spec), context)
    assert saved.data["name"] == skill_name
    listed = await skill_tool_definitions()[2].handler(SkillList(), context)
    assert listed.data["items"][0]["name"] == skill_name
    run_result = await skill_tool_definitions()[1].handler(
        SkillRun(name=skill_name, inputs={"project": "DriveAgent"}), context
    )
    assert "DriveAgent" in " ".join(run_result.data["procedure"])
    archived = await skill_tool_definitions()[3].handler(
        SkillArchive(skill_id=saved.data["id"]), context
    )
    assert archived.data["active"] is False

    registry = SimpleNamespace(execute=AsyncMock(return_value={"data": {"items": []}}))
    request = _request(registry=registry)
    with patch.object(skills, "get_settings", return_value=settings):
        assert await skills.list_all(request, user, context.db) == {"data": {"items": []}}
    registry.execute.assert_awaited_once()

    with patch.object(skills, "invoke", AsyncMock(return_value={"ok": True})) as invoke:
        assert await skills.save(SkillSave(skill=spec), request, user, context.db) == {"ok": True}
        assert await skills.run(
            SkillRun(name=skill_name, inputs={"project": "X"}), request, user, context.db
        ) == {"ok": True}
        assert await skills.archive(
            SkillArchive(skill_id=saved.data["id"]), request, user, context.db
        ) == {"ok": True}
    assert [call.args[0] for call in invoke.await_args_list] == [
        "skill_save",
        "skill_run",
        "skill_archive",
    ]


@pytest.mark.asyncio
async def test_system_health_catalog_and_operation_guards(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path)
    request = _request(
        vector_store=SimpleNamespace(backend_name="qdrant-embedded"),
        runtime_started_at="2026-09-15T00:00:00Z",
        registry=SimpleNamespace(definitions=lambda: skill_tool_definitions()),
    )
    db = AsyncMock()
    with patch.object(system, "get_settings", return_value=settings):
        result = await system.health(request, db)
        assert result.status == "ok" and result.database is True
        catalog = await system.tool_catalog(request, _user())
        assert {item["name"] for item in catalog} == {
            "skill_save",
            "skill_run",
            "skill_list",
            "skill_archive",
        }

    db.execute.side_effect = RuntimeError("database unavailable")
    request.app.state.vector_store.backend_name = "sqlite"
    with patch.object(system, "get_settings", return_value=settings):
        degraded = await system.health(request, db)
    assert degraded.status == "degraded" and degraded.database is False

    user = _user()
    with (
        patch.object(system, "get_settings", return_value=settings),
        patch.object(system, "is_trusted_ui_origin", return_value=False),
    ):
        for action in (
            lambda: system.acknowledge_operation("op", request, user),
            lambda: system.reconcile_operation("op", request, user, AsyncMock()),
            lambda: system.archive_operation("op", request, user),
        ):
            with pytest.raises(HTTPException) as blocked:
                await action()
            assert blocked.value.status_code == 403

    with (
        patch.object(system, "get_settings", return_value=settings),
        patch.object(system, "is_trusted_ui_origin", return_value=True),
        patch.object(system.OperationStore, "get", return_value={"capability": "unknown"}),
    ):
        with pytest.raises(ToolError) as unsupported:
            await system.reconcile_operation("op", request, user, AsyncMock())
    assert unsupported.value.code == "reconcile_unavailable"


@pytest.mark.asyncio
async def test_system_operation_success_paths(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path)
    user = _user()
    registry = SimpleNamespace(execute=AsyncMock(return_value={"status": "succeeded"}))
    request = _request(registry=registry)
    with (
        patch.object(system, "get_settings", return_value=settings),
        patch.object(system, "is_trusted_ui_origin", return_value=True),
        patch.object(system.OperationStore, "list_status", return_value=[{"id": "op"}]),
        patch.object(system.OperationStore, "acknowledge_uncertain", return_value=None) as ack,
        patch.object(system.OperationStore, "archive", return_value=None) as archive,
        patch.object(
            system.OperationStore,
            "get",
            return_value={"capability": "gmail_draft_create"},
        ),
    ):
        assert await system.operation_status(user, 25) == [{"id": "op"}]
        await system.acknowledge_operation("op", request, user)
        await system.archive_operation("op", request, user)
        result = await system.reconcile_operation("op", request, user, AsyncMock())
    ack.assert_called_once()
    archive.assert_called_once()
    assert result == {"status": "succeeded"}
    assert registry.execute.await_args.args[0] == "gmail_reconcile_draft"
