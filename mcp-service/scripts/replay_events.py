"""Replay logged Loss Prevention events, optionally delivering to the hub."""

from __future__ import annotations

import argparse
import json
import time

from config import get_settings
from delivery import push_event_to_hub
from tools import store


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-seq", type=int, default=0, help="Resume after this stored sequence number.")
    parser.add_argument("--event-type", help="Replay only this event type (loss_event | age_estimate).")
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Playback speed multiplier; 1 follows original event timing, 0 runs immediately.",
    )
    parser.add_argument(
        "--deliver",
        action="store_true",
        help="POST matching standard event envelopes to the configured event hub.",
    )
    args = parser.parse_args()
    if args.from_seq < 0 or args.speed < 0:
        parser.error("--from-seq and --speed must be non-negative")

    settings = get_settings()
    previous_ts: int | None = None
    replayed = 0
    failures = 0
    for event in store.replay(from_seq=args.from_seq):
        if args.event_type and event.event_type != args.event_type:
            continue
        if args.speed > 0 and previous_ts is not None and event.ts_ms > previous_ts:
            time.sleep((event.ts_ms - previous_ts) / 1000 / args.speed)
        previous_ts = event.ts_ms
        replayed += 1

        if args.deliver:
            delivered = push_event_to_hub(settings.event_hub_url, event)
            failures += not delivered
            print(json.dumps({"seq_replay_index": replayed, "ref_id": event.ref_id, "delivered": delivered}))
        else:
            print(event.to_json())

    print(f"replayed={replayed} delivery_failures={failures}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
