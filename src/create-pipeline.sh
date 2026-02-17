#!/bin/bash

# -----------------------------
# Pipeline Creation Script
# Creates the GStreamer pipeline file from configuration
# Usage: create-pipeline.sh [pipelines_directory] [pipeline_file_name]
# -----------------------------

set -euo pipefail

# -----------------------------
# Parse command line arguments
# -----------------------------
pipelines_dir="${1:-/home/pipeline-server/pipelines}"
pipeline_file_name="${2:-pipeline.sh}"
num_of_pipelines="${3:-1}"
echo "################# Using pipelines directory: $pipelines_dir ###################"
echo "################# Using pipeline file name: $pipeline_file_name ###################"
echo "################# Using number of pipelines: $num_of_pipelines ###################"

# -----------------------------
# Configuration & Environment
# -----------------------------
CAMERA_STREAM="${CAMERA_STREAM:-camera_to_workload.json}"
WORKLOAD_DIST="${WORKLOAD_DIST:-workload_to_pipeline.json}"
NUM_OF_PIPELINES="${num_of_pipelines}"

export CAMERA_STREAM
export WORKLOAD_DIST
export NUM_OF_PIPELINES

echo "################# Using camera config: $CAMERA_STREAM ###################"
echo "################# Using workload config: $WORKLOAD_DIST ###################"

export PYTHONPATH=/home/pipeline-server/src:$PYTHONPATH
# Use TIMESTAMP env variable if set, otherwise fallback to date
cid=$(date +%Y%m%d%H%M%S)$(date +%6N | cut -c1-6)
export TIMESTAMP=$cid
echo "===============TIMESTAMP===================: $TIMESTAMP"

gst_cmd=$(python3 "$(dirname "$0")/gst-pipeline-generator.py" "$NUM_OF_PIPELINES")    

# Exit container if gst_cmd is empty or whitespace
# Trim whitespace
trimmed_gst_cmd="$(echo "$gst_cmd" | tr -d '\n' | sed 's/[[:space:]]*$//')"

# Exit if gst_cmd is empty or only base stub
if [[ -z "$trimmed_gst_cmd" || "$trimmed_gst_cmd" == "gst-launch-1.0 --verbose \\" ]]; then
    echo "################# WARNING #################"
    echo "No workload is defined."
    echo "As a result, the generated GStreamer command is empty or invalid."
    echo "If this is not expected please check the workload configuration"
    echo "gst_cmd='$trimmed_gst_cmd'"
    echo "Stopping container........"
    exit 1
fi
echo "#############  GStreamer pipeline command generated successfully ##########"   

CONTAINER_NAME="${CONTAINER_NAME//\"/}" # Remove double quotes
cid="${cid}_${CONTAINER_NAME}"
echo "==================CONTAINER_NAME: ${CONTAINER_NAME}"
echo "cid: $cid"

echo "############# Generating GStreamer pipeline command ##########"
echo "################### RENDER_MODE ################# $RENDER_MODE"

# -----------------------------
# Prepare pipelines directory
# -----------------------------
mkdir -p "$pipelines_dir"

if [ -d "$pipelines_dir" ]; then
    echo "################# Pipelines directory exists: $pipelines_dir ###################"
else
    echo "################# ERROR: Failed to create pipelines directory: $pipelines_dir ###################"
fi

# Create pipeline.sh
pipeline_file="$pipelines_dir/$pipeline_file_name"
echo "################# Creating pipeline file: $pipeline_file ###################"
echo "#!/bin/bash" > "$pipeline_file"
echo "# Generated GStreamer pipeline command" >> "$pipeline_file"
echo "# Generated on: $(date)" >> "$pipeline_file"
echo "" >> "$pipeline_file"
echo "$gst_cmd" >> "$pipeline_file"
chmod +x "$pipeline_file"

if [ -f "$pipeline_file" ]; then
    echo "################# Pipeline file created successfully: $pipeline_file ###################"
    echo "################# File size: $(stat -c%s "$pipeline_file") bytes ###################"
else
    echo "################# ERROR: Failed to create pipeline file: $pipeline_file ###################"
    exit 1
fi

echo "################# Pipeline creation completed successfully ###################"
