# Performance Testing & Benchmarking

Test your Loss Prevention and Automated Self-Checkout pipeline performance on various hardware configurations. This guide covers everything from quick performance checks to comprehensive system capacity testing.

## Quick Start (5 minutes)

**Goal**: Run a basic performance test to verify your system works correctly

### 1. Initialize Performance Tools

```bash
make update-submodules
```

### 2. Run Quick Benchmark

```bash
make benchmark-quickstart
```

**What this does:**

- Benchmarks the six workloads in the default camera configuration using the default mixed CPU/GPU/NPU workload mapping
- Runs headless (no display needed)
- Uses registry images by default (`REGISTRY=false` builds the benchmark image locally)
- Generates consolidated metrics in `benchmark/metrics.csv`

**Expected results**: You'll see FPS metrics and resource utilization for each workload.

## Understanding Performance Testing Types

### Basic Performance Testing

**Default Benchmark Command:**

```bash
make benchmark
```

**Configuration:**

- Single pipeline instance (`PIPELINE_COUNT=1`)
- Mixed CPU/GPU/NPU processing (`WORKLOAD_DIST=workload_to_pipeline.json`)
- Standard camera setup (`CAMERA_STREAM=camera_to_workload.json`)
- No visual output (`RENDER_MODE=0`)

### Environment Variables Reference

| Category         | Variable         | Description                            | Common Values                                                                                         |
| ---------------- | ---------------- | -------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **Display**      | `RENDER_MODE`    | Show/hide visual output                | `0` (headless), `1` (visual)                                                                          |
| **Performance**  | `PIPELINE_COUNT` | Number of parallel pipeline instances | `1`, `2`, `4` (higher = more stress)                                                                  |
| **Hardware**     | `WORKLOAD_DIST`  | Target processing hardware             | `workload_to_pipeline_cpu.json`, `workload_to_pipeline_gpu.json`, `workload_to_pipeline_gpu-npu.json`, `workload_to_pipeline_hetero.json` |
| **Camera Setup** | `CAMERA_STREAM`  | Camera configuration                   | `camera_to_workload.json`                                                                             |
| **Build**        | `REGISTRY`       | Use pre-built vs local images          | `true` (faster), `false` (custom builds)                                                              |

## Workload Configuration Options

### Camera Stream Configurations

**Full Workload Testing** (`camera_to_workload.json`):

| Camera | Workload                     |
| :----- | :--------------------------- |
| cam1   | items_in_basket              |
| cam2   | hidden_items                 |
| cam3   | fake_scan_detection          |
| cam4   | multi_product_identification |
| cam5   | product_switching            |
| cam6   | sweet_heartening             |

### Hardware Distribution Options

| Configuration     | File                                | Best For                                |
| :---------------- | :---------------------------------- | :-------------------------------------- |
| **CPU Only**      | `workload_to_pipeline_cpu.json`     | Testing, development environments       |
| **GPU Only**      | `workload_to_pipeline_gpu.json`     | Production, high performance            |
| **Mixed GPU/NPU** | `workload_to_pipeline_gpu-npu.json` | Assign selected workloads to GPU or NPU |
| **Heterogeneous** | `workload_to_pipeline_hetero.json`  | Maximum performance across all hardware |
| **Default Mixed** | `workload_to_pipeline.json`         | CPU/GPU/NPU distribution used by default |

## Advanced Performance Testing (15-30 minutes)

### GPU Performance Testing

```bash
make benchmark WORKLOAD_DIST=workload_to_pipeline_gpu.json CAMERA_STREAM=camera_to_workload.json
```

### Multi-Pipeline Stress Testing

```bash
# Test with 2 parallel pipelines
make PIPELINE_COUNT=2 benchmark

# High stress test with 4 pipelines
make PIPELINE_COUNT=4 benchmark
```

### Custom Hardware Configuration

```bash
# Test heterogeneous workload distribution
make benchmark WORKLOAD_DIST=workload_to_pipeline_hetero.json CAMERA_STREAM=camera_to_workload.json REGISTRY=false
```

### Automated Self-Checkout Performance

```bash
# Object detection workload
CAMERA_STREAM=camera_to_workload_asc_object_detection.json WORKLOAD_DIST=workload_to_pipeline_asc_object_detection_gpu.json make benchmark

# Age verification workload
CAMERA_STREAM=camera_to_workload_asc_age_verification.json WORKLOAD_DIST=workload_to_pipeline_asc_age_verification_gpu.json make benchmark
```

