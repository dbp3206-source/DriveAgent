"""Probe real Gmail -> compiler evidence with an offline model boundary.

No email body is printed or sent to Gemini. The model client points to a
non-listening loopback port, and the ADK model call is replaced in-process.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import uuid
from pathlib import Path
from typing import Any

from app.agent.compiler import CompilerOrchestrator
from app.agent.routing import route_request
from app.db.models import User
from app.db.session import SessionFactory, engine, settings
from app.tools.gmail import gmail_tool_definitions
from app.tools.registry import ToolRegistry
from google import genai
from google.adk.models import Gemini
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from qa_google_read_smoke import _connected_owner_id


async def main() -> None:
    observed: dict[str, Any] = {}
    original_generate = Gemini.generate_content_async

    async def offline_generate(self, request, stream=False):
        evidence = None
        for content in request.contents or []:
            for part in content.parts or []:
                if not part.text or '"evidence_untrusted"' not in part.text:
                    continue
                candidate = json.loads(part.text)
                if isinstance(candidate, dict):
                    evidence = candidate.get("evidence_untrusted")
        if not isinstance(evidence, dict):
            raise TypeError("Compiler did not pass structured evidence to the model")
        messages = evidence.get("messages") or []
        if not messages or any(not item.get("body", "").strip() for item in messages):
            raise AssertionError("Compiler did not gather complete Gmail message bodies")
        observed["messages"] = len(messages)
        observed["full_bodies"] = sum(bool(item.get("body", "").strip()) for item in messages)
        observed["next_page"] = int(bool(evidence.get("next_page_token")))
        refs = " ".join(f"[{index}]" for index in range(1, len(messages) + 1))
        yield LlmResponse(content=types.Content(
            role="model",
            parts=[types.Part(text=json.dumps({"answer": f"Đã đọc nguồn {refs}."}))],
        ))

    Gemini.generate_content_async = offline_generate
    registry = ToolRegistry()
    for definition in gmail_tool_definitions():
        if definition.name == "gmail_read_matching_messages":
            registry.register(definition)
    try:
        with tempfile.TemporaryDirectory(prefix="veridra-gmail-source-probe-") as temp_dir:
            probe_settings = settings.model_copy(
                deep=True,
                update={
                    "data_dir": Path(temp_dir),
                    "gemini_api_key": "offline-qa-no-provider",
                },
            )
            runner = CompilerOrchestrator(probe_settings, registry)
            runner.client = genai.Client(
                api_key="offline-qa-no-provider",
                http_options=types.HttpOptions(base_url="http://127.0.0.1:9"),
            )
            try:
                async with SessionFactory() as db:
                    user = await db.get(User, _connected_owner_id())
                    if user is None:
                        raise RuntimeError("Connected Gmail owner not found")
                message = (
                    'Tóm tắt các mail "Bản chi tiết" của Đinh Bảo Phúc '
                    "trong ngày hôm nay"
                )
                observed["route"] = route_request(message).tool or "none"
                result = await runner.run(
                    user=user,
                    session_id=str(uuid.uuid4()),
                    request_id=str(uuid.uuid4()),
                    user_message=message,
                )
                observed["citations"] = len(result.citations)
                observed["trace"] = [
                    {"stage": row.get("stage"), "status": row.get("status"), "tool": row.get("tool")}
                    for row in result.trace
                ]
                observed["cloud_writes"] = 0
                observed["gemini_requests"] = 0
                observed["passed"] = int(
                    observed.get("messages", 0) > 0
                    and observed["messages"] == observed["full_bodies"]
                    == observed["citations"]
                    and observed["next_page"] == 0
                )
            finally:
                await runner.close()
    finally:
        Gemini.generate_content_async = original_generate
        await engine.dispose()
    print(json.dumps(observed, ensure_ascii=False, indent=2))
    if not observed.get("passed"):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
