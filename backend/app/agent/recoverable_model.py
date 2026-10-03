"""Shared Gemini retry boundary for ADK-based generation paths."""

import asyncio
import time
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.models import Gemini
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import errors
from pydantic import Field

from app.core.config import APPROVED_GEMINI_MODELS
from app.services.quota import conservative_tokens
from app.tools.contracts import ToolError


class RecoverableGemini(Gemini):
    """Retry once on an approved fallback before any response/tool call is emitted."""

    fallback_model: str
    records: list[dict[str, Any]] = Field(default_factory=list, exclude=True)
    quota: Any = Field(default=None, exclude=True)
    circuit: Any = Field(default=None, exclude=True)
    reserve_primary: bool = Field(default=False, exclude=True)
    enable_fallback: bool = Field(default=True, exclude=True)

    def _validate_tool_calls(self, response: LlmResponse, request: LlmRequest) -> None:
        """Fail closed before ADK dispatches an invented or forbidden tool."""
        for part in getattr(response.content, "parts", None) or ():
            call = getattr(part, "function_call", None)
            if call is not None and call.name not in request.tools_dict:
                self.records.append({
                    "stage": "guardrail", "status": "blocked",
                    "rule": "unavailable_tool", "tool": (call.name or "")[:80],
                })
                raise ToolError(
                    "Chưa xác minh được câu trả lời: công cụ cần dùng không có trong "
                    "phạm vi đã cho phép. Yêu cầu của bạn được giữ nguyên; "
                    "không có nguồn bị cấm nào được truy cập.",
                    code="unavailable_tool",
                )

    async def generate_content_async(
        self,
        llm_request: LlmRequest,
        stream: bool = False,
    ) -> AsyncGenerator[LlmResponse, None]:
        # Never replay a partially emitted response or an already executed tool.
        serialized_request = llm_request.model_dump_json()
        if len(serialized_request) > 160_000:
            raise ToolError(
                "Ngữ cảnh quá dài. Hãy mở cuộc trò chuyện mới và chọn ít tài liệu hơn.",
                code="context_budget",
            )
        started = time.monotonic()
        emitted = False
        effective_fallback_model = self.fallback_model
        if effective_fallback_model == self.model:
            effective_fallback_model = next(
                candidate for candidate in sorted(APPROVED_GEMINI_MODELS) if candidate != self.model
            )
        primary_capability = f"generate:{self.model}"
        try:
            if self.circuit is not None:
                await asyncio.to_thread(self.circuit.before_request, primary_capability)
            if self.quota is not None and self.reserve_primary:
                await asyncio.to_thread(
                    self.quota.reserve,
                    "flash",
                    conservative_tokens(serialized_request, 8192),
                )
            async for response in super().generate_content_async(llm_request, stream=False):
                self._validate_tool_calls(response, llm_request)
                emitted = True
                yield response
            if self.circuit is not None:
                await asyncio.to_thread(self.circuit.success, primary_capability)
            self.records.append(
                {
                    "stage": "model",
                    "status": "success",
                    "model": self.model,
                    "requested_model": self.model,
                    "actual_model": self.model,
                    "fallback_model": effective_fallback_model,
                    "fallback_reason": None,
                    "latency_ms": round((time.monotonic() - started) * 1000),
                }
            )
        except errors.APIError as exc:
            if self.circuit is not None:
                await asyncio.to_thread(self.circuit.failure, primary_capability, exc)
            retryable = exc.code in {404, 429, 500, 502, 503, 504}
            if emitted or not retryable or not self.enable_fallback:
                raise
            if self.quota is not None:
                # Fallback is another real provider request. It must not reuse
                # the primary reservation or silently bypass the daily/RPM cap.
                await asyncio.to_thread(
                    self.quota.reserve,
                    "flash",
                    conservative_tokens(serialized_request, 8192),
                )
            fallback_candidates = [effective_fallback_model]
            for candidate in sorted(APPROVED_GEMINI_MODELS):
                if candidate != self.model and candidate not in fallback_candidates:
                    fallback_candidates.append(candidate)

            last_fallback_exc: Exception | None = None
            for idx, candidate_model in enumerate(fallback_candidates):
                candidate_capability = f"generate:{candidate_model}"
                record = {
                    "stage": "model",
                    "status": "fallback",
                    "model": candidate_model,
                    "requested_model": self.model,
                    "actual_model": candidate_model,
                    "fallback_model": candidate_model,
                    "fallback_reason": f"provider_{exc.code}",
                    "provider_code": exc.code,
                }
                # tools_dict may contain locks; copy the request object, not runtime
                # resources, and replace only the model identifier.
                request = llm_request.model_copy()
                request.model = candidate_model
                fallback = Gemini(model=candidate_model, client=self.client)
                try:
                    if self.circuit is not None:
                        # A primary-model outage must not open the fallback model's
                        # circuit. The two models can have independent capacity and
                        # availability even while sharing one user-owned API key.
                        try:
                            await asyncio.to_thread(
                                self.circuit.before_request, candidate_capability
                            )
                        except ToolError as circuit_err:
                            if circuit_err.code == "gemini_circuit_open":
                                record["status"] = "circuit_open"
                                self.records.append(record)
                                last_fallback_exc = circuit_err
                                continue
                            raise
                    async for response in fallback.generate_content_async(request, stream=False):
                        self._validate_tool_calls(response, request)
                        yield response
                    if self.circuit is not None:
                        await asyncio.to_thread(self.circuit.success, candidate_capability)
                    self.records.append(record)
                    self.model = candidate_model
                    return
                except errors.APIError as fallback_exc:
                    last_fallback_exc = fallback_exc
                    if self.circuit is not None:
                        await asyncio.to_thread(
                            self.circuit.failure, candidate_capability, fallback_exc
                        )
                    record["status"] = "failed"
                    record["fallback_error_code"] = fallback_exc.code
                    self.records.append(record)
                    if fallback_exc.code in {404, 429, 500, 502, 503, 504} and idx + 1 < len(
                        fallback_candidates
                    ):
                        if self.quota is not None:
                            await asyncio.to_thread(
                                self.quota.reserve,
                                "flash",
                                conservative_tokens(serialized_request, 8192),
                            )
                        continue
                    raise
            if last_fallback_exc:
                raise last_fallback_exc from exc