## Viewing Results

### Generate Consolidated Metrics

```bash
make consolidate-metrics
```

**Output**: `benchmark/metrics.csv` containing:

- FPS (frames per second) for each pipeline
- CPU/GPU/NPU utilization percentages
- Memory usage statistics
- Power consumption data
- Latency measurements

### View Results

```bash
cat benchmark/metrics.csv
```

## Stream Density Testing (30+ minutes)

**Goal**: Find the maximum number of parallel pipelines your system can handle while maintaining target performance.

### Basic Stream Density Test

```bash
make benchmark-stream-density
```

**Default behavior:**

- Requires every stream to reach at least 95% of its effective target FPS; by default targets come from each camera's `targetFps`, then `fps`, with a fallback of `15`.
- Uses OOM protection to prevent system crashes
- Reports maximum sustainable pipeline count

### Custom Target FPS

Set the target FPS for each camera using the `targetFps` field in the selected `camera_to_workload_*.json` file. Choose the value based on workload criticality and the source FPS.

If `targetFps` is not defined for a camera (or is not a positive value), the benchmark uses that camera's `fps` field instead. If neither field provides a positive value, it falls back to the default target FPS of `15`.

To override the camera configuration, set the `TARGET_FPS` environment variable. When supplied, `TARGET_FPS` applies the same target to every stream and takes precedence over both `targetFps` and `fps`.

In summary, the effective target FPS for each camera is resolved in this order:

1. `TARGET_FPS` environment variable, when explicitly supplied (overrides the camera configuration for every stream).
2. The camera's `targetFps` in `camera_to_workload_*.json`.
3. The camera's `fps`, used when `targetFps` is missing or not a positive value.
4. The default target FPS, `15`, when neither camera field provides a positive value.

The benchmark passes when each stream reaches at least 95% of its effective target. The resolved target FPS and its source are recorded in `stream_density.log`.

CLI examples:

```bash
# Test for different performance thresholds
make TARGET_FPS=13.5 benchmark-stream-density

# With explicit camera and workload configurations
make CAMERA_STREAM=camera_to_workload.json WORKLOAD_DIST=workload_to_pipeline_gpu.json TARGET_FPS=13.5 benchmark-stream-density
```

### Measurement interval and warmup period

`MEASUREMENT_WINDOW_SECONDS` controls how long FPS samples are collected for each density step. Its default is **100 seconds**, and values below 100 are rejected because the benchmark requires at least 100 samples per pipeline log. Each step adds a lane after one passing measurement interval, the final count is confirmed by run acceptance criterion (two consecutive passes), and a lane is only given up after two failing measurement interval in a row. Each measurement interval is evaluated independently; measurement interval are not combined into one longer measurement interval.

`INIT_DURATION` sets the warmup period, defaulting to **10 seconds**, before measurement starts. A longer warmup period lets the pipelines stabilize more, and a longer measurement interval can reduce short-term measurement noise, but both increase the total benchmark duration. The resolved warmup period is also printed in the stream-density result summary.

```sh
make benchmark-stream-density \
  INIT_DURATION=120 \
  MEASUREMENT_WINDOW_SECONDS=120
```

### Stream Density Environment Variables

| Variable                    | Description                                             | Values                            |
| :-------------------------- | :------------------------------------------------------ | :-------------------------------- |
| `TARGET_FPS`                | Override the target FPS for all streams; unset uses camera configuration | Unset by default, `13.5`, `20.0` |
| `MEASUREMENT_WINDOW_SECONDS` | Duration FPS samples are collected per density step (minimum 100 seconds) | `100` (default), `120` |
| `INIT_DURATION`             | warmup period before measurement starts                   | `10` (default), `120`, `60`       |
| `OOM_PROTECTION`            | Prevent out-of-memory crashes                           | `1` (enabled), `0` (disabled)     |
| `PASS_TOLERANCE_RATIO`      | Fraction of each target FPS required to pass            | `0.95` (default), up to `1.0`     |

> **Warning:** Setting `OOM_PROTECTION=0` may crash your system requiring a hard reboot.

Note: stream-density caches camera-target mappings using `(config_path, file_mtime)` and auto-refreshes when the camera config changes; unit tests for this behavior are in the `performance-tools` repository at `benchmark-scripts/stream_density_test.py`.

### Expected Output

```
Stream density completed: use case density <lanes> lanes, stream density <streams> streams. For the detailed report, see benchmark/stream_density.log.
```

