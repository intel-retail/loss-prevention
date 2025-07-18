#!/bin/bash
#
# Copyright (C) 2025 Intel Corporation.
#
# SPDX-License-Identifier: Apache-2.0
#

# Get dynamic gst-launch command from Python script
set -eo pipefail

# Use TIMESTAMP env variable if set, otherwise fallback to date
cid=$(date +%Y%m%d%H%M%S)$(date +%6N | cut -c1-6)
export TIMESTAMP=$cid
echo "===============TIMESTAMP===================: $TIMESTAMP"
CONTAINER_NAME="${CONTAINER_NAME//\"/}" # Ensure to remove all double quotes from CONTAINER_NAME
cid="${cid}"_${CONTAINER_NAME}
echo "==================CONTAINER_NAME: ${CONTAINER_NAME}"
echo "cid: $cid"

echo "############# Generating GStreamer pipeline command ##########"
echo "################### RENDER_MODE #################"$RENDER_MODE 
gst_cmd=$(python3 "$(dirname "$0")/gst-pipeline-generator.py")
echo "#############  GStreamer pipeline command generated succussfully ##########"

# Generate timestamp for log files


# Create pipelines directory if it doesn't exist (use absolute path)
pipelines_dir="/home/pipeline-server/pipelines"
mkdir -p "$pipelines_dir"

# Debug: Check if directory was created
if [ -d "$pipelines_dir" ]; then
    echo "################# Pipelines directory exists: $pipelines_dir ###################"
else
    echo "################# ERROR: Failed to create pipelines directory: $pipelines_dir ###################"
fi

# Create pipeline.sh file with the generated command
pipeline_file="$pipelines_dir/pipeline.sh"
echo "################# Creating pipeline file: $pipeline_file ###################"

echo "#!/bin/bash" > "$pipeline_file"
echo "# Generated GStreamer pipeline command" >> "$pipeline_file"
echo "# Generated on: $(date)" >> "$pipeline_file"
echo "" >> "$pipeline_file"
echo "$gst_cmd" >> "$pipeline_file"

# Make the pipeline file executable
chmod +x "$pipeline_file"

# Debug: Check if file was created
if [ -f "$pipeline_file" ]; then
    echo "################# Pipeline file created successfully: $pipeline_file ###################"
    echo "################# File size: $(stat -c%s "$pipeline_file") bytes ###################"
else
    echo "################# ERROR: Failed to create pipeline file: $pipeline_file ###################"
fi

# Append logging pipeline to gst_cmd with proper line breaks
gst_cmd=$(printf "%s \\\\\n\\\\\n%s" "$gst_cmd" "2>&1 | tee /home/pipeline-server/results/gst-launch_\$cid.log | (stdbuf -oL sed -n -E 's/.*total=([0-9]+\.[0-9]+) fps.*/\1/p' > /home/pipeline-server/results/pipeline\$cid.log)")

# Print and run the pipeline command
echo "################# Running Pipeline ###################"
echo "GST_DEBUG=\"GST_TRACER:7\" GST_TRACERS='latency_tracer(flags=pipeline)' $gst_cmd"
eval "GST_DEBUG=\"GST_TRACER:7\" GST_TRACERS='latency_tracer(flags=pipeline)' $gst_cmd"

echo "############# GST COMMAND COMPLETED SUCCESSFULLY #############"
