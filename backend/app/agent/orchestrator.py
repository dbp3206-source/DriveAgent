"""Orchestration Harness dùng LangGraph và Gemini.

Graph có planning, ReAct routing, tool execution, checkpoint và recovery. ToolNode không
gọi dịch vụ trực tiếp: mỗi tool wrapper bắt buộc quay về Tool Registry sáu cổng.
"""

import asyncio
import json
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from app.agent.state import AgentState
from app.core.config import Settings
from app.db.models import User
from app.db.session import SessionFactory
from app.tools.contracts import ToolContext
from app.tools.registry import ToolRegistry

SYSTEM_PROMPT = """Bạn là DriveAgent, trợ lý tài liệu Google Drive có kiểm soát.

Quy tắc bắt buộc:
- Trả lời bằng tiếng Việt rõ ràng, súc tích.
- Khi câu hỏi liên quan tệp chưa biết ID, hãy tìm tệp trước rồi mới đọc hoặc tra RAG.
- Chỉ khẳng định nội dung tài liệu khi tool đã trả về bằng chứng.
- Nếu RAG không có ngữ cảnh đủ tốt, nói rõ là chưa tìm thấy thay vì suy đoán.
- Không yêu cầu hoặc ghi nhớ API key, access token, refresh token hay mật khẩu.
- Chỉ dùng tool cần thiết và tôn trọng lỗi quyền.
- Khi có nguồn, dùng ký hiệu [1], [2] trong câu trả lời. Hệ thống sẽ gắn link nguồn.
"""


class AgentPlan(BaseModel):
    steps: list[str] = Field(min_length=1, max_length=5)


class AgentRunResult(BaseModel):
    answer: str
    plan: list[str]
    trace: list[dict[str, Any]]
    citations: list[dict[str, Any]]


class AgentNotConfiguredError(RuntimeError):
    pass


