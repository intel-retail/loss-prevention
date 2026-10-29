"""Start the Loss Prevention FastMCP server.

A background watcher (`jsonl_watch.py`) tails pipeline output into the durable
log while the server runs (LP_JSONL_WATCH=off disables it): non-VLM
`rs-*.jsonl` become age/loss events, VLM `vlm-results/results_*.jsonl` become
item verifications. `scripts/import_jsonl.py` remains for manual backfill and
`scripts/seed_demo.py` for demo data.
"""

from __future__ import annotations

import logging

from config import get_settings
from jsonl_watch import JsonlWatcher
from tools import mcp, record_age_estimate, record_item_verification, record_loss_event, store


def _configure_logging() -> None:
    # Scoped to the service logger so library request logs stay at their defaults.
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger = logging.getLogger("lp")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def main() -> None:
    s = get_settings()
    _configure_logging()
    if s.jsonl_watch_enabled:
        JsonlWatcher(
            store, s.results_dir, s.camera_config_path, s.lane,
            record_age_estimate, record_loss_event,
            sample_seconds=s.jsonl_sample_seconds, poll_seconds=s.jsonl_poll_seconds,
            record_item=record_item_verification,
        ).start()
    if s.transport in {"http", "streamable-http"}:
        mcp.run(transport="http", host=s.host, port=s.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
