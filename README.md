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

## 🚀 QuickStart
+ __Clone the repo with the below command__
    ```
    git clone -b <release-or-tag> --single-branch https://github.com/intel-retail/loss-prevention
    ```
    >Replace <release-or-tag> with the version you want to clone (for example, **v4.0.0**).
    ```
    git clone -b v4.0.0 --single-branch https://github.com/intel-retail/loss-prevention
    ```
>[!IMPORTANT]
>Default Settings
>
> - Run with Pre-built images.
> - Headless mode is enabled.
> - Default workload : loss prevention(CPU) 
>   - To know more about available default and preconfigured workloads :point_right: [Workloads](#4-pre-configured-workloads)
+ __Run the application__

    *Headless Mode*

    ```
    make run-lp
    ```
  
    *Visual Mode*

    ```
    RENDER_MODE=1 make run-lp
    ```
> :bulb:
> For the first time execution, it will take some time to download videos, models and docker images

__What to Expect__
  
+ *Visual Mode*
  - A video window opens showing the retail video with detection overlays
      
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

## 📁 Project Structure

- `configs/` — Configuration files (camera/workload mapping, pipeline mapping)
- `docker/` — Dockerfiles for downloader and pipeline containers
- `docs/` — Documentation (HLD, LLD, system design)
- `download-scripts/` — Scripts for downloading models and videos
- `src/` — Main source code and pipeline runner scripts
- `Makefile` — Build automation and workflow commands

## :heavy_plus_sign: Advanced Usage
>[!IMPORTANT]
>For a comprehensive and advanced guide, :point_right: [Loss Prevention Documentation Guide](https://intel-retail.github.io/documentation/use-cases/loss-prevention/loss-prevention.html)

### 1. To build the images locally and run the application:

```sh
    #Download the models
    make download-models REGISTRY=false
    #Update github performance-tool submodule
    make update-submodules REGISTRY=false
    #Download sample videos used by the performance tools
    make download-sample-videos REGISTRY=false
    #Run the LP application
    make run-render-mode REGISTRY=false RENDER_MODE=1
```
- Or simply:
```sh
    make run-lp REGISTRY=false RENDER_MODE=1
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
 make run-lp CAMERA_STREAM=camera_to_workload_vlm.json
 ```

### 3. Pre-configured Workloads
The preconfigured workload supports multiple hardware configurations out of the box. Use the `CAMERA_STREAM` and `WORKLOAD_DIST` variables to customize which cameras and hardware (CPU, GPU, NPU) are used by your pipeline.

For more details, please refer [Default Workloads](https://intel-retail.github.io/documentation/use-cases/loss-prevention/getting_started.html#pre-configured-workloads)

### 4. Benchmark
>By default, the configuration is set to use the Loss Prevention (CPU) workload.
>
>If you want to benchmark the application on GPU or NPU, please :point_right: [Workloads](#4-run-different-workloads)

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

      
## &#8505; Useful Information

+ __Make Commands__
    - `make validate-all-configs` — Validate all configuration files
    - `make clean-images` — Remove dangling Docker images
    - `make clean-containers` — Remove stopped containers
    - `make clean-all` — Remove all unused Docker resources


