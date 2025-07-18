import os
import json
from pathlib import Path
import copy
from datetime import datetime
from dotenv import dotenv_values

CONFIG_CAMERA_TO_WORKLOAD = "/home/pipeline-server/configs/camera_to_workload.json"
CONFIG_WORKLOAD_TO_PIPELINE = "/home/pipeline-server/configs/workload_to_pipeline.json"


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
    model = cfg["model"]
    device = cfg["device"]
    precision = cfg.get("precision", "")
    workload_name = cfg.get("workload_name")
    camera_id = cfg.get("camera_id", "")
    # Load env vars for this device
    env_vars = get_env_vars_for_device(device)
    DECODE = env_vars.get("DECODE") or "decodebin"
    PRE_PROCESS = env_vars.get("PRE_PROCESS", "")
    DETECTION_OPTIONS = env_vars.get("DETECTION_OPTIONS", "")
    CLASSIFICATION_PRE_PROCESS = env_vars.get("CLASSIFICATION_PRE_PROCESS", "")
    # Add inference-region=1 if region_of_interest is present in cfg (from camera_to_workload.json)
    inference_region = ""
    name_str = f"name={workload_name}_{camera_id}" if workload_name and camera_id and cfg["type"] == "gvadetect" else ""
    if cfg["type"] == "gvadetect" and cfg.get("region_of_interest") is not None:
        inference_region = " inference-region=1"
    if cfg["type"] == "gvadetect":
        model_path = download_model_if_missing(model, "gvadetect", precision)
        elem = f"gvadetect {name_str} batch-size=1 {inference_region} model={model_path} device={device} {PRE_PROCESS} {DETECTION_OPTIONS}"
    elif cfg["type"] == "gvaclassify":
        model_path, label_path, proc_path = download_model_if_missing(model, "gvaclassify", precision)
        elem = f"gvaclassify {name_str} batch-size=1 model={model_path} device={device} labels={label_path} model-proc={proc_path} {CLASSIFICATION_PRE_PROCESS}"
    elif cfg["type"] in ["gvatrack", "gvaattachroi", "gvametaconvert", "gvametapublish", "gvawatermark", "gvafpscounter", "fpsdisplaysink", "queue", "videoconvert", "decodebin", "filesrc", "fakesink"]:
        # These are valid GStreamer elements that may not need model/device
        elem = cfg["type"]
    else:
        raise ValueError(f"Unknown or unsupported GStreamer element type: {cfg['type']}")
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
            sig = json.dumps([pipeline_cfg_signature(s) for s in norm_steps], sort_keys=True)
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
        # Get DECODE for the first step's device
        first_device = steps[0]["device"]
        first_env_vars = get_env_vars_for_device(first_device)
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
        inference_types = {"gvadetect", "gvaclassify"}
        detect_count = 1
        classify_count = 1
        for i, step in enumerate(steps):
            # Get env vars for each step's device
            step_env_vars = get_env_vars_for_device(step["device"])
            # If you want to use step_env_vars for other options, you can do so here
            if not rois and i == 0 and step["type"] in inference_types:
                pipeline += " ! gvaattachroi"
            if step["type"] == "gvadetect":
                model_instance_id = f"detect{branch_idx+1}_{idx+1}"
                elem, _ = build_gst_element(step)
                elem = elem.replace("gvadetect", f"gvadetect model-instance-id={model_instance_id} threshold=0.5")
                pipeline += f" ! {elem} ! gvatrack ! queue"
                last_added_queue = True
            elif step["type"] == "gvaclassify":
                model_instance_id = f"classify{branch_idx+1}_{idx+1}"
                elem, _ = build_gst_element(step)
                elem = elem.replace("gvaclassify", f"gvaclassify model-instance-id={model_instance_id}")
                pipeline += f" ! {elem} "
                last_added_queue = False
            else:
                elem, _ = build_gst_element(step)
                pipeline += f" ! {elem}"
                last_added_queue = False
            # Only add queue if not just added by gvadetect/gvatrack
            if i < len(steps) - 1:
                if not (step["type"] == "gvadetect"):
                    pipeline += " ! queue"
        tee_name = f"t{branch_idx+1}_{idx+1}"
        results_dir = "/home/pipeline-server/results"
        out_file = f"{results_dir}/rs-{branch_idx+1}_{idx+1}_{timestamp}.jsonl"
        pipeline += f" ! gvametaconvert format=json ! tee name={tee_name} "
        pipeline += f"    {tee_name}. ! queue ! gvametapublish method=file file-path={out_file} ! gvafpscounter ! fakesink sync=false async=false "
        render_mode = os.environ.get("RENDER_MODE", "0")
        if render_mode == "1":
            pipeline += f"    {tee_name}. ! queue ! gvawatermark ! videoconvert ! fpsdisplaysink video-sink=autovideosink text-overlay=true signal-fps-measurements=true"
        else:
            pipeline += f"    {tee_name}. ! queue ! fakesink sync=false async=false"
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
    for idx, cam in enumerate(camera_config["lane_config"]["cameras"]):
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