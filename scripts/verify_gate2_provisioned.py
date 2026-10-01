
"""Read back app-created Gate 2 sources through the product's Drive tool."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.agent.orchestrator import _pdf_page_citations
from app.core.config import Settings
from app.db.models import User, UserRole
from app.db.session import SessionFactory
from app.tools.contracts import ToolContext
from app.tools.drive import ReadDriveFileInput, read_drive_file

from scripts.provision_gate2_sources import RECEIPT


async def verify() -> dict[str, object]:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "backend/evals/golden_gate2.json").read_text(encoding="utf-8"))
    if receipt["manifest_version"] != manifest["version"]:
        raise ValueError("Provisioned sources belong to another manifest version")
    sources = {item["name"]: item for item in receipt["sources"]}
    if set(sources) != {"Evaluation-Harness.pdf", "budget.xlsx"}:
        raise ValueError("Incomplete provision receipt")
    async with SessionFactory() as db:
        users = list((await db.scalars(select(User).where(User.is_active.is_(True)))).all())
        admins = [
            user for user in users
            if user.role == UserRole.SUPER_ADMIN.value and user.encrypted_google_credentials
        ]
        if len(admins) != 1:
            raise ValueError("Exactly one connected admin is required for QA readback")
        context = ToolContext(
            request_id="gate2-source-readback", user=admins[0], db=db,
            settings=Settings(), source="qa",
        )
        checked: dict[str, object] = {}
        for name, item in sources.items():
            content = await read_drive_file(
                ReadDriveFileInput(file_id=item["file_id"], max_characters=500_000), context
            )
            if content.file.name != name or content.truncated or not content.text.strip():
                raise ValueError(f"Product Drive readback incomplete for {name}")
            if name.endswith(".pdf"):
                expectations = [
                    binding
                    for case in manifest["cases"] if case["category"] == "pdf"
                    for binding in case["answer_key"]["claim_source_bindings"]
                ]
                anchors = {binding["evidence_fact"] for binding in expectations}
                pages = _pdf_page_citations({
                    "file": {"id": item["file_id"], "name": name},
                    "text": content.text,
                })
                missing = [
                    binding for binding in expectations
                    if not any(
                        citation["page_number"] == binding["page_number"]
                        and binding["evidence_fact"].casefold()
                        in citation["snippet"].casefold()
                        for citation in pages
                    )
                ]
                checked[name] = {
                    "characters": len(content.text), "anchors": len(anchors),
                    "missing_anchor_count": len(missing),
                }
                if missing:
                    raise ValueError(
                        f"Product PDF citations missed source pages for {len(missing)} anchors"
                    )
            else:
                required = ("Cột 1", "Cột 14", "| 1 | 2 | 3 |", "| 12 | 13 | 14 |")
                missing = [value for value in required if value not in content.text]
                checked[name] = {"characters": len(content.text), "missing_cells": missing}
                if missing:
                    raise ValueError("Product Sheet extraction missed QA cells")
        return {"status": "passed", "manifest_version": manifest["version"], "readback": checked}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(verify()), ensure_ascii=False))