## Visualization & Analysis

### Generate Performance Graphs

```bash
make plot-metrics
```

**Output**: `benchmark/plot_metrics.png` showing:

- CPU Usage Over Time
- NPU Utilization Over Time
- GPU Usage for each GPU device found

### Useful Maintenance Commands

```bash
make validate-all-configs    # Validate configuration files
make clean-images           # Remove dangling Docker images
make clean-containers       # Remove stopped containers
make clean-all             # Remove all unused Docker resources
```

## Custom Configuration (Advanced)

### Creating Custom Workloads

The application is highly configurable via JSON files in the `configs/` directory:

#### Camera Configuration (`camera_to_workload.json`)

```json
{
  "lane_config": {
    "cameras": [
      {
        "camera_id": "cam1",
        "fileSrc": "sample-media/video1.mp4",
        "targetFps": 12.5,
        "workloads": ["items_in_basket", "multi_product_identification"],
        "region_of_interest": {"x": 100, "y": 100, "x2": 800, "y2": 600}
      }
    ]
  }
}
```

#### Pipeline Configuration (`workload_to_pipeline.json`)

```json
{
  "workload_pipeline_map": {
    "items_in_basket": [
      {"type": "gvadetect", "model": "yolo11n", "precision": "INT8", "device": "CPU"},
      {"type": "gvaclassify", "model": "efficientnet-v2-b0", "precision": "INT8", "device": "CPU"}
    ]
  }
}
```

### To Add Custom Workloads:

1. Edit `configs/camera_to_workload.json` to add your camera and assign workloads
2. Edit `configs/workload_to_pipeline.json` to define the pipeline for your workload
3. Place your video files in `performance-tools/sample-media/` and update the `fileSrc` path
4. Run `make validate-all-configs` to verify your configuration
5. Re-run the pipeline: `make benchmark`

## Detailed Hardware Distribution (Reference)

### Heterogeneous Configuration Breakdown

The `workload_to_pipeline_hetero.json` distributes workloads across multiple processing units:

| Workload                     | Object Detection | Classification | Inference |
| :--------------------------- | :--------------- | :------------- | :-------- |
| items_in_basket              | CPU              | CPU            | -         |
| hidden_items                 | GPU              | GPU            | -         |
| fake_scan_detection          | GPU              | GPU            | -         |
| multi_product_identification | NPU              | NPU            | -         |
| product_switching            | CPU              | CPU            | -         |
| sweet_heartening             | NPU              | -              | NPU       |

### Mixed Configuration Details

The `workload_to_pipeline.json` balances workloads across available hardware:

- **CPU**: items_in_basket, multi_product_identification, sweet_heartening
- **GPU**: product_switching, hidden_items
- **NPU**: fake_scan_detection

## Project Structure (Reference)

- `configs/` — Configuration files (camera/workload mapping)
- `docker/` — Dockerfiles for containers
- `download-scripts/` — Model and video download scripts
- `src/` — Pipeline runner scripts
- `benchmark/` — Benchmark logs, consolidated metrics, and plots (default `RESULTS_DIR`)
- `Makefile` — Build automation commands

---

## Appendix: System Configuration

### Proxy Configuration (If Required)

If your organization requires proxy settings for internet access:

#### Shell Session Proxy

```bash
export http_proxy=http://<proxy-host>:<port>
export https_proxy=http://<proxy-host>:<port>
export HTTP_PROXY=http://<proxy-host>:<port>
export HTTPS_PROXY=http://<proxy-host>:<port>
export NO_PROXY=localhost,127.0.0.1,::1
```

#### System-Wide Proxy (`/etc/environment`)

```bash
sudo nano /etc/environment
# Add the following lines:
http_proxy=http://<proxy-host>:<port>
https_proxy=http://<proxy-host>:<port>
HTTP_PROXY=http://<proxy-host>:<port>
HTTPS_PROXY=http://<proxy-host>:<port>
NO_PROXY=localhost,127.0.0.1,::1
```

#### Docker Proxy Configuration
Create `/etc/systemd/system/docker.service.d/http-proxy.conf`:

```bash
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo nano /etc/systemd/system/docker.service.d/http-proxy.conf

[Service]
Environment="http_proxy=http://<proxy-host>:<port>"
Environment="https_proxy=http://<proxy-host>:<port>"
Environment="no_proxy=localhost,127.0.0.1,::1"

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart docker
```