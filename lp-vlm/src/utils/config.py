"""Configuration settings for the grocery video app."""

import os
import logging

# ---------------- Base Configuration -----------------
LP_IP = os.environ.get("LP_IP")
LP_PORT = os.environ.get("LP_PORT", "8000")
MINIO_API_HOST_PORT = os.environ.get("MINIO_API_HOST_PORT", "4000")

VLM_MODEL = os.environ.get("VLM_MODEL_NAME", "Qwen/Qwen2.5-VL-7B-Instruct")
VLM_URL = f"http://vlm-service:{LP_PORT}/v1/chat/completions"
SAMPLE_MEDIA_DIR = "sample-media"
LP_APP_BASE_DIR = "/app"

RESULTS_DIR = "results"
MODELS_DIR = "models"
METADATA_DIR = "metadata"
LOGS_DIR = os.path.join(LP_APP_BASE_DIR)

MINIO_HOST = f"{LP_IP}:{MINIO_API_HOST_PORT}"

CONFIG_FILES_PATH = os.path.join(LP_APP_BASE_DIR, "config")
INVENTORY_FILE = os.path.join(CONFIG_FILES_PATH, "inventory.json")

AGENT_RESULTS_DIR_FULL_PATH = os.path.join(LP_APP_BASE_DIR, RESULTS_DIR, METADATA_DIR,"agent_results.json")
COMMON_RESULTS_DIR_FULL_PATH = os.path.join(LP_APP_BASE_DIR, RESULTS_DIR, METADATA_DIR,"results.jsonl")
STREAM_RESULTS_DIR_FULL_PATH = os.path.join(LP_APP_BASE_DIR, RESULTS_DIR, METADATA_DIR,"stream_results.log")

####### volume-mount paths ############
FRAME_DIR_VOL_BASE = "/app"
FRAME_DIR = "frames"


METADATA_DIR_FULL_PATH = os.path.join(FRAME_DIR_VOL_BASE, RESULTS_DIR, METADATA_DIR)
FRAMES_DIR_FULL_PATH = os.path.join(FRAME_DIR_VOL_BASE, RESULTS_DIR, FRAME_DIR)

BUCKET_NAME = "loss-prevention-enhanced-vlm-results"

def setup_logging():
    logger = logging.getLogger("loss_prevention_app")
    logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(os.path.join(LOGS_DIR, "loss_prevention_app.log"))
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    # Avoid duplicate handlers if called multiple times
    if not logger.handlers:
        logger.addHandler(file_handler)

    return logger


# Create logger instance
logger = setup_logging()



