#!/usr/bin/env python3
import argparse
import json
import logging
import os
from pathlib import Path
from urllib.parse import urlparse
import socket
import subprocess

# -------------------- Logger Setup --------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# -------------------- Defaults --------------------
CONFIG_PATH_DEFAULT = "../../configs/camera_to_workload.json"
TARGET_WORKLOAD = "lp_vlm"  # normalized compare
RTSP_DEFAULT_HOST = os.getenv("RTSP_STREAM_HOST", "rtsp-streamer")
RTSP_DEFAULT_PORT = os.getenv("RTSP_STREAM_PORT", "8554")

# -------------------- Stream Validation --------------------
def check_rtsp_stream_exists(stream_uri: str, timeout: int = 3) -> bool:
    """
    Check if a specific RTSP stream path is available using GStreamer.
    Returns True if the stream is accessible, False otherwise.
    """
    try:
        import subprocess
        
        # Use gst-launch to test if stream exists with a very short timeout
        # This will fail quickly if the stream doesn't exist (404 Not Found)
        cmd = [
            'timeout', '5',  # Kill after 5 seconds
            'gst-launch-1.0',
            'rtspsrc', f'location={stream_uri}',
            'protocols=tcp',
            'latency=200',
            'timeout=2000000',  # 2 second RTSP timeout
            '!', 'fakesink'
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=6,
            text=True
        )
        
        # Check if stderr contains "Not Found" or "404"
        if result.stderr and ('Not Found' in result.stderr or '404' in result.stderr or 'Not found' in result.stderr):
            logger.warning(f"RTSP stream not found: {stream_uri}")
            return False
            
        # If command succeeded or timed out (stream exists but we didn't wait), it's available
        return True
        
    except subprocess.TimeoutExpired:
        # Timeout means stream connected successfully
        return True
    except Exception as e:
        logger.warning(f"Could not check RTSP stream {stream_uri}: {e}")
        # If we can't check, assume it exists to avoid false negatives
        return True

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
    """Return a sanitized stem for legacy file-based workloads."""
    if not fileSrc:
        return ""
    raw = fileSrc.split("|")[0].strip()
    base = Path(raw).stem if raw else ""
    if not base:
        return ""
    if width is None or fps is None:
        return base
    w = str(width).strip()
    f = str(fps).strip()
    return f"{base}-{w}-{f}-bench"


def derive_stream_uri(camera: dict) -> str:
    """
    Dynamically construct RTSP stream URI from fileSrc.
    Format: rtsp://{host}:{port}/{video_name}-{width}-{fps}-bench
    Falls back to legacy streamUri keys if fileSrc is not available.
    """
    # First, try to construct from fileSrc (preferred approach)
    fileSrc = str(camera.get("fileSrc", "")).split("|")[0].strip()
    if fileSrc:
        # Remove .mp4 extension if present
        base_name = fileSrc[:-4] if fileSrc.endswith('.mp4') else fileSrc
        width = camera.get("width", 1920)
        fps = camera.get("fps", 15)
        stream_path = f"{base_name}-{width}-{fps}-bench"
        return f"rtsp://{RTSP_DEFAULT_HOST}:{RTSP_DEFAULT_PORT}/{stream_path}"
    
    # Legacy fallback: check for explicit streamUri keys
    for key in ("streamUri", "stream_uri", "rtspUri", "rtsp_url"):
        raw = str(camera.get(key, ""))
        cleaned = raw.strip().strip('"').strip("'")
        if cleaned:
            if "://" in cleaned:
                parsed = urlparse(cleaned)
                scheme = parsed.scheme or "rtsp"
                host = RTSP_DEFAULT_HOST or (parsed.hostname or "rtsp-streamer")
                port = RTSP_DEFAULT_PORT or (str(parsed.port) if parsed.port else "8554")
                path = parsed.path or ""
                query = f"?{parsed.query}" if parsed.query else ""
                return f"{scheme}://{host}:{port}{path}{query}"
            path = cleaned if cleaned.startswith("/") else f"/{cleaned}"
            return f"rtsp://{RTSP_DEFAULT_HOST}:{RTSP_DEFAULT_PORT}{path}"

    # Last resort: use camera_id
    camera_id = str(camera.get("camera_id", "")).strip()
    if camera_id:
        return f"rtsp://{RTSP_DEFAULT_HOST}:{RTSP_DEFAULT_PORT}/{camera_id}"
    return ""


def derive_stream_name(camera: dict, stream_uri: str) -> str:
    camera_id = str(camera.get("camera_id", "")).strip()
    if camera_id:
        return camera_id

    if stream_uri:
        parsed = urlparse(stream_uri)
        candidate = Path(parsed.path).name
        if candidate:
            return candidate
        if parsed.hostname:
            return parsed.hostname

    fileSrc = camera.get("fileSrc", "")
    return extract_video_name(fileSrc, camera.get("width"), camera.get("fps"))