class AgentOrchestrator:
    def __init__(self, settings: Settings, registry: ToolRegistry):
        self.settings = settings
        self.registry = registry
        self._checkpointer_context: AbstractAsyncContextManager | None = None
        self._checkpointer: AsyncSqliteSaver | None = None

    async def initialize(self) -> None:
        checkpoint_path = Path(self.settings.data_dir) / "langgraph_checkpoints.db"
        self._checkpointer_context = AsyncSqliteSaver.from_conn_string(str(checkpoint_path))
        self._checkpointer = await self._checkpointer_context.__aenter__()

    async def close(self) -> None:
        if self._checkpointer_context:
            await self._checkpointer_context.__aexit__(None, None, None)

    async def run(
        self,
        *,
        user: User,
        session_id: str,
        request_id: str,
        user_message: str,
    ) -> AgentRunResult:
        if not self.settings.gemini_is_configured:
            raise AgentNotConfiguredError(
                "Chưa cấu hình GEMINI_API_KEY. Bạn vẫn có thể duyệt Drive và quản lý dữ liệu."
            )
        if not self._checkpointer:
            raise RuntimeError("LangGraph checkpointer chưa được khởi tạo.")

        execution_records: list[dict[str, Any]] = []
        record_lock = asyncio.Lock()
        tools = self._build_tools(user.id, request_id, execution_records, record_lock)
        model = ChatGoogleGenerativeAI(
            model=self.settings.gemini_chat_model,
            google_api_key=self.settings.gemini_api_key,
            temperature=0.1,
            max_retries=1,
        )
        tool_model = model.bind_tools(tools)

        async def planner_node(state: AgentState) -> dict[str, Any]:
            planner = model.with_structured_output(AgentPlan)
            try:
                plan = await planner.ainvoke(
                    [
                        SystemMessage(
                            content=(
                                "Lập kế hoạch 1-5 bước bằng tiếng Việt. Chỉ nêu hành động cần "
                                "làm, không bịa kết quả. Các tool hiện có: "
                                + ", ".join(tool.name for tool in tools)
                            )
                        ),
                        HumanMessage(content=user_message),
                    ]
                )
                steps = plan.steps
            except Exception:
                # Planner lỗi không làm hỏng toàn bộ request; ReAct node vẫn có thể xử lý.
                steps = ["Phân tích yêu cầu", "Dùng tool phù hợp", "Tổng hợp câu trả lời có nguồn"]
            return {
                "plan": steps,
                "trace": [{"stage": "planning", "status": "success", "steps": steps}],
            }

        async def agent_node(state: AgentState) -> dict[str, Any]:
            prompt = [SystemMessage(content=SYSTEM_PROMPT)] + list(state.get("messages", []))
            response = await tool_model.ainvoke(prompt)
            trace = list(state.get("trace", []))
            trace.append(
                {
                    "stage": "model",
                    "status": "tool_call" if response.tool_calls else "success",
                    "tools": [call["name"] for call in response.tool_calls],
                }
            )
            return {
                "messages": [response],
                "trace": trace,
                "tool_rounds": state.get("tool_rounds", 0) + (1 if response.tool_calls else 0),
            }

        def route_after_agent(state: AgentState) -> str:
            last = state["messages"][-1]
            if isinstance(last, AIMessage) and last.tool_calls:
                if state.get("tool_rounds", 0) >= 6:
                    return "limit"
                return "tools"
            return END

        async def limit_node(state: AgentState) -> dict[str, Any]:
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "Mình đã dừng sau 6 vòng tool để tránh vòng lặp. "
                            "Hãy thu hẹp câu hỏi hoặc chọn một tệp cụ thể."
                        )
                    )
                ],
                "error": "tool_round_limit",
            }

        builder = StateGraph(AgentState)
        builder.add_node("planner", planner_node)
        builder.add_node("agent", agent_node)
        builder.add_node("tools", ToolNode(tools, handle_tool_errors=True))
        builder.add_node("limit", limit_node)
        builder.add_edge(START, "planner")
        builder.add_edge("planner", "agent")
        builder.add_conditional_edges(
            "agent", route_after_agent, {"tools": "tools", "limit": "limit", END: END}
        )
        builder.add_edge("tools", "agent")
        builder.add_edge("limit", END)
        graph = builder.compile(checkpointer=self._checkpointer)

        # Checkpointer SQLite đã giữ các message cũ theo thread_id. Chỉ thêm lượt mới;
        # gửi lại toàn bộ lịch sử DB ở mỗi request sẽ làm reducer nhân đôi hội thoại.
        initial_messages = [HumanMessage(content=user_message)]
        final_state = await graph.ainvoke(
            {
                "messages": initial_messages,
                "user_id": user.id,
                "session_id": session_id,
                "request_id": request_id,
                "plan": [],
                "tool_rounds": 0,
                "trace": [],
            },
            config={"configurable": {"thread_id": f"{user.id}:{session_id}"}},
        )
        final_message = final_state["messages"][-1]
        answer = self._message_text(final_message)
        citations = self._collect_citations(final_state["messages"])
        trace = list(final_state.get("trace", [])) + execution_records
        return AgentRunResult(
            answer=answer,
            plan=final_state.get("plan", []),
            trace=trace,
            citations=citations,
        )

    def _build_tools(
        self,
        user_id: str,
        request_id: str,
        records: list[dict[str, Any]],
        lock: asyncio.Lock,
    ) -> list[StructuredTool]:
        tools: list[StructuredTool] = []
        for definition in self.registry.definitions():

            async def invoke_tool(
                _definition=definition, **arguments: Any
            ) -> str:  # default arg binds the current loop item
                async with SessionFactory() as db:
                    user = await db.get(User, user_id)
                    if not user:
                        raise PermissionError("Không tìm thấy người dùng của phiên agent.")
                    started_record = {
                        "stage": "tool",
                        "tool": _definition.name,
                        "status": "running",
                    }
                    async with lock:
                        records.append(started_record)
                    try:
                        result = await self.registry.execute(
                            _definition.name,
                            arguments,
                            ToolContext(
                                request_id=request_id,
                                user=user,
                                db=db,
                                settings=self.settings,
                                source="agent",
                            ),
                        )
                        started_record["status"] = "success"
                        return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
                    except Exception as exc:
                        started_record.update(status="error", error=str(exc)[:500])
                        raise

            tools.append(
                StructuredTool.from_function(
                    coroutine=invoke_tool,
                    name=definition.name,
                    description=definition.description,
                    args_schema=definition.input_model,
                )
            )
        return tools

    @staticmethod
    def _message_text(message: BaseMessage) -> str:
        if isinstance(message.content, str):
            return message.content
        parts: list[str] = []
        for item in message.content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
        return "\n".join(parts)

    @staticmethod
    def _collect_citations(messages: list[BaseMessage]) -> list[dict[str, Any]]:
        seen: set[tuple[str, int]] = set()
        citations: list[dict[str, Any]] = []
        for message in messages:
            if not isinstance(message, ToolMessage) or message.name != "rag_search":
                continue
            try:
                payload = json.loads(str(message.content))
            except json.JSONDecodeError:
                continue
            for citation in payload.get("citations", []):
                key = (citation["file_id"], citation["chunk_index"])
                if key not in seen:
                    citations.append(citation)
                    seen.add(key)
        return citations
