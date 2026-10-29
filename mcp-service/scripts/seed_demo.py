"""Seed demo loss + age events into the Loss Prevention durable log.

Run once so the read tools (Get_loss_history, Get_age_range_counts,
Get_loss_event_count, Get_lanes) return sample data during a local demo:

    .venv/bin/python scripts/seed_demo.py

Writes to the same persistent log the running MCP server reads (see config.py).
Re-runs are idempotent because each event carries a stable ref_id.
"""

from __future__ import annotations

import queries
from tools import record_age_estimate, record_loss_event, store

_LOSS = [
    {"scenario": "hidden_items", "lane": "lane-1", "camera_id": "cam2",
     "severity": "high", "tracking_id": "101", "ref_id": "seed-loss-1",
     "frame": "s3://lp-frames/lane-1/seed-loss-1.jpg",
     "description": "Item concealed below the basket at lane-1"},
    {"scenario": "fake_scan_detection", "lane": "lane-1", "camera_id": "cam3",
     "severity": "critical", "tracking_id": "102", "ref_id": "seed-loss-2",
     "frame": "s3://lp-frames/lane-1/seed-loss-2.jpg",
     "description": "Barcode not registered during scan motion"},
    {"scenario": "product_switching", "lane": "lane-2", "camera_id": "cam5",
     "severity": "high", "tracking_id": "201", "ref_id": "seed-loss-3",
     "frame": "s3://lp-frames/lane-2/seed-loss-3.jpg",
     "description": "Label swap suspected between two products"},
    {"scenario": "sweethearting", "lane": "lane-2", "camera_id": "cam6",
     "severity": "medium", "tracking_id": "202", "ref_id": "seed-loss-4",
     "frame": "s3://lp-frames/lane-2/seed-loss-4.jpg",
     "description": "Item passed without scan near operator"},
]

_AGE = [
    {"age_range": "18-25", "lane": "lane-1", "camera_id": "cam1", "gender": "female",
     "tracking_id": "301", "ref_id": "seed-age-1", "frame": "s3://lp-frames/lane-1/seed-age-1.jpg"},
    {"age_range": "25-35", "lane": "lane-1", "camera_id": "cam1", "gender": "male",
     "tracking_id": "302", "ref_id": "seed-age-2", "frame": "s3://lp-frames/lane-1/seed-age-2.jpg"},
    {"age_range": "0-18", "lane": "lane-2", "camera_id": "cam1", "gender": "male",
     "tracking_id": "303", "ref_id": "seed-age-3", "frame": "s3://lp-frames/lane-2/seed-age-3.jpg"},
    {"age_range": "18-25", "lane": "lane-2", "camera_id": "cam1", "gender": "female",
     "tracking_id": "304", "ref_id": "seed-age-4", "frame": "s3://lp-frames/lane-2/seed-age-4.jpg"},
]


def main() -> None:
    for event in _LOSS:
        record_loss_event(**event)
    for event in _AGE:
        record_age_estimate(**event)
    print(
        f"seeded {len(queries.loss_history(store))} loss events, "
        f"{sum(c['detections'] for c in queries.age_range_counts(store))} age estimates "
        f"across lanes {queries.lanes(store)}"
    )


if __name__ == "__main__":
    main()
