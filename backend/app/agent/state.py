"""State của LangGraph. Reducer ``add_messages`` giữ lịch sử qua mỗi node."""

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    user_id: str
    session_id: str
    request_id: str
    plan: list[str]
    tool_rounds: int
    trace: list[dict[str, Any]]
    error: str | None
