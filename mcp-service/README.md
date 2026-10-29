# Loss Prevention MCP Service

A sensor MCP service that exposes self-checkout **loss** scenarios and
**age-range** classification from the Loss Prevention pipeline. The age mix feeds
the signage-board decision; the loss history feeds operator review.

- Service owns its SQLite event log, hub delivery, and (later) live ingestion.
- Sensor contract: `describe` + read tools only. **No subscribe/callback, no
  action tools.**

## 1. Events

Three event types share one durable, ordered log.

| Event | Payload |
|---|---|
| `loss_event` | `scenario`, `lane`, `camera_id`, `severity`, `tracking_id`, `frame`, `description` |
| `age_estimate` | `age_range`, `lane`, `camera_id`, `tracking_id`, `gender`, `frame` |
| `item_verification` | `item_name`, `matched` (in store inventory), `lane`, `camera_id` (VLM workload only) |

`scenario` is one of: `items_in_basket`, `hidden_items`, `fake_scan_detection`,
`multi_product_identification`, `product_switching`, `sweethearting`.

Every event is wrapped in the standard envelope:

```python
EventEnvelope(event_type, service="loss_prevention", store_id, payload,
              ref_id, ts_ms, schema_version=1)
```

### Durability and delivery
- **Log first.** `record_loss_event` / `record_age_estimate` persist to the
  service's SQLite log *before* any delivery — nothing is dropped, and the full
  run is replayable.
- **Idempotent.** `ref_id` deduplicates redelivered events (stored once).
- **Hub fan-out.** Committed loss events at/above `LP_EVENT_HUB_MIN_SEVERITY`
  are POSTed to `LP_EVENT_HUB_URL` in the agent-inbox shape (`event_id`,
  `event_type`, `occurred_at`, `data`). `store_id` stays inside `data`.
- **Replay.** `scripts/replay_events.py` streams the ordered log, optionally
  delivering (`--deliver`) at original timing (`--speed`).

## 2. MCP tools

| Tool | Params | Returns |
|---|---|---|
| `describe` | — | service info, event-type schemas, read tools, `act_tools: []`, `subscribe: disabled` |
| `Get_loss_history` | `scenario?`, `lane?`, `start_time?`, `end_time?`, `limit?` | newest matching loss events |
| `Get_age_range_counts` | `start_time?`, `end_time?`, `lane?` | sampled detections grouped by age range (not unique people) |
| `Get_loss_event_count` | `scenario?`, `lane?`, `start_time?`, `end_time?` | compact count |
| `Get_lanes` | — | lanes with recorded loss activity |
| `Get_item_verifications` | `matched?`, `lane?`, `start_time?`, `end_time?`, `limit?` | VLM-identified items and whether each is in inventory |
| `Get_item_verification_summary` | `lane?`, `start_time?`, `end_time?` | matched / unmatched counts + unmatched item names |

Time values are ISO-8601; naive values use `LP_TIMEZONE`.

## 3. Quick start (DX walkthrough)

```bash
cd mcp-service
python3 -m venv .venv
.venv/bin/pip install -e .

# Optional: preload demo history (fake events; don't mix with real pipeline runs):
.venv/bin/python scripts/seed_demo.py

# Run the MCP server (stdio by default; HTTP for remote agents):
.venv/bin/lp-mcp
.venv/bin/lp-mcp  # MCP_TRANSPORT=streamable-http MCP_PORT=9100 for HTTP
```

Run the tests:

```bash
.venv/bin/python -m pytest -q
```

## 4. One command up (Docker)

The MCP service (`lp-mcp-service`) lives in the main `src/docker-compose.yml`
stack under the `mcp` profile and shares that stack's network and result
directory. From the repository root:

```bash
make run-lp CAMERA_STREAM=camera_to_workload_asc_age_verification.json \
  WORKLOAD_DIST=workload_to_pipeline_asc_age_verification_gpu.json
```

`run-lp` enables the profile, so one `docker compose up` starts the MCP after the
pipeline; `make down-lp` stops it with the rest of the stack. `make benchmark` and
`make benchmark-stream-density` run the file without the profile, so the MCP
never adds load to measurements and its log survives their `down --volumes`. There is
no wait or import step: a background watcher inside the MCP service streams
results written after it starts into the log every few seconds while the
pipeline runs (see section 7). VLM runs are ingested from their results file
once each run finishes.


