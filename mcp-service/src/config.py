"""Env-driven settings for the Loss Prevention MCP service."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

# Persistent by default so a separate seed/replay process and the running MCP
# server share the same durable log (an in-memory log would isolate them).
_DEFAULT_LOG_PATH = str(Path(__file__).resolve().parents[1] / "data" / "lp_log.sqlite")


@dataclass(frozen=True)
class Settings:
    store_id: str
    transport: str  # stdio | sse | streamable-http
    host: str
    port: int
    log_path: str
    event_hub_url: str | None
    event_delivery_enabled: bool
    event_hub_min_severity: str
    lane_config_path: str
    use_case: str
    store_timezone: str
    results_dir: str = "/results"
    camera_config_path: str = "/configs/camera_to_workload.json"
    lane: str = "lane-1"
    jsonl_watch_enabled: bool = True
    jsonl_poll_seconds: float = 2.0
    jsonl_sample_seconds: float = 1.0


def configured_lanes(path: str) -> list[str]:
    """Read known lane ids from an optional lane config; empty when absent."""
    config_path = Path(path)
    if not config_path.is_file():
        return []
    data = json.loads(config_path.read_text(encoding="utf-8"))
    lanes = data.get("lanes", data.get("lane_config", {}).get("lanes", []))
    if isinstance(lanes, dict):
        return sorted(str(lane) for lane in lanes if lane)
    out: list[str] = []
    for lane in lanes if isinstance(lanes, list) else []:
        if isinstance(lane, str):
            out.append(lane)
        elif isinstance(lane, dict) and lane.get("id"):
            out.append(str(lane["id"]))
    return sorted(out)


def get_settings() -> Settings:
    log_path = os.getenv("LP_LOG_PATH", _DEFAULT_LOG_PATH)
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    return Settings(
        store_id=os.getenv("STORE_ID", "store_001"),
        transport=os.getenv("MCP_TRANSPORT", "stdio"),
        host=os.getenv("MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("MCP_PORT", "9100")),
        log_path=log_path,
        event_hub_url=os.getenv("LP_EVENT_HUB_URL"),
        # "off" is the clean-benchmark setting: no outbound delivery at all.
        event_delivery_enabled=os.getenv("LP_EVENT_DELIVERY", "on").lower() != "off",
        event_hub_min_severity=os.getenv("LP_EVENT_HUB_MIN_SEVERITY", "high").lower(),
        lane_config_path=os.getenv("LP_LANE_CONFIG_PATH", "/app/lane_config.json"),
        use_case=os.getenv("USE_CASE", "retail"),
        store_timezone=os.getenv("LP_TIMEZONE", "Asia/Kolkata"),
        results_dir=os.getenv("LP_RESULTS_DIR", "/results"),
        camera_config_path=os.getenv("LP_CAMERA_CONFIG", "/configs/camera_to_workload.json"),
        lane=os.getenv("LP_LANE", "lane-1"),
        jsonl_watch_enabled=os.getenv("LP_JSONL_WATCH", "on").lower() != "off",
        jsonl_poll_seconds=float(os.getenv("LP_JSONL_POLL_SECONDS", "2")),
        jsonl_sample_seconds=float(os.getenv("LP_IMPORT_SAMPLE_SECONDS", "1.0")),
    )
