"""Read-only diagnostic for the six public ProtonX source bundles."""

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings
from app.tools.contracts import ToolContext, ToolError
from app.tools.web_research import (
    WebResearchInput,
    collect_public_source_bundle,
)


async def main() -> None:
    cases = json.loads(
        (ROOT / "backend" / "evals" / "protonx_company_benchmark.json").read_text(
            encoding="utf-8"
        )
    )["cases"]
    selected_ids = set(sys.argv[1:])
    if selected_ids:
        cases = [case for case in cases if case["id"] in selected_ids]
    settings = get_settings()
    context = ToolContext(
        request_id="protonx-source-probe",
        user=SimpleNamespace(id="qa"),
        db=SimpleNamespace(),
        settings=settings,
    )

    async def probe(case):
        try:
            sources, _blocks = await collect_public_source_bundle(
                WebResearchInput(
                    company_name=case["company"],
                    domain=case["official_domain"],
                    news_query=case.get("news_query"),
                    max_sources=12,
                ),
                context,
            )
            official = [
                source for source in sources if source.evidence_kind == "page_text"
            ]
            return {
                "case_id": case["id"],
                "status": "pass" if official else "partial",
                "sources": len(sources),
                "official_characters": sum(
                    len(source.evidence_excerpt or "") for source in official
                ),
                "official_urls": [source.url for source in official],
                "headline_sources": sum(
                    source.evidence_kind == "headline" for source in sources
                ),
                "scope": "source_transport_only_not_answer_quality",
            }
        except ToolError as exc:
            return {
                "case_id": case["id"],
                "status": "fail",
                "error_type": type(exc).__name__,
                "error_code": getattr(exc, "code", None),
            }

    results = await asyncio.gather(*(probe(case) for case in cases))
    print(json.dumps(results, ensure_ascii=False))
    if any(result["status"] != "pass" for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
