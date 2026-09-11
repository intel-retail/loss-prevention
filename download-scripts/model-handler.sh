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

ovms_model_ready() {
    local model_name="$1"
    local model_dir="$MODELS_PATH/ovms-model/$model_name"

    [[ -f "$model_dir/graph.pbtxt" ]] && ls "$model_dir"/*.xml >/dev/null 2>&1
}

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
    OVMS_MODEL_DIR="$MODELS_PATH/ovms-model/$MODEL_NAME"
    if ovms_model_ready "$MODEL_NAME"; then
        echo "[INFO] OVMS VLM model already exists at $OVMS_MODEL_DIR, skipping download."
    elif [[ -f "$SCRIPT_BASE_PATH/setup_ovms_vlm_model.sh" ]]; then
        echo "[INFO] ###### Exporting VLM model for OVMS: $MODEL_NAME ($PRECISION)"
        bash "$SCRIPT_BASE_PATH/setup_ovms_vlm_model.sh" "$MODEL_NAME" "$PRECISION" "${HUGGINGFACE_TOKEN:-}"
    else
        echo "[ERROR] Missing required script: $SCRIPT_BASE_PATH/setup_ovms_vlm_model.sh" >&2
        exit 1
    fi
elif [[ "$MODEL_NAME" == face-reidentification-retail-* || "$MODEL_NAME" == age-gender-recognition-retail-* ]] && [[ "$PRECISION" == "FP16" || "$PRECISION" == "FP32" ]]; then
    echo "[INFO] ###### Downloading face model: $MODEL_NAME ($PRECISION)"
    "$SCRIPT_BASE_PATH/omz-model-download.sh" "$MODEL_NAME" "$MODELS_PATH/object_classification" "$PRECISION"
elif [[ "$MODEL_NAME" == age-gender-recognition-retail-* ]] && [[ "$PRECISION" == "INT8" ]]; then
    echo "[INFO] ###### Downloading and quantizing face model: $MODEL_NAME ($PRECISION)"
    # First download the FP16 model if it doesn't exist
    if ! find "$MODELS_PATH" -type f -path "*/$MODEL_NAME/FP16/*.xml" | grep -q "$MODEL_NAME.xml"; then
        "$SCRIPT_BASE_PATH/omz-model-download.sh" "$MODEL_NAME" "$MODELS_PATH/object_classification" "FP16"
    else
        echo "[INFO] FP16 model for $MODEL_NAME already exists, skipping FP16 download."
    fi
    # Then quantize to INT8
    python3 "$SCRIPT_BASE_PATH/model_convert.py" quantize_age_gender_face_detection "$MODEL_NAME" "$MODELS_PATH/object_classification"
elif [[ "$MODEL_NAME" == efficientnet* ]]; then
    echo "[INFO] ###### Downloading classification model: $MODEL_NAME ($PRECISION)"
    python3 "$SCRIPT_BASE_PATH/effnetb0_download.py" "$MODEL_NAME" "$MODELS_PATH"
elif [[ "$MODEL_NAME" == face-detection-retail-* ]] && [[ "$PRECISION" == "FP16" || "$PRECISION" == "FP32" ]]; then
    echo "[INFO] ###### Downloading detection model: $MODEL_NAME ($PRECISION)"
   "$SCRIPT_BASE_PATH/omz-model-download.sh" "$MODEL_NAME" "$MODELS_PATH/object_detection" "$PRECISION"
elif [[ "$MODEL_NAME" == face-detection-retail-* ]] && [[ "$PRECISION" == "INT8" ]]; then
    echo "[INFO] ###### Downloading and quantizing detection model: $MODEL_NAME ($PRECISION)"
    # First download the FP16 model if it doesn't exist
    if ! find "$MODELS_PATH" -type f -path "*/$MODEL_NAME/FP16/*.xml" | grep -q "$MODEL_NAME.xml"; then
        "$SCRIPT_BASE_PATH/omz-model-download.sh" "$MODEL_NAME" "$MODELS_PATH/object_detection" "FP16"
    else
        echo "[INFO] FP16 model for $MODEL_NAME already exists, skipping FP16 download."
    fi
    # Then quantize to INT8
    python3 "$SCRIPT_BASE_PATH/model_convert.py" quantize_age_gender_face_detection "$MODEL_NAME" "$MODELS_PATH/object_detection"
else
    echo "[WARN] Unknown model type: $MODEL_NAME"
fi
