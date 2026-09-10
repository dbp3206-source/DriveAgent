"""Small, deterministic visual renderer: one spec becomes private SVG and PNG files."""

from __future__ import annotations

import html
import sqlite3
from pathlib import Path
from typing import Literal
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.tools.contracts import ToolError


class VisualSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=100)
    body: str = Field(default="", max_length=360)
    value: str | None = Field(default=None, max_length=40)


class VisualConnection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: int = Field(ge=0, le=11)
    target: int = Field(ge=0, le=11)
    label: str = Field(default="", max_length=60)


class VisualSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal[
        "infographic", "architecture", "flowchart", "timeline", "comparison", "chart", "card"
    ]
    title: str = Field(min_length=1, max_length=120)
    subtitle: str = Field(default="", max_length=240)
    sections: list[VisualSection] = Field(min_length=1, max_length=12)
    connections: list[VisualConnection] = Field(default_factory=list, max_length=24)
    accent: str = Field(default="#4f6df5", pattern=r"^#[0-9A-Fa-f]{6}$")

    @model_validator(mode="after")
    def valid_connections(self):
        if any(max(edge.source, edge.target) >= len(self.sections) for edge in self.connections):
            raise ValueError("Connection references a missing section")
        return self


class VisualStore:
    """Filesystem artifacts plus a tiny ownership ledger; no public static directory."""

    def __init__(self, data_dir: Path):
        self.root = data_dir / "visuals"
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = data_dir / "visuals.db"
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS visuals (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL,
                kind TEXT NOT NULL, spec TEXT NOT NULL, created REAL NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS ix_visual_user ON visuals(user_id, created)")

    def connect(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def create(self, user_id: str, spec: VisualSpec) -> dict:
        visual_id = str(uuid4())
        folder = self.root / user_id
        folder.mkdir(parents=True, exist_ok=True)
        svg = render_svg(spec)
        (folder / f"{visual_id}.svg").write_text(svg, encoding="utf-8")
        render_png(spec, folder / f"{visual_id}.png")
        import time

        with self.connect() as db:
            db.execute(
                "INSERT INTO visuals VALUES (?,?,?,?,?,?)",
                (visual_id, user_id, spec.title, spec.type, spec.model_dump_json(), time.time()),
            )
        return {"id": visual_id, "title": spec.title, "kind": spec.type, "verified": True}

    def list(self, user_id: str) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT id,title,kind,spec,created FROM visuals "
                "WHERE user_id=? ORDER BY created DESC",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, user_id: str, visual_id: str) -> dict:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM visuals WHERE id=? AND user_id=?", (visual_id, user_id)
            ).fetchone()
        if row is None:
            raise ToolError("Không tìm thấy visual.", code="visual_not_found")
        return dict(row)

    def path(self, user_id: str, visual_id: str, format: str) -> Path:
        self.get(user_id, visual_id)
        if format not in {"png", "svg"}:
            raise ToolError("Định dạng visual không hợp lệ.", code="invalid_format")
        path = self.root / user_id / f"{visual_id}.{format}"
        if not path.is_file():
            raise ToolError("Tệp visual không còn tồn tại.", code="visual_file_missing")
        return path


def _layout(spec: VisualSpec) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    width = 1200
    columns = (
        2 if spec.type in {"architecture", "comparison", "chart"} and len(spec.sections) > 2 else 1
    )
    rows = (len(spec.sections) + columns - 1) // columns
    box_w = 500 if columns == 2 else 1020
    box_h = 150
    height = 250 + rows * (box_h + 34) + 80
    boxes = []
    for i in range(len(spec.sections)):
        row, col = divmod(i, columns)
        x = 70 + col * 560
        y = 210 + row * (box_h + 34)
        boxes.append((x, y, box_w, box_h))
    return width, height, boxes


def render_svg(spec: VisualSpec) -> str:
    width, height, boxes = _layout(spec)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f6f4ef"/>',
        f'<rect x="70" y="54" width="84" height="8" rx="4" fill="{spec.accent}"/>',
        '<text x="70" y="112" font-family="Arial,sans-serif" font-size="42" '
        f'font-weight="700" fill="#15171c">{html.escape(spec.title)}</text>',
        '<text x="70" y="151" font-family="Arial,sans-serif" font-size="19" '
        f'fill="#60646c">{html.escape(spec.subtitle)}</text>',
    ]
    for edge in spec.connections:
        sx, sy, sw, sh = boxes[edge.source]
        tx, ty, tw, th = boxes[edge.target]
        parts.append(
            f'<path d="M {sx + sw / 2} {sy + sh} L {tx + tw / 2} {ty}" '
            'stroke="#9198a4" stroke-width="3" fill="none"/>'
        )
    for i, (section, (x, y, w, h)) in enumerate(zip(spec.sections, boxes, strict=True)):
        parts.extend(
            [
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="24" '
                'fill="#ffffff" stroke="#d9d7d0"/>',
                f'<circle cx="{x + 38}" cy="{y + 40}" r="19" fill="{spec.accent}"/>',
                f'<text x="{x + 38}" y="{y + 47}" text-anchor="middle" '
                'font-family="Arial,sans-serif" font-size="17" font-weight="700" '
                f'fill="#fff">{i + 1}</text>',
                f'<text x="{x + 72}" y="{y + 47}" font-family="Arial,sans-serif" '
                'font-size="24" font-weight="700" fill="#202229">'
                f"{html.escape(section.title)}</text>",
            ]
        )
        if section.value:
            parts.append(
                f'<text x="{x + w - 28}" y="{y + 47}" text-anchor="end" '
                'font-family="Arial,sans-serif" font-size="24" font-weight="700" '
                f'fill="{spec.accent}">{html.escape(section.value)}</text>'
            )
        for line_no, line in enumerate(_wrap(section.body, 66 if w > 700 else 30)[:3]):
            parts.append(
                f'<text x="{x + 38}" y="{y + 87 + line_no * 24}" '
                'font-family="Arial,sans-serif" font-size="17" fill="#5b606b">'
                f"{html.escape(line)}</text>"
            )
    parts.append("</svg>")
    return "".join(parts)


def _wrap(text: str, width: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def render_png(spec: VisualSpec, path: Path) -> None:
    width, height, boxes = _layout(spec)
    image = Image.new("RGB", (width, height), "#f6f4ef")
    draw = ImageDraw.Draw(image)
    regular = ImageFont.load_default(size=20)
    small = ImageFont.load_default(size=16)
    title_font = ImageFont.load_default(size=42)
    draw.rounded_rectangle((70, 54, 154, 62), radius=4, fill=spec.accent)
    draw.text((70, 78), spec.title, fill="#15171c", font=title_font)
    draw.text((70, 145), spec.subtitle, fill="#60646c", font=small)
    for i, (section, (x, y, w, h)) in enumerate(zip(spec.sections, boxes, strict=True)):
        draw.rounded_rectangle(
            (x, y, x + w, y + h), radius=24, fill="white", outline="#d9d7d0", width=2
        )
        draw.ellipse((x + 19, y + 21, x + 57, y + 59), fill=spec.accent)
        draw.text((x + 31, y + 28), str(i + 1), fill="white", font=small)
        draw.text((x + 72, y + 24), section.title, fill="#202229", font=regular)
        for line_no, line in enumerate(_wrap(section.body, 66 if w > 700 else 30)[:3]):
            draw.text((x + 38, y + 77 + line_no * 23), line, fill="#5b606b", font=small)
    image.save(path, "PNG", optimize=True)
