"""Import non-VLM pipeline JSONL metadata into the LP durable log.

    python scripts/import_jsonl.py --results-dir ../results \
        --camera-config ../configs/camera_to_workload_asc_age_verification.json

Manual backfill (the server's background watcher handles live runs). Maps each
`rs-*.jsonl` file to its camera (by branch index) using the camera config and
records sampled age_estimate / loss_event entries. Idempotent: ref_ids match the
watcher's (file name + record/track), so re-imports never duplicate events.
"""

from __future__ import annotations

import argparse
import json
import os
import warnings
from glob import glob
from pathlib import Path

# Authlib installs an "always" filter while importing this warning class.
from authlib.deprecate import AuthlibDeprecationWarning

warnings.filterwarnings("ignore", category=AuthlibDeprecationWarning)

import jsonl_ingest
from tools import record_age_estimate, record_loss_event


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default=os.getenv("LP_RESULTS_DIR", "/results"))
    parser.add_argument("--camera-config", required=True, help="Path to the camera_to_workload JSON.")
    parser.add_argument("--lane", default=os.getenv("LP_LANE", "lane-1"))
    parser.add_argument(
        "--since-ms", type=int, default=None,
        help="Ignore result files modified before this Unix timestamp in milliseconds.",
    )
    parser.add_argument(
        "--sample-seconds", type=float, default=float(os.getenv("LP_IMPORT_SAMPLE_SECONDS", "1.0")),
        help="Keep one reading per camera per N stream-seconds (0 = no sampling).",
    )
    args = parser.parse_args()

    camera_config = json.loads(Path(args.camera_config).read_text(encoding="utf-8"))
    cam_map = jsonl_ingest.camera_index_map(camera_config)
    sample_ns = int(args.sample_seconds * 1_000_000_000)

    age_count = 0
    loss_count = 0
    files = sorted(glob(os.path.join(args.results_dir, "rs-*.jsonl")))
    if not files:
        print(f"No pipeline metadata found in {args.results_dir}; nothing imported.")
        return
    if args.since_ms is not None:
        files = jsonl_ingest.filter_files_since(files, args.since_ms)
        if not files:
            print(f"No new pipeline metadata found after {args.since_ms}; nothing imported.")
            return

    mapped_files = 0
    for path in files:
        branch = jsonl_ingest.branch_index_from_filename(path)
        camera = cam_map.get(branch) if branch is not None else None
        if not camera:
            continue
        mapped_files += 1
        _offset, _window, n_age, n_loss = jsonl_ingest.ingest_file(
            path, 0, None, camera, args.lane, sample_ns,
            record_age_estimate, record_loss_event,
        )
        age_count += n_age
        loss_count += n_loss

    if age_count == 0 and loss_count == 0:
        print(
            f"No matching age or loss detections found in {mapped_files} pipeline "
            f"file(s) under {args.results_dir}; check that inference produced metadata "
            "and the selected camera/workload config matches those files."
        )
        return

    print(
        f"MCP import complete: processed {age_count} age readings, {loss_count} loss events "
        f"from {mapped_files} pipeline file(s) (already-stored events are skipped)."
    )


if __name__ == "__main__":
    main()
