 #!/bin/bash
#
# Copyright (C) 2024 Intel Corporation.
#
# SPDX-License-Identifier: Apache-2.0
#

PRE_PROCESS="${PRE_PROCESS:=""}" #""|pre-process-backend=vaapi-surface-sharing|pre-process-backend=vaapi-surface-sharing pre-process-config=VAAPI_FAST_SCALE_LOAD_FACTOR=1 
AGGREGATE="${AGGREGATE:="gvametaaggregate name=aggregate !"}" # Aggregate function at the end of the pipeline ex. "" | gvametaaggregate name=aggregate
PUBLISH="${PUBLISH:="name=destination file-format=2 file-path=/tmp/results/r$cid.jsonl"}" # address=localhost:1883 topic=inferenceEvent method=mqtt

ROI="${ROI:="0,0,400,400"}"

if [ "$RENDER_MODE" == "1" ]; then
    OUTPUT="${OUTPUT:="! videoconvert ! video/x-raw,format=I420 ! gvawatermark ! videoconvert ! fpsdisplaysink video-sink=ximagesink sync=true --verbose"}"
else
    OUTPUT="${OUTPUT:="! fpsdisplaysink video-sink=fakesink sync=true --verbose"}"
fi

echo "decode type $DECODE"
echo "Run person-detection pipeline on $DEVICE with batch size = $BATCH_SIZE"

gstLaunchCmd="GST_DEBUG=\"GST_TRACER:7\" GST_TRACERS=\"latency_tracer(flags=pipeline,interval=100)\" gst-launch-1.0 $inputsrc ! $DECODE ! gvaattachroi roi=$ROI ! gvadetect batch-size=$BATCH_SIZE model-instance-id=odmodel name=detection model=models/object_detection/person-detection-0200/FP16-INT8/person-detection-0200.xml threshold=.5 device=$DEVICE $PRE_PROCESS inference-region=1 ! $AGGREGATE gvametaconvert name=metaconvert add-empty-results=true ! gvametapublish name=destination file-format=2 file-path=/tmp/results/r$cid.jsonl $OUTPUT 2>&1 | tee >/tmp/results/gst-launch_$cid\"_gst\".log >(stdbuf -oL sed -n -e 's/^.*current: //p' | stdbuf -oL cut -d , -f 1 > /tmp/results/pipeline$cid.log)"

echo "$gstLaunchCmd"

eval $gstLaunchCmd