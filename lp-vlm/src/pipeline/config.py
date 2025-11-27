"""Configuration settings for the grocery video app."""

import os
import logging

# ---------------- Base Configuration -----------------
LP_IP = os.environ.get("LP_IP", "localhost")
LP_PORT = os.environ.get("LP_PORT", "8000")
MINIO_API_HOST_PORT = os.environ.get("MINIO_API_HOST_PORT", "4000")


RESULTS_DIR = "results"
MODELS_DIR = "models"
METADATA_DIR = "metadata"

MINIO_HOST = f"{LP_IP}:{MINIO_API_HOST_PORT}"



####### volume-mount paths ############
FRAME_DIR_VOL_BASE = "/app"
FRAME_DIR = "frames"


METADATA_DIR_FULL_PATH = os.path.join(FRAME_DIR_VOL_BASE, RESULTS_DIR, METADATA_DIR)
FRAMES_DIR_FULL_PATH = os.path.join(FRAME_DIR_VOL_BASE, RESULTS_DIR, FRAME_DIR)

BUCKET_NAME = "loss-prevention-enhanced-vlm-results"



