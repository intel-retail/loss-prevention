#!/usr/bin/env bash
set -euo pipefail

VIDEO_NAME="${VIDEO_NAME:-""}"
INPUT_DIR="${INPUT_DIR:-"/home/pipeline-server/lp-vlm/sample-media"}"
MODEL_PATH="/home/pipeline-server/lp-vlm/models"
WORKLOAD_PIPELINE_CONFIG="/home/pipeline-server/lp-vlm/configs/"$WORKLOAD_DIST


echo "VIDEO_NAME from env:" $VIDEO_NAME
echo "WORKLOAD_DIST from env:" $WORKLOAD_DIST
echo "CONFIG_PATH set to:" $WORKLOAD_PIPELINE_CONFIG

WORKLOAD_NAME=lp_vlm

# Parse workload config to get model and precision
if [ ! -f "$WORKLOAD_PIPELINE_CONFIG" ]; then
  echo "Error: Workload config file not found: $WORKLOAD_PIPELINE_CONFIG"
  exit 1
fi

echo "📄 Parsing workload config for workload: $WORKLOAD_NAME"

# Extract model and precision using jq (or python fallback)
if command -v jq >/dev/null 2>&1; then
  MODEL_NAME=$(jq -r --arg workload "$WORKLOAD_NAME" \
    '.workload_pipeline_map[$workload][0].model // empty' "$WORKLOAD_PIPELINE_CONFIG")
  PRECISION=$(jq -r --arg workload "$WORKLOAD_NAME" \
    '.workload_pipeline_map[$workload][0].precision // empty' "$WORKLOAD_PIPELINE_CONFIG")
  DEVICE=$(jq -r --arg workload "$WORKLOAD_NAME" \
    '.workload_pipeline_map[$workload][0].device // "CPU"' "$WORKLOAD_PIPELINE_CONFIG")
else
  # Fallback to python if jq not available
  MODEL_NAME=$(python3 -c "import json,sys; data=json.load(open('$WORKLOAD_PIPELINE_CONFIG')); print(data['workload_pipeline_map'].get('$WORKLOAD_NAME',[{}])[0].get('model',''))")
  PRECISION=$(python3 -c "import json,sys; data=json.load(open('$WORKLOAD_PIPELINE_CONFIG')); print(data['workload_pipeline_map'].get('$WORKLOAD_NAME',[{}])[0].get('precision',''))")
  DEVICE=$(python3 -c "import json,sys; data=json.load(open('$WORKLOAD_PIPELINE_CONFIG')); print(data['workload_pipeline_map'].get('$WORKLOAD_NAME',[{}])[0].get('device','CPU'))")
fi

# Validate extracted values
if [ -z "$MODEL_NAME" ] || [ -z "$PRECISION" ]; then
  echo "❌ Error: Could not extract model or precision for workload '$WORKLOAD_NAME' from config"
  echo "Model: $MODEL_NAME, Precision: $PRECISION, Device: $DEVICE"
  exit 1
fi

echo "✅ Extracted from config:"
echo "   Model: $MODEL_NAME"
echo "   Precision: $PRECISION"
echo "   Device: $DEVICE"
echo "   ROI Coordinates: $ROI_COORDINATES"

# Construct model path
MODEL_FULL_PATH="$MODEL_PATH/object_detection/$MODEL_NAME/$PRECISION/$MODEL_NAME.xml"

if [ ! -f "$MODEL_FULL_PATH" ]; then
  echo "❌ Error: Model file not found: $MODEL_FULL_PATH"
  exit 1
fi

echo "🔍 Using model: $MODEL_FULL_PATH"

if [ -z "$VIDEO_NAME" ] || [ ! -f "$INPUT_DIR/$VIDEO_NAME" ]; then
  echo "Error: VIDEO_NAME is not set or file does not exist: $INPUT_DIR/$VIDEO_NAME"
  exit 1
fi

echo "Starting Object Detection pipeline for video: $INPUT_DIR/$VIDEO_NAME"

export GST_DEBUG=4

# Build ROI element conditionally
if [ -n "$ROI_COORDINATES" ] && [ "$ROI_COORDINATES" != ",,," ]; then
  ROI_ELEMENT="gvaattachroi roi=$ROI_COORDINATES ! queue !"
  echo "🎯 Using ROI: $ROI_COORDINATES"
else
  ROI_ELEMENT="queue !"
  echo "⚠️  No ROI specified, processing full frame"
fi

time gst-launch-1.0 --verbose \
  filesrc location="$INPUT_DIR/$VIDEO_NAME" ! \
  decodebin3 ! videoconvert ! videorate ! \
  video/x-raw,format=BGR,framerate=13/1 ! \
  ${ROI_ELEMENT} \
  gvadetect model-instance-id=detect1_1 name=lp-vlm batch-size=1 inference-region=1 \
    model=$MODEL_FULL_PATH \
    device=$DEVICE threshold=0.4 pre-process-backend=opencv \
    ie-config=CPU_THROUGHPUT_STREAMS=2 nireq=2 \
    pre-process-config=resize_type=standard ! \
  queue ! gvametaconvert format=json ! queue ! \
  gvapython class=Publisher function=process module=/home/pipeline-server/lp-vlm/gvapython/publish.py name=publish ! \
  gvawatermark ! queue ! fakesink sync=false async=false

# --- Capture exit code ---
EXIT_CODE=$?
echo "🔴 Pipeline finished with exit code: $EXIT_CODE"

# --- Send end message using your new Python script ---
echo "📨 Sending end message using send_end_message.py..."
python3 /home/pipeline-server/lp-vlm/gvapython/send_end_message.py

echo "✅ Pipeline processing completed."
