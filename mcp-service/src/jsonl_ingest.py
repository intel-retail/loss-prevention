"""Parse non-VLM pipeline JSONL metadata (results/rs-*.jsonl) into MCP events.

Non-VLM workloads publish detections/age via `gvametapublish file-format=json-lines`
(one file per camera branch). This module holds the pure, incremental parsing
logic shared by the background watcher (`jsonl_watch.py`) and the manual
`scripts/import_jsonl.py` backfill, so both produce identical ref_ids. RabbitMQ is
only used by the VLM workload, so it is not involved here.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from events import SCENARIOS

# Upper-exclusive bucket ceilings; ages at/above the last ceiling fall in "60+".
_AGE_BUCKETS = ((18, "0-18"), (25, "18-25"), (35, "25-35"), (45, "35-45"), (60, "45-60"))


def bucket_age(age: int) -> str:
    for ceiling, label in _AGE_BUCKETS:
        if age < ceiling:
            return label
    return "60+"


def camera_index_map(camera_config: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Map a camera's positional index to its id and workloads."""
    cameras = camera_config.get("lane_config", {}).get("cameras", [])
    return {
        index: {"camera_id": cam.get("camera_id", f"cam{index + 1}"),
                "workloads": list(cam.get("workloads", []))}
        for index, cam in enumerate(cameras)
    }


def branch_index_from_filename(path: str | Path) -> int | None:
    """rs-{branch+1}_{idx+1}__{counter}_{ts}.jsonl -> zero-based branch index."""
    match = re.match(r"rs-(\d+)_", Path(path).name)
    return int(match.group(1)) - 1 if match else None


def filter_files_since(paths: list[str], since_ms: int | None) -> list[str]:
    """Keep files whose modification time is at or after the optional run marker."""
    if since_ms is None:
        return paths
    return [path for path in paths if int(os.path.getmtime(path) * 1000) >= since_ms]


def read_complete_lines(path: str | Path, offset: int) -> tuple[list[str], int]:
    """Read newline-terminated lines after `offset`; a trailing partial line is left for later.

    Returns (lines, new_offset). The pipeline appends while we read, so only data
    up to the last newline is consumed.
    """
    with open(path, "rb") as handle:
        handle.seek(offset)
        data = handle.read()
    end = data.rfind(b"\n")
    if end == -1:
        return [], offset
    return data[: end + 1].decode("utf-8", errors="replace").splitlines(), offset + end + 1


def parse_record(line: str) -> tuple[int, list[dict[str, Any]]] | None:
    """Parse one JSON-lines record into (stream_timestamp_ns, objects)."""
    line = line.strip()
    if not line:
        return None
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(record, dict):
        return None
    try:
        timestamp = int(record.get("timestamp", 0))
    except (TypeError, ValueError):
        return None
    objects = record.get("objects", [])
    return timestamp, objects if isinstance(objects, list) else []


def camera_scenario(camera: dict[str, Any]) -> str | None:
    """The loss scenario this camera runs, if any of its workloads is a known scenario."""
    return next((w for w in camera.get("workloads", []) if w in SCENARIOS), None)


