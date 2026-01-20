"""Vision Language Model integration for grocery item detection."""
import json
from typing import List, Dict, Any, Tuple
from io import BytesIO
import os
import re
import time
import numpy as np
import openvino as ov
from PIL import Image
import requests
import sys
from pathlib import Path
import argparse
from utils.config import VLM_URL, VLM_MODEL, LP_IP, logger, LP_PORT, SAMPLE_MEDIA_DIR, FRAME_DIR_VOL_BASE, FRAME_DIR, LP_APP_BASE_DIR, RESULTS_DIR
from utils.prompts import *
from openvino_genai import VLMPipeline, GenerationConfig
from vlm_metrics_logger import (
    log_start_time, 
    log_end_time, 
    log_custom_event,
    log_performance_metric
)

WORKLOAD_PIPELINE_CONFIG = "/app/lp/configs/"
TARGET_WORKLOAD = "lp_vlm"  # normalized compare
# Get env variables
frames_base_dir = os.path.join(LP_APP_BASE_DIR, RESULTS_DIR, FRAME_DIR)

# VLMComponent implementation (singleton pattern)
class VLMComponent:
    _model = None
    _config = None
    
    def __init__(self, model_path, device, max_new_tokens=512, temperature=0.0):
        self.model_path = model_path
        self.device = device
        self.temperature = temperature
        self.max_new_tokens = max_new_tokens
        
        config_key = (model_path, device, temperature, max_new_tokens)
        if VLMComponent._model is None or VLMComponent._config != config_key:
            logger.info(f"[VLM] Loading model: {model_path} on {device}")
            VLMComponent._model = VLMPipeline(
                models_path=model_path,
                device=device
            )
            VLMComponent._config = config_key
            logger.info("[VLM] Model loaded.\n")
        
        self.vlm = VLMComponent._model
        self.gen_config = GenerationConfig(
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=False
        )
    
    def generate(self, prompt, images=None):
        """Generate output from VLM model."""
        if images is None:
            images = []
        
        ov_frames = [ov.Tensor(img) for img in images]
        output = self.vlm.generate(prompt, images=ov_frames, generation_config=self.gen_config)
        log_performance_metric("USECASE_2", output)
        return output


# Global VLMComponent instance
_vlm_component = None

def get_vlm_component():
    """Get or initialize VLMComponent singleton."""
    global _vlm_component
    if _vlm_component is None:
        try:
            vlm_model_name, vlm_precision, vlm_device = get_vlm_model_from_workload()
            model_path = os.environ.get("VLM_MODEL_PATH", 
                                       f"/home/pipeline-server/lp-vlm/ov-model/{vlm_model_name}/{vlm_precision}")
            device = vlm_device
        except Exception as e:
            logger.warning(f"Failed to get VLM model from config: {e}, using defaults")
            model_path = os.environ.get("VLM_MODEL_PATH", 
                                       "/home/pipeline-server/lp-vlm/ov-model/Qwen2.5-VL-7B-Instruct/int8")
            device = os.environ.get("VLM_DEVICE", "GPU")
        
        max_tokens = int(os.environ.get("VLM_MAX_TOKENS", "512"))        
        logger.info(f"Initializing VLMComponent with model_path={model_path}, device={device}")
        _vlm_component = VLMComponent(
            model_path=model_path,
            device=device,
            max_new_tokens=max_tokens,
            temperature=0.0
        )
    return _vlm_component


def extract_prompt_and_images(frame_records: Dict[str, Any], use_case: str = None) -> Tuple[str, List[np.ndarray]]:
    """Extract prompt and images from frame_records."""
    # Select prompt based on use_case
    if use_case == "decision_agent":
        prompt = AGENT_PROMPT
    else:
        prompt = COMMON_PROMPT
    
    images = []
    
    # Extract images based on frame_records format
    if use_case == "decision_agent":
        # For decision_agent, append the JSON data to prompt
        prompt = f"{prompt}\nInput {json.dumps(frame_records.get('items', {}), indent=4)}"
    else:
        # Extract image from presigned_url
        presigned_url = frame_records.get("presigned_url", "")
        if presigned_url:
            try:
                response = requests.get(presigned_url, timeout=30)
                response.raise_for_status()
                img = Image.open(BytesIO(response.content)).convert("RGB")
                img = img.resize((512, 512))
                images.append(np.array(img))
                logger.info(f"Successfully loaded image from {presigned_url}")
            except Exception as e:
                logger.error(f"Failed to load image from {presigned_url}: {str(e)}")
    
    return prompt, images


