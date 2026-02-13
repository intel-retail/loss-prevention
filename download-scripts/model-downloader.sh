#!/bin/bash
set -euo pipefail

SCRIPT_BASE_PATH=/workspace/scripts
MODELS_PATH="${MODELS_DIR:-/workspace/models}"
CONFIG_JSON="/workspace/configs/${WORKLOAD_DIST:-}"

echo "[INFO] WORKLOAD_DIST in: $WORKLOAD_DIST"
echo "[INFO] CONFIG_JSON in: $CONFIG_JSON"

mkdir -p "$MODELS_PATH"

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
            VLM_PRECISION=$(jq -r '.vlm_precision // "int8"' <<< "$entry")
            
            export MODEL_NAME="$VLM_MODEL"
            export PRECISION="$VLM_PRECISION"

            echo "[INFO] VLM | $MODEL_NAME | $PRECISION"
        else
            # ---- Non-VLM handling ----
            MODEL=$(jq -r '.model' <<< "$entry")
            PRECISION=$(jq -r '.precision // "FP16"' <<< "$entry")
           
            export MODEL_NAME="$MODEL"
            export PRECISION="$PRECISION"

            echo "[INFO] $TYPE | $MODEL | $PRECISION"
        fi

        # Skip if already exists
        if find "$MODELS_PATH" -type f -path "*/$MODEL_NAME/*.xml" | grep -q "$MODEL_NAME.xml"; then
            echo "[INFO] Model $MODEL_NAME already exists, skipping"
            continue
        fi

        bash "$SCRIPT_BASE_PATH/model-handler.sh"
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
