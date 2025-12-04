#!/bin/bash

# -----------------------------
# Conditional execution based on VLM_WORKLOAD_ENABLED
# -----------------------------


echo ">>>>>>>>>>>>> VLM_WORKLOAD_ENABLED=${VLM_WORKLOAD_ENABLED} <<<<<<<<<<<<<<<"

if [ "${VLM_WORKLOAD_ENABLED}" = "0" ]; then
    # -----------------------------
    # Configuration & Environment
    # -----------------------------
    CAMERA_STREAM="${CAMERA_STREAM:-camera_to_workload.json}"
    WORKLOAD_DIST="${WORKLOAD_DIST:-workload_to_pipeline.json}"

    export CAMERA_STREAM
    export WORKLOAD_DIST

    echo "################# Using camera config: $CAMERA_STREAM ###################"
    echo "################# Using workload config: $WORKLOAD_DIST ###################"

    export PYTHONPATH=/home/pipeline-server/src:$PYTHONPATH

    # Use TIMESTAMP env variable if set, otherwise fallback to date
    cid=$(date +%Y%m%d%H%M%S)$(date +%6N | cut -c1-6)
    export TIMESTAMP=$cid
    echo "===============TIMESTAMP===================: $TIMESTAMP"

    CONTAINER_NAME="${CONTAINER_NAME//\"/}" # Remove double quotes
    cid="${cid}_${CONTAINER_NAME}"
    echo "==================CONTAINER_NAME: ${CONTAINER_NAME}"
    echo "cid: $cid"

    echo "############# Generating GStreamer pipeline command ##########"
    echo "################### RENDER_MODE ################# $RENDER_MODE"

    gst_cmd=$(python3 "$(dirname "$0")/gst-pipeline-generator.py")
    echo "#############  GStreamer pipeline command generated successfully ##########"

    # -----------------------------
    # Prepare pipelines directory
    # -----------------------------
    pipelines_dir="/home/pipeline-server/pipelines"
    mkdir -p "$pipelines_dir"

    if [ -d "$pipelines_dir" ]; then
        echo "################# Pipelines directory exists: $pipelines_dir ###################"
    else
        echo "################# ERROR: Failed to create pipelines directory: $pipelines_dir ###################"
    fi

    # Create pipeline.sh
    pipeline_file="$pipelines_dir/pipeline.sh"
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
    fi

    # -----------------------------
    # Prepare result directory
    # -----------------------------
    results_dir="/home/pipeline-server/results"
    mkdir -p "$results_dir"

    # Count filesrc lines to determine number of streams
    filesrc_count=$(grep -c "filesrc location=" "$pipeline_file")
    echo "Found $filesrc_count filesrc lines in $pipeline_file"

    # Extract first name= value from each filesrc line
    declare -a filesrc_names
    while IFS= read -r line; do
        if [[ "$line" == *"filesrc location="* ]]; then
            # Extract first name= value from this line
            if [[ "$line" =~ name=([^[:space:]]+) ]]; then
                name="${BASH_REMATCH[1]}"
                filesrc_names+=("$name")
            else
                # Fallback if no name found
                filesrc_names+=("stream${#filesrc_names[@]}")
            fi
        fi
    done < "$pipeline_file"

    echo "Extracted filesrc names: ${filesrc_names[*]}"

    # Create per-stream pipeline log files using extracted names
    declare -a pipeline_logs
    for i in "${!filesrc_names[@]}"; do
        name="${filesrc_names[i]}"
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
            if [[ "$num_streams" -eq "$filesrc_count" ]]; then
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
    echo "================ VIDEO_NAME=${VIDEO_NAME} ===================="
    export VIDEO_NAME
    MODEL="/home/pipeline-server/lp-vlm/models/object_detection/yolo11n/INT8/yolo11n.xml"

    echo "🔄 Checking model availability: $MODEL"

    while [ ! -f "$MODEL" ]; do
        echo "⏳===================== Model not found. Waiting 5s................. ====================="
        sleep 5
    done

    echo "✔️ Model found. Validating VLM workload configuration..."

    echo "########### lp_vlm workload is detected in camera-workload config #############"
    echo "VLM_WORKLOAD_ENABLED=1 detected. Launching lp_vlm based workload ..."
    bash "/home/pipeline-server/lp-vlm/gvapython/vlm_od_pipeline.sh"
    echo "############# lp_vlm WORKLOAD COMPLETED SUCCESSFULLY #############"
    # Keep the container alive for inspection if needed
    sleep 10m
fi