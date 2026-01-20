import os
import json
from pathlib import Path
import copy
from datetime import datetime
from dotenv import dotenv_values
import sys

WORKLOAD_DIST = os.environ.get("WORKLOAD_DIST", "workload_to_pipeline.json")
CAMERA_STREAM = os.environ.get("CAMERA_STREAM", "camera_to_workload.json")
CONFIG_CAMERA_TO_WORKLOAD = f"/home/pipeline-server/configs/{CAMERA_STREAM}"
CONFIG_WORKLOAD_TO_PIPELINE = f"/home/pipeline-server/configs/{WORKLOAD_DIST}"


MODELSERVER_DIR = "/home/pipeline-server"
MODELSERVER_MODELS_DIR = "/home/pipeline-server/models"
MODELSERVER_VIDEOS_DIR = "/home/pipeline-server/sample-media"


def download_video_if_missing(video_name, width=None, fps=None):
    # Use default width and fps if not provided
    width = width if width is not None else 1920
    fps = fps if fps is not None else 15
    # Remove .mp4 extension if present for base name
    base_name = video_name[:-4] if video_name.endswith('.mp4') else video_name
    # Compose the expected file name
    file_name = f"{base_name}-{width}-{fps}-bench.mp4"
    video_path = os.path.join(MODELSERVER_VIDEOS_DIR, file_name)
    return video_path

def download_model_if_missing(model_name, model_type=None, precision=None):
    if model_type == "gvadetect":
        precision_lower = precision.lower()
        return f"{MODELSERVER_MODELS_DIR}/object_detection/{model_name}/{precision}/{model_name}.xml"
    elif model_type == "gvainference":
        base_path = f"{MODELSERVER_MODELS_DIR}/object_classification/{model_name}"
        model_path = f"{base_path}/{precision}/{model_name}.xml"
        return model_path
    elif model_type == "gvaclassify":
        base_path = f"{MODELSERVER_MODELS_DIR}/object_classification/{model_name}"
        model_path = f"{base_path}/{precision}/{model_name}.xml"
        label_path = f"{base_path}/{model_name}.txt"
        proc_path = f"{base_path}/{model_name}.json"
        return model_path, label_path, proc_path
    else:
        # fallback
        return os.path.join(MODELSERVER_MODELS_DIR, model_name)

def load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found: {path}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error: Failed to decode JSON in {path}: {e}")
        return None
    except Exception as e:
        print(f"Error: Unexpected error reading {path}: {e}")
        return None

def pipeline_cfg_signature(cfg):
    # Remove fields that don't affect pipeline structure (like device, ROI order doesn't matter)
    sig = copy.deepcopy(cfg)
    sig.pop('device', None)
    sig.pop('region_of_interest', None)
    return json.dumps(sig, sort_keys=True)

def get_env_vars_for_device(device):
    device_env_map = {
        "CPU": "/res/all-cpu.env",
        "NPU": "/res/all-npu.env",
        "GPU": "/res/all-gpu.env"
    }
    env_file = device_env_map.get(device.upper())
    if not env_file or not os.path.exists(env_file):
        return {}
    return dotenv_values(env_file)

