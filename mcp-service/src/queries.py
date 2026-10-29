"""Pure query logic over the durable log. No MCP or agent concerns here.

A "record" is a flattened event: the envelope's ref_id + ts_ms + a store-local
timestamp merged with the payload fields.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

from events import AGE_EVENT, ITEM_EVENT, LOSS_EVENT
from models import AgeRangeCount, ItemVerificationSummary

_MAX = 10_000
SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
_STORE_TIMEZONE = os.getenv("LP_TIMEZONE", "Asia/Kolkata")


def _to_record(event: Any) -> dict[str, Any]:
    """Flatten an event envelope into a query row."""
    local_time = datetime.fromtimestamp(
        event.ts_ms / 1000, tz=timezone.utc
    ).astimezone(ZoneInfo(_STORE_TIMEZONE))
    timestamp = (
        f"{local_time.strftime('%B')} {local_time.day}, {local_time.year} at "
        f"{local_time.strftime('%I').lstrip('0')}:{local_time.strftime('%M:%S %p %Z')}"
    )
    return {
        "ref_id": event.ref_id,
        "ts_ms": event.ts_ms,
        "timestamp": timestamp,
        "event_type": event.event_type,
        **event.payload,
    }


Period = Literal["last_hour", "today", "last_24_hours"]


def period_range(period: str, store_timezone: str, now: datetime | None = None) -> tuple[int, int]:
    """Resolve a relative period to epoch-ms bounds using the server clock."""
    now = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(store_timezone))
    if period == "last_hour":
        start = now - timedelta(hours=1)
    elif period == "last_24_hours":
        start = now - timedelta(hours=24)
    elif period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        raise ValueError(f"Unknown period '{period}'. Valid values: last_hour, today, last_24_hours.")
    return int(start.timestamp() * 1000), int(now.timestamp() * 1000)


def parse_time_range(
    start_time: str | None,
    end_time: str | None,
    store_timezone: str,
) -> tuple[int | None, int | None]:
    """Convert ISO datetimes to epoch milliseconds using the store timezone."""
    zone = ZoneInfo(store_timezone)

    def parse(value: str | None) -> int | None:
        if value is None:
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=zone)
        return int(parsed.timestamp() * 1000)

    start_ms = parse(start_time)
    end_ms = parse(end_time)
    if start_ms is not None and end_ms is not None and start_ms > end_ms:
        raise ValueError("start_time must be earlier than or equal to end_time")
    return start_ms, end_ms


def _iter_records(
    log: Any,
    event_type: str,
    start_ms: int | None,
    end_ms: int | None,
) -> Iterator[dict[str, Any]]:
    newest_first = start_ms is None and end_ms is None
    records = [
        _to_record(event)
        for event in log.read(
            event_type=event_type,
            limit=_MAX,
            start_ms=start_ms,
            end_ms=end_ms,
            newest_first=newest_first,
        )
    ]
    yield from reversed(records) if newest_first else records


def loss_history(
    log: Any,
    scenario: str | None = None,
    lane: str | None = None,
    start_ms: int | None = None,
    end_ms: int | None = None,
    limit: int = _MAX,
) -> list[dict[str, Any]]:
    """Loss events, optionally filtered by scenario and/or lane, oldest first."""
    out: list[dict[str, Any]] = []
    for record in _iter_records(log, LOSS_EVENT, start_ms, end_ms):
        if scenario and record.get("scenario") != scenario:
            continue
        if lane and str(record.get("lane")) != str(lane):
            continue
        out.append(record)
        if len(out) >= limit:
            break
    return out


def age_range_counts(
    log: Any,
    start_ms: int | None = None,
    end_ms: int | None = None,
    lane: str | None = None,
) -> list[AgeRangeCount]:
    """Count age estimates by age range over the period, optionally per lane."""
    buckets: dict[str, int] = {}
    for record in _iter_records(log, AGE_EVENT, start_ms, end_ms):
        if lane and str(record.get("lane")) != str(lane):
            continue
        age_range = str(record.get("age_range", "unknown"))
        buckets[age_range] = buckets.get(age_range, 0) + 1
    return [{"age_range": age_range, "detections": count}
            for age_range, count in sorted(buckets.items())]


def loss_event_count(
    log: Any,
    scenario: str | None = None,
    lane: str | None = None,
    start_ms: int | None = None,
    end_ms: int | None = None,
) -> int:
    """Compact count of loss events matching the supplied filters."""
    count = 0
    for record in _iter_records(log, LOSS_EVENT, start_ms, end_ms):
        if scenario and record.get("scenario") != scenario:
            continue
        if lane and str(record.get("lane")) != str(lane):
            continue
        count += 1
    return count


def lanes(log: Any) -> list[str]:
    """Distinct lane ids that have any loss activity."""
    return sorted({str(record["lane"]) for record in loss_history(log) if record.get("lane")})


def item_verifications(
    log: Any,
    matched: bool | None = None,
    lane: str | None = None,
    start_ms: int | None = None,
    end_ms: int | None = None,
) -> list[dict[str, Any]]:
    """VLM item verifications, optionally filtered by match result and lane, oldest first."""
    out: list[dict[str, Any]] = []
    for record in _iter_records(log, ITEM_EVENT, start_ms, end_ms):
        if matched is not None and bool(record.get("matched")) != matched:
            continue
        if lane and str(record.get("lane")) != str(lane):
            continue
        out.append(record)
    return out


def item_verification_summary(
    log: Any,
    lane: str | None = None,
    start_ms: int | None = None,
    end_ms: int | None = None,
) -> ItemVerificationSummary:
    """Matched/unmatched counts plus the distinct unmatched item names."""
    records = item_verifications(log, None, lane, start_ms, end_ms)
    unmatched = [r for r in records if not r.get("matched")]
    return {
        "total": len(records),
        "matched": len(records) - len(unmatched),
        "unmatched": len(unmatched),
        "unmatched_items": sorted({str(r.get("item_name", "")) for r in unmatched}),
    }


def all_scenarios(log: Any) -> set[str]:
    """Scenario values present in the log (for filter validation)."""
    return {str(record["scenario"]) for record in loss_history(log) if record.get("scenario")}
