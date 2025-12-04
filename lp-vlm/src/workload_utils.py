#!/usr/bin/env python3
import json
import os
import logging
from pathlib import Path
import argparse

# -------------------- Logger Setup --------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# -------------------- Defaults --------------------
CONFIG_PATH_DEFAULT = "/app/lp/configs/camera_to_workload.json"
#CONFIG_PATH_DEFAULT = "../../configs/camera_to_workload.json"
TARGET_WORKLOAD = "lp_vlm"  # normalized compare

# -------------------- Load JSON --------------------
def load_config(camera_cfg_path: str) -> dict:
    cfg_file = Path(camera_cfg_path)
    if not cfg_file.exists():
        raise FileNotFoundError(f"[ERROR] Config file not found: {cfg_file}")
    
    with open(cfg_file, "r") as f:
        return json.load(f)

# -------------------- Workload Utils --------------------
def camera_has_vlm(camera_obj) -> bool:
    """Check if workloads include lp_vlm ignoring case and whitespace."""
    workloads = camera_obj.get("workloads", [])
    # Support both list and single string
    if isinstance(workloads, str):
        workloads = [workloads]
    normalized = [str(w).strip().lower() for w in workloads]
    return TARGET_WORKLOAD in normalized

def extract_video_name(fileSrc, width=None, fps=None) -> str:
    """
    Return "<first-fileSrc>-<width>-<fps>.mp4"
    - first-fileSrc is the segment before '|'
    - existing extension is removed before appending width/fps
    """
    if not fileSrc:
        return ""
    base = fileSrc.split("|")[0].strip()
    # remove extension if present
    if "." in base:
        base = base.rsplit(".", 1)[0]
    w = "" if width is None else str(width).strip()
    f = "" if fps is None else str(fps).strip()
    return f"{base}-{w}-{f}-bench.mp4"

# -------------------- Main Validation --------------------
def validate_and_extract_vlm_config(camera_cfg_path: str = None) -> dict:
    """
    Validate that exactly one camera has LP_VLM workload.
    Extract and return video metadata.
    
    Returns:
        dict with keys: camera_id, video_name, width, fps, roi
    
    Raises:
        ValueError: if zero or more than one LP_VLM workload found
    """
    # Determine config path
    if not camera_cfg_path:
        camera_cfg_path = os.getenv("CAMERA_STREAM")
        if not camera_cfg_path:
            camera_cfg_path = CONFIG_PATH_DEFAULT
    
    logger.info("📄 Loading camera config: %s", camera_cfg_path)
    cfg = load_config(camera_cfg_path)
    
    lane = cfg.get("lane_config", {})
    cameras = lane.get("cameras", [])
    
    if not cameras:
        raise ValueError("[ERROR] No cameras found in configuration")
    
    # Find all cameras with LP_VLM workload
    vlm_cameras = [cam for cam in cameras if camera_has_vlm(cam)]
    
    if len(vlm_cameras) == 0:
        raise ValueError(
            f"[ERROR] No LP_VLM workload found in any camera. "
            f"Available workloads: {[c.get('workloads', []) for c in cameras]}"
        )
    
    if len(vlm_cameras) > 1:
        camera_ids = [c.get("camera_id", "unknown") for c in vlm_cameras]
        raise ValueError(
            f"[ERROR] More than one LP_VLM workload defined. "
            f"Found {len(vlm_cameras)} cameras with LP_VLM: {camera_ids}. "
            f"Only one camera should have LP_VLM workload."
        )
    
    # Extract metadata from the single LP_VLM camera
    cam = vlm_cameras[0]
    camera_id = cam.get("camera_id", "unknown")
    fileSrc = cam.get("fileSrc", "")
    width = cam.get("width")
    fps = cam.get("fps")
    roi_dict = cam.get("region_of_interest", {})
    
    video_name = extract_video_name(fileSrc, width, fps)
    
    if not video_name:
        raise ValueError(f"[ERROR] Camera {camera_id} has empty fileSrc")
    
    # Format ROI as comma-separated string: x,y,x2,y2
    roi = f"{roi_dict.get('x', '')},{roi_dict.get('y', '')},{roi_dict.get('x2', '')},{roi_dict.get('y2', '')}"
    
    result = {        
        "video_name": video_name,        
        "roi": roi
    }    
    logger.info("✅ Found LP_VLM workload in camera: %s", camera_id)
    logger.info("  📹 Video: %s", video_name)
    logger.info("  🎯 ROI: %s", roi)
    return result

def get_video_from_config(camera_cfg_path: str = None):
    """
    Validate VLM configuration and extract video file name.
    Sets VIDEO_NAME and ROI_COORDINATES environment variables.
    
    Args:
        camera_cfg_path: Optional path to camera config file
        
    Returns:
        str: video file name from configuration
        
    Raises:
        ValueError: if configuration validation fails
    """
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Validating LP_VLM workload configuration...")
        vlm_config = validate_and_extract_vlm_config(camera_cfg_path)
        
        video_file_name = vlm_config.get("video_name")
        roi_coordinates = vlm_config.get("roi", "")
        
        logger.info("Using video from config: %s", video_file_name)
        return video_file_name
        
    except Exception as e:
        logger.error("Failed to validate VLM configuration: %s", str(e))
        raise ValueError(f"Configuration validation failed: {str(e)}")

# -------------------- CLI --------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate and extract LP_VLM camera configuration"
    )
    parser.add_argument(
        "--camera-config",
        help="Camera workload mapping JSON path",
        default=None
    )
    
    args = parser.parse_args()

    try:
        video_name = get_video_from_config(args.camera_config)
        logger.info("✅ Validation successful!")

        # IMPORTANT: print ONLY the value for Bash script
        print(video_name)

    except Exception as e:
        logger.error("❌ Validation failed: %s", e)
        # Print nothing (so Bash receives empty value)
        exit(1)
