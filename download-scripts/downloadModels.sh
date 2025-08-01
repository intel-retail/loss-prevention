#!/bin/bash
#
# Copyright (C) 2025 Intel Corporation.
#
# SPDX-License-Identifier: Apache-2.0
#

set -euo pipefail

SCRIPT_BASE_PATH=/workspace/scripts/
# MODELS_PATH is set to /workspace/models by default, matching the container mount
MODELS_PATH="${MODELS_DIR:-/workspace/models}"
mkdir -p "$MODELS_PATH"
cd "$MODELS_PATH" || { echo "Failure to cd to $MODELS_PATH"; exit 1; }

pwd 

# Path to workload_to_pipeline.json
CONFIG_JSON="/workspace/configs/workload_to_pipeline.json"

# Check for jq
if ! command -v jq &>/dev/null; then
    echo "[ERROR] jq is required but not installed. Please install jq." >&2
    exit 1
fi

# Extract all type/model pairs from the JSON
mapfile -t MODEL_DATA < <(jq -r '
  .workload_pipeline_map[] | 
  .[] | 
  [.type, .model, .device, .precision] | @tsv
' "$CONFIG_JSON" | sort -u)

echo "[INFO] Found ${#MODEL_DATA[@]} model configurations to process."

declare -A TYPE_MODELS

# Build associative array: TYPE_MODELS[type]="model1,model2,..."
for DATA in "${MODEL_DATA[@]}"; do
    TYPE_RAW="$(echo "$DATA" | cut -f1)"
    MODEL_NAME_RAW="$(echo "$DATA" | cut -f2)"
    DEVICE="$(echo "$DATA" | cut -f3)"
    PRECISION="$(echo "$DATA" | cut -f4)"
    
    MODEL_NAME="${MODEL_NAME_RAW%.xml}"
    TYPE_KEY="$(echo "$TYPE_RAW" | tr '[:upper:]' '[:lower:]')"
    ENTRY="$MODEL_NAME"
    
    if [[ -z "${TYPE_MODELS[$TYPE_KEY]+x}" ]]; then
        TYPE_MODELS[$TYPE_KEY]="$ENTRY"
    else
        # Only add if not already present
        if [[ ",${TYPE_MODELS[$TYPE_KEY]}," != *",$ENTRY,"* ]]; then
            TYPE_MODELS[$TYPE_KEY]+=",$ENTRY"
        fi
    fi
done

echo "####### MODEL_TYPES ====  "${!TYPE_MODELS[@]}""

for TYPE_KEY in "${!TYPE_MODELS[@]}"; do
    IFS=',' read -ra MODELS <<< "${TYPE_MODELS[$TYPE_KEY]}"
    for MODEL_NAME in "${MODELS[@]}"; do
        MODEL_PATH="$MODELS_PATH/$MODEL_NAME"
        if [ -e "$MODEL_PATH" ]; then
            echo "[INFO] ########## $MODEL_NAME already exists, skipping download."
            continue
        fi
        echo "[INFO] ########### Processing $MODEL_NAME ($TYPE_KEY) ..."
        PRECISION="INT8"
        MODEL_XML_PATH=""
        case "$TYPE_KEY" in
            gvadetect|object_detection)
                PRECISION=$(jq -r --arg model "$MODEL_NAME" '
                  .workload_pipeline_map[] | 
                  .[] | 
                  select(.model == $model and .type == "gvadetect") | 
                  .precision // "INT8"
                ' "$CONFIG_JSON" | head -1)
                MODEL_XML_PATH="$MODELS_PATH/object_detection/$MODEL_NAME/$PRECISION/$MODEL_NAME.xml"
                ;;
            gvaclassify|object_classification)
                PRECISION=$(jq -r --arg model "$MODEL_NAME" '
                  .workload_pipeline_map[] | 
                  .[] | 
                  select(.model == $model and .type == "gvaclassify") | 
                  .precision // "INT8"
                ' "$CONFIG_JSON" | head -1)
                MODEL_XML_PATH="$MODELS_PATH/object_classification/$MODEL_NAME/$PRECISION/$MODEL_NAME.xml"
                ;;
            gvainference)
                MODEL_XML_PATH="$MODELS_PATH/object_classification/$MODEL_NAME/$PRECISION/$MODEL_NAME.xml"
                ;;
        esac
        # Default to INT8 if no precision found
        if [[ -z "$PRECISION" || "$PRECISION" == "null" ]]; then
            PRECISION="INT8"
        fi
        echo "[INFO] ########### Using precision: $PRECISION for model: $MODEL_NAME #########"
        if [ -f "$MODEL_XML_PATH" ]; then
            echo "[INFO] ###### Model $MODEL_NAME with precision $PRECISION already exists at $MODEL_XML_PATH, skipping download."
            continue
        fi
        # Download logic
        if [[ "$TYPE_KEY" == "gvadetect" || "$TYPE_KEY" == "object_detection" ]]; then
            if [[ "$MODEL_NAME" == face-detection-retail-* ]]; then
                echo "[INFO] ######  Downloading face model: $MODEL_NAME using face-model-download.sh"
                "$SCRIPT_BASE_PATH/face-model-download.sh" "$MODEL_NAME" "$MODELS_PATH/object_detection"
            else
                echo "[INFO] ######  Downloading and converting model: $MODEL_NAME"
                python3 "$SCRIPT_BASE_PATH/model_convert.py" export_yolo "$MODEL_NAME" "$MODELS_PATH"
                # Quantize if needed
                quant_dataset="$MODELS_PATH/datasets/coco128.yaml"
                if [ ! -f "$quant_dataset" ]; then
                    mkdir -p "$(dirname "$quant_dataset")"
                    wget --no-check-certificate --timeout=30 --tries=2 "https://raw.githubusercontent.com/ultralytics/ultralytics/v8.1.0/ultralytics/cfg/datasets/coco128.yaml" -O "$quant_dataset"
                fi
                python3 "$SCRIPT_BASE_PATH/model_convert.py" quantize_yolo "$MODEL_NAME" "$quant_dataset" "$MODELS_PATH"
            fi
        elif [[ "$TYPE_KEY" == "gvaclassify" || "$TYPE_KEY" == "object_classification" ]]; then
            if [[ "$MODEL_NAME" == face-reidentification-retail-* ]]; then
                echo "[INFO] ######  Downloading face reidentification model: $MODEL_NAME using face-model-download.sh"
                "$SCRIPT_BASE_PATH/face-model-download.sh" "$MODEL_NAME" "$MODELS_PATH/object_classification"
            else
                python3 "$SCRIPT_BASE_PATH/efnetv2b0_download_quant.py" "$MODEL_NAME" "$MODELS_PATH"
            fi
        elif [[ "$TYPE_KEY" == "gvainference" ]]; then
            echo "[INFO] ######  Downloading face reidentification model: $MODEL_NAME using face-model-download.sh"
            "$SCRIPT_BASE_PATH/face-model-download.sh" "$MODEL_NAME" "$MODELS_PATH/object_classification"
            echo "[WARN] Unsupported type: $TYPE_KEY, skipping..."
        fi
    done
done




echo "###################### Model downloading has been completed successfully #########################"
