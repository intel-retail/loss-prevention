"""One-way event-hub delivery for committed Loss Prevention envelopes."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from events import EventEnvelope


def to_hub_event(event: EventEnvelope) -> dict:
    """Map the LP envelope onto the agent inbox's event shape.

    `store_id` stays inside `data`; at the top level the inbox compares it
    against its own store id and rejects the event on any mismatch.
    """
    occurred_at = datetime.fromtimestamp(event.ts_ms / 1000, tz=timezone.utc)
    return {
        "event_id": event.ref_id,
        "event_type": event.event_type,
        "occurred_at": occurred_at.isoformat().replace("+00:00", "Z"),
        "data": {
            **event.payload,
            "ref_id": event.ref_id,
            "service": event.service,
            "store_id": event.store_id,
            "ts_ms": event.ts_ms,
        },
    }


def _post(hub_url: str, event: EventEnvelope, timeout_s: float) -> bool:
    request = urllib.request.Request(
        hub_url,
        data=json.dumps(to_hub_event(event)).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout_s) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def push_event_to_hub(
    hub_url: str | None,
    event: EventEnvelope,
    retries: int = 3,
    timeout_s: float = 5.0,
) -> bool:
    """Push one already-persisted event envelope to the configured hub."""
    if not hub_url:
        return False
    for attempt in range(retries):
        if _post(hub_url, event, timeout_s):
            return True
        if attempt + 1 < retries:
            time.sleep(0.5 * (2**attempt))
    print(f"[LP MCP] Event hub delivery failed after {retries} attempts: {hub_url}", flush=True)
    return False