## 5. Configuration

| Var | Default | Meaning |
|---|---|---|
| `STORE_ID` | `store_001` | Store identity stamped on every event. |
| `MCP_TRANSPORT` | `stdio` | `stdio` \| `sse` \| `streamable-http`. |
| `MCP_HOST` / `MCP_PORT` | `0.0.0.0` / `9100` | Bind host/port for HTTP transports. |
| `LP_LOG_PATH` | `data/lp_log.sqlite` | Durable log path. |
| `LP_EVENT_HUB_URL` | — | Agent inbox URL for fan-out. |
| `LP_EVENT_DELIVERY` | `on` | `off` disables fan-out (clean benchmarks). |
| `LP_EVENT_HUB_MIN_SEVERITY` | `high` | Minimum loss severity delivered to the hub. |
| `LP_LANE_CONFIG_PATH` | `/app/lane_config.json` | Optional known-lane list. |
| `LP_TIMEZONE` | `Asia/Kolkata` | Timezone for naive ISO datetimes. |
| `SEED_DEMO` | `false` | Preload fake demo history at container start (demo/benchmark only). |
| `LP_JSONL_WATCH` | `on` | `off` disables the background JSONL watcher. |
| `LP_RESULTS_DIR` | `/results` | Directory watched for `rs-*.jsonl`. |
| `LP_CAMERA_CONFIG` | `/configs/camera_to_workload.json` | Camera config mapping files to cameras (Compose sets it from `CAMERA_STREAM`). |
| `LP_LANE` | `lane-1` | Lane stamped on ingested events. |
| `LP_JSONL_POLL_SECONDS` | `2` | Watcher poll interval. |
| `LP_IMPORT_SAMPLE_SECONDS` | `1.0` | Keep one record per camera per N stream-seconds (`0` = all). |

## 6. Coding-agent walkthrough

To add a new read tool or event field:

1. Extend the schema in `src/events.py` (`LOSS_SCHEMA` / `AGE_SCHEMA`) and the
   matching builder; keep `ref_id` idempotency.
2. Add query logic in `src/queries.py` over the durable log only.
3. Expose a `@mcp.tool(annotations={"readOnlyHint": True})` in `src/tools.py`;
   never add subscribe or action tools to this sensor service.
4. Add a test in `tests/` and a row to the tool table above.

## 7. Ingestion from the pipeline

How the loss-prevention pipeline emits data depends on the workload:

- **Non-VLM workloads** (age verification, object detection/classification, loss
  scenarios) publish via `gvametapublish file-format=json-lines` to per-camera
  files `results/rs-*.jsonl`. This is the primary ingestion source.
- **VLM workload** (`lp_vlm`) refines generic detections with the VLM and checks
  each item against the store inventory. When a run finishes, the handler's
  `results/vlm-results/results_*.jsonl` (with `od_results`, `vlm_results`,
  `agent_results`) becomes one `item_verification` per item: the agent verdict
  wins, falling back to the VLM verdict. Ingestion is per finished run, not live.

### Live ingestion (non-VLM)
`src/jsonl_watch.py` runs as a background thread in the MCP server. Every
`LP_JSONL_POLL_SECONDS` it:
- reads only newline-terminated records past a per-file byte offset (a partial
  line still being written is left for the next poll);
- maps each `rs-*.jsonl` to its camera (by branch index) using the camera config;
- samples one record per camera per `LP_IMPORT_SAMPLE_SECONDS` of stream time
  (tracker ids are not stable across frames, so sampling bounds volume);
- records an `age_estimate` per sampled person (`age.label` bucketed into
  `0-18, 18-25, 25-35, 35-45, 45-60, 60+`), and one `loss_event` per track for a
  camera whose workload name is a known scenario.

Offsets and sampling state are persisted in the same SQLite file, so a restart
resumes where it stopped without duplicates. A file is picked up only if it was
modified after the watcher started, so results from earlier runs are never
re-attributed to the current camera config (`make mcp-import` backfills them).

### Manual backfill
`scripts/import_jsonl.py` reuses the same parsing, so its ref_ids match the
watcher's and re-imports never duplicate events. Use it to load results from
earlier runs (the MCP container mounts `results/` and `configs/`):

```bash
make mcp-import CAMERA_STREAM=camera_to_workload_asc_age_verification.json
```
