"""Quota-first ADK: deterministic gather, one structured generation, no tool loop.

Canonical Message rows supply bounded history across framework switches. Retrieved
documents remain data; this compiler has no side-effect tools and cannot execute them.
"""

import asyncio
import json
from typing import Any

from google import genai
from google.adk.agents import LlmAgent
from google.adk.agents.run_config import RunConfig
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from langchain_core.messages import ToolMessage
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select

from app.agent.creation import CREATION_INSTRUCTION, CreationAnswer, WireAnswer
from app.agent.evidence import source_references
from app.agent.orchestrator import (
    SYSTEM_PROMPT,
    AgentNotConfiguredError,
    AgentOrchestrator,
    AgentRunResult,
)
from app.agent.routing import route_request
from app.core.config import Settings
from app.db.models import Message, User
from app.db.session import SessionFactory
from app.services.quota import QuotaGuard, conservative_tokens
from app.tools.contracts import ToolContext, ToolError
from app.tools.registry import ToolRegistry


class CompiledAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=40000)


class CompilerOrchestrator:
    def __init__(self, settings: Settings, registry: ToolRegistry):
        self.settings, self.registry = settings, registry
        self.quota = QuotaGuard(settings.data_dir / "quota.db")
        self.client: genai.Client | None = None

    async def initialize(self):
        if self.settings.gemini_is_configured:
            self.client = genai.Client(
                api_key=self.settings.gemini_api_key,
                vertexai=False,
                http_options=types.HttpOptions(
                    base_url="https://generativelanguage.googleapis.com",
                    timeout=60000,
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )

    async def close(self):
        if self.client:
            await self.client.aio.aclose()
            self.client.close()

    async def run(self, *, user: User, session_id: str, request_id: str, user_message: str):
        route = route_request(user_message)
        trace: list[dict[str, Any]] = []
        evidence: list[ToolMessage] = []
        context_data: Any = None
        async with SessionFactory() as db:
            user = await db.get(User, user.id)
            if not user or not user.is_active:
                raise ToolError("Phiên không còn hợp lệ.", code="authentication_required")
            if route.tool:
                result = await self.registry.execute(
                    route.tool,
                    route.arguments or {},
                    ToolContext(
                        request_id=request_id,
                        user=user,
                        db=db,
                        settings=self.settings,
                        source="compiler_gather",
                    ),
                )
                context_data = result.model_dump(mode="json")
                evidence.append(
                    ToolMessage(
                        content=json.dumps(context_data), name=route.tool, tool_call_id=request_id
                    )
                )
                trace.append({"stage": "tool", "tool": route.tool, "status": "success"})
                if route.read_match:
                    local = route.tool == "local_source_search"
                    matches = (
                        context_data.get("data", {}).get("sources", [])
                        if local
                        else context_data.get("files", [])
                    )
                    # Drive full-text search may also return documents mentioning
                    # this filename. Prefer a unique exact name before asking.
                    query = (route.arguments or {}).get("query", "").strip().casefold()
                    exact = [item for item in matches if item.get("name", "").casefold() == query]
                    if exact:
                        matches = exact
                    if len(matches) != 1:
                        return AgentRunResult(
                            answer=(
                                "Không tìm thấy đúng một tệp. "
                                "Hãy chọn tệp cụ thể trong khu vực tài liệu rồi thử lại."
                            ),
                            plan=[],
                            trace=trace,
                            citations=[],
                        )
                    name = "local_source_read" if local else "drive_read_file"
                    args = (
                        {"source_id": matches[0]["id"]}
                        if local
                        else {"file_id": matches[0]["id"], "max_characters": 20000}
                    )
                    read = await self.registry.execute(
                        name,
                        args,
                        ToolContext(
                            request_id=request_id,
                            user=user,
                            db=db,
                            settings=self.settings,
                            source="compiler_gather",
                        ),
                    )
                    context_data = read.model_dump(mode="json")
                    evidence.append(
                        ToolMessage(
                            content=json.dumps(context_data),
                            name=name,
                            tool_call_id=request_id + "-read",
                        )
                    )
                    trace.append({"stage": "tool", "tool": name, "status": "success"})
            history = list(
                await db.scalars(
                    select(Message)
                    .where(Message.user_id == user.id, Message.session_id == session_id)
                    .order_by(Message.created_at.desc())
                    .limit(8)
                )
            )
        citations = AgentOrchestrator._collect_citations(evidence)
        if route.direct:
            answer = self._direct_answer(context_data)
            return AgentRunResult(answer=answer, plan=[], trace=trace, citations=citations)
        if not self.client:
            raise AgentNotConfiguredError("Chưa cấu hình Gemini; thao tác trực tiếp vẫn dùng được.")
        if self.settings.gemini_chat_model not in {"gemini-3.8-flash", "gemini-3.5-flash-lite"}:
            raise ToolError("Model không nằm trong danh sách đã duyệt.", code="model_not_allowed")
        # Canonical history survives both ADK and LangGraph. No framework checkpoint replay.
        history_data = [{"role": row.role, "text": row.content[:4000]} for row in reversed(history)]
        if history_data and history_data[-1] == {"role": "user", "text": user_message[:4000]}:
            history_data.pop()
        prompt = json.dumps(
            {
                "current_user_request": user_message,
                "history_untrusted": history_data,
                "evidence_untrusted": context_data,
                "source_references": source_references(citations),
                "artifact_contract": CreationAnswer.model_json_schema(),
            },
            ensure_ascii=False,
        )
        instruction = (
            SYSTEM_PROMPT
            + CREATION_INSTRUCTION
            + (
                "\nBạn đang tổng hợp đúng một lượt, không có tool để tự thực thi. "
                "Không tuyên bố đã tạo/sửa/gửi/chạy sản phẩm nếu evidence không xác nhận. "
                "Chỉ dùng số reference trong source_references, "
                "không dùng chunk_index làm số nguồn. "
                "Nếu thiếu tài liệu/ID, hỏi ngắn để làm rõ, không bịa nội dung tài liệu. "
                "Định dạng truyền: mỗi proposal có kind và spec_json. spec_json là chuỗi JSON "
                "của đúng spec theo kind trong artifact_contract, không bọc thêm kind hay "
                "tên capability bên trong. Kiểm tra dữ liệu trước khi trả."
            )
        )
        await asyncio.to_thread(
            self.quota.reserve,
            "flash",
            conservative_tokens(
                prompt + instruction + json.dumps(WireAnswer.provider_schema()), 8192
            ),
        )
        sessions = InMemorySessionService()
        await sessions.create_session(
            app_name="drive_compiler", user_id=user.id, session_id=request_id
        )
        agent = LlmAgent(
            name="drive_compiler",
            model=Gemini(model=self.settings.gemini_chat_model, client=self.client),
            instruction=instruction,
            tools=[],
            include_contents="none",
            generate_content_config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=8192,
                # ADK output_schema targets the legacy responseSchema dialect.
                # Pydantic extra='forbid' needs JSON Schema's additionalProperties.
                response_mime_type="application/json",
                response_json_schema=WireAnswer.provider_schema(),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        runner = Runner(agent=agent, app_name="drive_compiler", session_service=sessions)
        answer = None
        proposals = []
        async with asyncio.timeout(90):
            async for event in runner.run_async(
                user_id=user.id,
                session_id=request_id,
                new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
                run_config=RunConfig(max_llm_calls=1),
            ):
                if event.usage_metadata:
                    trace.append(
                        {
                            "stage": "usage",
                            "status": "success",
                            **event.usage_metadata.model_dump(exclude_none=True),
                        }
                    )
                if event.is_final_response() and event.content:
                    raw = "".join(
                        p.text for p in event.content.parts or [] if p.text and not p.thought
                    )
                    try:
                        compiled = WireAnswer.model_validate_json(raw).validate_artifacts()
                        answer = compiled.answer
                        proposals = [item.model_dump(mode="json") for item in compiled.proposals]
                    except (ValidationError, ValueError):
                        # Do not leak generated content or spend a second call repairing it.
                        raise ToolError(
                            "Model trả về dữ liệu không đúng định dạng; "
                            "chưa thực thi thay đổi nào.",
                            code="invalid_spec",
                        ) from None
        if not answer:
            raise ToolError(
                "Model không trả về spec hợp lệ; chưa thực thi thay đổi nào.", code="invalid_spec"
            )
        trace.append(
            {
                "stage": "model",
                "status": "success",
                "model": self.settings.gemini_chat_model,
                "model_call_count": 1,
                "note": "Một lượt ADK; không fallback, không vòng lặp tool.",
            }
        )
        return AgentRunResult(
            answer=answer, plan=[], trace=trace, citations=citations, proposals=proposals
        )

    @staticmethod
    def _direct_answer(data: dict) -> str:
        if "result" in data:
            return str(data["result"])
        if "kind" in data and "content" in data:
            return "Đã lưu vào bộ nhớ: " + str(data["content"])
        if "files" in data:
            items = data["files"]
            if not items:
                return "Không tìm thấy tệp phù hợp."
            lines = [f"- {item['name']} — ID: `{item['id']}`" for item in items]
            if data.get("next_page_token"):
                lines.append("\nCòn kết quả; mở Google Drive để xem trang tiếp theo.")
            return "Các tệp tìm được:\n\n" + "\n".join(lines)
        return str(data.get("text", "Không có nội dung để hiển thị."))
