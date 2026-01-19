#!/bin/bash
#
# Copyright (C) 2025 Intel Corporation.
#
# SPDX-License-Identifier: Apache-2.0
#

set -euo pipefail

SCRIPT_BASE_PATH=/workspace/scripts/
MODELS_PATH="${MODELS_DIR:-/workspace/models}"
mkdir -p "$MODELS_PATH"
cd "$MODELS_PATH" || { echo "Failure to cd to $MODELS_PATH"; exit 1; }

if [[ "$MODEL_NAME" == yolo* ]]; then
    echo "[INFO] ###### Downloading YOLO model: $MODEL_NAME ($PRECISION)"
    python3 "$SCRIPT_BASE_PATH/model_convert.py" export_yolo "$MODEL_NAME" "$MODELS_PATH"

    quant_dataset="$MODELS_PATH/datasets/coco128.yaml"
    if [ ! -f "$quant_dataset" ]; then
        mkdir -p "$(dirname "$quant_dataset")"
        wget --no-check-certificate --timeout=30 --tries=2 \
            "https://raw.githubusercontent.com/ultralytics/ultralytics/v8.1.0/ultralytics/cfg/datasets/coco128.yaml" \
            -O "$quant_dataset"
    fi
    python3 "$SCRIPT_BASE_PATH/model_convert.py" quantize_yolo "$MODEL_NAME" "$quant_dataset" "$MODELS_PATH"
elif [[ "$MODEL_NAME" == Qwen* ]]; then
    echo "[INFO] ###### Downloading VLM model: $MODEL_NAME ($PRECISION)"    
    # Extract model name after "/" if present (e.g., Qwen/Qwen2.5-VL-7B-Instruct → Qwen2.5-VL-7B-Instruct)
    ACTUAL_MODEL_NAME="${MODEL_NAME##*/}"    
    # Check if model already exists
    MODEL_PATH="$MODELS_PATH/ov-model/$ACTUAL_MODEL_NAME/$PRECISION/openvino_language_model.xml"
    if [[ -d "$MODEL_PATH" ]]; then
        echo "[INFO] VLM model already exists at $MODEL_PATH, skipping download."
    elif [[ -f "$SCRIPT_BASE_PATH/compress_model.sh" ]]; then
        echo "[INFO] ###### Compressing VLM model: $MODEL_NAME ($PRECISION)"
        bash "$SCRIPT_BASE_PATH/compress_model.sh" "$MODEL_NAME" "$PRECISION" "${HUGGINGFACE_TOKEN:-}"
    fi
elif [[ "$MODEL_NAME" == face-reidentification-retail-* ]] || [[ "$MODEL_NAME" == age-gender-recognition-retail-* ]]; then
    echo "[INFO] ###### Downloading face model: $MODEL_NAME ($PRECISION)"
    "$SCRIPT_BASE_PATH/omz-model-download.sh" "$MODEL_NAME" "$MODELS_PATH/object_classification" "$PRECISION"
    echo "[INFO] ###### Downloading model_proc JSON for: $MODEL_NAME"
    MODEL_PROC_URL="https://raw.githubusercontent.com/open-edge-platform/dlstreamer/refs/heads/master/samples/gstreamer/model_proc/intel/${MODEL_NAME}.json"
    MODEL_PROC_PATH="$MODELS_PATH/object_classification/${MODEL_NAME}/${MODEL_NAME}.json"
    
    if [[ -f "$MODEL_PROC_PATH" ]]; then
        echo "[INFO] Model proc JSON already exists at $MODEL_PROC_PATH, skipping download"
    else
        if wget --no-check-certificate --timeout=30 --tries=2 "$MODEL_PROC_URL" -P "$(dirname "$MODEL_PROC_PATH")"; then
            echo "[INFO] Successfully downloaded model_proc JSON for $MODEL_NAME"
        else
            echo "[WARN] Failed to download model_proc JSON from $MODEL_PROC_URL"
            echo "[WARN] Model $MODEL_NAME may not work properly without model_proc configuration"
        fi
    fi
elif [[ "$MODEL_NAME" == efficientnet* ]]; then
    echo "[INFO] ###### Downloading classification model: $MODEL_NAME ($PRECISION)"
    python3 "$SCRIPT_BASE_PATH/effnetb0_download.py" "$MODEL_NAME" "$MODELS_PATH"
elif [[ "$MODEL_NAME" == face-detection-retail-* ]]; then
    echo "[INFO] ###### Downloading detection model: $MODEL_NAME ($PRECISION)"
   "$SCRIPT_BASE_PATH/omz-model-download.sh" "$MODEL_NAME" "$MODELS_PATH/object_detection" "$PRECISION"   
    echo "[INFO] ###### Downloading model_proc JSON for: $MODEL_NAME"
    MODEL_PROC_URL="https://raw.githubusercontent.com/open-edge-platform/dlstreamer/refs/heads/master/samples/gstreamer/model_proc/intel/${MODEL_NAME}.json"
    MODEL_PROC_PATH="$MODELS_PATH/object_detection/${MODEL_NAME}/${MODEL_NAME}.json"
    
    if [[ -f "$MODEL_PROC_PATH" ]]; then
        echo "[INFO] Model proc JSON already exists at $MODEL_PROC_PATH, skipping download"
    else
        if wget --no-check-certificate --timeout=30 --tries=2 "$MODEL_PROC_URL" -P "$(dirname "$MODEL_PROC_PATH")"; then
            echo "[INFO] Successfully downloaded model_proc JSON for $MODEL_NAME"
        else
            echo "[WARN] Failed to download model_proc JSON from $MODEL_PROC_URL"
            echo "[WARN] Model $MODEL_NAME may not work properly without model_proc configuration"
        fi
    fi
else
    echo "[WARN] Unknown model type: $MODEL_NAME"
fi