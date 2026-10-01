"""Read-only, privacy-minimal acceptance probe for the daily Gmail skill source gather."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import uuid
from datetime import datetime, timedelta
from email.utils import parseaddr, parsedate_to_datetime
from zoneinfo import ZoneInfo

from qa_google_read_smoke import _connected_owner_id

from app.db.models import User
from app.db.session import SessionFactory, engine, settings
from app.tools.contracts import ToolContext
from app.tools.gmail import _html_to_text, gmail_tool_definitions
from app.tools.registry import ToolRegistry


async def main(*, today: bool = False) -> None:
    local_now = datetime.now(ZoneInfo("Asia/Bangkok"))
    day = local_now.date() if today else local_now.date() - timedelta(days=1)
    registry = ToolRegistry()
    for definition in gmail_tool_definitions():
        if definition.name in {"gmail_read_matching_messages", "gmail_read_thread"}:
            registry.register(definition)
    async with SessionFactory() as db:
        user = await db.get(User, _connected_owner_id())
        if user is None:
            raise RuntimeError("Connected owner not found")
        result = await registry.execute(
            "gmail_read_matching_messages",
            {
                "query": 'from:"Bảo Phúc Đinh" subject:"Bản chi tiết" newer_than:3d',
                "local_date": day.isoformat(),
                "day_scope": "today" if today else "any",
                "timezone": "Asia/Bangkok",
                "sender_name": "Đinh Bảo Phúc",
                "max_results": 20,
            },
            ToolContext(
                request_id=str(uuid.uuid4()),
                user=user,
                db=db,
                settings=settings,
                source="qa_read_only",
            ),
        )
        matching_sender = [
            message for message in result.messages
            if parseaddr(message.sender)[0].strip().casefold() == "bảo phúc đinh"
        ]
        representation_lengths = []
        for message in matching_sender:
            thread = await registry.execute(
                "gmail_read_thread",
                {"thread_id": message.thread_id},
                ToolContext(
                    request_id=str(uuid.uuid4()),
                    user=user,
                    db=db,
                    settings=settings,
                    source="qa_read_only",
                ),
            )
            detail = next(item for item in thread.messages if item.id == message.id)
            match = re.search(r"Bản chi tiết\s*(\d{1,2})h", message.subject, re.IGNORECASE)
            try:
                header_local_time = parsedate_to_datetime(message.date).astimezone(
                    ZoneInfo("Asia/Bangkok")
                ).strftime("%H:%M")
            except (TypeError, ValueError, OverflowError):
                header_local_time = None
            representation_lengths.append({
                "slot": int(match.group(1)) if match else None,
                "received_local_time": datetime.fromisoformat(
                    message.received_at_local
                ).strftime("%H:%M"),
                "header_local_time": header_local_time,
                "selected_chars": len(message.body),
                "plain_chars": len(detail.plain_body),
                "html_text_chars": len(_html_to_text(detail.html_body)),
            })
    await engine.dispose()
    slots = sorted(
        int(match.group(1))
        for message in matching_sender
        if (match := re.search(r"Bản chi tiết\s*(\d{1,2})h", message.subject, re.IGNORECASE))
    )
    as_of = datetime.fromisoformat(result.as_of_local)
    within_cutoff = all(
        datetime.fromisoformat(message.received_at_local).date() == day
        and datetime.fromisoformat(message.received_at_local) <= as_of
        for message in result.messages
    )
    report = {
        "cloud_writes": 0,
        "local_date": day.isoformat(),
        "examined": result.examined_count,
        "messages_read": len(result.messages),
        "matching_sender": len(matching_sender),
        "body_available": sum(message.body_available for message in result.messages),
        "body_bytes": sum(len(message.body.encode("utf-8")) for message in result.messages),
        "as_of_local": result.as_of_local,
        "representation_lengths": sorted(
            representation_lengths, key=lambda item: item["slot"] or 0
        ),
        "subject_hour_labels_diagnostic_only": slots,
        "all_received_within_day_and_cutoff": within_cutoff,
        "unverified_dates": result.date_unverified_count,
        "future_excluded": result.future_excluded_count,
        "sender_mismatch": result.sender_mismatch_count,
        "local_day_mismatch": result.local_day_mismatch_count,
        "next_page": bool(result.next_page_token),
    }
    report["passed"] = (
        report["messages_read"] > 0
        and report["matching_sender"] == report["messages_read"]
        and report["body_available"] == report["messages_read"]
        and len({message.id for message in result.messages}) == report["messages_read"]
        and within_cutoff
        and report["unverified_dates"] == 0
        and not report["next_page"]
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--today", action="store_true", help="Probe the current local day")
    args = parser.parse_args()
    asyncio.run(main(today=args.today))
