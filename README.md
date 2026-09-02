# Loss Prevention — transparent benchmarking for real-world retail AI on Intel® hardware
> Part of the **Intel® Retail AI Suite**: open-source, runnable AI workloads that let you measure real performance on Intel hardware and decide whether it fits your deployment.

> [!WARNING]
>  The **main** branch  is work-in-progress and not guaranteed stable. For the latest stable release :point_right: [Releases](https://github.com/intel-retail/loss-prevention/releases)

>[!IMPORTANT]
>**Migrating from Automated Self-Checkout (ASC)?** The `automated-self-checkout` repo is **End-of-Life (deprecated by August 2026)** — its pipelines and all future updates, issues, and contributions moved here. The ASC use cases (object detection, object-detection + classification, age verification) run in this repo: see [Use cases](#1--foundation--automated-self-checkout-basic-sco-migrated-from-the-eol-asc-repo) and [Walkthroughs](#1--foundation--automated-self-checkout-basic-sco-migrated-from-the-eol-asc-repo).

# Table of Contents
1. [Why this exists / what it is](#why-this-exists--what-it-is)
2. [Use cases in this repo](#use-cases-in-this-repo)
3. [What to expect when you run it](#what-to-expect-when-you-run-it)
4. [How to think about performance & stream density](#how-to-think-about-performance--stream-density)
5. [Prerequisites](#prerequisites)
6. [Quick start](#quickstart)
7. [Per-use-case walkthroughs](#per-use-case-walkthroughs) (run · benchmark · density)
8. [Advanced usage](#advanced-usage)
9. [Architecture, services & project layout](#architecture--services)
10. [Getting help](#getting-help)

# Why this exists / what it is

We build these workloads to demonstrate real-world retail scenarios and to **measure their performance on different Intel hardware platforms.** They’re released as open source so partners can read the code and the metrics instrumentation, **run the benchmarks themselves to reproduce the numbers we publish,** or swap in their own models, pipelines, and business logic and see exactly how performance changes. These are **open-source reference pipelines built on Intel® hardware and software, GStreamer, and OpenVINO™** — running scalable, real-time object detection and classification at the edge.

It answers one question: **“How do I know if Intel’s hardware will actually perform for *my* workload?”** — so it’s a **hardware-sizing tool**, not a production starting point.
<table>
  <tr>
    <td><b>Transparent</b></td>
    <td>Full source + metrics instrumentation. <i>A window into how we did it — not a starting point for your production code.</i></td>
  </tr>
   <tr>
    <td><b>Representative</b></td>
    <td>Off-the-shelf, non-fine-tuned models; sample datasets included; easy to customize.</td>
  </tr>
  <tr>
    <td><b>Measurable</b></td>
    <td>Latency · FPS · utilization (CPU/GPU/NPU) · power · <b>stream density.</b></td>
  </tr>
</table>

The conversation we want: *“Here’s a real workload. Run it. Compare it. Let’s talk about what you’re actually seeing”* — not a TOPS spec sheet.

## Use cases in this repo

The workloads **build on each other** — start with a basic self-checkout, add a concurrent age-verification pipeline for a real-world lane, then the loss-prevention scenarios themselves, and finally an LVLM enhancement. Each layer adds compute, so the progression is also a **hardware-sizing** story (see use-case density). Each is selected by a `CAMERA_STREAM + WORKLOAD_DIST` config pair in `configs/`, with CPU / iGPU / NPU / hetero variants where available ([matrix](#per-use-case-walkthroughs)).

### 1 · Foundation — Automated Self-Checkout (basic SCO) *migrated from the EOL ASC repo)*

The **simplest workload, and the base everything else builds on:** a self-checkout vision pipeline that identifies products as they’re scanned. - **Object Detection** — detect/identify scanned products (`asc_object_detection`). - **Object Detection + Classification** — richer item ID: detect *and* classify, e.g. YOLO11n + EfficientNet-B0 (`asc_object_detection_classification`).

*Business takeaway*: the entry point — can this Intel box run a basic self-checkout lane at the frame rate it needs? Everything below adds load on top of this.

### 2 · + Age Verification (a real-world lane: parallel pipelines)
Add a **second, customer-facing pipeline** so the *same lane* can clear **age-restricted purchases** (alcohol, tobacco) without a staff override — a realistic shopping lane now runs **multiple pipelines concurrently**. A prebuilt config ships for exactly this: `asc_hetero` runs object detection, classification, **age prediction** and face detection across four cameras, deliberately spread over the **iGPU and NPU** — a full lane’s worth of pipelines distributed across the box’s accelerators (see the [walkthrough](#per-use-case-walkthroughs)). This is the **multi-pipeline-per-lane** step, and the reason to run the **benchmark + density** tests here is to see how that concurrency — and the iGPU/NPU split — drives hardware sizing.

*Business takeaway*: shows whether a box can run a **complete lane** — scanning plus the age-verification pipeline for unattended alcohol/tobacco sales — at the frame rates the lane requires.

### 3 · + Loss Prevention scenarios (the core)
Now layer the **actual loss-prevention scenarios** on top. *As a retail operator, I want to detect common loss scenarios at the lane so that I can reduce shrink without adding staff.* The default workload models a single lane as **six cameras**, each running a scenario detector:

| Camera | Scenario detector | Camera | Scenario detector |
|--------|-------------------|--------|-------------------|
| cam1   | Items-in-Basket   | cam4   | Multi-Product Identification |
| cam2   | Hidden Items      | cam5   | Product Switching |
| cam3   | Fake-Scan Detection     | cam6   | Sweethearting |

Run with `make run-lp`. (*This 6-camera lane is the concrete example of use-case density.*)

### 4 · + LVLM enhancement (GenAI at the edge) *(epic #62)*
Push item-recognition accuracy beyond traditional CV with a **local Large Vision-Language Model**, invoked by an agent *only when CV is too generic or uncertain* — no custom training (`vlm`). E.g. “bottle” → “Heinz Ketchup 32 oz”, seasonal/regional packaging, produce varieties, partially obscured or bulk-bagged items, age-restricted variants with changed packaging.

*Business takeaway*: fewer false positives (less customer friction, fewer staff interventions), better real-loss capture, and adaptability to new/seasonal/regional products **without a retraining cycle.** It’s the suite’s **GenAI-at-the-edge** workload — surfacing the metrics that matter for LLM/LVLM sizing (**TTFT, token throughput**, CPU/GPU/NPU utilization). Runs entirely locally, no cloud dependency.


## Scope & related repositories
  This repo covers loss prevention **at the self-checkout / point of sale** — built on the Automated Self-Checkout foundation above. **Store-wide** loss prevention is a   separate effort in the Intel Retail AI Suite: - **Store-wide** loss prevention — suspicious-activity / behavioral analysis, person-of-interest re-identification &       alerting → [`intel-retail/storewide-loss-prevention.`](https://github.com/intel-retail/storewide-loss-prevention) ⚙️ *(confirm scope split with BU)* - Other suite      use cases: [Order Accuracy](https://github.com/intel-retail/order-accuracy) · [Voice-Enabled Interactions](https://github.com/intel-retail/voice-enabled-interactions) · [Digital Signage](https://github.com/intel-retail/digital-signage).

> Each use case in *this* repo is selected by a `CAMERA_STREAM` + `WORKLOAD_DIST` config pair (`configs/`). Device variants — **CPU / iGPU / NPU / hetero** — vary by use case; see the [matrix](#per-use-case-walkthroughs).

## What to expect when you run it
- **Visual mode** (`RENDER_MODE=1 DISPLAY=:0`) opens a video window with detection overlays/alerts; the pipeline runs until the video completes. **Headless mode** runs the same pipeline for servers and automated benchmarking.
- These are **off-the-shelf, non-fine-tuned models** — *expected* misclassifications under real-world conditions are part of an authentic evaluation, not defects to hide. The goal is a faithful performance picture, not a flawless demo.
- For a 15 fps source, a healthy stream holds **~15 fps per stream**; throughput, latency, and utilization vary by platform and configuration (see §4).
- Output files (visual + headless): `results/pipeline_stream*.log` (per-stream FPS) and `results/gst-launch_*.log` (full GStreamer output). First run downloads videos, models, and images, so it takes a while.

## How to think about performance & stream density
The metrics that matter: **FPS, end-to-end latency, CPU/GPU/NPU utilization, power, and stream density** (for GenAI/LVLM use cases also **TTFT** and **token throughput**).

- **Stream density = the most concurrent streams a box sustains at a target FPS.** Because an LP lane is **multi-camera** (six cameras at potentially different frame-rate needs), density is best read as **use-case instances**f — “how many shopping lanes with this use case running per box” — judging **each camera against its own FPS target** (use-case density, not a raw stream count).
- **Reading the result:** a stream cannot sustain more than its source FPS — any per-stream reading **above** the source rate is a measurement artifact (catch-up burst), not real throughput.
- **How we measure it:** we ramp the number of streams, let each step settle, then read the sustained per-stream FPS against the target to find the most streams that hold it. This method has **known limitations** (a short measurement window can misread under noise) and we’re **actively improving it** toward a more robust steady-state measurement. ⚙️ *engineering: align on the final method.*

## Prerequisites

- Ubuntu 24.04 or newer (Linux recommended), Desktop edition (or Server + GUI).
- [Docker](https://docs.docker.com/engine/install/)
- [Make](https://www.gnu.org/software/make/) (`sudo apt install make`)
- **Python 3** (`sudo apt install python3`) - required for video download and validation scripts
- Intel hardware (CPU, iGPU, dGPU, NPU) + drivers:
    - [Intel GPU drivers](https://dgpu-docs.intel.com/driver/client/overview.html)
    - [NPU](https://dlstreamer.github.io/dev_guide/advanced_install/advanced_install_guide_prerequisites.html#prerequisite-2-install-intel-npu-drivers)
- 32 GB RAM . 300 GB Storage
- Corporate proxy / optional RTSP config:
    ```sh
    # HTTP/HTTPS Proxy settings
    export HTTP_PROXY=<HTTP PROXY>
    export HTTPS_PROXY=<HTTPS PROXY>
    export NO_PROXY=localhost,127.0.0.1,rabbitmq,minio-service,rtsp-streamer
    # Optional RTSP Configuration (defaults shown)
    export RTSP_STREAM_HOST=rtsp-streamer  # Hostname of RTSP server
    export RTSP_STREAM_PORT=8554           # RTSP port
    export RTSP_MEDIA_DIR=../performance-tools/sample-media  # Video source directory
    export STREAM_LOOP=false               # Set to 'true' to loop video streams indefinitely
    ```
## QuickStart
```sh
git clone -b <release-or-tag> --single-branch https://github.com/intel-retail/loss-prevention  # e.g. v4.0.0
cd loss-prevention
RENDER_MODE=1 DISPLAY=:0 make run-lp      # visual: see detections live (recommended first run)
make run-lp                               # headless
make down-lp                              # stop the application
```

First run downloads videos, models, and images (several minutes). By default `make run-lp` pulls **pre-built images,** runs **headless**, and uses the **Loss Prevention (CPU)** workload — add `REGISTRY=false` to build images locally instead (see [Advanced](#advanced-usage)).

## Per-use-case walkthroughs
Each use case supports three actions — **run** it, **benchmark** a fixed load, and measure **stream density** — listed below in the same order they’re introduced above. The device target is selected by the `WORKLOAD_DIST` config, but **not every use case ships every device variant** — check the matrix below before swapping a suffix. ⚙️ *Commands below extend today’s run-only examples to benchmark + density; engineering to validate exact flags/targets.*

| Use case | `WORKLOAD_DIST` variants available |
|---|---|
| ASC — object detection | `_cpu` · `_gpu` · `_npu` |
| ASC — object detection + classification | `_cpu` · `_gpu` · `_npu` · `_hetero` |
| ASC — age verification | `_cpu` · `_gpu` · `_npu` · `_hetero` |
| ASC — combined lane (`asc_hetero`) | none — single `workload_to_pipeline_asc_hetero.json` |
| Loss Prevention (core, 6-camera) | `_cpu` · `_gpu` · `_gpu-npu` · `_hetero` (no `_npu`) |
| LVLM-enhanced | none — single `workload_to_pipeline_vlm.json`; devices are set inside the JSON (`device`, `vlm_device`) |

Run `ls configs/workload_to_pipeline_*` to confirm what your checkout provides. Passing a variant that doesn't exist fails fast — `make run-lp` validates the pair first and reports `Configuration file not found: configs/<name>.json`.

> **View results for any benchmark/density run:** `make consolidate-metrics` → `cat benchmark/metrics.csv,` and `make plot-metrics `→ utilization chart. *(Docs elsewhere say* `make consolidate/make plot;` *the repo targets are* `consolidate-metrics/plot-metrics` — ⚙️ *to reconcile.*)
>For Advanced Benchmark settings, :point_right: [Benchmarking Guide](https://intel-retail.github.io/documentation/use-cases/loss-prevention/performance.html)

#### 1 · ASC — basic self-checkout (the foundation)
```sh
# Object Detection + Classification (iGPU)
make run-lp CAMERA_STREAM=camera_to_workload_asc_object_detection_classification.json \
            WORKLOAD_DIST=workload_to_pipeline_asc_object_detection_classification_gpu.json \
            RENDER_MODE=1 DISPLAY=:0
# Object Detection only (CPU)
make run-lp CAMERA_STREAM=camera_to_workload_asc_object_detection.json \
            WORKLOAD_DIST=workload_to_pipeline_asc_object_detection_cpu.json
# benchmark + density (CPU)
make benchmark-stream-density CAMERA_STREAM=camera_to_workload_asc_object_detection.json \
            WORKLOAD_DIST=workload_to_pipeline_asc_object_detection_cpu.json
# benchmark results
make consolidate-metrics && cat benchmark/metrics.csv
```
#### 2. ASC — real-world lane: scanning + age verification (parallel)
```sh
# Age Verification on its own (iGPU)
make run-lp CAMERA_STREAM=camera_to_workload_asc_age_verification.json \
            WORKLOAD_DIST=workload_to_pipeline_asc_age_verification_gpu.json
# benchmark + density
make benchmark-stream-density CAMERA_STREAM=camera_to_workload_asc_age_verification.json \
            WORKLOAD_DIST=workload_to_pipeline_asc_age_verification_gpu.json
# Combined lane: detection + classification + age prediction + face detection, spread across iGPU + NPU
make run-lp CAMERA_STREAM=camera_to_workload_asc_hetero.json \
            WORKLOAD_DIST=workload_to_pipeline_asc_hetero.json
# benchmark + density
make benchmark-stream-density CAMERA_STREAM=camera_to_workload_asc_hetero.json \
            WORKLOAD_DIST=workload_to_pipeline_asc_hetero.json
# benchmark results
make consolidate-metrics && cat benchmark/metrics.csv
```
#### 3. Loss Prevention (the core — default 6-camera lane)
```sh
RENDER_MODE=1 DISPLAY=:0 make run-lp                 # run (visual)
make benchmark                                       # fixed-load benchmark
make benchmark-stream-density                        # max sustainable lanes  ⚙️
make consolidate-metrics && cat benchmark/metrics.csv # benchmark resutls
```

#### 4 · LVLM-enhanced workload
```sh
export MINIO_ROOT_USER=<...> MINIO_ROOT_PASSWORD=<...>
export RABBITMQ_USER=<...> RABBITMQ_PASSWORD=<...>
export GATED_MODEL=true HUGGINGFACE_TOKEN=<...>      # gated model access

make run-lp CAMERA_STREAM=camera_to_workload_vlm.json STREAM_LOOP=false

make benchmark CAMERA_STREAM=camera_to_workload_vlm.json WORKLOAD_DIST=workload_to_pipeline_vlm.json        
```


__What to Expect__
  
+ *Visual Mode*
  - Opens a video window with retail footage and detection overlays.
  - The pipeline runs until the input video finishes.
      
    **Note: The pipeline runs until the video completes**

+ *Visual and Headless Mode*
   - Verify that these output files are created and contain data:     
     - `<loss-prevention-workspace>/results/pipeline_stream*.log`: per-stream FPS metrics (one value per line)
     - `<oss-prevention-workspace>/results/gst-launch_*.log`: full GStreamer logs
              
   - Expected result:
      - Files exist with content
      - Files are non-empty
     
If a run failse, see [TroubleShooting](https://intel-retail.github.io/documentation/use-cases/loss-prevention/getting_started.html#troubleshooting)


__Stop the application__
```sh
make down-lp
```


## Advanced Usage
**Build images locally** (instead of pulling pre-built):
```sh
#Download the models
make download-models REGISTRY=false
#Update github performance-tool submodule
make update-submodules REGISTRY=false
#Download sample videos used by the performance tools
make download-sample-videos REGISTRY=false
#Run the LP application for visual mode
make run-render-mode DISPLAY=:0 REGISTRY=false RENDER_MODE=1
or
#Run the LP application for headless mode
make run REGISTRY=false
```
- Or simply:
- Visual Mode
```sh
make run-lp DISPLAY=:0 REGISTRY=false RENDER_MODE=1
```
- Headless Mode
```sh
make run-lp REGISTRY=false
```
### Configuration & user-defined workloads
- Workloads are driven by JSON in `configs/` plus the `CAMERA_STREAM` / `WORKLOAD_DIST` env vars (CPU/GPU/NPU/hetero variants, [availability varies by use case](#per-use-case-walkthroughs)). You can also **define your own** — map cameras to custom pipelines by editing `camera_to_workload_*.json` (which cameras run which workloads) and `workload_to_pipeline_*.json` (each workload’s *pipeline* — a sequence of GStreamer elements + models, e.g. `gvadetect` / `gvaclassify`, on a chosen device). See the [Documentation Guide](https://intel-retail.github.io/documentation/use-cases/loss-prevention/getting_started.html) for pre-configured workloads and [User-Defined Workloads](https://intel-retail.github.io/documentation/use-cases/loss-prevention/advanced.html#user-defined-workloads) for the full definitions.

- Inference interval

   The `INFERENCE_INTERVAL` environment variable controls how often the detector runs        inference (the `gvadetect inference-interval` property). A value of `N` runs inference    on every `N`th frame and relies on the tracker for the frames in between.

    - Default: `3`
    - `1` — run inference on every frame (smoothest, most consistent detections; highest load)
    - `2`, `3`, ... — infer less frequently (better performance, more reliance on the tracker between frames)

```sh
make run-lp CAMERA_STREAM=camera_to_workload_asc_object_detection_classification.json WORKLOAD_DIST=workload_to_pipeline_asc_object_detection_classification_gpu.json RENDER_MODE=1 DISPLAY=:0 INFERENCE_INTERVAL=1
```

## Architecture & services

The system runs as a set of **Docker** containers orchestrated by `docker-compose`. AI inference runs on **OpenVINO™** across Intel® **CPU / iGPU / NPU**; the video-analytics pipeline is built with **GStreamer** (Intel® DLStreamer `gvadetect / gvaclassify` elements) and generated dynamically from the config files; and video is fed in over **RTSP**. The sections below cover that streaming source, the container services, and the repository layout.

### RTSP streaming architecture
An integrated **MediaMTX** RTSP server (`rtsp-streamer` container) streams the sample video files for testing and development.

#### How it works

1. **RTSP server container** (`rtsp-streamer`) — auto-starts MediaMTX on port **8554**; streams every `.mp4` in `performance-tools/sample-media/;` each video becomes an RTSP stream at `rtsp://rtsp-streamer:8554/<video-name>.`

2. **Pipeline consumption** — GStreamer pipelines connect via the rtspsrc element, with TCP transport, configurable latency, and automatic retry/timeout handling.

3. Stream naming convention — e.g. video `items-in-basket-32658421-1080-15-bench.mp4` → stream `rtsp://rtsp-streamer:8554/items-in-basket-32658421-1080-15-bench.`

#### RTSP server features

- **Loop playback** — videos restart automatically when finished
- **TCP transport** — reliable streaming over corporate networks
- **Low latency** — 200 ms default for real-time processing
- **Multiple streams** — supports concurrent camera streams
- **Proxy support** — works through corporate HTTP/HTTPS proxies

### Docker Services

| Service | Purpose | Port | Notes |
|---------|---------|------|-------|
| `rtsp-streamer` | RTSP video streaming server | 8554 | Streams videos from sample-media |
| `rabbitmq` | Message broker for VLM workload | 5672, 15672 | Requires credentials |
| `minio-service` | Object storage for frames | 4000, 4001 | S3-compatible storage |
| `model-downloader` | Downloads AI models | - | Runs once at startup |
| `lp-vlm-workload-handler` | VLM inference processor | - | GPU/CPU inference |
| `vlm-pipeline-runner` | VLM pipeline orchestrator | - | Requires DISPLAY variable |
| `lp-pipeline-runner` | Main inference pipeline | - | Supports CPU/GPU/NPU |

All services run on `my_network` bridge network for DNS resolution;use `rtsp-streamer`, `rabbitmq`, `minio-service` as hostnames for inter-service communication


## Project Structure

- `configs/` — Configuration files (camera/workload mapping, pipeline mapping)
- `docker/` — Dockerfiles for downloader and pipeline containers
- `docs/` — Documentation (HLD, LLD, system design)
- `download-scripts/` — Scripts for downloading models and videos
- `src/` — Main source code and pipeline runner scripts
- `src/rtsp-streamer/` — RTSP server container (MediaMTX + FFmpeg)
- `src/gst-pipeline-generator.py` — Dynamic GStreamer pipeline generator
- `src/docker-compose.yml` — Multi-container orchestration
- `performance-tools/sample-media/` — Video files for RTSP streaming
- `Makefile` — Build automation and workflow commands


   
## Useful Information

+ __Make Commands__
    - `make validate-all-configs` — Validate all configuration files
    - `make clean-images` — Remove dangling Docker images
    - `make clean-containers` — Remove stopped containers
    - `make clean-all` — Remove all unused Docker resources
 + __Known Issues__
    - On EMT OS, containers built on Alpine base images (e.g., MinIO) may report as *unhealthy* despite the service functioning normally.
      Docker health checks are failing with OCI runtime errors, preventing proper container orchestration and monitoring. 

## Getting help

Pick the use case closest to your needs, run the included benchmarks, and **reach out to your Intel Solution Manager to talk about what you found.** Full docs: the [Loss Prevention Documentation Guide](https://intel-retail.github.io/documentation/use-cases/loss-prevention/getting_started.html). In case of failure, see [Troubleshooting](https://intel-retail.github.io/documentation/use-cases/loss-prevention/getting_started.html#troubleshooting).
