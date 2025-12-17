# Loss Prevention Pipeline System

## Overview

The Loss Prevention Pipeline System is an open-source reference implementation for building and deploying video analytics pipelines for retail loss prevention use cases. It leverages Intel® hardware and software, GStreamer, and OpenVINO™ to enable scalable, real-time object detection and classification at the edge.

## 📋 Prerequisites

- Ubuntu 24.04 or newer (Linux recommended)
- [Docker](https://docs.docker.com/engine/install/)
- [Make](https://www.gnu.org/software/make/) (`sudo apt install make`)
- Intel hardware (CPU, iGPU, dGPU, NPU)
- Intel drivers (see [Intel GPU drivers](https://dgpu-docs.intel.com/driver/client/overview.html))
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


- **For running VLM service (in case of lp_vlm workload)**, set the following environment variables:
  ```bash
  export MINIO_ROOT_USER=minio_minio
  export MINIO_ROOT_PASSWORD=minio_miniol
  export RABBITMQ_USER=RabbitMQ
  export RABBITMQ_PASSWORD=RabbitPass
  export HUGGINGFACE_TOKEN=<Huggingface_Token>   
  ```
  Then run:
  ```bash
  WORKLOAD_DIST=workload_to_pipeline.json make run-lp
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

```sh
make down-lp
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

- **`camera_to_workload.json`**: Maps each camera to one or more workloads. To add or remove a camera, edit the `lane_config.cameras` array in this file. Each camera entry can specify its video source, region of interest, and assigned workloads.
    - Example:
      ```json
      {
        "lane_config": {
          "cameras": [
            {
              "camera_id": "cam1",
              "fileSrc": "sample-media/video1.mp4",
              "workloads": ["items_in_basket", "multi_product_identification"],
              "region_of_interest": {"x": 100, "y": 100, "x2": 800, "y2": 600}              
            },
            ...
          ]
        }
      }
      ```
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
2. Edit `configs/workload_to_pipeline.json` to define or update the pipeline for your workload.
3. (Optional) Place your video files in the appropriate directory and update the `fileSrc` path.
4. Re-run the pipeline as described above.

## 📁 Project Structure

- `configs/` — Configuration files (camera/workload mapping, pipeline mapping)
- `docker/` — Dockerfiles for downloader and pipeline containers
- `docs/` — Documentation (HLD, LLD, system design)
- `download-scripts/` — Scripts for downloading models and videos
- `src/` — Main source code and pipeline runner scripts
- `Makefile` — Build automation and workflow commands

---

