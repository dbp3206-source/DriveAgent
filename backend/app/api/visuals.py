"""Private visual library; bytes are served only after an ownership lookup."""

import json

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.api.dependencies import CurrentUser, DbSession
from app.api.documents import invoke
from app.core.config import get_settings
from app.services.visuals import VisualStore
from app.tools.visuals import VisualRender

router = APIRouter(prefix="/api/visuals", tags=["visuals"])


@router.get("")
async def list_visuals(user: CurrentUser):
    rows = VisualStore(get_settings().data_dir).list(user.id)
    return {
        "items": [
            {
                **{key: row[key] for key in ("id", "title", "kind", "created")},
                "spec": json.loads(row["spec"]),
                "png_url": f"/api/visuals/{row['id']}/png",
                "svg_url": f"/api/visuals/{row['id']}/svg",
            }
            for row in rows
        ]
    }


@router.post("")
async def render(payload: VisualRender, request: Request, user: CurrentUser, db: DbSession):
    return await invoke("visual_render", payload, request, user, db)


@router.get("/{visual_id}/{format}")
async def download(visual_id: str, format: str, user: CurrentUser):
    path = VisualStore(get_settings().data_dir).path(user.id, visual_id, format)
    media = "image/svg+xml" if format == "svg" else "image/png"
    return FileResponse(path, media_type=media, filename=f"visual-{visual_id}.{format}")
