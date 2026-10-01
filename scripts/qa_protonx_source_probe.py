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
    results = []
    for case in cases:
        try:
            sources, blocks = await collect_public_source_bundle(
                WebResearchInput(
                    company_name=case["company"],
                    domain=case["official_domain"],
                    news_query=case.get("news_query"),
                    max_sources=12,
                ),
                context,
            )
            results.append(
                {
                    "case_id": case["id"],
                    "status": "pass",
                    "sources": len(sources),
                    "official_characters": len(blocks[0]),
                }
            )
        except ToolError as exc:
            results.append(
                {
                    "case_id": case["id"],
                    "status": "fail",
                    "error_type": type(exc).__name__,
                    "error_code": getattr(exc, "code", None),
                }
            )
    print(json.dumps(results, ensure_ascii=False))
    if any(result["status"] != "pass" for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
