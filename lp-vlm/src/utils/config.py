"""Configuration settings for the grocery video app."""

import os
import logging

# ---------------- Base Configuration -----------------
LP_IP = os.environ.get("LP_IP", "localhost")
LP_PORT = os.environ.get("LP_PORT", "8000")
MINIO_API_HOST_PORT = os.environ.get("MINIO_API_HOST_PORT", "4000")

VLM_MODEL = os.environ.get("VLM_MODEL_NAME", "Qwen/Qwen2.5-VL-7B-Instruct")
VLM_URL = f"http://{LP_IP}:{LP_PORT}/v1/chat/completions"
SAMPLE_MEDIA_DIR = "sample-media"
LP_APP_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LP_PIPELINE_DOCKER_COMPOSE_DIR = os.path.join(LP_APP_BASE_DIR, "pipeline","docker")
LP_PIPELINE_DOCKER_COMPOSE_PATH = os.path.join(LP_PIPELINE_DOCKER_COMPOSE_DIR, "docker-compose.yaml")

RESULTS_DIR = "results"
MODELS_DIR = "models"
METADATA_DIR = "metadata"

MINIO_HOST = f"{LP_IP}:{MINIO_API_HOST_PORT}"

CONFIG_FILES_PATH = os.path.join(LP_APP_BASE_DIR, "config")
INVENTORY_FILE = os.path.join(CONFIG_FILES_PATH, "inventory.json")

VLM_RESULTS_DIR_FULL_PATH = os.path.join(LP_APP_BASE_DIR,"..", RESULTS_DIR, METADATA_DIR,"vlm_results.json")
OD_RESULTS_DIR_FULL_PATH = os.path.join(LP_APP_BASE_DIR,"..", RESULTS_DIR, METADATA_DIR,"object_detection_results.json")
AGENT_RESULTS_DIR_FULL_PATH = os.path.join(LP_APP_BASE_DIR,"..", RESULTS_DIR, METADATA_DIR,"agent_results.json")
COMMON_RESULTS_DIR_FULL_PATH = os.path.join(LP_APP_BASE_DIR,"..", RESULTS_DIR, METADATA_DIR,"results.jsonl")

####### volume-mount paths ############
FRAME_DIR_VOL_BASE = "/app"
FRAME_DIR = "frames"


METADATA_DIR_FULL_PATH = os.path.join(FRAME_DIR_VOL_BASE, RESULTS_DIR, METADATA_DIR)
FRAMES_DIR_FULL_PATH = os.path.join(FRAME_DIR_VOL_BASE, RESULTS_DIR, FRAME_DIR)

BUCKET_NAME = "loss-prevention-enhanced-vlm-results"

def setup_logging():
    """Configure logging with detailed format."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('loss_prevention_app.log')
        ]
    )
    return logging.getLogger("loss_prevention_app")

# Create logger instance
logger = setup_logging()


