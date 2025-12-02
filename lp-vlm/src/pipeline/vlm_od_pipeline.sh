#!/usr/bin/env bash
set -euo pipefail

VIDEO_NAME="${VIDEO_NAME:-""}"
INPUT_DIR="${INPUT_DIR:-"/home/pipeline-server/lp-vlm/sample-media"}"
MODEL_PATH="/home/pipeline-server/lp-vlm/models"

echo "VIDEO_NAME from env:" $VIDEO_NAME

if [ -z "$VIDEO_NAME" ] || [ ! -f "$INPUT_DIR/$VIDEO_NAME" ]; then
  echo "Error: VIDEO_NAME is not set or file does not exist: $INPUT_DIR/$VIDEO_NAME"
  exit 1
fi

echo "Starting Object Detection pipeline for video: $INPUT_DIR/$VIDEO_NAME"

export GST_DEBUG=4

time gst-launch-1.0 --verbose \
  filesrc location="$INPUT_DIR/$VIDEO_NAME" ! \
  decodebin3 ! videoconvert ! videorate ! \
  video/x-raw,format=BGR,framerate=13/1 ! \
  gvaattachroi roi=600,30,1300,1000 ! queue ! \
  gvadetect model-instance-id=detect1_1 name=items_in_basket_cam1 batch-size=1 inference-region=1 \
    model=$MODEL_PATH/object_detection/yolo11n/INT8/yolo11n.xml \
    device=CPU threshold=0.4 pre-process-backend=opencv \
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
