import json
import os
import subprocess
from pathlib import Path
import argparse

# -------------------- Defaults --------------------
CONFIG_PATH_DEFAULT = "./configs/camera_to_workload.json"

BASE_COMPOSE = "./lp-vlm/src/docker-compose-base.yml"
CAMERA_COMPOSE = "./lp-vlm/src/docker-compose.yaml"
TARGET_WORKLOAD = "lp_vlm"  # normalized compare


# -------------------- Load JSON --------------------
def load_config(camera_cfg_path: str) -> dict:
    cfg_file = Path(camera_cfg_path)
    if not cfg_file.exists():
        raise FileNotFoundError(f"[ERROR] Config file not found: {cfg_file}")

    with open(cfg_file, "r") as f:
        return json.load(f)

def compose_exists(path: str):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"[ERROR] Compose file not found: {path}")


# -------------------- Workload Utils --------------------
def camera_has_vlm(camera_obj) -> bool:
    """Check if workloads include lp_vlm ignoring case and whitespace."""
    workloads = camera_obj.get("workloads", [])
    # Support both list and single string
    if isinstance(workloads, str):
        workloads = [workloads]
    normalized = [str(w).strip().lower() for w in workloads]
    return TARGET_WORKLOAD in normalized


def extract_video_name(fileSrc):
    """
    Takes something like:
      "video.mp4|https://something"
    Returns:
      "video.mp4"
    """
    if not fileSrc:
        return ""
    return fileSrc.split("|")[0]

def build(compose_file, env_vars=None):
    """docker compose build"""
    env = os.environ.copy()
    if env_vars:
        env.update({k: str(v) for k, v in env_vars.items()})

    compose_exists(compose_file)

    print(f"\n🔨 Building docker images from: {compose_file}")
    subprocess.run(
        ["docker", "compose", "-f", compose_file, "build"],
        env=env,
        check=True
    )

def launch(compose_file, env_vars=None):
    """docker compose up -d with override env."""
    env = os.environ.copy()
    if env_vars:
        env.update({k: str(v) for k, v in env_vars.items()})  # enforce string values

    # Ensure compose file exists to avoid cryptic docker errors
    if not Path(compose_file).exists():
        raise FileNotFoundError(f"[ERROR] Compose file not found: {compose_file}")

    print(f"\n🚀 Launching compose: {compose_file}")
    subprocess.run(
        ["docker", "compose", "-f", compose_file, "up", "-d"],
        env=env,
        check=True
    )


# -------------------- Main Logic --------------------
def run(args):
    # Load cfg
    env_stream = os.getenv("CAMERA_STREAM")
    camera_cfg_path = args.camera_config if args.camera_config else (env_stream or CONFIG_PATH_DEFAULT)
    print(f"📄 Loading camera config: {camera_cfg_path}")

    cfg = load_config(camera_cfg_path)

    lane = cfg.get("lane_config", {})
    cameras = lane.get("cameras", [])

    if not cameras:
        print("[WARN] No cameras found in configuration — exiting.")
        return

    # 1) detect vlm workload
    vlm_found_any = any(camera_has_vlm(c) for c in cameras)

    if vlm_found_any:
        print("\n✔ Found LP_VLM workload — building & starting base stack")

        # 🔨 BUILD BASE
        build(BASE_COMPOSE, {"VLM_WORKLOAD_ENABLED": "1"})

        # 🚀 RUN BASE
        launch(BASE_COMPOSE, {"VLM_WORKLOAD_ENABLED": "1"})
    else:
        dbg = [c.get("workloads", []) for c in cameras]
        print(f"\n➡ No LP_VLM workload found. Workloads observed: {dbg}")
        return

    # 2) per-camera VLM workloads    



# -------------------- CLI --------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--camera-config",
        help="Camera workload mapping JSON path",
        default=CONFIG_PATH_DEFAULT
    )

    args = parser.parse_args()
    run(args)
