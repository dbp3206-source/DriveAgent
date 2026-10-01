"""User-scoped company knowledge with explicit provenance."""

import json
import re
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import or_, select

from app.auth.permissions import COMPANY_READ, COMPANY_WRITE
from app.db.models import CompanyProfile
from app.tools.contracts import ToolContext, ToolDefinition, ToolError


def _normalise_name(value: str) -> str:
    return " ".join(value.casefold().split())


def _normalise_domain(value: str) -> str:
    raw = value.strip().casefold()
    parsed = urlsplit(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").removeprefix("www.")
    if not host or len(host) > 253 or not re.fullmatch(r"[a-z0-9.-]+", host):
        raise ValueError("Domain không hợp lệ.")
    return host


class CompanySearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=2, max_length=240)
    limit: int = Field(default=10, ge=1, le=50)


class CompanyUpsertInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=240)
    domain: str = Field(min_length=3, max_length=253)
    industry: str | None = Field(default=None, max_length=240)
    products: list[str] = Field(default_factory=list, max_length=50)
    contacts: list[str] = Field(default_factory=list, max_length=50)
    notes: str = Field(default="", max_length=20_000)
    source_url: str = Field(min_length=8, max_length=2_000)
    source_kind: Literal["official", "internal", "research"] = "official"

    @field_validator("name", "industry", "notes")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        return _normalise_domain(value)

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Nguồn phải là URL HTTP(S) đầy đủ.")
        return value


class CompanyView(BaseModel):
    id: str
    name: str
    domain: str
    industry: str | None
    products: list[str]
    contacts: list[str]
    notes: str
    source_url: str
    source_kind: str
    last_verified_at: datetime


class CompanySearchOutput(BaseModel):
    items: list[CompanyView]


def _view(row: CompanyProfile) -> CompanyView:
    return CompanyView(
        id=row.id,
        name=row.name,
        domain=row.domain,
        industry=row.industry,
        products=json.loads(row.products_json or "[]"),
        contacts=json.loads(row.contacts_json or "[]"),
        notes=row.notes,
        source_url=row.source_url,
        source_kind=row.source_kind,
        last_verified_at=row.last_verified_at,
    )


async def company_search(payload: CompanySearchInput, context: ToolContext) -> CompanySearchOutput:
    needle = _normalise_name(payload.query)
    rows = await context.db.scalars(
        select(CompanyProfile)
        .where(
            CompanyProfile.user_id == context.user.id,
            or_(
                CompanyProfile.normalized_name.contains(needle),
                CompanyProfile.domain.contains(needle),
            ),
        )
        .order_by(CompanyProfile.last_verified_at.desc())
        .limit(payload.limit)
    )
    return CompanySearchOutput(items=[_view(row) for row in rows])


async def company_upsert(payload: CompanyUpsertInput, context: ToolContext) -> CompanyView:
    row = await context.db.scalar(
        select(CompanyProfile).where(
            CompanyProfile.user_id == context.user.id,
            CompanyProfile.domain == payload.domain,
        )
    )
    now = datetime.now(UTC)
    if row is None:
        row = CompanyProfile(user_id=context.user.id, domain=payload.domain)
        context.db.add(row)
    row.name = payload.name
    row.normalized_name = _normalise_name(payload.name)
    row.industry = payload.industry
    row.products_json = json.dumps(payload.products, ensure_ascii=False)
    row.contacts_json = json.dumps(payload.contacts, ensure_ascii=False)
    row.notes = payload.notes
    row.source_url = payload.source_url
    row.source_kind = payload.source_kind
    row.last_verified_at = now
    row.updated_at = now
    try:
        await context.db.flush()
    except Exception as exc:
        raise ToolError("Không thể lưu hồ sơ công ty.", code="company_write_failed") from exc
    return _view(row)


def company_tool_definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="company_search",
            description="Tra cứu hồ sơ công ty riêng của người dùng, kèm nguồn và ngày xác minh.",
            input_model=CompanySearchInput,
            output_model=CompanySearchOutput,
            handler=company_search,
            required_permissions={COMPANY_READ},
            max_attempts=1,
        ),
        ToolDefinition(
            name="company_upsert",
            description="Lưu hoặc cập nhật hồ sơ công ty sau khi người dùng duyệt.",
            input_model=CompanyUpsertInput,
            output_model=CompanyView,
            handler=company_upsert,
            required_permissions={COMPANY_WRITE},
            requires_user_action=True,
            max_attempts=1,
        ),
    ]
