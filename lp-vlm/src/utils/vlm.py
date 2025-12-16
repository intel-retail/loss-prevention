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

from utils.config import VLM_URL, VLM_MODEL, LP_IP, logger, LP_PORT, SAMPLE_MEDIA_DIR, FRAME_DIR_VOL_BASE, FRAME_DIR, LP_APP_BASE_DIR, RESULTS_DIR
from utils.prompts import *
from openvino_genai import VLMPipeline, GenerationConfig

# Get env variables
frames_base_dir = os.path.join(LP_APP_BASE_DIR, RESULTS_DIR, FRAME_DIR)

# VLMComponent implementation (singleton pattern)
class VLMComponent:
    _model = None
    _config = None
    
    def __init__(self, model_path, device="GPU", max_new_tokens=512, temperature=0.0):
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
        return output


# Global VLMComponent instance
_vlm_component = None

def get_vlm_component():
    """Get or initialize VLMComponent singleton."""
    global _vlm_component
    if _vlm_component is None:
        model_path = os.environ.get("VLM_MODEL_PATH", "/home/pipeline-server/lp-vlm/ov-model/Qwen2.5-VL-7B-Instruct/int8")
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
        prompt = f"{prompt}\nInput {json.dumps(frame_records)}"
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

def build_vlm_payload(frame_record: Dict[str, Any], seed: int = 42, use_case=None) -> Dict[str, Any]:
    """Build payload for VLM API call using video format."""
    prompt = COMMON_PROMPT
    messages_content = None
    
    if use_case == "decision_agent":
        prompt = AGENT_PROMPT
    
    logger.info(f"VLM - use_case in build_vlm_payload: {use_case}, frame_record: {frame_record}")
    
    if use_case != "decision_agent":
        if frame_record is None or frame_record == {} or frame_record.get("presigned_url") in (None, ""):
            logger.warning("VLM - ⚠️ No valid frame record provided to build VLM payload.")
            return {}
        else:
            # Build the message content with video format
            messages_content = [
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "image_url",
                    "image_url": {"url": frame_record.get("presigned_url")}
                }
            ]
    else:
        messages_content = [
            {
                "type": "text",
                "text": f"{prompt}\nInput {json.dumps(frame_record)}"
            }
        ]
    
    logger.info(f"VLM - messages_content: {messages_content}")
    return {
        "model": VLM_MODEL,
        "messages": [{"role": "user", "content": messages_content}],
        "max_completion_tokens": 200,
        "temperature": 0.0,
        "top_p": 1.0,
        "frequency_penalty": 1,
        "do_sample": False,
    }


def call_vlm(
    frame_records: Dict[str, Any],
    seed: int = 0,
    use_case: str = None,
) -> Tuple[bool, Dict[str, Any], str]:
    """Call the Vision Language Model to analyze frames using VLMComponent or HTTP API."""
    
    use_local = os.environ.get("USE_LOCAL_VLM", "true").lower() == "true"
    
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            start_time = time.time()
            logger.info("VLM call attempt %d/%d (local=%s)", attempt + 1, max_retries, use_local)
            
            # Extract prompt and images
            prompt, images = extract_prompt_and_images(frame_records, use_case)
            
            if use_local:
                # Use local VLMComponent
                if not images and use_case != "decision_agent":
                    return False, {}, "No images extracted from frame_records"
                
                vlm = get_vlm_component()
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
                            return True, parsed, ""
                        except Exception as e:
                            return False, {}, f"Failed to parse JSON: {e}; content: {raw_text}"
                    
                    # If no JSON array, try to parse as generic response
                    try:
                        parsed = json.loads(raw_text)
                        return True, parsed, ""
                    except:
                        return True, {"raw_response": raw_text}, ""
                else:
                    return False, {}, "No output from VLM model"
            
            else:
                # Use HTTP API (fallback)
                payload = build_vlm_payload(frame_records, seed=seed, use_case=use_case)
                logger.info(f"########## VLM - VLM_URL: {VLM_URL}, LP_IP: {LP_IP}, LP_PORT: {LP_PORT}")
                if payload is None or payload == {}:
                    return False, {}, "Failed to build VLM payload"
                
                resp = requests.post(
                    VLM_URL,
                    json=payload,
                    timeout=600
                )
                
                elapsed = time.time() - start_time
                logger.info("VLM API call completed in %.2f seconds, status: %d", elapsed, resp.status_code)
                
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except Exception:
                        return False, {}, f"Invalid VLM response: {resp.text[:200]}"
                    
                    content = None
                    if isinstance(data, dict):
                        choices = data.get('choices')
                        if choices and isinstance(choices, list):
                            first = choices[0]
                            if isinstance(first, dict):
                                message = first.get('message')
                                if isinstance(message, dict):
                                    content = message.get('content')
                    
                    if not content:
                        return False, {}, f"No content in VLM response: {data}"
                    
                    json_start = content.find('[')
                    json_end = content.rfind(']')
                    if json_start != -1 and json_end != -1 and json_end > json_start:
                        json_str = content[json_start:json_end + 1]
                        try:
                            parsed = json.loads(json_str)
                            return True, parsed, ""
                        except Exception as e:
                            return False, {}, f"Failed to parse JSON: {e}; content: {content}"
                    return False, {}, f"JSON not found in content: {content}"
                else:
                    error_msg = f"VLM returned status {resp.status_code}: {resp.text[:200]}"
                    logger.error(error_msg)
                    
                    # Don't retry on client errors (4xx)
                    if 400 <= resp.status_code < 500:
                        return False, None, error_msg
                    
                    # Retry on server errors (5xx)
                    if attempt < max_retries - 1:
                        logger.warning("Retrying in %d seconds...", retry_delay)
                        time.sleep(retry_delay)
                        continue
                    
                    return False, None, error_msg
        
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            logger.error(error_msg)
            
            if attempt < max_retries - 1:
                logger.warning("Retrying in %d seconds...", retry_delay)
                time.sleep(retry_delay)
                continue
            
            return False, None, error_msg
        
        except requests.exceptions.Timeout as e:
            error_msg = f"Request timeout: {str(e)}"
            logger.error(error_msg)
            
            if attempt < max_retries - 1:
                logger.warning("Retrying in %d seconds...", retry_delay)
                time.sleep(retry_delay)
                continue
            
            return False, None, error_msg
        
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
    
    return False, None, "Max retries exceeded"