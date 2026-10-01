"""Governed customer/partner research workflow required by the ProtonX brief."""

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import get_settings
from app.tools.contracts import ToolContext, ToolError
from app.tools.web_research import WebSource

router = APIRouter(prefix="/api/briefings", tags=["briefings"])


class CustomerBriefingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gmail_thread_id: str = Field(min_length=3, max_length=100)
    company_name: str = Field(min_length=2, max_length=240)
    company_domain: str | None = Field(default=None, max_length=253)
    calendar_query: str | None = Field(default=None, max_length=240)
    research_question: str = Field(
        default="Tổng quan công ty, ngành, sản phẩm và tin tức 30 ngày gần đây",
        max_length=800,
    )


class CustomerBriefingResponse(BaseModel):
    report_markdown: str
    source_count: int
    email_message_count: int
    meeting_count: int
    ready_for_human_approval: bool
    next_action: str
    web_research_degraded: bool = False
    warnings: list[str] = Field(default_factory=list)


@router.post("/customer", response_model=CustomerBriefingResponse)
async def prepare_customer_briefing(
    payload: CustomerBriefingRequest,
    request: Request,
    user: CurrentUser,
    db: DbSession,
) -> CustomerBriefingResponse:
    """Read, research and draft; never forward, save or write to Google."""

    settings = get_settings()
    context = ToolContext(
        request_id=request.state.request_id,
        user=user,
        db=db,
        settings=settings,
        source="api",
    )
    registry = request.app.state.registry
    email = await registry.execute(
        "gmail_read_thread", {"thread_id": payload.gmail_thread_id}, context
    )
    company = await registry.execute(
        "company_search", {"query": payload.company_domain or payload.company_name}, context
    )
    web_research_degraded = False
    warnings: list[str] = []
    try:
        web = await registry.execute(
            "web_research",
            {
                "company_name": payload.company_name,
                "domain": payload.company_domain,
                "question": payload.research_question,
                "max_sources": settings.web_research_max_sources,
            },
            context,
        )
        web_summary = web.summary
        sources = list(web.sources)
    except ToolError as exc:
        if exc.code not in {
            "web_research_quota_exhausted",
            "web_research_provider_error",
            "web_research_unavailable",
        }:
            raise
        web_research_degraded = True
        warnings.append(
            "Web research tạm thời không khả dụng; báo cáo vẫn dùng email, "
            "hồ sơ nội bộ và Calendar. Không suy diễn dữ kiện web còn thiếu."
        )
        web_summary = warnings[-1]
        sources = []
    calendar = await registry.execute(
        "calendar_list_upcoming",
        {"days": 30, "max_results": 20, "query": payload.calendar_query or payload.company_name},
        context,
    )
    for profile in company.items:
        if profile.source_url not in {source.url for source in sources}:
            sources.append(
                WebSource(title=f"Hồ sơ: {profile.name}", url=profile.source_url)
            )
    email_context = "\n\n".join(
        f"### {message.sender} — {message.date}\n{message.body[:6000]}"
        for message in email.messages
    )
    company_context = (
        "\n".join(
            f"- {item.name} ({item.domain}); ngành: {item.industry or 'chưa xác minh'}; "
            f"nguồn: {item.source_url}"
            for item in company.items
        )
        or "- Chưa có hồ sơ nội bộ; cần duyệt trước khi lưu dữ kiện mới."
    )
    meetings = (
        "\n".join(
            f"- {event.start}: {event.title}" + (f" — {event.location}" if event.location else "")
            for event in calendar.events
        )
        or "- Không tìm thấy lịch hẹn phù hợp trong 30 ngày tới."
    )
    citations = "\n".join(
        f"{index}. [{source.title}]({source.url})" for index, source in enumerate(sources, start=1)
    )
    report = (
        f"# Hồ sơ trước cuộc họp — {payload.company_name}\n\n"
        "## Email khởi tạo\n\n"
        f"**Chủ đề:** {email.subject}\n\n{email_context}\n\n"
        "## Hồ sơ công ty đã lưu\n\n"
        f"{company_context}\n\n"
        "## Web research có grounding\n\n"
        f"{web_summary}\n\n"
        "## Lịch hẹn sắp tới\n\n"
        f"{meetings}\n\n"
        "## Nguồn kiểm chứng\n\n"
        f"{citations}\n\n"
        "## Human approval\n\n"
        "Bản này chỉ là bản xem trước. Chưa chuyển tiếp email, chưa lưu hồ sơ công ty, "
        "chưa tạo tài liệu và chưa gửi dữ liệu ra ngoài ngoài các truy vấn đọc/nghiên cứu nêu trên."
    )
    return CustomerBriefingResponse(
        report_markdown=report,
        source_count=len(sources),
        email_message_count=len(email.messages),
        meeting_count=len(calendar.events),
        ready_for_human_approval=bool(email.messages),
        next_action="Người dùng xem nguồn và duyệt riêng thao tác lưu/chuyển tiếp nếu cần.",
        web_research_degraded=web_research_degraded,
        warnings=warnings,
    )
