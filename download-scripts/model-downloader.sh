#!/bin/bash
set -euo pipefail

SCRIPT_BASE_PATH=/workspace/scripts
MODELS_PATH="${MODELS_DIR:-/workspace/models}"
CONFIG_JSON="/workspace/configs/${WORKLOAD_DIST:-}"

echo "[INFO] WORKLOAD_DIST in: $WORKLOAD_DIST"
echo "[INFO] CONFIG_JSON in: $CONFIG_JSON"

mkdir -p "$MODELS_PATH"

ovms_model_ready() {
    local model_name="$1"
    local model_dir="$MODELS_PATH/ovms-model/$model_name"

    [[ -f "$model_dir/graph.pbtxt" ]] && ls "$model_dir"/*.xml >/dev/null 2>&1
}

model_ready() {
    local model_dir="$MODELS_PATH/$1/$MODEL_NAME"
    [[ -s "$model_dir/$PRECISION/$MODEL_NAME.xml" &&
       -s "$model_dir/$PRECISION/$MODEL_NAME.bin" ]] || return 1
    if [[ "$MODEL_NAME" == age-gender-recognition-retail-* ||
          "$MODEL_NAME" == face-detection-retail-* ||
          "$MODEL_NAME" == face-reidentification-retail-* ]]; then
        [[ -s "$model_dir/$MODEL_NAME.json" ]] || return 1
    fi
    return 0
}

############################################
# MODE 1: JSON-driven (bulk download)
############################################
if [[ -n "${WORKLOAD_DIST:-}" && -f "$CONFIG_JSON" ]]; then
    echo "[INFO] Using workload JSON: $CONFIG_JSON"

    jq -c '.workload_pipeline_map[] | .[]' "$CONFIG_JSON" | while read -r entry; do
        TYPE=$(jq -r '.type' <<< "$entry")

        if [[ "$TYPE" == "vlm" ]]; then
            # ---- VLM handling ----
            VLM_MODEL=$(jq -r '.vlm_model' <<< "$entry")
            VLM_DEVICE=$(jq -r '.vlm_device // empty' <<< "$entry")
            VLM_PRECISION=$(jq -r '.vlm_precision // "int8"' <<< "$entry")
            MODEL=$(jq -r '.model' <<< "$entry")
            MODEL_PRECISION=$(jq -r '.precision // "FP16"' <<< "$entry")
            
            # Download VLM model
            export MODEL_NAME="$VLM_MODEL"
            export PRECISION="$VLM_PRECISION"
            if [[ -n "$VLM_DEVICE" && "$VLM_DEVICE" != "null" ]]; then
                export VLM_DEVICE
            else
                unset VLM_DEVICE || true
            fi

            echo "[INFO] VLM | $MODEL_NAME | $PRECISION"
            
            # Skip if already exists
            if ovms_model_ready "$MODEL_NAME"; then
                echo "[INFO] VLM Model $MODEL_NAME already exists, skipping"
            else
                bash "$SCRIPT_BASE_PATH/model-handler.sh"
            fi
            
            # Download detection model if it exists and is not null/empty
            if [[ "$MODEL" != "null" && -n "$MODEL" ]]; then
                export MODEL_NAME="$MODEL"
                export PRECISION="$MODEL_PRECISION"

                echo "[INFO] VLM Detection Model | $MODEL_NAME | $PRECISION"
                
                # Skip if already exists
                if model_ready object_detection; then
                    echo "[INFO] Detection Model $MODEL_NAME already exists, skipping"
                else
                    bash "$SCRIPT_BASE_PATH/model-handler.sh"
                fi
            fi
        else
            # ---- Non-VLM handling ----
            MODEL=$(jq -r '.model' <<< "$entry")
            PRECISION=$(jq -r '.precision // "FP16"' <<< "$entry")
           
            export MODEL_NAME="$MODEL"
            export PRECISION="$PRECISION"

            echo "[INFO] $TYPE | $MODEL | $PRECISION"
            
            # Skip if already exists
            MODEL_SUBDIR=object_classification
            if [[ "$TYPE" == "gvadetect" ]]; then
                MODEL_SUBDIR=object_detection
            fi
            if model_ready "$MODEL_SUBDIR"; then
                echo "[INFO] Model $MODEL_NAME already exists, skipping"
                continue
            fi

            bash "$SCRIPT_BASE_PATH/model-handler.sh"
        fi
    done

############################################
# MODE 2: Single model (env-driven)
############################################
elif [[ -n "${MODEL_NAME:-}" ]]; then    
    echo "[INFO] Single model mode: $MODEL_NAME"
    bash "$SCRIPT_BASE_PATH/model-handler.sh"
else
    echo "[ERROR] No valid input provided"
    echo "Use either:"
    echo "  - WORKLOAD_DIST=<json file>"
    echo "  - MODEL_NAME (+ optional MODEL_TYPE, PRECISION)"
    exit 1
fi

############################################
# Final step: fix ownership for host user
############################################
if [[ -n "${LOCAL_UID:-}" && -n "${LOCAL_GID:-}" ]]; then
    echo "[INFO] Adjusting ownership of downloaded models to ${LOCAL_UID}:${LOCAL_GID}"
    chown -R "${LOCAL_UID}:${LOCAL_GID}" "${MODELS_PATH}" 2>/dev/null || \
      echo "[WARN] Unable to chown models directory; continuing."
else
    echo "[INFO] LOCAL_UID/LOCAL_GID not set; skipping ownership adjustment"
fi
