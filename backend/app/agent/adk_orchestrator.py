"""ADK adapter: session riêng, tool luôn đi qua registry, rollback không xóa lịch sử.

Database ADK tách khỏi checkpoint LangGraph. API vẫn lưu Message độc lập để
người dùng đọc hội thoại cũ. Không diễn giải checkpoint của framework khác.
"""

import asyncio
import json
import re
import time
from collections.abc import AsyncGenerator
from typing import Any
from weakref import WeakValueDictionary

from google import genai
from google.adk.agents import LlmAgent
from google.adk.agents.run_config import RunConfig
from google.adk.models import Gemini
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.adk.tools.base_tool import BaseTool
from google.genai import errors, types
from langchain_core.messages import ToolMessage
from pydantic import Field

from app.agent.compiler import CompilerOrchestrator
from app.agent.evidence import source_references
from app.agent.orchestrator import (
    SYSTEM_PROMPT,
    AgentNotConfiguredError,
    AgentOrchestrator,
    AgentRunResult,
)
from app.auth.permissions import permissions_for_role
from app.core.config import Settings
from app.core.security import redact
from app.db.models import User
from app.db.session import SessionFactory
from app.tools.contracts import ToolContext, ToolDefinition, ToolError
from app.tools.registry import ToolRegistry


class RecoverableGemini(Gemini):
    fallback_model: str
    records: list[dict[str, Any]] = Field(default_factory=list, exclude=True)

    async def generate_content_async(
        self,
        llm_request: LlmRequest,
        stream: bool = False,
    ) -> AsyncGenerator[LlmResponse, None]:
        # Không cắt giữa function-call/response. Hết ngân sách thì yêu cầu phiên mới.
        if len(llm_request.model_dump_json()) > 160_000:
            raise ToolError(
                "Ngữ cảnh quá dài. Hãy mở cuộc trò chuyện mới và chọn ít tài liệu hơn.",
                code="context_budget",
            )
        started = time.monotonic()
        emitted = False
        try:
            async for response in super().generate_content_async(llm_request, stream=False):
                emitted = True
                yield response
            self.records.append(
                {
                    "stage": "model",
                    "status": "success",
                    "model": self.model,
                    "latency_ms": round((time.monotonic() - started) * 1000),
                }
            )
        except errors.APIError as exc:
            # Chỉ thử model dự phòng trước khi có output; không replay toàn bộ run/tool.
            if emitted or exc.code not in {404, 429, 500, 502, 503, 504}:
                raise
            self.records.append(
                {
                    "stage": "model",
                    "status": "fallback",
                    "model": self.fallback_model,
                    "provider_code": exc.code,
                }
            )
            # tools_dict chứa client/lock không thể deepcopy; chỉ đổi trường model.
            request = llm_request.model_copy()
            request.model = self.fallback_model
            fallback = Gemini(model=self.fallback_model, client=self.client)
            async for response in fallback.generate_content_async(request, stream=False):
                yield response


class GovernedAdkTool(BaseTool):
    def __init__(
        self,
        definition: ToolDefinition,
        registry: ToolRegistry,
        settings: Settings,
        user_id: str,
        request_id: str,
        records: list,
        evidence: list,
        semaphore: asyncio.Semaphore,
        signatures: set[str],
    ):
        super().__init__(name=definition.name, description=definition.description)
        self.definition, self.registry, self.settings = definition, registry, settings
        self.user_id, self.request_id = user_id, request_id
        self.records, self.evidence = records, evidence
        self.semaphore, self.signatures = semaphore, signatures

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters_json_schema=self.definition.input_model.model_json_schema(),
        )

    async def run_async(self, *, args: dict[str, Any], tool_context: Any) -> dict[str, Any]:
        signature = self.name + json.dumps(args, sort_keys=True, ensure_ascii=False)
        async with self.semaphore:
            if signature in self.signatures or len(self.signatures) >= 12:
                return {"error": "Tool đã gọi hoặc hết ngân sách; tổng hợp bằng chứng hiện có."}
            self.signatures.add(signature)
            started = time.monotonic()
            async with SessionFactory() as db:
                # Actor lấy từ server, tuyệt đối không lấy user_id do model cung cấp.
                user = await db.get(User, self.user_id)
                if not user or not user.is_active:
                    return {"error": "Người dùng không còn quyền truy cập."}
                record = {"stage": "tool", "tool": self.name, "status": "running"}
                self.records.append(record)
                try:
                    result = await self.registry.execute(
                        self.name,
                        args,
                        ToolContext(
                            request_id=self.request_id,
                            user=user,
                            db=db,
                            settings=self.settings,
                            source="adk",
                        ),
                    )
                    payload = result.model_dump(mode="json")
                    self.evidence.append(
                        ToolMessage(
                            content=json.dumps(payload), name=self.name, tool_call_id=signature
                        )
                    )
                    record["status"] = "success"
                    # Number the actual deduplicated evidence, not raw chunk positions.
                    # This synchronous block shares the same ordering as the final UI list.
                    payload["source_references"] = source_references(
                        AgentOrchestrator._collect_citations(self.evidence)
                    )
                    return payload
                except Exception as exc:
                    record.update(status="error", error=redact(str(exc))[:500])
                    return {"error": record["error"], "code": getattr(exc, "code", "tool_error")}
                finally:
                    record["latency_ms"] = round((time.monotonic() - started) * 1000)


