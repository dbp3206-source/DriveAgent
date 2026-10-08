"""The acceptance source probe must measure the configured product path."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from app.tools.web_research import WebSource

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "qa_protonx_source_probe.py"
spec = importlib.util.spec_from_file_location("tavily_source_probe_test", SCRIPT)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_probe_selects_only_locked_requested_cases():
    assert len(probe.selected_cases(set())) == 6
    selected = probe.selected_cases({"company-02", "U01"})
    assert [case["id"] for case in selected] == ["company-02", "U01"]
    assert "ASIAD 2026" in selected[1]["question"]


def test_unknown_case_cannot_be_an_empty_passing_run():
    with pytest.raises(ValueError, match="Unknown case ID"):
        probe.selected_cases({"company-02", "UNKNOWN"})


async def test_main_uses_tavily_and_never_labels_third_party_as_official(
    monkeypatch, tmp_path, capsys,
):
    selected = probe.selected_cases({"company-02", "U01"})
    source = WebSource(title="Third-party page", url="https://news.example/page",
                       evidence_kind="page_text", evidence_excerpt="Public content")
    collector = AsyncMock(return_value=([source], ["Public content"]))
    legacy = AsyncMock(side_effect=AssertionError("Must measure configured Tavily path"))
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(probe, "selected_cases", lambda _: selected)
    monkeypatch.setattr(probe, "get_settings", lambda: SimpleNamespace(
        tavily_api_key=SecretStr("test-key")))
    monkeypatch.setattr(probe, "collect_tavily_source_bundle", collector)
    monkeypatch.setattr(probe, "collect_public_source_bundle", legacy)
    await probe.main()
    assert collector.await_count == 2
    legacy.assert_not_awaited()
    output = json.loads(capsys.readouterr().out)
    receipt = json.loads(Path(output["receipt"]).read_text(encoding="utf-8"))
    assert receipt["model_calls"] == 0
    for result in receipt["results"]:
        assert result["provider"] == "tavily_basic"
        assert result["status"] == "collected"  # Not accepted or quality-scored.
        assert result["official_urls"] == [] and result["official_characters"] == 0
        assert result["page_text_sources"] == 1
        assert result["source_receipts"][0]["evidence_excerpt"] == "Public content"
