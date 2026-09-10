"""Governed skill CRUD and deterministic expansion through the shared Tool Registry."""

import asyncio

from pydantic import BaseModel, ConfigDict, Field

from app.auth.permissions import SKILL_MANAGE
from app.services.skills import SkillSpec, SkillStore
from app.tools.contracts import ToolContext, ToolDefinition


class SkillSave(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skill: SkillSpec
    expected_revision: int | None = Field(default=None, ge=0)


class SkillRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    inputs: dict[str, str] = Field(default_factory=dict)


class SkillList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    include_archived: bool = False


class SkillArchive(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skill_id: str = Field(pattern=r"^[a-f0-9-]{36}$")


class SkillResult(BaseModel):
    data: dict


async def save(payload: SkillSave, context: ToolContext):
    row = await asyncio.to_thread(
        SkillStore(context.settings.data_dir).save,
        context.user.id,
        payload.skill,
        payload.expected_revision,
    )
    return SkillResult(data=row)


async def run(payload: SkillRun, context: ToolContext):
    row = await asyncio.to_thread(
        SkillStore(context.settings.data_dir).run, context.user.id, payload.name, payload.inputs
    )
    return SkillResult(data=row)


async def list_skills(payload: SkillList, context: ToolContext):
    rows = await asyncio.to_thread(
        SkillStore(context.settings.data_dir).list, context.user.id, payload.include_archived
    )
    return SkillResult(data={"items": rows})


async def archive(payload: SkillArchive, context: ToolContext):
    row = await asyncio.to_thread(
        SkillStore(context.settings.data_dir).archive, context.user.id, payload.skill_id
    )
    return SkillResult(data=row)


def skill_tool_definitions() -> list[ToolDefinition]:
    definitions = [
        (
            "skill_save",
            "Tạo hoặc cập nhật một quy trình tái sử dụng theo phiên bản.",
            SkillSave,
            save,
            True,
        ),
        (
            "skill_run",
            "Nạp và điền đầu vào cho một skill; luôn lấy context mới.",
            SkillRun,
            run,
            False,
        ),
        (
            "skill_list",
            "Liệt kê các skill thuộc tài khoản hiện tại.",
            SkillList,
            list_skills,
            False,
        ),
        ("skill_archive", "Cất một skill khỏi danh sách đang dùng.", SkillArchive, archive, True),
    ]
    return [
        ToolDefinition(
            name=name,
            description=description,
            input_model=model,
            output_model=SkillResult,
            handler=handler,
            required_permissions={SKILL_MANAGE},
            max_attempts=1,
            requires_user_action=user_action,
        )
        for name, description, model, handler, user_action in definitions
    ]
