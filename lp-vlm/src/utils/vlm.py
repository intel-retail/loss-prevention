"""Vision Language Model integration for grocery item detection."""
import json
from typing import List, Dict, Any, Tuple

import requests
from utils.config import VLM_URL, VLM_MODEL, LP_IP, logger, LP_PORT,SAMPLE_MEDIA_DIR,FRAME_DIR_VOL_BASE, FRAME_DIR,LP_APP_BASE_DIR, RESULTS_DIR
from utils.prompts import *

# get env variables using os module 
import os 
frames_base_dir = os.path.join(LP_APP_BASE_DIR,RESULTS_DIR,FRAME_DIR)

def build_vlm_payload(frame_record: Dict[str, Any], seed: int = 42,use_case=None) -> Dict[str, Any]:
    """Build payload for VLM API call using video format."""
    prompt = COMMON_PROMPT
    messages_content = None
    # Build the video URLs array
    if use_case == "decision_agent":
        prompt = AGENT_PROMPT
    logger.info(f"VLM - use_case in build_vlm_payload: {use_case}, frame_record: {frame_record}")
    
    if use_case!="decision_agent":
        if  frame_record is None or frame_record=={} or frame_record.get("presigned_url") in (None,""):
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
    """Call the Vision Language Model to analyze frames. Optionally save output to MinIO with order_id and accept video_id."""
    import time
    payload = build_vlm_payload(frame_records, seed=seed, use_case=use_case)
    logger.info(f"########## VLM - VLM_URL: {VLM_URL}, LP_IP: {LP_IP}, LP_PORT: {LP_PORT}")
    logger.info(f"VLM - Payload built for VLM call: {payload}")
    if payload is None or payload=={}:
        return False, {}, "Failed to build VLM payload"
    
    try:
        start_time = time.time()
        resp = requests.post(VLM_URL, json=payload, timeout=600)
        elapsed = time.time() - start_time
        logger.info(f"VLM - VLM call time taken: {elapsed:.2f} seconds, resp {resp.status_code}, text, {resp.text} #########")
        
        if resp.status_code != 200:
            return False, {}, f"VLM call failed: {resp.status_code} {resp.text}"
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
            json_str = content[json_start: json_end + 1]
            try:
                parsed = json.loads(json_str)
                return True, parsed, ""
            except Exception as e:
                return False, {}, f"Failed to parse JSON: {e}; content: {content}"
        return False, {}, f"JSON not found in content: {content}"
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, {}, f"Exception calling VLM: {e}"