def call_vlm(
    frame_records: Dict[str, Any],
    seed: int = 0,
    use_case: str = None,
) -> Tuple[bool, Dict[str, Any], str]:
    """Call the Vision Language Model to analyze frames using VLMComponent or HTTP API.""" 
    try:
        start_time = time.time()
        logger.info("Making OVGenAI VLM call...")
        
        # Extract prompt and images
        prompt, images = extract_prompt_and_images(frame_records, use_case)            
        
        # Use local VLMComponent
        if not images and use_case != "decision_agent":
            return False, {}, "No images extracted from frame_records"
        
        vlm = get_vlm_component()
        #logger.info(f"VLM Input: {prompt}, images count: {len(images)}")
        output = vlm.generate(prompt, images=images)
        
        elapsed = time.time() - start_time
        logger.info("VLM call completed in %.2f seconds", elapsed)
        
        # Parse the output
        if hasattr(output, 'texts') and output.texts:
            raw_text = output.texts[0]
            
            # Try to extract JSON from response
            json_start = raw_text.find('[')
            json_end = raw_text.rfind(']')
            if json_start != -1 and json_end != -1 and json_end > json_start:
                json_str = raw_text[json_start:json_end + 1]
                try:
                    parsed = json.loads(json_str)
                    logger.info(f"vlm Script - [call_vlm] Successfully parsed JSON from extracted string: {parsed}")
                    return True, parsed, ""
                except Exception as e:
                    logger.error(f"vlm Script - [call_vlm] - Failed to parse JSON from extracted string: {e}")
                    return False, {}, f"Failed to parse JSON: {e}; content: {raw_text}"
            
            # If no JSON array, try to parse as generic response
            try:
                parsed = json.loads(raw_text)
                return True, parsed, ""
            except Exception as e:
                logger.error(f"vlm Script - [call_vlm] - Failed to parse JSON from raw text: {e}")
                return True, {"raw_response": raw_text}, ""
        else:
            return False, {}, "No output from VLM model"
    
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        return False, None, error_msg


def get_vlm_model_from_workload(workload_config_path: str = None) -> tuple:
    """
    Extract vlm_model, vlm_precision, and vlm_device from workload configuration.

    Returns:
        (vlm_model, vlm_precision, vlm_device)
    """
    # Resolve config path
    workload_dist = os.getenv("WORKLOAD_DIST")
    if workload_dist:
        workload_config_path = os.path.join(WORKLOAD_PIPELINE_CONFIG, workload_dist)

    if not workload_config_path:
        raise ValueError("WORKLOAD_DIST or workload_config_path must be provided")

    cfg_file = Path(workload_config_path)
    if not cfg_file.exists():
        raise FileNotFoundError(f"Workload config file not found: {cfg_file}")

    with open(cfg_file, "r") as f:
        config = json.load(f)

    workload_map = config.get("workload_pipeline_map", {})

    # 1️⃣ Select the lp_vlm workload
    pipeline_list = workload_map.get(TARGET_WORKLOAD)
    if not isinstance(pipeline_list, list):
        raise ValueError(f"No pipeline list found for workload '{TARGET_WORKLOAD}'")

    # 2️⃣ Find the VLM entry inside lp_vlm
    for entry in pipeline_list:
        if not isinstance(entry, dict):
            continue

        if entry.get("type", "").lower() == "vlm":
            vlm_model = entry.get("vlm_model")
            vlm_precision = entry.get("vlm_precision", "int8")
            vlm_device = entry.get("vlm_device", "GPU")

            if not vlm_model:
                raise ValueError("vlm_model is missing in VLM configuration")

            # Optional cleanup
            if vlm_model.startswith("Qwen/"):
                vlm_model = vlm_model.replace("Qwen/", "", 1)

            logger.info(
                "✅ Found VLM config: model=%s, precision=%s, device=%s",
                vlm_model,
                vlm_precision,
                vlm_device,
            )

            return vlm_model, vlm_precision, vlm_device

    raise ValueError(
        f"No VLM entry found in workload '{TARGET_WORKLOAD}'"
    )