def build_gst_element(cfg):
    model = cfg.get("model")
    device = cfg.get("device")
    precision = cfg.get("precision", "")
    workload_name = cfg.get("workload_name")
    camera_id = cfg.get("camera_id", "")
    # Load env vars for this device
    env_vars = get_env_vars_for_device(device) if device else {}
    DECODE = env_vars.get("DECODE") or "decodebin"
    PRE_PROCESS = env_vars.get("PRE_PROCESS", "")
    DETECTION_OPTIONS = env_vars.get("DETECTION_OPTIONS", "")
    PRE_PROCESS_CONFIG = env_vars.get("PRE_PROCESS_CONFIG", "")

    try:
        BATCH_SIZE_DETECT = int(os.environ.get("BATCH_SIZE_DETECT", 
                                              env_vars.get("BATCH_SIZE_DETECT", 1)))
    except ValueError:
        print(f"Warning: Invalid BATCH_SIZE_DETECT value, using default 1", file=sys.stderr)
        BATCH_SIZE_DETECT = 1
        
    try:
        BATCH_SIZE_CLASSIFY = int(os.environ.get("BATCH_SIZE_CLASSIFY", 
                                                env_vars.get("BATCH_SIZE_CLASSIFY", 1)))
    except ValueError:
        print(f"Warning: Invalid BATCH_SIZE_CLASSIFY value, using default 1", file=sys.stderr)
        BATCH_SIZE_CLASSIFY = 1
    
    print("******************************************", file=sys.stderr)
    print(f"DETECT {BATCH_SIZE_DETECT} - CLASSIFY {BATCH_SIZE_CLASSIFY}", file=sys.stderr)
    print("******************************************", file=sys.stderr)
    
    CLASSIFICATION_PRE_PROCESS = env_vars.get("CLASSIFICATION_PRE_PROCESS", "")
    # Add inference-region=1 if region_of_interest is present in cfg (from camera_to_workload.json)
    inference_region = ""   
    name_str = f"name={camera_id}_{workload_name}" if workload_name and camera_id and cfg["type"] == "gvadetect" else ""
    if cfg["type"] == "gvadetect" and cfg.get("region_of_interest") is not None:
        inference_region = " inference-region=1"

    if cfg["type"] == "gvadetect":
        # Always use the precision from the current step config
        model_path = download_model_if_missing(model, "gvadetect", cfg.get("precision", ""))
        elem = f"gvadetect {name_str} batch-size={BATCH_SIZE_DETECT} inference-interval=3 scale-method=fast {inference_region} model={model_path} device={device} {PRE_PROCESS} {DETECTION_OPTIONS} {PRE_PROCESS_CONFIG}"
    elif cfg["type"] == "gvaclassify":
        # Always use the precision from the current step config
        model_path, label_path, proc_path = download_model_if_missing(model, "gvaclassify", cfg.get("precision", "")) 
        elem = f"gvaclassify {name_str} batch-size={BATCH_SIZE_CLASSIFY} inference-region=1 scale-method=fast model={model_path} device={device} model-proc={proc_path} {CLASSIFICATION_PRE_PROCESS}"
    elif cfg["type"] == "gvainference":
        model_path = download_model_if_missing(model, "gvainference", cfg.get("precision", ""))
        elem = f"gvainference  model={model_path} device={device} "
    elif cfg["type"] == "gvapython":
        # Try to get module and function from cfg (populated from camera_to_workload.json)
        module = cfg.get("module", "")
        function = cfg.get("function", "")
        elem = f"gvapython module=/home/pipeline-server/src/{module} function={function}  "
    elif cfg["type"] in ["gvatrack", "gvaattachroi", "gvametaconvert", "gvametapublish", "gvawatermark", "gvafpscounter", "fpsdisplaysink", "queue", "videoconvert", "decodebin", "filesrc", "fakesink"]:
        elem = cfg["type"]
    else:
        # Log warning but allow unknown types to pass through
        print(f"Warning: Unknown or unsupported GStreamer element type: {cfg['type']}", file=sys.stderr)
        elem = cfg["type"]
    return elem, DECODE

