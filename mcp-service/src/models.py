"""Typed structures returned by the Loss Prevention tools (structured output)."""

from __future__ import annotations

from typing import TypedDict


class LossEvent(TypedDict):
    """One self-checkout loss scenario, flattened for the agent."""

    ref_id: str
    ts_ms: int
    timestamp: str
    event_type: str
    scenario: str
    lane: str
    camera_id: str
    severity: str
    tracking_id: str
    frame: str
    description: str


class AgeEstimate(TypedDict):
    """One age-range classification, flattened for the agent."""

    ref_id: str
    ts_ms: int
    timestamp: str
    event_type: str
    age_range: str
    lane: str
    camera_id: str
    tracking_id: str
    gender: str
    frame: str


class AgeRangeCount(TypedDict):
    """Number of sampled age detections (not unique people) for one age range."""

    age_range: str
    detections: int


class ItemVerification(TypedDict):
    """One VLM-identified item and whether it is in the store inventory."""

    ref_id: str
    ts_ms: int
    timestamp: str
    event_type: str
    item_name: str
    matched: bool
    lane: str
    camera_id: str


class ItemVerificationSummary(TypedDict):
    """Matched vs unmatched item counts over the queried period."""

    total: int
    matched: int
    unmatched: int
    unmatched_items: list[str]