class AdkOrchestrator:
    def __init__(self, settings: Settings, registry: ToolRegistry):
        self.settings, self.registry = settings, registry
        self.sessions: DatabaseSessionService | None = None
        self.client: genai.Client | None = None
        self.locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()
        self.compiler = CompilerOrchestrator(settings, registry)

    async def initialize(self) -> None:
        path = (self.settings.data_dir / "adk_sessions.db").resolve().as_posix()
        self.sessions = DatabaseSessionService(db_url=f"sqlite+aiosqlite:///{path}")
        if self.settings.gemini_is_configured:
            self.client = genai.Client(
                api_key=self.settings.gemini_api_key, http_options=types.HttpOptions(timeout=60_000)
            )
        await self.compiler.initialize()

    async def close(self) -> None:
        if self.sessions:
            await self.sessions.close()
        if self.client:
            await self.client.aio.aclose()
            self.client.close()
        await self.compiler.close()

    async def run(
        self,
        *,
        user: User,
        session_id: str,
        request_id: str,
        user_message: str,
        model_name: str | None = None,
    ) -> AgentRunResult:
        # Creation uses one structured compiler call so the UI receives inert,
        # typed proposals. The ADK tool loop remains the default for open-ended work.
        if re.search(
            r"\b(?:tạo|soạn|làm|sửa|chỉnh sửa|create|edit)\b.*\b(?:google\s*)?"
            r"(?:docs?|sheets?|slides?|presentation|visual|infographic|biểu đồ)\b",
            user_message,
            re.I,
        ):
            return await self.compiler.run(
                user=user,
                session_id=session_id,
                request_id=request_id,
                user_message=user_message,
            )
        if not self.client or not self.sessions:
            raise AgentNotConfiguredError("Chưa cấu hình Gemini cho ADK.")
        key = f"{user.id}:{session_id}"
        lock = self.locks.setdefault(key, asyncio.Lock())
        async with lock, asyncio.timeout(180):
            records: list[dict[str, Any]] = []
            evidence: list[ToolMessage] = []
            semaphore, signatures = asyncio.Semaphore(2), set()
            allowed = permissions_for_role(user.role)
            tools = [
                GovernedAdkTool(
                    d,
                    self.registry,
                    self.settings,
                    user.id,
                    request_id,
                    records,
                    evidence,
                    semaphore,
                    signatures,
                )
                for d in self.registry.definitions()
                if d.required_permissions <= allowed and not d.requires_user_action
            ]
            model = RecoverableGemini(
                model=model_name or self.settings.gemini_chat_model,
                fallback_model=self.settings.gemini_fallback_model,
                client=self.client,
                records=records,
            )
            model.records = records  # Pydantic sao chép list khi validate; giữ cùng trace run.
            agent = self._build_agent_tree(model, tools, records)
            existing = await self.sessions.get_session(
                app_name="drive_agent", user_id=user.id, session_id=session_id
            )
            if existing is None:
                await self.sessions.create_session(
                    app_name="drive_agent", user_id=user.id, session_id=session_id
                )
                records.append(
                    {
                        "stage": "context",
                        "status": "success",
                        "note": "Phiên ADK mới; lịch sử LangGraph vẫn đọc được trong UI.",
                    }
                )
            runner = Runner(agent=agent, app_name="drive_agent", session_service=self.sessions)
            answer = ""
            active_agent = ""
            async for event in runner.run_async(
                user_id=user.id,
                session_id=session_id,
                new_message=types.Content(role="user", parts=[types.Part(text=user_message)]),
                run_config=RunConfig(max_llm_calls=8),
            ):
                if event.author and event.author != active_agent:
                    records.append(
                        {
                            "stage": "agent_handoff",
                            "status": "success",
                            "from": active_agent or "user",
                            "to": event.author,
                        }
                    )
                    active_agent = event.author
                if event.usage_metadata:
                    records.append(
                        {
                            "stage": "usage",
                            "status": "success",
                            **event.usage_metadata.model_dump(exclude_none=True),
                        }
                    )
                if event.is_final_response() and event.content:
                    answer = "".join(
                        p.text for p in event.content.parts or [] if p.text and not p.thought
                    )
            if not answer:
                raise ToolError(
                    "Model chưa tạo được câu trả lời. Hãy thử yêu cầu cụ thể hơn.",
                    code="empty_response",
                )
            return AgentRunResult(
                answer=answer,
                plan=[],
                trace=records,
                citations=AgentOrchestrator._collect_citations(evidence),
            )

    @staticmethod
    def _build_agent_tree(
        model: RecoverableGemini,
        tools: list[GovernedAdkTool],
        records: list[dict[str, Any]],
    ) -> LlmAgent:
        """Create a real ADK coordinator with bounded, role-specific sub-agents.

        Tool policy still lives in ``ToolRegistry``. Roles only reduce the tool set
        exposed to each model turn; they never create a second authorization path.
        """

        common = (
            SYSTEM_PROMPT
            + "\nChỉ dùng số reference trong source_references do server cấp cho [n]. "
            "chunk_index là vị trí đoạn trong tài liệu, KHÔNG phải số trích dẫn. "
            "Không tự tạo số nguồn. Không có nguồn phù hợp thì nói rõ."
        )
        config = types.GenerateContentConfig(temperature=0.2, max_output_tokens=8192)

        def select(*prefixes: str, names: set[str] | None = None) -> list[GovernedAdkTool]:
            exact = names or set()
            return [
                tool
                for tool in tools
                if tool.name in exact or any(tool.name.startswith(prefix) for prefix in prefixes)
            ]

        specialists = [
            LlmAgent(
                name="research_agent",
                description=(
                    "Tìm, đọc và kiểm chứng thông tin trong Google Drive, nguồn local và RAG."
                ),
                model=model,
                instruction=common
                + (
                    "\nBạn là Research Agent. Thu thập đủ bằng chứng, ưu tiên nguồn đã "
                    "chọn và trả lời có citation."
                ),
                tools=select("drive_", "rag_", "local_source_"),
                generate_content_config=config,
            ),
            LlmAgent(
                name="communication_agent",
                description="Đọc Gmail và chuẩn bị nội dung giao tiếp; không tự gửi email.",
                model=model,
                instruction=common
                + (
                    "\nBạn là Communication Agent. Chỉ đọc email cần thiết; mọi thao tác "
                    "gửi phải để người dùng duyệt ở UI."
                ),
                tools=select("gmail_"),
                generate_content_config=config,
            ),
            LlmAgent(
                name="study_agent",
                description=(
                    "Giải thích, tính toán, dùng bộ nhớ và chuẩn bị nội dung học tập "
                    "hoặc công việc."
                ),
                model=model,
                instruction=common
                + (
                    "\nBạn là Study Agent. Giải thích cho người không chuyên, tính chính "
                    "xác và dùng memory có chọn lọc."
                ),
                tools=select("memory_", "artifact_", names={"calculate"}),
                generate_content_config=config,
            ),
            LlmAgent(
                name="workspace_agent",
                description="Chuẩn bị bản xem trước Google Docs hoặc Sheets để người dùng duyệt.",
                model=model,
                instruction=common
                + (
                    "\nBạn là Workspace Agent. Chỉ chuẩn bị bản xem trước; không nói đã "
                    "tạo file trước khi UI xác minh thành công."
                ),
                tools=select("docs_", "sheets_", "slides_", "visual_", "skill_"),
                generate_content_config=config,
            ),
        ]
        records.append(
            {
                "stage": "multi_agent",
                "status": "ready",
                "coordinator": "drive_coordinator",
                "agents": [agent.name for agent in specialists],
            }
        )
        return LlmAgent(
            name="drive_coordinator",
            description="Điều phối yêu cầu giữa các chuyên gia DriveAgent.",
            model=model,
            instruction=(
                common + "\nBạn là điều phối viên. Trả lời trực tiếp nếu không cần dữ liệu riêng. "
                "Nếu cần tool, chuyển đúng một lần cho agent phù hợp: research_agent cho "
                "Drive/RAG/local, communication_agent cho Gmail, study_agent cho memory/tính toán, "
                "workspace_agent cho Docs/Sheets/Slides/visual/skill. Không chuyển vòng quanh."
            ),
            sub_agents=specialists,
            generate_content_config=config,
        )
