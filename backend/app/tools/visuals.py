"""Audited local visual tools. Rendering never calls a model or external API."""

import asyncio

from pydantic import BaseModel, ConfigDict

from app.auth.permissions import ARTIFACT_WRITE
from app.services.visuals import VisualSpec, VisualStore
from app.tools.contracts import ToolContext, ToolDefinition


class VisualRender(BaseModel):
    model_config = ConfigDict(extra="forbid")
    visual: VisualSpec


class VisualResult(BaseModel):
    data: dict


async def visual_render(payload: VisualRender, context: ToolContext):
    result = await asyncio.to_thread(
        VisualStore(context.settings.data_dir).create, context.user.id, payload.visual
    )
    return VisualResult(
        data={
            **result,
            "png_url": f"/api/visuals/{result['id']}/png",
            "svg_url": f"/api/visuals/{result['id']}/svg",
        }
    )


def visual_tool_definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="visual_render",
            description="Tạo PNG và SVG local từ một VisualSpec có kiểm tra; không gọi model.",
            input_model=VisualRender,
            output_model=VisualResult,
            handler=visual_render,
            required_permissions={ARTIFACT_WRITE},
            max_attempts=1,
            timeout_seconds=20,
            requires_user_action=True,
        )
    ]