def build_dynamic_gstlaunch_command(camera, workloads, workload_map, branch_idx=0, model_instance_map=None, model_instance_counter=None, timestamp=None):
    if model_instance_map is None:
        model_instance_map = {}
    if model_instance_counter is None:
        model_instance_counter = [0]  # Use list for mutability in nested scope
    # For each workload, build its steps and signature
    workload_steps = []
    workload_signatures = []
    video_files = []
    camera_id = camera.get("camera_id", f"cam{branch_idx+1}")
    signature_to_steps = {}
    signature_to_video = {}
    for w in workloads:
        if w in workload_map:
            steps = []
            for step in workload_map[w]:
                roi = camera.get("region_of_interest")
                step = step.copy()
                if roi:
                    step["region_of_interest"] = roi
                # Add workload_name and camera_id to step for later use in gvadetect name
                step["workload_name"] = w
                step["camera_id"] = camera_id
                steps.append(step)
            # Normalize steps for signature (remove workload_name, camera_id)
            norm_steps = []
            for s in steps:
                s_norm = s.copy()
                s_norm.pop('workload_name', None)
                s_norm.pop('camera_id', None)
                norm_steps.append(s_norm)
            # Build a unique signature that includes model and precision for all steps
            # This ensures that if any step has a different model or precision, it will be a new stream
            model_prec_signature = json.dumps([
                {
                    'type': s.get('type'),
                    'model': s.get('model'),
                    'precision': s.get('precision'),
                    'device': s.get('device')
                } for s in steps
            ], sort_keys=True)
            sig = model_prec_signature
            if sig not in signature_to_steps:
                signature_to_steps[sig] = steps
                # Each unique signature gets a video file
                file_src = camera["fileSrc"]
                video_name = file_src.split("|")[0].strip()
                width = camera.get("width", 1920)
                fps = camera.get("fps", 15)
                video_file = download_video_if_missing(video_name, width, fps)
                signature_to_video[sig] = video_file
    pipelines = []
    for idx, (sig, steps) in enumerate(signature_to_steps.items()):
        video_file = signature_to_video[sig]
        # Get DECODE for the first step's device, if present
        first_device = steps[0].get("device")
        
        # Determine if vapostproc should be used based on device type
        vapostproc_elem = "vapostproc !" if first_device and first_device.upper() in ["NPU", "GPU"] else ""
        
        first_env_vars = get_env_vars_for_device(first_device) if first_device else {}
        DECODE = first_env_vars.get("DECODE") or "decodebin"
        pipeline = f"filesrc location={video_file} ! {DECODE} "
        rois = []
        seen_rois = set()
        for step in steps:
            roi = step.get("region_of_interest")
            if roi:
                roi_tuple = (roi.get('x', 0), roi.get('y', 0), roi.get('x2', 1), roi.get('y2', 1))
                if roi_tuple not in seen_rois:
                    seen_rois.add(roi_tuple)
                    rois.append(roi)
        if rois:
            roi_strs = [f"roi={r['x']},{r['y']},{r['x2']},{r['y2']}" for r in rois]
            gvaattachroi_elem = "gvaattachroi " + " ".join(roi_strs)
            pipeline += f" ! {gvaattachroi_elem} ! queue"
        # Only add gvaattachroi if region_of_interest is present (i.e., rois is not empty)
        # Remove unconditional gvaattachroi for first inference step
        inference_types = {"gvadetect", "gvaclassify", "gvainference"}
        detect_count = 1
        classify_count = 1
        for i, step in enumerate(steps):
            # Get env vars for each step's device, if present
            step_env_vars = get_env_vars_for_device(step["device"]) if "device" in step else {}
            if step["type"] == "gvadetect":
                model_instance_id = f"detect{branch_idx+1}_{idx+1}"
                elem, _ = build_gst_element(step)
                elem = elem.replace("gvadetect", f"gvadetect model-instance-id={model_instance_id} threshold=0.5")
                pipeline += f" ! {elem} ! gvatrack tracking-type=zero-term-imageless ! queue"
                last_added_queue = True
            elif step["type"] == "gvaclassify":
                model_instance_id = f"classify{branch_idx+1}_{idx+1}"
                elem, _ = build_gst_element(step)
                elem = elem.replace("gvaclassify", f"gvaclassify model-instance-id={model_instance_id}")
                pipeline += f" ! {elem} "
                last_added_queue = True
            elif step["type"] == "gvainference":
                elem, _ = build_gst_element(step)
                pipeline += f" ! {elem} "    
                last_added_queue = True
            elif step["type"] == "gvapython":
                elem, _ = build_gst_element(step)
                pipeline += f" ! {elem} "
                last_added_queue = False            
            # Only add queue if not just added by gvadetect/gvatrack
            if i < len(steps) - 1:
                if not (step["type"] == "gvadetect"):
                    pipeline += " ! queue"
        tee_name = f"t{branch_idx+1}_{idx+1}"
        has_gvapython = any(step.get("type") == "gvapython" for step in steps)
        if not has_gvapython:
            pipeline += f" ! gvametaconvert ! tee name={tee_name} "
            results_dir = "/home/pipeline-server/results"
            out_file = f"{results_dir}/rs-{branch_idx+1}_{idx+1}_{timestamp}.jsonl"
            pipeline += f"    {tee_name}. ! queue ! gvametapublish file-format=json-lines file-path={out_file} ! gvafpscounter ! fakesink sync=false async=false "
        else:
            pipeline += f" ! tee name={tee_name}  {tee_name}. ! queue ! gvafpscounter ! fakesink sync=false async=false"
            #pipeline += f"    {tee_name}. ! queue ! gvafpscounter ! fakesink sync=false async=false "
        render_mode = os.environ.get("RENDER_MODE", "0")
        if render_mode == "1":
            pipeline += f"    {tee_name}. ! queue ! gvawatermark ! {vapostproc_elem} fpsdisplaysink video-sink=autovideosink text-overlay=true signal-fps-measurements=true"
        else:
            pipeline += f"    {tee_name}. ! queue ! fpsdisplaysink video-sink=fakesink signal-fps-measurements=true"
        pipelines.append(pipeline)
    return pipelines

