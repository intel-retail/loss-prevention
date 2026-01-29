# Loss Prevention Pipeline System
> [!WARNING]
>  The **main** branch of this repository contains work-in-progress development code for the upcoming release, and is **not guaranteed to be stable or working**.
>
> **The source for the latest release can be found at [Releases](https://github.com/intel-retail/loss-prevention/releases).**
## Overview

The Loss Prevention Pipeline System is an open-source reference implementation for building and deploying video analytics pipelines for retail loss prevention use cases. It leverages Intel® hardware and software, GStreamer, and OpenVINO™ to enable scalable, real-time object detection and classification at the edge.

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

## 🚀 QuickStart: Run with Pre-Built Images
+ __Clone the repo with the below command__
    ```
    git clone -b <release-or-tag> --single-branch https://github.com/intel-retail/loss-prevention
    ```
    >Replace <release-or-tag> with the version you want to clone (for example, **v4.0.0**).
    ```
    git clone -b v4.0.0 --single-branch https://github.com/intel-retail/loss-prevention
    ```
+ __Run the application__
  
    *Visual Mode*

    ```
    RENDER_MODE=1 REGISTRY=true make run-lp
    ```

    *Headless Mode*

    ```
    RENDER_MODE=0 REGISTRY=true make run-lp
    ```
> :bulb:
> For the first time execution, it will take some time to download videos, models and docker images

__:eyes: What to Expect__
  
+ *Visual Mode*
  - A video window opens showing the retail video with detection overlays
      
    **Note: The pipeline runs until the video completes**

+ *Visual and Headless Mode*
   - Verify Output files:       
     - `<loss-prevention-workspace>/results/pipeline_stream*.log` - FPS metrics (one value per line)
     - `<oss-prevention-workspac>/results/gst-launch_*.log` - Full GStreamer output
              
          :white_check_mark: Content in files ❌ No Content in files
     
        >🐞
        >In case of failure refer Section [TroubleShooting](#%EF%B8%8F-troubleshooting)


__:stop_sign: Stop the application__
```sh
make down-lp
```

## 📁 Project Structure

- `configs/` — Configuration files (camera/workload mapping, pipeline mapping)
- `docker/` — Dockerfiles for downloader and pipeline containers
- `docs/` — Documentation (HLD, LLD, system design)
- `download-scripts/` — Scripts for downloading models and videos
- `src/` — Main source code and pipeline runner scripts
- `Makefile` — Build automation and workflow commands-

## :heavy_plus_sign: Advanced Usage
>[!IMPORTANT]
>For a comprehensive and advanced guide, refer to- [Loss Prevention Documentation Guide](https://intel-retail.github.io/documentation/use-cases/loss-prevention/loss-prevention.html)

#### 1. To build the images locally and run the application:

```sh
    #Download the models
    make download-models REGISTRY=false
    #Update github performance-tool submodule
    make update-submodules REGISTRY=false
    #Download sample videos used by the performance tools
    make download-sample-videos
    #Run the LP application
    make run-render-mode REGISTRY=false RENDER_MODE=1
```
- Or simply:
```sh
    make run-lp REGISTRY=false RENDER_MODE=1
```

#### 2. Run the VLM based workload

> [!IMPORTANT]
> Required Environment Variables
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

#### 3. Run benchmarking on CPU/NPU/GPU.
>*By default, the configuration is set to use the CPU. If you want to benchmark the application on GPU or NPU, please update the device value in workload_to_pipeline.json.*

```sh
make benchmark
```

+ See the benchmarking results.

    ```sh
    make consolidate-metrics

    cat benchmark/metrics.csv
    ```

#### 4. Run Custom Workloads
The application is highly configurable via JSON files in the `configs/` directory

**To try a new camera or workload:**
1. Edit `configs/camera_to_workload.json` to add your camera and assign workloads.
2. Edit `configs/workload_to_pipeline.json` to define or update the pipeline for your workload.
3. (Optional) Place your video files in the appropriate directory and update the `fileSrc` path.
4. Re-run the pipeline as described above.
   
##### ⚙️ Configuration
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

## 🛠️ TroubleShooting

+ If results are empty, check Docker logs for errors:
```
docker logs pipeline-runner
```


## &#8505; Useful Information

+ __Make Commands__
    - `make validate-all-configs` — Validate all configuration files
    - `make clean-images` — Remove dangling Docker images
    - `make clean-containers` — Remove stopped containers
    - `make clean-all` — Remove all unused Docker resources
+ __View the Dynamically Generated GStreamer Pipeline__
>*Since the GStreamer pipeline is generated dynamically based on the provided configuration(camera_to_workload and workload_to_pipeline json), the pipeline.sh file gets updated every time the user runs make run-lp or make benchmark. This ensures that the pipeline reflects the latest changes.*
```sh

src/pipelines/pipeline.sh

```

