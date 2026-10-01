"""One-call live smoke for the ProtonX grounded Web Research gate."""

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.services.provider_credentials import active_gemini_key
from app.tools.contracts import ToolContext
from app.tools.web_research import WebResearchInput, web_research


async def main() -> None:
    settings = get_settings()
    async with SessionFactory() as db:
        stored = await active_gemini_key(db, "qa", settings)
        if stored is None:
            from qa_google_read_smoke import _connected_owner_id

            stored = await active_gemini_key(db, _connected_owner_id(), settings)
    if stored is not None:
        settings = settings.model_copy(update={"gemini_api_key": stored[1]})
    result = await web_research(
        WebResearchInput(
            company_name="OpenAI",
            domain="openai.com",
            question="Giới thiệu ngắn và hai cập nhật chính thức gần đây",
            max_sources=4,
        ),
        ToolContext(
            request_id="protonx-live-web-smoke",
            user=SimpleNamespace(id="qa"),
            db=SimpleNamespace(),
            settings=settings,
        ),
    )
    print(
        json.dumps(
            {
                "status": "pass",
                "model": result.model,
                "source_count": len(result.sources),
                "source_hosts": [source.url.split("/")[2] for source in result.sources],
                "summary_characters": len(result.summary),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
