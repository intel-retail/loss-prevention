# Get Started

## Prerequisites

- Ubuntu 24.04 or newer (Linux recommended), Desktop edition (or Server edition with GUI installed).
- [Docker](https://docs.docker.com/engine/install/)
- [Make](https://www.gnu.org/software/make/) (`sudo apt install make`)
- **Python 3** (`sudo apt install python3`) - required for video download and validation scripts
- Intel hardware (CPU, iGPU, dGPU, NPU)
- Intel drivers:
  - [Intel GPU drivers](https://dgpu-docs.intel.com/driver/client/overview.html)
  - [NPU](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/dlstreamer/dev_guide/advanced_install/advanced_install_guide_prerequisites.html#optional-prerequisite-2-install-intel-npu-drivers)
- Sufficient disk space for models, videos, and results

> **Note:** First-time setup downloads AI models, sample videos, and Docker images - this may take 5-15 minutes depending on your internet connection.

## Choose Your Workload Type

### Loss Prevention

**Purpose**: Detect theft, suspicious behavior, and inventory shrinkage
**Use When**: You want to monitor customer interactions and prevent loss
**Includes**: Hidden items detection, fake scan detection, product switching alerts

### Automated Self-Checkout

**Purpose**: Validate customer scanning and detect checkout fraud
**Use When**: You want to ensure proper product scanning at self-checkout stations
**Options**: Object detection, age verification, product classification

### Enhanced Loss Prevention with LVLM

**Purpose**: Advanced item recognition using Large Vision Language Models
**Use When**: You need higher accuracy for complex items or edge cases
**Includes**: Agent-based LVLM invocation, traditional CV fallback, improved item identification

## Quick Configuration Reference

### Loss Prevention Hardware Options

| Configuration     | Command                                                                                                                             | Best For                          |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| **CPU (Default)** | `make run-lp RENDER_MODE=1`                                                                                                         | Basic setups, testing             |
| **GPU**           | `make run-lp WORKLOAD_DIST=workload_to_pipeline_gpu.json RENDER_MODE=1`                                                             | Performance, real-time processing |
| **NPU + GPU**     | `make run-lp WORKLOAD_DIST=workload_to_pipeline_gpu-npu.json RENDER_MODE=1`                                                         | Latest Intel hardware             |
| **Heterogeneous** | `make run-lp WORKLOAD_DIST=workload_to_pipeline_hetero.json RENDER_MODE=1`                                                          | Mixed workloads across hardware   |
| **VLM**           | `make run-lp STREAM_LOOP=false CAMERA_STREAM=camera_to_workload_vlm.json WORKLOAD_DIST=workload_to_pipeline_vlm.json RENDER_MODE=1` | Advanced AI-powered detection     |

**Included Detection Types:** Hidden items, fake scanning, product switching, multi-product ID, sweet-heartening

### Automated Self-Checkout Quick Commands

**Object Detection (Identify scanned products):**

```bash
# GPU (recommended)
make run-lp CAMERA_STREAM=camera_to_workload_asc_object_detection.json WORKLOAD_DIST=workload_to_pipeline_asc_object_detection_gpu.json RENDER_MODE=1

# CPU alternative
make run-lp CAMERA_STREAM=camera_to_workload_asc_object_detection.json WORKLOAD_DIST=workload_to_pipeline_asc_object_detection_cpu.json RENDER_MODE=1
```

**Age Verification (Age-restricted products):**

```bash
# GPU (recommended)
make run-lp CAMERA_STREAM=camera_to_workload_asc_age_verification.json WORKLOAD_DIST=workload_to_pipeline_asc_age_verification_gpu.json RENDER_MODE=1
```

**Combined Detection & Classification:**

```bash
# GPU (recommended)
make run-lp CAMERA_STREAM=camera_to_workload_asc_object_detection_classification.json WORKLOAD_DIST=workload_to_pipeline_asc_object_detection_classification_gpu.json RENDER_MODE=1
```

> **Note:**
>
> **Hardware Selection**: Replace `_gpu` with `_cpu` or `_npu` in any command above based on your available hardware.
>
> **Complete Reference**: For the full configuration matrix with all hardware combinations and detailed specifications, see [Complete Workload Configuration Matrix](./get-started/advanced.md#complete-workload-configuration-matrix) in Advanced Settings.

## Step by step instructions

1. Clone the repo with the below command:

   ```bash
   git clone -b <release-or-tag> --single-branch https://github.com/intel-retail/loss-prevention
   ```

   > Replace <release-or-tag> with the version you want to clone (for example, **release-2026.2.0**).

   ```bash
   git clone -b release-2026.2.0 --single-branch https://github.com/intel-retail/loss-prevention
   ```

2. **Run Loss Prevention (Recommended for First Time)**

   **Simple Setup with Visual Output:**

   ```bash
   # RENDER_MODE=1 shows live video with detection boxes (recommended for first run)
   make run-lp RENDER_MODE=1
   ```

   **Alternative Options:**

   ```bash
   # Headless mode - no visual output (for servers or automated testing)
   make run-lp
   ```

   **What This Does:**
   - Downloads AI models (YOLOv5, EfficientNet)
   - Downloads sample videos for testing
   - Starts the loss prevention pipeline
   - Enables 6 detection types: hidden items, fake scanning, product switching, etc.
   - Visual mode shows real-time detection boxes and alerts

3. **Run Automated Self-Checkout Workloads**

   **Object Detection (Identifies scanned products):**

   ```bash
   # GPU accelerated - recommended for performance
   CAMERA_STREAM=camera_to_workload_asc_object_detection.json WORKLOAD_DIST=workload_to_pipeline_asc_object_detection_gpu.json make run-lp RENDER_MODE=1

   # CPU version - for systems without GPU
   CAMERA_STREAM=camera_to_workload_asc_object_detection.json WORKLOAD_DIST=workload_to_pipeline_asc_object_detection_cpu.json make run-lp RENDER_MODE=1
   ```

   **Age Verification (For age-restricted products):**

   ```bash
   # Detects customer age for alcohol/tobacco purchases
   CAMERA_STREAM=camera_to_workload_asc_age_verification.json WORKLOAD_DIST=workload_to_pipeline_asc_age_verification_gpu.json make run-lp RENDER_MODE=1
   ```

   **Combined Detection & Classification:**

   ```bash
   # Both identifies AND categorizes products
   CAMERA_STREAM=camera_to_workload_asc_object_detection_classification.json WORKLOAD_DIST=workload_to_pipeline_asc_object_detection_classification_gpu.json make run-lp RENDER_MODE=1
   ```

   > **Note:**
   >
   > **Display Options**: Add `RENDER_MODE=1` to any command above to see live video with detection boxes. Remove it for headless operation (servers/automation).
   >
   > **Choose Your Hardware**: Replace `_gpu` with `_cpu` or `_npu` based on your available hardware. See [Automated Self-Checkout Configurations](./get-started/advanced.md#automated-self-checkout-configurations) for all options.

## What You will See When Working

### Loss Prevention Results

- **Visual**: Red bounding boxes around suspicious activities
- **Alerts**: Console notifications for hidden items, fake scanning, product switching
- **Logs**: Detection confidence scores and behavior analysis

### Automated Self-Checkout Results

- **Object Detection**: Green boxes around identified products with labels
- **Age Verification**: Face detection boxes with estimated age ranges
- **Classification**: Product categories and scanning validation status

### Expected Performance

- **Startup Time**: 2-5 minutes (first run includes downloads)
- **Processing**: Real-time video analysis at 15-30 FPS
- **Results**: JSON files appear in `results/` folder within seconds

## Verify Results

After starting Loss Prevention you will begin to see result files being written into the results/ directory. Here are example outputs from the 3 log files.

Sample `gst-launch\_<time>\_gst.log` output:

```text
/GstPipeline:pipeline0/GstGvaWatermark:gvawatermark0/GstCapsFilter:capsfilter1: caps = video/x-raw(memory:VASurface), format=(string)RGBA
/GstPipeline:pipeline0/GstFPSDisplaySink:fpsdisplaysink0/GstXImageSink:ximagesink0: sync = true
Got context from element 'vaapipostproc1': gst.vaapi.Display=context, gst.vaapi.Display=(GstVaapiDisplay)"\(GstVaapiDisplayGLX\)\ vaapidisplayglx0", gst.vaapi.Display.GObject=(GstObject)"\(GstVaapiDisplayGLX\)\ vaapidisplayglx0";
Progress: (open) Opening Stream
Pipeline is PREROLLED ...
Prerolled, waiting for progress to finish...
Progress: (connect) Connecting to rtsp://localhost:8554/camera_0
Progress: (open) Retrieving server options
Progress: (open) Retrieving media info
Progress: (request) SETUP stream 0
```

Sample `pipeline<time>\_gst.log` output:

```text
14.58
14.58
15.47
15.47
15.10
15.10
14.60
14.60
14.88
14.88
```

Sample `r<time>\_gst.jsonl` output:

```json
{
  "objects": [
    {
      "detection": {
        "bounding_box": {
          "x_max": 0.7873924346958825,
          "x_min": 0.6701603093745723,
          "y_max": 0.7915918938548927,
          "y_min": 0.14599881349270305
        },
        "confidence": 0.8677337765693665,
        "label": "apple",
        "label_id": 39
      },
      "h": 697,
      "region_id": 610,
      "roi_type": "apple",
      "w": 225,
      "x": 1287,
      "y": 158
    },
    {
      "detection": {
        "bounding_box": {
          "x_max": 0.3221945836811382,
          "x_min": 0.19950163649114616,
          "y_max": 0.7924592239981934,
          "y_min": 0.1336837231479251
        },
        "confidence": 0.8625879287719727,
        "label": "apple",
        "label_id": 39
      },
      "h": 711,
      "region_id": 611,
      "roi_type": "apple",
      "w": 236,
      "x": 383,
      "y": 144
    },
    {
      "detection": {
        "bounding_box": {
          "x_max": 0.5730873789069046,
          "x_min": 0.42000878963365595,
          "y_max": 0.9749763191740435,
          "y_min": 0.12431765065780453
        },
        "confidence": 0.854443371295929,
        "label": "apple",
        "label_id": 39
      },
      "h": 919,
      "region_id": 612,
      "roi_type": "apple",
      "w": 294,
      "x": 806,
      "y": 134
    }
  ],
  "resolution": {
    "height": 1080,
    "width": 1920
  },
  "timestamp": 755106652
}
```

> **Note:** If unable to see results folder or files, please refer to the [Troubleshooting](#troubleshooting) section for more details.

## Stop the containers

   When pre-built images are pulled-

   ```bash
   make down-lp
   ```

   When images are built locally-

   ```bash
   make down-lp REGISTRY=false
   ```

## Troubleshooting

- If results folder is empty, check Docker logs for errors:
  - List the Docker containers

    ```sh
      docker ps -a
    ```

  - Verify Docker containers if it is running or no errors in container logs

  ```bash
  docker ps --all
  ```

  Result:

  ```bash
  NAMES                    STATUS                     IMAGE
  src-pipeline-runner-1    Up 17 seconds (healthy)    pipeline-runner:lp
  model-downloader         Exited(0) 17 seconds       model-downloader:lp
  ```

  - Check each container logs

    ```sh
      docker logs <container_id>
    ```

- If the file content in `<loss-prevention-workspace>/results/pipeline_stream*.log` is empty, check GStreamer output file for errors:
  - `<loss-prevention-workspace>/results/gst-launch_*.log`

- RTSP :

  - **Connection timeout**: Check `RTSP_STREAM_HOST` and `RTSP_STREAM_PORT` environment variables
  - **Stream not found**: Verify video file exists in `performance-tools/sample-media/`
  - **Black frames**: Ensure video codec is H.264 (most compatible)
  - **Check RTSP server logs**: `docker logs rtsp-streamer`

## [Proceed to Advanced Settings](./get-started/advanced.md)

<!--hide_directive
:::{toctree}
:hidden:

./get-started/advanced.md

:::
hide_directive-->
