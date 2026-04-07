# Loss Prevention Pipeline System
> [!WARNING]
>  The **main** branch of this repository contains work-in-progress development code for an upcoming release, and is **not guaranteed to be stable or working**.
>
> For the latest stable release :point_right: [Releases](https://github.com/intel-retail/loss-prevention/releases)

# Table of Contents 📑
1. [Overview](#overview)
2. [Prerequisites](#-prerequisites)
3. [QuickStart](#-quickstart)
4. [Project Structure](#-project-structure)
5. [Advanced Usage](#heavy_plus_sign-advanced-usage)
6. [Useful Information](#ℹ-useful-information)

## Overview

The Loss Prevention Pipeline System is an open-source reference implementation for building and deploying video analytics pipelines for retail use cases:
- Loss Prevention
- Automated self checkout
- User Defined Workloads
    
It leverages Intel® hardware and software, GStreamer, and OpenVINO™ to enable scalable, real-time object detection and classification at the edge.

### 🎥 RTSP Streaming Architecture

The system includes an integrated RTSP server (MediaMTX) that streams video files for testing and development:

#### How It Works:
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

#### RTSP Server Features:
- **Loop Playback**: Videos restart automatically when finished
- **TCP Transport**: Reliable streaming over corporate networks
- **Low Latency**: Default 200ms latency for real-time processing
- **Multiple Streams**: Supports concurrent camera streams
- **Proxy Support**: Works through corporate HTTP/HTTPS proxies

## 📋 Prerequisites

- Ubuntu 24.04 or newer (Linux recommended), Desktop edition (or Server edition with GUI installed).
- [Docker](https://docs.docker.com/engine/install/)
- [Make](https://www.gnu.org/software/make/) (`sudo apt install make`)
- **Python 3** (`sudo apt install python3`) - required for video download and validation scripts
- Intel hardware (CPU, iGPU, dGPU, NPU)
- Intel drivers:
    - [Intel GPU drivers](https://dgpu-docs.intel.com/driver/client/overview.html)
    - [NPU](https://dlstreamer.github.io/dev_guide/advanced_install/advanced_install_guide_prerequisites.html#prerequisite-2-install-intel-npu-drivers)
- Sufficient disk space for models, videos, and results

- For Corporate Networks with Proxy:
    ```sh
    # HTTP/HTTPS Proxy settings
    export HTTP_PROXY=<HTTP PROXY>
    export HTTPS_PROXY=<HTTPS PROXY>
    export NO_PROXY=localhost,127.0.0.1,rabbitmq,minio-service,rtsp-streamer
    ```
- Optional RTSP Configuration:
    ```sh
    # RTSP Server configuration (defaults shown)
    export RTSP_STREAM_HOST=rtsp-streamer  # Hostname of RTSP server
    export RTSP_STREAM_PORT=8554           # RTSP port
    export RTSP_MEDIA_DIR=../performance-tools/sample-media  # Video source directory
    export STREAM_LOOP=false               # Set to 'true' to loop video streams indefinitely
    ```
## 🚀 QuickStart
+ __Clone the repo with the below command__
    ```
    git clone -b <release-or-tag> --single-branch https://github.com/intel-retail/loss-prevention
    ```
    >Replace <release-or-tag> with the version you want to clone (for example, **v4.0.0**).
    ```
    git clone -b v4.0.0 --single-branch https://github.com/intel-retail/loss-prevention
    ```
### Run Loss Prevention Workload

>[!IMPORTANT]
>Default Settings
>
> - Run with Pre-built images.
> - Headless mode is enabled.
> - Default workload : loss prevention(CPU) 
>   - To know more about available default and preconfigured workloads :point_right: [Workloads](https://intel-retail.github.io/documentation/use-cases/loss-prevention/getting_started.html#pre-configured-workloads)
+ __Run the application__

    *Headless Mode*

    ```
    make run-lp
    ```
  
    *Visual Mode*

    ```
    RENDER_MODE=1 DISPLAY=:0 make run-lp
    ```
> :bulb:
> For the first time execution, it will take some time to download videos, models and docker images

### Run Automated Self Checkout Workload

#### 1. Object Detection
*Headless Mode*
```
make run-lp CAMERA_STREAM=camera_to_workload_asc_object_detection.json WORKLOAD_DIST=workload_to_pipeline_asc_object_detection_cpu.json 
```
*Visual Mode* 
```
make run-lp CAMERA_STREAM=camera_to_workload_asc_object_detection.json WORKLOAD_DIST=workload_to_pipeline_asc_object_detection_cpu.json RENDER_MODE=1 DISPLAY=:0
```
#### 2. Age Verification
*Headless Mode* 
```
make run-lp CAMERA_STREAM=camera_to_workload_asc_age_verification.json WORKLOAD_DIST=workload_to_pipeline_asc_age_verification_gpu.json
```
*Visual Mode* 
```
make run-lp CAMERA_STREAM=camera_to_workload_asc_age_verification.json WORKLOAD_DIST=workload_to_pipeline_asc_age_verification_gpu.json RENDER_MODE=1 DISPLAY=:0
```
#### 3. Combined Detection and Classification
*Headless Mode*
```
make run-lp CAMERA_STREAM=camera_to_workload_asc_object_detection_classification.json WORKLOAD_DIST=workload_to_pipeline_asc_object_detection_classification_gpu.json
```
*Visual Mode* 
```
make run-lp CAMERA_STREAM=camera_to_workload_asc_object_detection_classification.json WORKLOAD_DIST=workload_to_pipeline_asc_object_detection_classification_gpu.json RENDER_MODE=1 DISPLAY=:0
```
>[!IMPORTANT]
>For more Automated Self Checkout Workloads, :point_right: [Loss Prevention Documentation Guide](https://intel-retail.github.io/documentation/use-cases/loss-prevention/advanced.html#automated-self-checkout-configurations)


__What to Expect__
  
+ *Visual Mode*
  - A video window opens showing the retail video with detection overlays.
      
    **Note: The pipeline runs until the video completes**

+ *Visual and Headless Mode*
   - Verify Output files:       
     - `<loss-prevention-workspace>/results/pipeline_stream*.log` - FPS metrics (one value per line)
     - `<oss-prevention-workspace>/results/gst-launch_*.log` - Full GStreamer output
              
          :white_check_mark: Content in files ❌ No Files ❌ No Content in files
     
        >In case of failure :point_right: [TroubleShooting](https://intel-retail.github.io/documentation/use-cases/loss-prevention/getting_started.html#troubleshooting)


__Stop the application__
```sh
make down-lp
```


## :heavy_plus_sign: Advanced Usage
>[!IMPORTANT]
>For a comprehensive and advanced guide, :point_right: [Loss Prevention Documentation Guide](https://intel-retail.github.io/documentation/use-cases/loss-prevention/getting_started.html#step-by-step-instructions)

### 1. To build the images locally and run the application:

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

### 2. Run the VLM based workload

> [!IMPORTANT]
> Set the below bash Environment Variables
>```sh
>    #MinIO credentials (object storage)
>    export MINIO_ROOT_USER=<your-minio-username>
>    export MINIO_ROOT_PASSWORD=<your-minio-password>
>    #RabbitMQ credentials (message broker)
>    export RABBITMQ_USER=<your-rabbitmq-username>
>    export RABBITMQ_PASSWORD=<your-rabbitmq-password>
>    #Hugging Face token (required for gated models)
>    #Generate a token from: https://huggingface.co/settings/tokens
>    export GATED_MODEL=true
>    export HUGGINGFACE_TOKEN=<your-huggingface-token>
>    ```
- Run the workload
    
 ```
 make run-lp CAMERA_STREAM=camera_to_workload_vlm.json STREAM_LOOP=false
 ```

### 3. Configuration
The application is highly configurable via JSON files in the `configs/` directory and with environment variables `CAMERA_STREAM` and `WORKLOAD_DIST`. 
For more details, please refer [Pre Configured Workloads](https://intel-retail.github.io/documentation/use-cases/loss-prevention/getting_started.html#pre-configured-workloads)

### 4. Benchmark
>By default, the configuration is set to use the Loss Prevention (CPU) workload.

```sh
make benchmark
```
+ See the benchmarking results.

    ```sh
    make consolidate-metrics

    cat benchmark/metrics.csv
    ```
>[!IMPORTANT]
>For Advanced Benchmark settings, :point_right: [Benchmarking Guide](https://intel-retail.github.io/documentation/use-cases/loss-prevention/advanced.html)

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
   
## &#8505; Useful Information

+ __Make Commands__
    - `make validate-all-configs` — Validate all configuration files
    - `make clean-images` — Remove dangling Docker images
    - `make clean-containers` — Remove stopped containers
    - `make clean-all` — Remove all unused Docker resources
 + __Known Issues__
    - On EMT OS, containers built on Alpine base images (e.g., MinIO) may report as unhealthy despite the service functioning normally.
      Docker health checks are failing with OCI runtime errors, preventing proper container orchestration and monitoring. 


