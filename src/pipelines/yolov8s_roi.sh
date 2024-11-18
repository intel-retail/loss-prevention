 #!/bin/bash
#
# Copyright (C) 2024 Intel Corporation.
#
# SPDX-License-Identifier: Apache-2.0
#

PRE_PROCESS="${PRE_PROCESS:=""}" #""|pre-process-backend=vaapi-surface-sharing|pre-process-backend=vaapi-surface-sharing pre-process-config=VAAPI_FAST_SCALE_LOAD_FACTOR=1 
AGGREGATE="${AGGREGATE:="gvametaaggregate name=aggregate !"}" # Aggregate function at the end of the pipeline ex. "" | gvametaaggregate name=aggregate
PUBLISH="${PUBLISH:="name=destination file-format=2 file-path=/tmp/results/r$cid.jsonl"}" # address=localhost:1883 topic=inferenceEvent method=mqtt

CLASS_IDS="46,39,47" # YOLOv8 classes to be detected example "0,1,30"
MQTT_HOST="127.0.0.1:1883"
ROI="BASKET,BAGGING"

if [ "$RENDER_MODE" == "1" ]; then
    OUTPUT="${OUTPUT:="! videoconvert ! gvawatermark ! videoconvert ! fpsdisplaysink video-sink=ximagesink sync=true --verbose"}"
else
    OUTPUT="${OUTPUT:="! fpsdisplaysink video-sink=fakesink sync=true --verbose"}"
fi

echo "decode type $DECODE"
echo "Run YOLOv8 pipeline with ROI and Filtering on $DEVICE with batch size = $BATCH_SIZE"

gstLaunchCmd="GST_DEBUG=1 GST_TRACERS=\"latency_tracer(flags=pipeline,interval=100)\" gst-launch-1.0 $inputsrc ! $DECODE ! gvaattachroi mode=1 file-path=/home/pipeline-server/pipelines/roi.json ! gvadetect batch-size=$BATCH_SIZE model-instance-id=odmodel name=detection model=models/object_detection/yolov8s/FP32/yolov8s.xml device=$DEVICE $PRE_PROCESS inference-region=1 object-class="$ROI" threshold=0.5 ! \
gvapython module=/home/pipeline-server/extensions/object_filter.py class=ObjectDetectionFilter kwarg=\"{\\\"class_ids\\\": \\\"$CLASS_IDS\\\", \\\"rois\\\": \\\"$ROI\\\"}\" !  gvatrack ! \
$AGGREGATE gvametaconvert name=metaconvert add-empty-results=true ! \
gvapython module=/home/pipeline-server/extensions/gva_roi_metadata.py class=RoiMetadata kwarg=\"{\\\"rois\\\": \\\"$ROI\\\"}\" ! \
gvametapublish method=mqtt file-format=2 address="$MQTT_HOST" mqtt-client-id=yolov8 topic=event/detection ! \
queue ! \
gvametapublish name=destination file-format=2 file-path=/tmp/results/r$cid.jsonl $OUTPUT 2>&1 | tee >/tmp/results/gst-launch_$cid.log >(stdbuf -oL sed -n -e 's/^.*current: //p' | stdbuf -oL cut -d , -f 1 > /tmp/results/pipeline$cid.log)"


echo "$gstLaunchCmd"

eval $gstLaunchCmd