# -------------------- Main Validation --------------------
def validate_and_extract_vlm_config(camera_cfg_path: str = None) -> dict:
    """
    Validate that exactly one camera has LP_VLM workload.
    Extract and return video metadata.
    
    Returns:
        dict with keys: stream_name, stream_uri, roi
    
    Raises:
        ValueError: if zero or more than one LP_VLM workload found
    """
    # Determine config path
    if not camera_cfg_path:
        camera_cfg_path = os.getenv("CAMERA_STREAM")
        if not camera_cfg_path:
            camera_cfg_path = CONFIG_PATH_DEFAULT    
    
    cfg = load_config(camera_cfg_path)
    
    lane = cfg.get("lane_config", {})
    cameras = lane.get("cameras", [])
    
    if not cameras:
        raise ValueError("[ERROR] No cameras found in configuration")
    
    # Find all cameras with LP_VLM workload
    vlm_cameras = [cam for cam in cameras if camera_has_vlm(cam)]
    
    if len(vlm_cameras) == 0:
        raise ValueError(
            f"[ERROR] No lp_vlm workload found in any camera. "
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
    roi_dict = cam.get("region_of_interest", {})

    stream_uri = derive_stream_uri(cam)
    stream_name = derive_stream_name(cam, stream_uri)

    if not stream_uri:
        raise ValueError(f"[ERROR] Camera {camera_id} is missing an RTSP stream URI")
    if not stream_name:
        raise ValueError(f"[ERROR] Camera {camera_id} has no stream identifier")
    
    # Validate RTSP stream availability
    if stream_uri.startswith("rtsp://"):
        if not check_rtsp_stream_exists(stream_uri):
            file_src = str(cam.get("fileSrc", "")).split("|")[0].strip()
            logger.warning(f"⚠️  WARNING: RTSP stream not available for camera '{camera_id}': {stream_uri}")
            logger.warning(f"    Expected video file: {file_src}")
            logger.warning(f"    Please ensure the video exists in the sample-media directory.")
            raise ValueError(
                f"[ERROR] RTSP stream not available for camera {camera_id}: {stream_uri}. "
                f"Expected video: {file_src}"
            )
    
    # Format ROI as comma-separated string: x,y,x2,y2
    roi = f"{roi_dict.get('x', '')},{roi_dict.get('y', '')},{roi_dict.get('x2', '')},{roi_dict.get('y2', '')}"
    
    result = {
        "stream_name": stream_name,
        "stream_uri": stream_uri,
        "roi": roi
    }
    return result

def has_lp_vlm_workload(camera_cfg_path: str = None) -> bool:
    if not camera_cfg_path:
        camera_cfg_path = os.getenv("CAMERA_STREAM") or CONFIG_PATH_DEFAULT

    cfg = load_config(camera_cfg_path)
    cameras = cfg.get("lane_config", {}).get("cameras", [])

    for cam in cameras:
        if camera_has_vlm(cam):
            return True
    return False

def get_video_name_only(camera_cfg_path: str = None) -> str:
    stream_name, _, _ = get_video_from_config(camera_cfg_path)
    return stream_name

def get_video_from_config(camera_cfg_path: str = None):
    """
    Validate VLM configuration and extract stream metadata.
    Sets stream name, URI, and ROI values.
    
    Args:
        camera_cfg_path: Optional path to camera config file
        
    Returns:
        tuple: (stream_name, stream_uri, roi_coordinates)
        
    Raises:
        ValueError: if configuration validation fails
    """
    logger = logging.getLogger(__name__)
    
    try:
        vlm_config = validate_and_extract_vlm_config(camera_cfg_path)

        stream_name = vlm_config.get("stream_name")
        stream_uri = vlm_config.get("stream_uri")
        roi_coordinates = vlm_config.get("roi", "")

        return stream_name, stream_uri, roi_coordinates
        
    except Exception as e:
        logger.error("Failed to validate lp_vlm configuration: %s", str(e))
        raise ValueError(f"Configuration validation failed: {str(e)}")

# -------------------- CLI --------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="lp_vlm workload utilities"
    )
    parser.add_argument(
        "--camera-config",
        help="Camera workload mapping JSON path",
        default=None
    )
    parser.add_argument(
        "--has-lp-vlm",
        action="store_true",
        help="Return 1 if lp_vlm workload exists, else 0"
    )
    parser.add_argument(
    "--get-video-name",
    action="store_true",
    help="Return only video name for lp_vlm workload"
    )
    parser.add_argument(
        "--get-video",
        action="store_true",
        help="Return stream metadata for lp_vlm workload"
    )
    parser.add_argument(
        "--get-stream-uri",
        action="store_true",
        help="Return only the RTSP URI for lp_vlm workload"
    )

    args = parser.parse_args()

    try:
        if args.has_lp_vlm:
            exists = has_lp_vlm_workload(args.camera_config)
            print("1" if exists else "0")
            exit(0)

        if args.get_video:
            stream_name, stream_uri, roi_coordinates = get_video_from_config(args.camera_config)
            print(json.dumps({
                "stream_name": stream_name,
                "stream_uri": stream_uri,
                "roi": roi_coordinates
            }))
            exit(0)
        if args.get_stream_uri:
            _, stream_uri, _ = get_video_from_config(args.camera_config)
            print(stream_uri)
            exit(0)
        if args.get_video_name:
            video_name = get_video_name_only(args.camera_config)
            print(video_name)
            exit(0)
        parser.print_help()
        exit(1)

    except Exception as e:
        logger.error(str(e))
        exit(1)
