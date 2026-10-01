"""Bounded, owner-scoped operational events; never model thoughts or user content.

Ephemeral UI channel for the single-process local deployment, not a durable queue.
"""

from collections import OrderedDict
from threading import RLock
from time import monotonic

from app.services.agentops import sanitize_run_trace

_runs: OrderedDict[tuple[str, str], tuple[float, list[dict]]] = OrderedDict()
_lock = RLock()
TTL_SECONDS = 1800
MAX_RUNS = 512


def publish_progress(user_id: str, request_id: str, event: dict) -> None:
    safe = sanitize_run_trace([event], request_id)
    if not safe:
        return
    with _lock:
        now = monotonic()
        for key, (updated, _) in list(_runs.items()):
            if now - updated > TTL_SECONDS:
                del _runs[key]
        key = (user_id, request_id)
        events = _runs.get(key, (now, []))[1]
        _runs[key] = (now, (events + safe)[-60:])
        _runs.move_to_end(key)
        while len(_runs) > MAX_RUNS:
            _runs.popitem(last=False)


def read_progress(user_id: str, request_id: str) -> list[dict]:
    with _lock:
        updated, events = _runs.get((user_id, request_id), (0, []))
        return [dict(event) for event in events] if monotonic() - updated <= TTL_SECONDS else []
