"""Loss Prevention event schema and envelope construction.

Three event types flow through one durable log:

- ``loss_event`` — a self-checkout loss scenario detected on a lane.
- ``age_estimate`` — an age-range classification (feeds the signage board).
- ``item_verification`` — a VLM-identified item checked against the inventory.

Builders write an envelope; the store persists it first, then delivery fans
committed envelopes out to the agent hub.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

LOSS_EVENT = "loss_event"
AGE_EVENT = "age_estimate"
ITEM_EVENT = "item_verification"
SERVICE = "loss_prevention"

# Known self-checkout loss scenarios (one per lane camera in the 6-cam lane).
SCENARIOS = (
    "items_in_basket",
    "hidden_items",
    "fake_scan_detection",
    "multi_product_identification",
    "product_switching",
    "sweethearting",
)

LOSS_SCHEMA: dict[str, str] = {
    "scenario": "str",      # one of SCENARIOS
    "lane": "str",          # lane identifier, e.g. lane-1
    "camera_id": "str",     # cam1..cam6
    "severity": "str",      # low | medium | high | critical
    "tracking_id": "str",   # gvatrack id, unique per tracked object
    "frame": "str",         # object-store URI for the evidence frame
    "description": "str",   # one-line summary
}

AGE_SCHEMA: dict[str, str] = {
    "age_range": "str",     # e.g. 0-18, 18-25, 25-35, 35-45, 45-60, 60+
    "lane": "str",          # lane identifier
    "camera_id": "str",     # cam serving the age-verification workload
    "tracking_id": "str",   # gvatrack id
    "gender": "str",        # male | female | unknown
    "frame": "str",         # object-store URI for the face frame
}

ITEM_SCHEMA: dict[str, str] = {
    "item_name": "str",    # VLM-identified product, e.g. Coca-Cola Bottle Large
    "matched": "bool",     # True when the item is in the store inventory list
    "lane": "str",         # lane identifier
    "camera_id": "str",    # camera running the lp_vlm workload
}

SCHEMAS: dict[str, dict[str, str]] = {
    LOSS_EVENT: LOSS_SCHEMA, AGE_EVENT: AGE_SCHEMA, ITEM_EVENT: ITEM_SCHEMA,
}


@dataclass(frozen=True)
class EventEnvelope:
    event_type: str
    service: str
    store_id: str
    payload: dict[str, Any]
    ref_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    ts_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    schema_version: int = 1

    def to_json(self) -> str:
        import json

        return json.dumps(asdict(self), separators=(",", ":"), sort_keys=True)

    @classmethod
    def from_json(cls, raw: str) -> EventEnvelope:
        import json

        return cls(**json.loads(raw))


def make_loss_event(
    store_id: str,
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
    return EventEnvelope(
        event_type=LOSS_EVENT,
        service=SERVICE,
        store_id=store_id,
        payload={
            "scenario": scenario,
            "lane": str(lane),
            "camera_id": camera_id,
            "severity": severity.lower(),
            "tracking_id": str(tracking_id),
            "frame": frame,
            "description": description or scenario.replace("_", " "),
        },
        ref_id=ref_id or uuid.uuid4().hex,
        ts_ms=ts_ms if ts_ms is not None else int(time.time() * 1000),
    )


def make_age_estimate(
    store_id: str,
    age_range: str,
    lane: str,
    camera_id: str = "",
    tracking_id: str = "",
    gender: str = "unknown",
    frame: str = "",
    ref_id: str | None = None,
    ts_ms: int | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_type=AGE_EVENT,
        service=SERVICE,
        store_id=store_id,
        payload={
            "age_range": age_range,
            "lane": str(lane),
            "camera_id": camera_id,
            "tracking_id": str(tracking_id),
            "gender": gender.lower(),
            "frame": frame,
        },
        ref_id=ref_id or uuid.uuid4().hex,
        ts_ms=ts_ms if ts_ms is not None else int(time.time() * 1000),
    )


def make_item_verification(
    store_id: str,
    item_name: str,
    matched: bool,
    lane: str,
    camera_id: str = "",
    ref_id: str | None = None,
    ts_ms: int | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_type=ITEM_EVENT,
        service=SERVICE,
        store_id=store_id,
        payload={
            "item_name": item_name,
            "matched": bool(matched),
            "lane": str(lane),
            "camera_id": camera_id,
        },
        ref_id=ref_id or uuid.uuid4().hex,
        ts_ms=ts_ms if ts_ms is not None else int(time.time() * 1000),
    )
