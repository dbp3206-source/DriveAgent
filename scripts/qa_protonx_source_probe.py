"""Read-only diagnostic for the six public ProtonX source bundles."""

import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings
from app.tools.contracts import ToolContext, ToolError
from app.tools.web_research import (
    WebResearchInput,
    collect_public_source_bundle,
    collect_tavily_source_bundle,
)


def selected_cases(selected_ids: set[str]) -> list[dict]:
    cases = json.loads(
        (ROOT / "backend" / "evals" / "protonx_company_benchmark.json").read_text(
            encoding="utf-8"
        )
    )["cases"]
    if not selected_ids:
        return cases
    acceptance = json.loads(
        (ROOT / "backend" / "evals" / "release_acceptance.json").read_text(encoding="utf-8")
    )
    # Only add the already locked U01 source-discovery case, not new examples.
    for group in acceptance["groups"]:
        for case in group.get("cases", []):
            if case["id"] == "U01":
                cases.append(case)
    unknown = selected_ids - {case["id"] for case in cases}
    if unknown:
        raise ValueError("Unknown case ID; no network requests were sent")
    return [case for case in cases if case["id"] in selected_ids]


async def main() -> None:
    try:
        cases = selected_cases(set(sys.argv[1:]))
    except ValueError as exc:
        print(str(exc))
        raise SystemExit(2) from None
    settings = get_settings()
    tavily = bool(settings.tavily_api_key and settings.tavily_api_key.get_secret_value().strip())
    collector = collect_tavily_source_bundle if tavily else collect_public_source_bundle
    provider = "tavily_basic" if tavily else "official_page_google_news_rss"
    context = ToolContext(
        request_id="protonx-source-probe",
        user=SimpleNamespace(id="qa"),
        db=SimpleNamespace(),
        settings=settings,
    )

    async def probe(case):
        started = time.perf_counter()
        try:
            sources, _blocks = await collector(
                WebResearchInput(
                    company_name=case.get("company"),
                    domain=case.get("official_domain"),
                    news_query=case.get("news_query"),
                    question=case.get("question", "Tổng quan, sản phẩm và tin tức gần đây"),
                    max_sources=12,
                ),
                context,
            )
            page_sources = [source for source in sources if source.evidence_kind == "page_text"]
            host = urlsplit("https://" + case.get("official_domain", "")).hostname
            official = [source for source in page_sources
                        if host and urlsplit(source.url).hostname == host]
            return {
                "case_id": case["id"],
                "status": "collected" if page_sources else "partial",
                "provider": provider,
                "latency_seconds": round(time.perf_counter() - started, 3),
                "sources": len(sources),
                "page_text_sources": len(page_sources),
                "official_characters": sum(
                    len(source.evidence_excerpt or "") for source in official
                ),
                "official_urls": [source.url for source in official],
                "source_receipts": [source.model_dump(mode="json") for source in sources],
                "headline_sources": sum(
                    source.evidence_kind == "headline" for source in sources
                ),
                "scope": "transport_only_not_authority_truth_or_answer_quality",
            }
        except ToolError as exc:
            return {
                "case_id": case["id"],
                "status": "fail",
                "provider": provider,
                "latency_seconds": round(time.perf_counter() - started, 3),
                "error_type": type(exc).__name__,
                "error_code": getattr(exc, "code", None),
            }

    results = await asyncio.gather(*(probe(case) for case in cases))
    output_dir = ROOT / "design-work" / "qa" / "validation"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"public-source-probe-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.json"
    output.write_text(json.dumps({
        "observed_at": datetime.now(UTC).isoformat(), "model_calls": 0,
        "scope": "Public source collection only; not authenticated cloud Chat acceptance",
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"receipt": str(output), "results": [
        {key: value for key, value in result.items() if key != "source_receipts"}
        for result in results]}, ensure_ascii=False))
    if any(result["status"] != "collected" for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