def events_from_lines(
    stem: str,
    lines: list[str],
    camera: dict[str, Any],
    sample_ns: int,
    last_window: int | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int | None]:
    """Convert JSONL lines into age/loss event kwargs, sampling one record per window.

    gvatrack assigns a fresh id per detection here, so sampling by stream time (not
    per-track dedup) is what bounds volume. `last_window` carries the sampling state
    across incremental reads; ref_ids are deterministic so re-reads are idempotent.
    """
    scenario = camera_scenario(camera)
    age_events: list[dict[str, Any]] = []
    loss_events: list[dict[str, Any]] = []
    loss_tracks: set[str] = set()
    for line in lines:
        parsed = parse_record(line)
        if parsed is None:
            continue
        timestamp, objects = parsed
        if sample_ns > 0:
            window = timestamp // sample_ns
            if last_window is not None and window <= last_window:
                continue
            last_window = window
        for index, obj in enumerate(objects):
            if not isinstance(obj, dict):
                continue
            tracking_id = str(obj.get("id", ""))
            if "age" in obj:
                try:
                    age = int(obj["age"]["label"])
                except (KeyError, TypeError, ValueError):
                    age = None
                if age is not None:
                    age_events.append({
                        "age_range": bucket_age(age),
                        "gender": str((obj.get("gender") or {}).get("label", "unknown")).lower(),
                        "tracking_id": tracking_id,
                        "ref_id": f"{stem}-age-{timestamp}-{index}",
                    })
            if scenario and obj.get("id") is not None and tracking_id not in loss_tracks:
                loss_tracks.add(tracking_id)
                loss_events.append({
                    "scenario": scenario,
                    "tracking_id": tracking_id,
                    "ref_id": f"{stem}-loss-{scenario}-{tracking_id}",
                })
    return age_events, loss_events, last_window


def ingest_file(
    path: str | Path,
    offset: int,
    last_window: int | None,
    camera: dict[str, Any],
    lane: str,
    sample_ns: int,
    record_age: Callable[..., Any],
    record_loss: Callable[..., Any],
) -> tuple[int, int | None, int, int]:
    """Record events for new complete lines in `path`.

    Returns (new_offset, last_window, age_count, loss_count). A file that shrank
    (truncated/replaced) is re-read from the start; ref_ids keep that idempotent.
    """
    if os.path.getsize(path) < offset:
        offset, last_window = 0, None
    lines, new_offset = read_complete_lines(path, offset)
    if not lines:
        return new_offset, last_window, 0, 0
    age_events, loss_events, last_window = events_from_lines(
        Path(path).stem, lines, camera, sample_ns, last_window
    )
    ts_ms = int(os.path.getmtime(path) * 1000)
    camera_id = camera["camera_id"]
    for event in age_events:
        record_age(event["age_range"], lane, camera_id, tracking_id=event["tracking_id"],
                   gender=event["gender"], ref_id=event["ref_id"], ts_ms=ts_ms)
    for event in loss_events:
        record_loss(event["scenario"], lane, camera_id, tracking_id=event["tracking_id"],
                    ref_id=event["ref_id"], ts_ms=ts_ms)
    return new_offset, last_window, len(age_events), len(loss_events)


def vlm_items_from_results(lines: list[str]) -> list[dict[str, Any]] | None:
    """Final per-item verdicts from a VLM results file, or None until the run finishes.

    The handler appends `od_results`, `vlm_results`, then `agent_results`; a run is
    complete once `agent_results` exists. Agent verdicts win; VLM items the agent
    dropped (e.g. a failed agent call) fall back to their VLM verdict.
    """
    sections: dict[str, list] = {}
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            for key in ("vlm_results", "agent_results"):
                if isinstance(record.get(key), list):
                    sections[key] = record[key]
    if "agent_results" not in sections:
        return None
    items: dict[str, bool] = {}
    for key in ("vlm_results", "agent_results"):
        for entry in sections.get(key, []):
            if isinstance(entry, dict) and str(entry.get("item_name", "")).strip():
                items[str(entry["item_name"]).strip()] = bool(entry.get("match"))
    return [{"item_name": name, "matched": matched} for name, matched in items.items()]


def ingest_vlm_results(
    path: str | Path,
    camera_id: str,
    lane: str,
    record_item: Callable[..., Any],
) -> int | None:
    """Record one item_verification per item; returns the count, or None if not finished."""
    lines, _ = read_complete_lines(path, 0)
    items = vlm_items_from_results(lines)
    if items is None:
        return None
    stem = Path(path).stem
    ts_ms = int(os.path.getmtime(path) * 1000)
    for item in items:
        record_item(item["item_name"], item["matched"], lane, camera_id,
                    ref_id=f"{stem}-item-{item['item_name']}", ts_ms=ts_ms)
    return len(items)
