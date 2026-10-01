"""Read public RSS evidence only; never call a model or private Workspace tools."""
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


async def main():
    from app.core.config import Settings
    from app.tools.contracts import ToolContext, ToolError
    from app.tools.web_research import WebResearchInput, collect_public_source_bundle

    context = ToolContext(request_id="public-fallback-qa", user=SimpleNamespace(id="qa"),
                          db=SimpleNamespace(), settings=Settings(_env_file=None))
    results = []
    for question in ["lịch thi đấu bóng đá nam ASIAD ngày hôm nay",
                     "Python latest release"]:
        try:
            sources, blocks = await collect_public_source_bundle(
                WebResearchInput(question=question, max_sources=3), context)
            results.append({"question": question, "collection": "PASS",
                            "sources": [source.model_dump(mode="json") for source in sources],
                            "blocks": len(blocks), "answer_correctness": "NOT VERIFIED"})
        except ToolError as exc:
            results.append({"question": question, "collection": "FAIL", "code": exc.code})
    report = ROOT / "design-work/qa/public-fallback-live-20260930.json"
    report.write_text(json.dumps({"model_calls": 0, "cases": results},
                                ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(report), "cases": [
        {"question": item["question"], "collection": item["collection"]} for item in results]},
        ensure_ascii=True))


if __name__ == "__main__":
    asyncio.run(main())
