# Loss Prevention Pipeline System

## Overview

The Loss Prevention Pipeline System is an open-source reference implementation for building and deploying video analytics pipelines for retail loss prevention use cases. It leverages Intel® hardware and software, GStreamer, and OpenVINO™ to enable scalable, real-time object detection and classification at the edge.

## 📋 Prerequisites

- Ubuntu 24.04 or newer (Linux recommended), Desktop edition (or Server edition with GUI installed).
- [Docker](https://docs.docker.com/engine/install/)
- [Make](https://www.gnu.org/software/make/) (`sudo apt install make`)
- Intel hardware (CPU, iGPU, dGPU, NPU)
- Intel drivers:
    - [Intel GPU drivers](https://dgpu-docs.intel.com/driver/client/overview.html)
    - [NPU](https://dlstreamer.github.io/dev_guide/advanced_install/advanced_install_guide_prerequisites.html#prerequisite-2-install-intel-npu-drivers)
- Sufficient disk space for models, videos, and results

## 🚀 QuickStart
Clone the repo with the below command
```
git clone -b <release-or-tag> --single-branch https://github.com/intel-retail/loss-prevention
```
>Replace <release-or-tag> with the version you want to clone (for example, **v4.0.0**).
```
git clone -b v4.0.0 --single-branch https://github.com/intel-retail/loss-prevention
```


### **NOTE:** 

By default the application runs by pulling the pre-built images. If you want to build the images locally and then run the application, set the flag:

```bash
REGISTRY=false

usage: make <command> REGISTRY=false (applicable for all commands like benchmark, benchmark-stream-density..)
Example: make run-lp REGISTRY=false
```

(If this is the first time, it will take some time to download videos, models, docker images and build images)

### 1. Step by step instructions:

1.1 Download the models using download_models/downloadModels.sh

```bash
make download-models
```

1.2 Update github submodules

```bash
make update-submodules
```

1.3 Download sample videos used by the performance tools

```bash
make download-sample-videos
```

1.4 Run the LP application

```bash
make run-render-mode
```

- Run Loss Prevention appliaction with single command.   

    ```bash
    make run-lp
    ```

    - Running Loss Prevention application with ENV variables:
      ```bash
      CAMERA_STREAM=camera_to_workload_full.json WORKLOAD_DIST=workload_to_pipeline_cpu.json make run-lp
      ```
      `CAMERA_STREAM=camera_to_workload_full.json`: runs all 6 workloads. <br>
      `WORKLOAD_DIST=workload_to_pipeline_cpu.json`: all workloads run on CPU. <br>

### 2 To build the images locally step by step:

- Follow the following steps:
  ```bash
  make download-models REGISTRY=false
  make update-submodules REGISTRY=false
  make download-sample-videos
  make run-render-mode REGISTRY=false
  ```
      
- The above series of commands can be executed using only one command:
    
  ```bash
  make run-lp REGISTRY=false
  ```

For a comprehensive and advanced guide, refer to- [Loss Prevention Documentation Guide](https://intel-retail.github.io/documentation/use-cases/loss-prevention/loss-prevention.html)

### 3. Stop all containers

When pre-built images are pulled-
```sh
make down-lp
```
When images are built locally-
```sh
make down-lp REGISTRY=false
```

### Note: Required Environment Variables

#### For VLM Workload:
```sh
# MinIO credentials (object storage)
export MINIO_ROOT_USER=<your-minio-username>
export MINIO_ROOT_PASSWORD=<your-minio-password>

# RabbitMQ credentials (message broker) - REQUIRED
export RABBITMQ_USER=<your-rabbitmq-username>
export RABBITMQ_PASSWORD=<your-rabbitmq-password>

# Hugging Face token (required for gated models)
# Generate a token from: https://huggingface.co/settings/tokens
export GATED_MODEL=true
export HUGGINGFACE_TOKEN=<your-huggingface-token>
```

#### For Corporate Networks with Proxy:
```sh
# HTTP/HTTPS Proxy settings
export HTTP_PROXY=<HTTP PROXY>
export HTTPS_PROXY=<HTTPS PROXY>
export NO_PROXY=localhost,127.0.0.1,rabbitmq,minio-service,rtsp-streamer
```

#### Optional RTSP Configuration:
```sh
# RTSP Server configuration (defaults shown)
export RTSP_STREAM_HOST=rtsp-streamer  # Hostname of RTSP server
export RTSP_STREAM_PORT=8554           # RTSP port
export RTSP_MEDIA_DIR=../performance-tools/sample-media  # Video source directory
```

### Run the VLM based workload
```sh
make run-lp CAMERA_STREAM=camera_to_workload_vlm.json

make benchmark CAMERA_STREAM=camera_to_workload_vlm.json
```

### 4. Run benchmarking on CPU/NPU/GPU.
>*By default, the configuration is set to use the CPU. If you want to benchmark the application on GPU or NPU, please update the device value in workload_to_pipeline.json.*

```sh
make benchmark
```

### 5. See the benchmarking results.

```sh
make consolidate-metrics

cat benchmark/metrics.csv
```

### 6. View the Dynamically Generated GStreamer Pipeline.
>*Since the GStreamer pipeline is generated dynamically based on the provided configuration(camera_to_workload and workload_to_pipeline json), the pipeline.sh file gets updated every time the user runs make run-lp or make benchmark. This ensures that the pipeline reflects the latest changes.*
```sh

src/pipelines/pipeline.sh

```

## 🛠️ Other Useful Make Commands.

- `make validate-all-configs` — Validate all configuration files
- `make clean-images` — Remove dangling Docker images
- `make clean-containers` — Remove stopped containers
- `make clean-all` — Remove all unused Docker resources


## ⚙️ Configuration

The application is highly configurable via JSON files in the `configs/` directory:

- **`camera_to_workload.json`**: Maps each camera to one or more workloads. To add or remove a camera, edit the `lane_config.cameras` array in this file. Each camera entry can specify its video source (file or RTSP stream), region of interest, and assigned workloads.
    
    **Option 1: RTSP Stream Source (Recommended for Production)**
    ```json
    {
      "lane_config": {
        "cameras": [
          {
            "camera_id": "cam1",
            "streamUri": "rtsp://rtsp-streamer:8554/video-stream-name",
            "workloads": ["items_in_basket", "multi_product_identification"],
            "region_of_interest": {"x": 100, "y": 100, "x2": 800, "y2": 600}
          }
        ]
      }
    }
    ```
    
    **Option 2: File-Based Source (Development/Testing)**
    ```json
    {
      "lane_config": {
        "cameras": [
          {
            "camera_id": "cam1",
            "fileSrc": "sample-media/video1.mp4|https://source-url.com/video.mp4",
            "width": 1920,
            "height": 1080,
            "fps": 15,
            "workloads": ["items_in_basket", "multi_product_identification"],
            "region_of_interest": {"x": 100, "y": 100, "x2": 800, "y2": 600}
          }
        ]
      }
    }
    ```
    
    **Option 3: Hybrid Configuration (Both RTSP and File Source)**
    ```json
    {
      "camera_id": "cam1",
      "streamUri": "rtsp://rtsp-streamer:8554/video-stream-name",
      "fileSrc": "sample-media/video1.mp4|https://fallback-url.com",
      "workloads": ["items_in_basket"]
    }
    ```
    > **Note:** If both `streamUri` and `fileSrc` are provided, `streamUri` takes priority. The system falls back to `fileSrc` if RTSP is unavailable.
- **`workload_to_pipeline.json`**: Maps each workload name to a pipeline definition (sequence of GStreamer elements and models). To add or update a workload, edit the `workload_pipeline_map` in this file.
    - Example:
      ```json
      {
        "workload_pipeline_map": {
          "items_in_basket": [
            {"type": "gvadetect", "model": "yolo11n", "precision": "INT8", "device": "CPU"},
            {"type": "gvaclassify", "model": "efficientnet-v2-b0", "precision": "INT8", "device": "CPU"}
          ],
          ...
        }
      }
      ```

**To try a new camera or workload:**
1. Edit `configs/camera_to_workload.json` to add your camera and assign workloads.
2. For RTSP sources: Add `"streamUri": "rtsp://host:port/stream-name"` to your camera config.
3. For file sources: Place your video files in `performance-tools/sample-media/` and update `fileSrc`.
4. Edit `configs/workload_to_pipeline.json` to define or update the pipeline for your workload.
5. Re-run the pipeline as described above.

## 🎥 RTSP Streaming Architecture

The system includes an integrated RTSP server (MediaMTX) that streams video files for testing and development:

### How It Works:
1. **RTSP Server Container** (`rtsp-streamer`): 
   - Automatically starts MediaMTX server on port 8554
   - Streams all `.mp4` files from `performance-tools/sample-media/`
   - Each video becomes an RTSP stream: `rtsp://rtsp-streamer:8554/<video-name>`

2. **Pipeline Consumption**:
   - GStreamer pipelines connect via `rtspsrc` element
   - Supports TCP transport with configurable latency
   - Automatic retry and timeout handling

3. **Stream Naming Convention**:
   - Video: `items-in-basket-32658421-1080-15-bench.mp4`
   - Stream: `rtsp://rtsp-streamer:8554/items-in-basket-32658421-1080-15-bench`

### RTSP Server Features:
- **Loop Playback**: Videos restart automatically when finished
- **TCP Transport**: Reliable streaming over corporate networks
- **Low Latency**: Default 200ms latency for real-time processing
- **Multiple Streams**: Supports concurrent camera streams
- **Proxy Support**: Works through corporate HTTP/HTTPS proxies

### Connecting External RTSP Cameras:
To use real RTSP cameras instead of the built-in server:

```json
{
  "camera_id": "external_cam1",
  "streamUri": "rtsp://192.168.1.100:554/stream1",
  "workloads": ["items_in_basket"]
}
```

### RTSP Troubleshooting:
- **Connection timeout**: Check `RTSP_STREAM_HOST` and `RTSP_STREAM_PORT` environment variables
- **Stream not found**: Verify video file exists in `performance-tools/sample-media/`
- **Black frames**: Ensure video codec is H.264 (most compatible)
- **Check RTSP server logs**: `docker logs rtsp-streamer`

## 📁 Project Structure

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

## 🐳 Docker Services

The application runs the following Docker containers:

| Service | Purpose | Port | Notes |
|---------|---------|------|-------|
| `rtsp-streamer` | RTSP video streaming server | 8554 | Streams videos from sample-media |
| `rabbitmq` | Message broker for VLM workload | 5672, 15672 | Requires credentials |
| `minio-service` | Object storage for frames | 4000, 4001 | S3-compatible storage |
| `model-downloader` | Downloads AI models | - | Runs once at startup |
| `lp-vlm-workload-handler` | VLM inference processor | - | GPU/CPU inference |
| `vlm-pipeline-runner` | VLM pipeline orchestrator | - | Requires DISPLAY variable |
| `lp-pipeline-runner` | Main inference pipeline | - | Supports CPU/GPU/NPU |

**Network Configuration:**
- All services run on `my_network` bridge network for DNS resolution
- Use `rtsp-streamer`, `rabbitmq`, `minio-service` as hostnames for inter-service communication

---

