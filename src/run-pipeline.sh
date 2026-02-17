#!/bin/bash

# -----------------------------
# Pipeline Execution Script
# Creates pipeline first, then runs it and captures results
# Usage: run-pipeline.sh [pipelines_directory] [pipeline_file_name]
# -----------------------------

set -euo pipefail

echo ">>>>>>>>>>>>> VLM_WORKLOAD_ENABLED=${VLM_WORKLOAD_ENABLED} <<<<<<<<<<<<<<<"
echo ">>>>>>>>>>>>> DEBUG: Environment variables related to PIPELINE <<<<<<<<<<<<<<<"
env | grep -i pipeline || echo "No PIPELINE variables found"
echo ">>>>>>>>>>>>> DEBUG: All environment variables <<<<<<<<<<<<<<<"
env | sort
#sleep 2h
if [ "${VLM_WORKLOAD_ENABLED}" = "0" ]; then
    # Parse command line arguments
    pipelines_dir="${1:-/home/pipeline-server/pipelines}"
    pipeline_file_name="${2:-pipeline.sh}"
    num_of_pipelines=${PIPELINE_COUNT:-1}
    echo "################# Using pipelines directory: $pipelines_dir ###################"
    echo "################# Using pipeline file name: $pipeline_file_name ###################"
    echo "################# Using number of pipelines: $num_of_pipelines ###################"
    
    # First, create the pipeline
    echo "################# Step 1: Creating Pipeline ###################"
    bash "$(dirname "$0")/create-pipeline.sh" "$pipelines_dir" "$pipeline_file_name" "$num_of_pipelines"
    
    if [ $? -ne 0 ]; then
        echo "################# ERROR: Pipeline creation failed ###################"
        exit 1
    fi
    
    echo "################# Step 2: Running Pipeline ###################"
    # Use TIMESTAMP env variable if set, otherwise fallback to date
    cid=$(date +%Y%m%d%H%M%S)$(date +%6N | cut -c1-6)
    export TIMESTAMP=$cid
    echo "===============TIMESTAMP===================: $TIMESTAMP"

    CONTAINER_NAME="${CONTAINER_NAME//\"/}" # Remove double quotes
    cid="${cid}_${CONTAINER_NAME}"
    echo "==================CONTAINER_NAME: ${CONTAINER_NAME}"
    echo "cid: $cid"

    # Check if pipeline file exists
    pipeline_file="$pipelines_dir/$pipeline_file_name"
    if [ ! -f "$pipeline_file" ]; then
        echo "################# ERROR: Pipeline file not found: $pipeline_file ###################"
        echo "Please run create-pipeline.sh first to generate the pipeline file."
        exit 1
    fi

    # -----------------------------
    # Prepare result directory
    # -----------------------------
    results_dir="/home/pipeline-server/results"
    mkdir -p "$results_dir"

    # Count source elements (filesrc or rtspsrc) to determine number of streams
    source_count=$(grep -E -i -c "(filesrc|rtspsrc)" "$pipeline_file" || echo "0")
    echo "Found $source_count source elements in $pipeline_file"
    
    # DEBUG: Print first few lines of pipeline file to understand format
    echo "===== DEBUG: First 5 lines of pipeline file ====="
    head -5 "$pipeline_file"
    echo "===== DEBUG: Lines containing rtspsrc or filesrc ====="
    grep -i -E "(rtspsrc|filesrc)" "$pipeline_file" || echo "No matches found"
    echo "================================================="

    # Extract stream identifiers from source elements
    declare -a source_names
    while IFS= read -r line; do
        # Match rtspsrc name=... or filesrc name=... (name comes before location)
        if [[ "$line" =~ (rtspsrc|filesrc)[[:space:]]+name=([^[:space:]]+) ]]; then
            # Extract the name value
            name="${BASH_REMATCH[2]}"
            source_names+=("$name")
        fi
    done < "$pipeline_file"

    echo "Extracted stream names: ${source_names[*]}"
    # Create per-stream pipeline log files using extracted names
    declare -a pipeline_logs
    pipeline_logs=()  # Initialize as empty array to prevent unbound variable error
    for i in "${!source_names[@]}"; do
        name="${source_names[i]}"
        # Sanitize name for filename
        safe_name=$(echo "$name" | tr -cd '[:alnum:]_-')
        # Updated filename pattern: pipeline_stream<i>_safe_name_timestamp.log
        logfile="$results_dir/pipeline_stream${i}_${cid}.log"
        #logfile="$results_dir/pipeline${cid}_${safe_name}.log"
        pipeline_logs+=("$logfile")
        > "$logfile"  # empty the file
        echo "Created log file: $logfile"
    done

    # Set GStreamer tracing environment
    export GST_DEBUG="GST_TRACER:7"
    export GST_TRACERS="latency(flags=pipeline)"
    export GST_VAAPI_INIT_DRM_DEVICE=/dev/dri/renderD128

    echo "Running with tracing enabled:"
    echo "GST_DEBUG=$GST_DEBUG"
    echo "GST_TRACERS=$GST_TRACERS"
    echo "GST_VAAPI_INIT_DRM_DEVICE=$GST_VAAPI_INIT_DRM_DEVICE"

    # -----------------------------
    # Run pipeline and capture FPS
    # -----------------------------
    gst_log="$results_dir/gst-launch_$cid.log"
    echo "################# Running Pipeline ###################"
    echo "GST_DEBUG=\"GST_TRACER:7\" GST_TRACERS='latency_tracer(flags=pipeline)' bash $pipeline_file"

    gst_log="$results_dir/gst-launch_$cid.log"

    # Run gst-launch in background and tee to log
    stdbuf -oL bash "$pipeline_file" 2>&1 | tee "$gst_log" &
    GST_PID=$!

    # Read the gst log file in "tail -F" mode
    tail -F "$gst_log" | while read -r line; do
        # Match only FpsCounter(last ...) lines (ignore 'average' lines)
        if [[ "$line" =~ FpsCounter\(last.*number-streams=([0-9]+) ]]; then
            num_streams="${BASH_REMATCH[1]}"
            if [[ "$num_streams" -eq "$source_count" ]]; then
                if [[ "$num_streams" -eq 1 ]]; then
                    if [[ "$line" =~ per-stream=([0-9]+\.[0-9]+) ]]; then
                        fps_array=("${BASH_REMATCH[1]}")
                    else
                        continue
                    fi
                else
                    multi_pattern='fps[[:space:]]*\(([^)]+)\)'
                    if [[ "$line" =~ $multi_pattern ]]; then
                        fps_values="${BASH_REMATCH[1]}"
                        IFS=',' read -ra fps_array <<< "$(echo "$fps_values" | tr -d ' ')"
                    else
                        continue
                    fi
                fi
                for idx in "${!fps_array[@]}"; do
                    fps="${fps_array[idx]}"
                    if [[ idx -lt ${#pipeline_logs[@]} ]]; then
                        echo "$fps" >> "${pipeline_logs[idx]}"
                    fi
                done
            fi
        fi
    done

    wait $GST_PID

    echo "############# GST COMMAND COMPLETED SUCCESSFULLY #############"
else
    echo "########### lp_vlm workload is detected in camera-workload config #############"
    echo "VLM_WORKLOAD_ENABLED=1 detected. Launching lp_vlm based workload ..."
    bash "/home/pipeline-server/lp-vlm/gvapython/vlm_od_pipeline.sh"
    echo "############# lp_vlm WORKLOAD COMPLETED SUCCESSFULLY #############"
    sleep 10m
fi
