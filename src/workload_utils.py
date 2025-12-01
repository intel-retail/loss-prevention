import json
from typing import Tuple, Optional

def parse_workloads_and_files(config_path: str) -> Tuple[bool, Optional[str]]:
    """
    Reads a pipeline config file.
    Returns:
        - has_lp_vlm: True/False
        - first_file_name: string or None
    """
    with open(config_path, "r") as f:
        config = json.load(f)

    cameras = config.get("lane_config", {}).get("cameras", [])

    has_lp_vlm = False
    first_file_name = None

    for cam in cameras:
        # check workload
        workloads = cam.get("workloads", [])
        if "lp_vlm" in workloads:
            has_lp_vlm = True

        # parse first fileSrc only once
        if first_file_name is None:
            file_src = cam.get("fileSrc", "")
            if "|" in file_src:
                first_file_name = file_src.split("|")[0]
            else:
                first_file_name = file_src

    return has_lp_vlm, first_file_name

def has_lp_vlm_workload():
    workload_file = os.getenv("CAMERA_STREAM", "camera_to_workload.json")

    with open(workload_file, "r") as f:
        data = json.load(f)

    cameras = data.get("lane_config", {}).get("cameras", [])

    for cam in cameras:
        workloads = cam.get("workloads", [])
        if "lp_vlm" in workloads:
            return True

    return False

def load_workload(file_path=None):
    """Load JSON workload file. Default fallback is camera_to_workload.json"""
    path = Path(file_path) if file_path else Path("camera_to_workload.json")
    if not path.exists():
        raise FileNotFoundError(f"Workload file not found: {path}")
    
    with open(path, "r") as f:
        return json.load(f)


def get_cameras_with_lp_vlm(file_path=None):
    """
    Return list of camera objects that have 'lp_vlm' in workloads.
    Each object is the full camera dictionary.
    """
    data = load_workload(file_path)
    cameras = data.get("lane_config", {}).get("cameras", [])
    return [cam for cam in cameras if "lp_vlm" in cam.get("workloads", [])]


def get_primary_video_name(cam):
    """
    Return the video file name before | separator from a camera object.
    """
    file_src = cam.get("fileSrc", "")
    return file_src.split("|")[0].strip()


def run_docker_per_camera(workload_file=None, compose_file="docker-compose.yaml"):
    """
    For each camera that has lp_vlm workload:
        - Set VLM_WORKLOAD_ENABLED=1
        - Set VIDEO_NAME to the camera's first video file
        - Run docker-compose build & up
    """
    cameras_lp_vlm = get_cameras_with_lp_vlm(workload_file)

    if not cameras_lp_vlm:
        print("No cameras with lp_vlm workload found. Skipping docker-compose.")
        return

    for cam in cameras_lp_vlm:
        camera_id = cam.get("camera_id")
        video_name = get_primary_video_name(cam)

        print(f"\n=== Running docker-compose for camera '{camera_id}' ===")
        print(f"VLM_WORKLOAD_ENABLED=1, VIDEO_NAME={video_name}")

        # Prepare environment variables
        env = os.environ.copy()
        env["VLM_WORKLOAD_ENABLED"] = "1"
        env["VIDEO_NAME"] = video_name
        env["CAMERA_ID"] = camera_id  # optional: pass camera ID

        # Build docker-compose
        subprocess.run(
            ["docker-compose", "-f", compose_file, "build"],
            check=True,
            env=env
        )

        # Run docker-compose
        subprocess.run(
            ["docker-compose", "-f", compose_file, "up", "-d"],
            check=True,
            env=env
        )

        print(f"Docker Compose for camera '{camera_id}' started successfully.")


if __name__ == "__main__":
    # Example:
    # python workload_utils.py lp_vlm
    # python workload_utils.py video
    #
    cmd = sys.argv[1] if len(sys.argv) > 1 else None

    if cmd == "lp_vlm":
        print(1 if has_lp_vlm_workload() else 0)
    elif cmd == "video":
        print(get_primary_video_name() or "")
    elif cmd == "workloads":
        print(",".join(get_all_workloads()))
    else:
        print("Usage:")
        print("  python workload_utils.py lp_vlm")
        print("  python workload_utils.py video")
        print("  python workload_utils.py workloads")
