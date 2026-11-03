# Advanced Settings

## Configuration Options

### Local Image Building

By default, the application uses pre-built Docker images for faster setup. If you need to build images locally (for customization or development):

```bash
# Build and run locally instead of using pre-built images
make run-lp RENDER_MODE=1 REGISTRY=false

# Apply to any command
make <command> REGISTRY=false

# Examples:
make benchmark REGISTRY=false
make benchmark-stream-density REGISTRY=false
```

**When to use local building:**

- Modifying source code or configurations
- Development and testing changes
- Air-gapped environments without internet access
- Custom hardware optimizations

**Note**: Local building takes significantly longer (15-30 minutes) compared to pre-built images (2-5 minutes).

### Step-by-Step Local Build Process

- To build the images locally step by step:
  - Follow the following steps:

    ```bash
    make download-models REGISTRY=false
    make update-submodules REGISTRY=false
    make download-sample-videos
    make run-render-mode REGISTRY=false
    ```

  - The above series of commands can be executed using only one command:

    ```bash
    make run-lp REGISTRY=false RENDER_MODE=1
    ```

### User Defined Workloads

The application is highly configurable via JSON files in the `configs/` directory

**To try a new camera or workload:**

1. Create new camera to workload mapping in `configs/camera_to_workload_custom.json` to add your camera and assign workloads.
   - **camera_to_workload_custom.json**: Maps each camera to one or more workloads. - To add or remove a camera, edit the `lane_config.cameras` array in the file. - Each camera entry can specify its video source, region of interest, and assigned workloads.
     Example:
     `json
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
    `
     If adding new videos, place your video files in the directory **performance-tools/sample-media/** and update the `streamUri` path.

2. Connecting External RTSP Cameras:
   To use real RTSP cameras instead of the built-in server:

   ```json
   {
     "camera_id": "external_cam1",
     "streamUri": "rtsp://192.168.1.100:554/stream1",
     "workloads": ["items_in_basket"]
   }
   ```

3. Create new `configs/workload_to_pipeline_custom.json` to define pipeline for your workload.
   - **workload_to_pipeline_custom.json**: Maps each workload name to a pipeline definition (sequence of GStreamer elements and models).
     Example:

     ```json
     {
       "workload_pipeline_map": {
         "custom_workload_1": [
           {
             "type": "gvadetect",
             "model": "yolo11n",
             "precision": "INT8",
             "device": "CPU"
           },
           {
             "type": "gvaclassify",
             "model": "efficientnet-v2-b0",
             "precision": "INT8",
             "device": "CPU"
           }
         ],
         "custom_workload_2": [
           {
             "type": "gvadetect",
             "model": "yolo11n",
             "precision": "INT16",
             "device": "NPU"
           },
           {
             "type": "gvaclassify",
             "model": "efficientnet-v2-b0",
             "precision": "INT16",
             "device": "NPU"
           }
         ],
         "custom_workload_3": [
           {
             "type": "gvadetect",
             "model": "yolo11n",
             "precision": "INT8",
             "device": "GPU"
           },
           {
             "type": "gvaclassify",
             "model": "efficientnet-v2-b0",
             "precision": "INT8",
             "device": "GPU"
           }
         ]
       }
     }
     ```

4. Run validate configs command, to verify configuration files

```sh
make validate-all-configs
```

5. Re-run the pipeline as described above.

> [!NOTE]
> Since the GStreamer pipeline is generated dynamically based on the provided configuration(camera_to_workload and workload_to_pipeline json),
> the pipeline.sh file gets updated every time the user runs make run-lp or make benchmark. This ensures that the pipeline reflects the latest changes.
>
> ```sh
> src/pipelines/pipeline.sh
> ```

## Complete Workload Configuration Matrix

The preconfigured workloads support multiple hardware configurations out of the box. Use the `CAMERA_STREAM` and `WORKLOAD_DIST` variables to customize which cameras and hardware (CPU, GPU, NPU) are used by your pipeline.

**Usage Pattern:**

```bash
CAMERA_STREAM=<camera_stream> WORKLOAD_DIST=<workload_dist> make run-lp
# Or for benchmarking:
CAMERA_STREAM=<camera_stream> WORKLOAD_DIST=<workload_dist> make benchmark
```

### Loss Prevention Configurations

| Description   | CAMERA_STREAM               | WORKLOAD_DIST                     |
| ------------- | --------------------------- | --------------------------------- |
| CPU (Default) | camera_to_workload.json     | workload_to_pipeline.json         |
| GPU           | camera_to_workload.json     | workload_to_pipeline_gpu.json     |
| NPU + GPU     | camera_to_workload.json     | workload_to_pipeline_gpu-npu.json |
| Heterogeneous | camera_to_workload.json     | workload_to_pipeline_hetero.json  |
| VLM           | camera_to_workload_vlm.json | workload_to_pipeline_vlm.json     |

> [!NOTE]
> **Included Sub-Workloads**: The following detection types are automatically enabled in all Loss Prevention configurations:
>
> - `items_in_basket` - Monitors items placed in shopping baskets
> - `hidden_items` - Detects concealed or hidden products
> - `fake_scan_detection` - Identifies scanning without actual item registration
> - `multi_product_identification` - Tracks multiple products simultaneously
> - `product_switching` - Detects when customers switch high-value items for lower-value ones
> - `sweet_heartening` - Monitors for collusion between customers and cashiers

### Automated Self-Checkout Configurations

| Description                             | CAMERA_STREAM                                               | WORKLOAD_DIST                                                        |
| --------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------------------------- |
| Object Detection (CPU)                  | camera_to_workload_asc_object_detection.json                | workload_to_pipeline_asc_object_detection_cpu.json                   |
| Object Detection (GPU)                  | camera_to_workload_asc_object_detection.json                | workload_to_pipeline_asc_object_detection_gpu.json                   |
| Object Detection (NPU)                  | camera_to_workload_asc_object_detection.json                | workload_to_pipeline_asc_object_detection_npu.json                   |
| Object Detection & Classification (CPU) | camera_to_workload_asc_object_detection_classification.json | workload_to_pipeline_asc_object_detection_classification_cpu.json    |
| Object Detection & Classification (GPU) | camera_to_workload_asc_object_detection_classification.json | workload_to_pipeline_asc_object_detection_classification_gpu.json    |
| Object Detection & Classification (NPU) | camera_to_workload_asc_object_detection_classification.json | workload_to_pipeline_asc_object_detection_classification_npu.json    |
| Age Prediction & Face Detection (CPU)   | camera_to_workload_asc_age_verification.json                | workload_to_pipeline_asc_age_verification_cpu.json                   |
| Age Prediction & Face Detection (GPU)   | camera_to_workload_asc_age_verification.json                | workload_to_pipeline_asc_age_verification_gpu.json                   |
| Age Prediction & Face Detection (NPU)   | camera_to_workload_asc_age_verification.json                | workload_to_pipeline_asc_age_verification_npu.json                   |
| Age Verification Heterogeneous          | camera_to_workload_asc_age_verification.json                | workload_to_pipeline_asc_age_verification_hetero.json                |
| Object Detection Heterogeneous          | camera_to_workload_asc_object_detection_classification.json | workload_to_pipeline_asc_object_detection_classification_hetero.json |
