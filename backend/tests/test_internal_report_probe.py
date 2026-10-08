"""Offline verification of the one-call internal assessment boundary."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from google import genai
from google.genai import errors, types

from app.agent.creation import WEB_CONSULTATION_INSTRUCTION
from app.tools.contracts import ToolError

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
spec = importlib.util.spec_from_file_location("protonx_scoring", SCRIPTS / "protonx_scoring.py")
scoring = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scoring)
sys.modules.setdefault("protonx_scoring", scoring)
spec = importlib.util.spec_from_file_location(
    "internal_report_probe", SCRIPTS / "qa_protonx_live_benchmark.py"
)
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)


def test_internal_probe_uses_product_consultation_guidance():
    assert probe.WEB_CONSULTATION_INSTRUCTION == WEB_CONSULTATION_INSTRUCTION


def install(monkeypatch, *, response=None, failure=None):
    reserve = Mock()
    guard = Mock(return_value=SimpleNamespace(reserve=reserve))
    generate = AsyncMock(
        return_value=SimpleNamespace(text=json.dumps(response or {})), side_effect=failure
    )
    client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate), aclose=AsyncMock()),
        close=Mock(),
    )
    factory = Mock(return_value=client)
    monkeypatch.setattr(probe, "quota_guard", guard)
    monkeypatch.setattr(probe, "create_inference_client", factory)
    settings = SimpleNamespace(
        gemini_is_configured=True,
        gemini_api_key="offline-fake-key",
        gemini_chat_model="offline-model",
        data_dir=Path("unused"),
    )
    return settings, reserve, generate, client, factory


async def test_quota_rejection_prevents_provider_call(monkeypatch):
    settings, reserve, generate, _client, factory = install(monkeypatch)
    reserve.side_effect = ToolError("Hết hạn mức", code="quota_exhausted")
    with pytest.raises(ToolError):
        await probe.generate_reports(settings, "public inputs")
    factory.assert_not_called()
    generate.assert_not_called()
    assert reserve.call_args.kwargs == {}


@pytest.mark.parametrize("code", [429, 503])
async def test_provider_failure_is_bounded_redacted_and_never_retried(monkeypatch, code):
    failure = errors.APIError(code, {"error": {"message": "PRIVATE ERROR BODY"}})
    settings, reserve, generate, client, factory = install(monkeypatch, failure=failure)
    with pytest.raises(ToolError) as caught:
        await probe.generate_reports(settings, "public inputs")
    assert caught.value.code == f"benchmark_provider_http_{code}"
    assert "PRIVATE" not in str(caught.value)
    assert generate.await_count == reserve.call_count == 1
    assert factory.call_args.kwargs["http_options"].retry_options.attempts == 1
    assert factory.call_args.kwargs["http_options"].timeout == 60_000
    client.aio.aclose.assert_awaited_once()
    client.close.assert_called_once()


async def test_invalid_response_does_not_trigger_second_call(monkeypatch):
    settings, reserve, generate, _client, _factory = install(monkeypatch)
    with pytest.raises(ToolError) as caught:
        await probe.generate_reports(settings, "public inputs")
    assert caught.value.code == "benchmark_response_invalid"
    assert generate.await_count == reserve.call_count == 1
    config = generate.call_args.kwargs["config"]
    assert config.tools is None
    schema = config.response_json_schema
    assert schema["additionalProperties"] is False
    assert schema["properties"]["reports"]["minItems"] == 6
    questions = schema["$defs"]["CompanyReport"]["properties"]["clarification_questions"]
    assert questions["minItems"] == questions["maxItems"] == 3


async def test_real_sdk_sends_one_structured_request_without_search(monkeypatch):
    reports = [
        dict(
            case_id=f"company-{index:02d}",
            company_overview="Verified company overview [S1]",
            industry="Industry [S1]",
            products=["Product [S1]"],
            company_scale="Chưa xác minh",
            recent_news=["Chưa xác minh"],
            contact_context="Dữ liệu giả lập đầu vào",
            meeting_notes="Chưa có lịch cuộc hẹn",
            human_approval_status="pending",
            clarification_questions=["Nhu cầu nào?", "Nguồn nào?", "Đầu ra nào?"],
        )
        for index in range(1, 7)
    ]
    requests = []

    async def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": json.dumps({"reports": reports})}],
                            "role": "model",
                        }
                    }
                ]
            },
        )

    settings, reserve, _generate, _client, _factory = install(monkeypatch)
    client = genai.Client(
        api_key="offline-fake-key",
        http_options=types.HttpOptions(
            async_client_args={"transport": httpx.MockTransport(handler)},
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
    monkeypatch.setattr(probe, "create_inference_client", Mock(return_value=client))
    result = await probe.generate_reports(settings, "public inputs")
    assert len(result.reports) == 6
    assert len(requests) == reserve.call_count == 1
    assert not requests[0].get("tools")
    assert requests[0]["generationConfig"]["responseJsonSchema"]["additionalProperties"] is False