def format_pipeline_multiline(pipeline):
    # Split pipeline into elements
    elems = [e.strip() for e in pipeline.split('!') if e.strip()]
    formatted = []
    for idx, elem in enumerate(elems):
        is_first = idx == 0
        indent = '' if is_first else '  '
        if idx < len(elems) - 1:
            line = f"{indent}{elem} ! \\"
        else:
            line = f"{indent}{elem}"
        formatted.append(line)
    return '\n'.join(formatted)

def format_pipeline_branch(pipeline):
    # Remove any trailing ! or whitespace
    pipeline = pipeline.strip()
    if pipeline.endswith('!'):
        pipeline = pipeline[:-1].strip()
    # Wrap in parentheses for GStreamer parallel branches
    return f'({pipeline})'

def main():
    # Ensure results directory exists at project root before running pipeline
    results_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results"))
    os.makedirs(results_dir, exist_ok=True)
    
    # Generate timestamp for all files
    timestamp = os.environ.get("TIMESTAMP")
  
    camera_config = load_json(CONFIG_CAMERA_TO_WORKLOAD)
    workload_map = load_json(CONFIG_WORKLOAD_TO_PIPELINE)["workload_pipeline_map"]
    pipelines = []
    model_instance_map = {}
    model_instance_counter = [0]
    
    # Filter out cameras with lp_vlm workload
    cameras = camera_config["lane_config"]["cameras"]
    filtered_cameras = []
    
    for cam in cameras:
        workloads = cam.get("workloads", [])
        # Support both list and single string
        if isinstance(workloads, str):
            workloads = [workloads]
        
        # Normalize workloads to lowercase for comparison
        normalized_workloads = [str(w).strip().lower() for w in workloads]
        
        # Exclude camera if it has lp_vlm workload
        if "lp_vlm" in normalized_workloads:
            print(f"Skipping camera {cam.get('camera_id', 'unknown')} with lp_vlm workload", file=sys.stderr)
            continue
        
        filtered_cameras.append(cam)
    
    # Process only filtered cameras
    for idx, cam in enumerate(filtered_cameras):
        workloads = [w.lower() for w in cam["workloads"]]
        norm_workload_map = {k.lower(): v for k, v in workload_map.items()}
        cam_pipelines = build_dynamic_gstlaunch_command(cam, workloads, norm_workload_map, branch_idx=idx, model_instance_map=model_instance_map, model_instance_counter=model_instance_counter, timestamp=timestamp)
        pipelines.extend([p.strip() for p in cam_pipelines])
    # Print gst-launch-1.0 --verbose and all pipelines, each filesrc on a new line, with a backslash at the end except the last
    print("gst-launch-1.0 --verbose \\")
    for idx, p in enumerate(pipelines):
        end = " \\" if idx < len(pipelines) - 1 else ""
        print(f"  {p}{end}")

if __name__ == "__main__":
    main()