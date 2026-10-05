import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api import metrics
from app.core.config import Settings


@pytest.mark.parametrize(
    ("input_price", "output_price", "has_runs", "expected"),
    [
        (None, None, True, None),
        (1, None, True, None),
        (None, 2, True, None),
        (1, 2, False, None),
        (0, 0, True, "0.0"),
        (1, 2, True, "0.0014"),
    ],
)
async def test_cost_requires_explicit_prices_and_observed_runs(
    monkeypatch, input_price, output_price, has_runs, expected
):
    settings = Settings(
        _env_file=None,
        gemini_input_usd_per_million=input_price,
        gemini_output_usd_per_million=output_price,
    )
    trace = json.dumps([{
        "stage": "usage", "prompt_token_count": 1000, "candidates_token_count": 200,
    }])
    db = SimpleNamespace(scalars=AsyncMock(side_effect=[
        SimpleNamespace(all=lambda: []),
        SimpleNamespace(all=lambda: [trace] if has_runs else []),
    ]))
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=db)
    context.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(metrics, "SessionFactory", lambda: context)
    monkeypatch.setattr(metrics, "get_settings", lambda: settings)
    monkeypatch.setattr(metrics, "_authorized", lambda _request: True)
    monkeypatch.setattr(metrics, "open_circuit_count", lambda *_args, **_kwargs: 0)
    response = await metrics.prometheus_metrics(SimpleNamespace())
    text = response.body.decode()
    if expected is None:
        assert "drive_agent_model_estimated_cost" not in text
    else:
        assert f"drive_agent_model_estimated_cost_usd_total {expected}" in text
        assert f"drive_agent_model_estimated_cost_usd_per_run {expected}" in text
    assert "drive_agent_observed_runs" in text


async def test_cloud_metrics_still_require_a_token(monkeypatch):
    settings = Settings(_env_file=None, environment="production", metrics_bearer_token="x" * 48)
    monkeypatch.setattr(metrics, "get_settings", lambda: settings)
    with pytest.raises(HTTPException) as denied:
        await metrics.prometheus_metrics(SimpleNamespace(headers={}))
    assert denied.value.status_code == 401


@pytest.mark.parametrize("events", [
    [{"stage": "model", "latency_ms": 20}],
    [{"stage": "usage", "prompt_token_count": 1000}],
    [{"stage": "usage", "prompt_token_count": True, "candidates_token_count": 200}],
])
async def test_missing_usage_cannot_be_published_as_zero_cost(monkeypatch, events):
    settings = Settings(
        _env_file=None, gemini_input_usd_per_million=1, gemini_output_usd_per_million=2
    )
    db = SimpleNamespace(scalars=AsyncMock(side_effect=[
        SimpleNamespace(all=lambda: []),
        SimpleNamespace(all=lambda: [json.dumps(events)]),
    ]))
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=db)
    context.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(metrics, "SessionFactory", lambda: context)
    monkeypatch.setattr(metrics, "get_settings", lambda: settings)
    monkeypatch.setattr(metrics, "_authorized", lambda _request: True)
    monkeypatch.setattr(metrics, "open_circuit_count", lambda *_args, **_kwargs: 0)
    response = await metrics.prometheus_metrics(SimpleNamespace())
    assert "drive_agent_model_estimated_cost" not in response.body.decode()


@pytest.mark.parametrize("invalid", [-1, float("nan"), float("inf")])
def test_invalid_prices_are_not_accepted(invalid):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, gemini_input_usd_per_million=invalid)
