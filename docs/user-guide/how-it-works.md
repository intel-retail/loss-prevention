# Loss Prevention: How It Works

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagrams](#architecture-diagrams)
3. [Configuration Management](#configuration-management)
4. [System Benefits](#system-benefits)

## System Overview

The Loss Prevention Pipeline System is a comprehensive video analytics platform designed for retail loss prevention using Intel hardware acceleration. The system processes multiple camera feeds simultaneously, applying AI-powered detection and classification models to identify potential security incidents.

### Key Features

- **Multi-camera Support**: Simultaneous processing of multiple camera feeds
- **AI-Powered Analytics**: Object detection and classification using YOLO and EfficientNet models
- **Intel Hardware Optimization**: Leverages CPU, GPU, and NPU acceleration
- **Real-time Processing**: GStreamer-based pipeline for low-latency video processing
- **Flexible Configuration**: JSON-based configuration for cameras, workloads, and pipelines
- **Performance Monitoring**: Comprehensive metrics collection and analysis
- **Containerized Deployment**: Docker-based deployment with Intel DL Streamer

## Architecture Diagrams

### Component Architecture

```mermaid
graph TB
    subgraph "Configuration Layer"
        CWC[camera_to_workload.json]
        WPC[workload_to_pipeline.json]
    end

    subgraph "Pipeline Generation Layer"
        PGL[Pipeline Generator]
        CL[Config Loader]
    end

    subgraph "Execution Layer"
        GST[GStreamer Runtime]
        ENV[Environment Manager]
        DEV[Device Manager]
    end

    subgraph "Processing Components"
        subgraph "Source"
            FS[filesrc]
            DEC[decodebin]
        end

        subgraph "AI Processing"
            ATT[gvaattachroi]
            DET[gvadetect]
            TRK[gvatrack]
            CLS[gvaclassify]
        end

        subgraph "Output"
            CNV[gvametaconvert]
            PUB[gvametapublish]
            TEE[tee]
            SINK[fakesink/fpsdisplaysink]
        end
    end

    subgraph "Performance Tools"
        BM[Benchmark Scripts]
        MC[Metrics Collection]
        AN[Analysis Tools]
    end

    CWC --> CL
    WPC --> CL
    CL --> PGL

    PGL --> GST
    GST --> ENV
    ENV --> DEV

    GST --> FS
    FS --> DEC
    DEC --> ATT
    ATT --> DET
    DET --> TRK
    TRK --> CLS
    CLS --> CNV
    CNV --> PUB
    CNV --> TEE
    TEE --> SINK

    GST --> BM
    BM --> MC
    MC --> AN
```

### Configuration Flow

```mermaid
flowchart LR
    subgraph "Configuration Files"
        CAM[camera_to_workload.json \n• Camera definitions \n• Workload assignments \n• ROI specifications]
        WORK[workload_to_pipeline.json \n• Pipeline steps \n• Model configurations \n• Device assignments]
    end

    subgraph "Processing"
        LOAD[Config Loader]
        NORM[Normalization]
        MERGE[Pipeline Consolidation]
    end

    subgraph "Output"
        GST[GStreamer Command]
        EXEC[Pipeline Execution]
    end

    CAM --> LOAD
    WORK --> LOAD
    LOAD --> NORM
    NORM --> MERGE
    MERGE --> GST
    GST --> EXEC
```

## Component Overview

### Core Components

#### 1. Pipeline Generator (`gst-pipeline-generator.py`)

**Purpose**: Dynamic GStreamer pipeline generation based on configuration
**Key Functions**:

- Configuration loading and validation
- Pipeline signature generation for optimization
- Dynamic element creation based on workload requirements
- Device-specific environment variable management

#### 2. Configuration Management

**Files**:

- `camera_to_workload.json`: Camera definitions and workload assignments
- `workload_to_pipeline.json`: Pipeline step definitions

#### 3. GStreamer Elements

**Source Elements**:

- `filesrc`: Video file input
- `decodebin`: Automatic video decoding

**AI Processing Elements**:

- `gvaattachroi`: Region of Interest attachment
- `gvadetect`: Object detection using YOLO models
- `gvatrack`: Object tracking across frames
- `gvaclassify`: Object classification using EfficientNet

**Output Elements**:

- `gvametaconvert`: Metadata format conversion
- `gvametapublish`: Results publishing to files
- `tee`: Pipeline branching for multiple outputs

#### Environment Configuration

Device-specific environment files:

- `/res/all-cpu.env`: CPU optimization settings
- `/res/all-gpu.env`: GPU acceleration settings
- `/res/all-npu.env`: NPU configuration

## Configuration Management

### Camera Configuration

```json
{
  "lane_config": {
    "cameras": [
      {
        "camera_id": "cam1",
        "fileSrc": "video-file.mp4",
        "width": 1920,
        "fps": 15,
        "workloads": ["detection", "classification"],
        "region_of_interest": {
          "x": 0.1,
          "y": 0.1,
          "x2": 0.9,
          "y2": 0.9
        }
      }
    ]
  }
}
```

### Workload Configuration

```json
{
  "workload_pipeline_map": {
    "detection": [
      {
        "type": "gvadetect",
        "model": "yolov5s",
        "device": "GPU",
        "precision": "FP16"
      }
    ],
    "classification": [
      {
        "type": "gvaclassify",
        "model": "efficientnet-b0",
        "device": "NPU",
        "precision": "INT8"
      }
    ]
  }
}
```

## System Benefits

### Performance Advantages

- **Hardware Optimization**: Native Intel hardware acceleration
- **Pipeline Efficiency**: Optimized GStreamer pipelines with minimal overhead
- **Parallel Processing**: Multi-camera, multi-workload concurrent execution
- **Resource Management**: Intelligent device allocation and load balancing

### Scalability Features

- **Configuration-Driven**: Easy addition of new cameras and workloads
- **Modular Design**: Independent processing pipelines
- **Container-Based**: Horizontal scaling with Docker orchestration
- **Performance Monitoring**: Real-time metrics for optimization

---

_This architecture documentation provides a comprehensive overview of the Loss Prevention Pipeline System. For implementation details, refer to the source code and configuration files in the repository._
