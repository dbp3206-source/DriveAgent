from pathlib import Path

import pytest
from pydantic import ValidationError

from app.services.visuals import VisualSpec, VisualStore
from app.tools.contracts import ToolError


def visual_spec():
    return VisualSpec(
        type="flowchart",
        title="RAG flow",
        subtitle="Từ câu hỏi đến câu trả lời",
        sections=[
            {"title": "Tìm", "body": "Lấy đoạn liên quan"},
            {"title": "Trả lời", "body": "Dùng bằng chứng"},
        ],
        connections=[{"source": 0, "target": 1}],
    )


def test_visual_renderer_creates_private_png_and_svg(tmp_path: Path):
    store = VisualStore(tmp_path)
    result = store.create("alice", visual_spec())
    png = store.path("alice", result["id"], "png")
    svg = store.path("alice", result["id"], "svg")
    assert png.read_bytes().startswith(b"\x89PNG")
    assert "RAG flow" in svg.read_text(encoding="utf-8")
    assert store.list("alice")[0]["id"] == result["id"]
    with pytest.raises(ToolError):
        store.path("bob", result["id"], "png")


def test_visual_rejects_invalid_connections():
    data = visual_spec().model_dump()
    data["connections"] = [{"source": 0, "target": 7}]
    with pytest.raises(ValidationError):
        VisualSpec.model_validate(data)
