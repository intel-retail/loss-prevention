"""FastMCP tools and Loss Prevention event-ingestion entry points.

Sensor contract: `describe` + read tools only. No subscribe/callback and no
action tools are exposed.
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

import queries
from config import configured_lanes, get_settings
from delivery import push_event_to_hub
from events import (
    AGE_EVENT,
    ITEM_EVENT,
    LOSS_EVENT,
    SCENARIOS,
    SCHEMAS,
    EventEnvelope,
    make_age_estimate,
    make_item_verification,
    make_loss_event,
)
from models import AgeEstimate, AgeRangeCount, ItemVerification, ItemVerificationSummary, LossEvent
from queries import SEVERITY_RANK
from store import DurableEventStore

_settings = get_settings()
store = DurableEventStore(
    _settings.log_path,
    service="loss_prevention",
    store_id=_settings.store_id,
)
mcp = FastMCP("loss_prevention")

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100
# Large lists overflow the agent's context and get truncated to the oldest rows.
_LimitParam = Annotated[
    int,
    Field(
        ge=1,
        le=_MAX_LIMIT,
        description="Maximum records to return; the newest matching records are kept.",
    ),
]


def _newest(records: list, limit: int) -> list:
    return records[-limit:]


_PeriodParam = Annotated[
    queries.Period | None,
    Field(description="Relative window computed by the server: 'last_hour', 'today', or "
                      "'last_24_hours'. Prefer this over start_time/end_time for relative "
                      "questions; it overrides them."),
]


def _window(start_time: str | None, end_time: str | None, period: str | None) -> tuple[int | None, int | None]:
    if period:
        return queries.period_range(period, _settings.store_timezone)
    return queries.parse_time_range(start_time, end_time, _settings.store_timezone)


def _validate_scenario(scenario: str | None) -> None:
    """Fail loudly on an unknown scenario; a silent [] reads as 'no loss events'."""
    if not scenario:
        return
    valid = set(SCENARIOS) | queries.all_scenarios(store)
    if scenario not in valid:
        raise ToolError(
            f"Unknown scenario '{scenario}'. Valid values: {sorted(valid)}. "
            "Retry with a valid value or omit the filter."
        )


def _validate_lane(lane: str | None) -> None:
    if not lane:
        return
    valid = set(configured_lanes(_settings.lane_config_path)) | set(queries.lanes(store))
    if valid and str(lane) not in valid:
        raise ToolError(
            f"Unknown lane '{lane}'. Valid values: {sorted(valid)}. "
            "Retry with a valid value or omit the filter."
        )


def _should_deliver(event: EventEnvelope) -> bool:
    """Only loss events at/above the threshold reach the hub; all stay queryable."""
    if not _settings.event_delivery_enabled:
        return False
    if event.event_type != LOSS_EVENT:
        return False
    minimum = SEVERITY_RANK.get(_settings.event_hub_min_severity, 0)
    severity = str(event.payload.get("severity", "")).lower()
    return SEVERITY_RANK.get(severity, 0) >= minimum


def _commit(event: EventEnvelope) -> EventEnvelope:
    """Persist first (idempotent), then fan out if delivery applies."""
    _seq, created = store.append_once(event)
    if created and _should_deliver(event):
        push_event_to_hub(_settings.event_hub_url, event)
    return event


def record_loss_event(
    scenario: str,
    lane: str,
    camera_id: str = "",
    severity: str = "high",
    tracking_id: str = "",
    frame: str = "",
    description: str = "",
    ref_id: str | None = None,
    ts_ms: int | None = None,
) -> EventEnvelope:
    """Ingest one loss scenario (used by seed/replay/pipeline bridge)."""
    return _commit(make_loss_event(
        _settings.store_id, scenario, lane, camera_id, severity,
        tracking_id, frame, description, ref_id, ts_ms,
    ))


def record_age_estimate(
    age_range: str,
    lane: str,
    camera_id: str = "",
    tracking_id: str = "",
    gender: str = "unknown",
    frame: str = "",
    ref_id: str | None = None,
    ts_ms: int | None = None,
) -> EventEnvelope:
    """Ingest one age-range classification."""
    return _commit(make_age_estimate(
        _settings.store_id, age_range, lane, camera_id,
        tracking_id, gender, frame, ref_id, ts_ms,
    ))


def record_item_verification(
    item_name: str,
    matched: bool,
    lane: str,
    camera_id: str = "",
    ref_id: str | None = None,
    ts_ms: int | None = None,
) -> EventEnvelope:
    """Ingest one VLM item verification (lp_vlm workload)."""
    return _commit(make_item_verification(
        _settings.store_id, item_name, matched, lane, camera_id, ref_id, ts_ms,
    ))


@mcp.tool(annotations={"readOnlyHint": True})
def describe() -> dict:
    """Describe the service: event types, schemas, and available read tools."""
    return {
        "service": "loss_prevention",
        "store_id": _settings.store_id,
        "use_case": _settings.use_case,
        "event_types": {
            LOSS_EVENT: SCHEMAS[LOSS_EVENT],
            AGE_EVENT: SCHEMAS[AGE_EVENT],
            ITEM_EVENT: SCHEMAS[ITEM_EVENT],
        },
        "read_tools": [
            "Get_loss_history",
            "Get_age_range_counts",
            "Get_loss_event_count",
            "Get_lanes",
            "Get_item_verifications",
            "Get_item_verification_summary",
        ],
        "act_tools": [],
        "subscribe": "disabled",
        "event_delivery": "one-way hub push" if _settings.event_hub_url else "not configured",
    }


@mcp.tool(annotations={"readOnlyHint": True})
def Get_loss_history(
    scenario: Annotated[
        str | None, Field(description="Optional loss scenario, e.g. 'hidden_items'.")
    ] = None,
    lane: Annotated[
        str | None, Field(description="Optional lane id, e.g. 'lane-1'.")
    ] = None,
    start_time: Annotated[
        str | None,
        Field(description=f"Inclusive ISO datetime; local values use {_settings.store_timezone}."),
    ] = None,
    end_time: Annotated[
        str | None,
        Field(description=f"Inclusive ISO datetime; local values use {_settings.store_timezone}."),
    ] = None,
    limit: _LimitParam = _DEFAULT_LIMIT,
    period: _PeriodParam = None,
) -> list[LossEvent]:
    """List the most recent loss events, optionally filtered by scenario/lane/time."""
    _validate_scenario(scenario)
    _validate_lane(lane)
    start_ms, end_ms = _window(start_time, end_time, period)
    return _newest(queries.loss_history(store, scenario, lane, start_ms, end_ms), limit)


@mcp.tool(annotations={"readOnlyHint": True})
def Get_age_range_counts(
    start_time: Annotated[
        str | None,
        Field(description=f"Inclusive ISO datetime; local values use {_settings.store_timezone}."),
    ] = None,
    end_time: Annotated[
        str | None,
        Field(description=f"Inclusive ISO datetime; local values use {_settings.store_timezone}."),
    ] = None,
    lane: Annotated[
        str | None, Field(description="Optional lane id to scope the counts.")
    ] = None,
    period: _PeriodParam = None,
) -> list[AgeRangeCount]:
    """Count sampled age detections by age range over a period (feeds signage decisions).

    Each count is detections (each visible face, sampled about once per second per
    camera), not unique people: report them as detections, never as people or customers.
    """
    _validate_lane(lane)
    start_ms, end_ms = _window(start_time, end_time, period)
    return queries.age_range_counts(store, start_ms, end_ms, lane)


@mcp.tool(annotations={"readOnlyHint": True})
def Get_loss_event_count(
    scenario: Annotated[
        str | None, Field(description="Optional loss scenario to filter by.")
    ] = None,
    lane: Annotated[str | None, Field(description="Optional lane id to filter by.")] = None,
    start_time: Annotated[
        str | None,
        Field(description=f"Inclusive ISO datetime; local values use {_settings.store_timezone}."),
    ] = None,
    end_time: Annotated[
        str | None,
        Field(description=f"Inclusive ISO datetime; local values use {_settings.store_timezone}."),
    ] = None,
    period: _PeriodParam = None,
) -> int:
    """Return a compact count of loss events matching the supplied filters."""
    _validate_scenario(scenario)
    _validate_lane(lane)
    start_ms, end_ms = _window(start_time, end_time, period)
    return queries.loss_event_count(store, scenario, lane, start_ms, end_ms)


@mcp.tool(annotations={"readOnlyHint": True})
def Get_lanes() -> list[str]:
    """List lanes that have recorded loss activity (configured lanes included)."""
    configured = configured_lanes(_settings.lane_config_path)
    return sorted(set(configured) | set(queries.lanes(store))) if configured else queries.lanes(store)


@mcp.tool(annotations={"readOnlyHint": True})
def Get_item_verifications(
    matched: Annotated[
        bool | None,
        Field(description="Optional: true = in inventory, false = not in inventory."),
    ] = None,
    lane: Annotated[str | None, Field(description="Optional lane id to filter by.")] = None,
    start_time: Annotated[
        str | None,
        Field(description=f"Inclusive ISO datetime; local values use {_settings.store_timezone}."),
    ] = None,
    end_time: Annotated[
        str | None,
        Field(description=f"Inclusive ISO datetime; local values use {_settings.store_timezone}."),
    ] = None,
    limit: _LimitParam = _DEFAULT_LIMIT,
    period: _PeriodParam = None,
) -> list[ItemVerification]:
    """List items the VLM identified at self-checkout and whether each is in the store inventory.

    Produced only by the VLM (lp_vlm) workload; `matched` = false means the item
    is not in the inventory list (unknown or unexpected product).
    """
    _validate_lane(lane)
    start_ms, end_ms = _window(start_time, end_time, period)
    return _newest(queries.item_verifications(store, matched, lane, start_ms, end_ms), limit)


@mcp.tool(annotations={"readOnlyHint": True})
def Get_item_verification_summary(
    lane: Annotated[str | None, Field(description="Optional lane id to filter by.")] = None,
    start_time: Annotated[
        str | None,
        Field(description=f"Inclusive ISO datetime; local values use {_settings.store_timezone}."),
    ] = None,
    end_time: Annotated[
        str | None,
        Field(description=f"Inclusive ISO datetime; local values use {_settings.store_timezone}."),
    ] = None,
    period: _PeriodParam = None,
) -> ItemVerificationSummary:
    """Count VLM-verified items that matched vs did not match the inventory, with unmatched names."""
    _validate_lane(lane)
    start_ms, end_ms = _window(start_time, end_time, period)
    return queries.item_verification_summary(store, lane, start_ms, end_ms)
