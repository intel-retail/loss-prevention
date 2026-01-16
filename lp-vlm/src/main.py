import sys,os
import json
import subprocess
import os
import time
import queue
from collections import defaultdict
import threading
import time

from utils.config import (SAMPLE_MEDIA_DIR,
                          RESULTS_DIR,
                          LP_APP_BASE_DIR,
                          
                          LP_IP,MINIO_API_HOST_PORT, 
                          COMMON_RESULTS_DIR_FULL_PATH,
                          )
from utils.vlm import call_vlm
from utils.frames_processor import get_best_frame
from agent.agent import ConfigAgent
import re
from utils.save_results import get_presigned_url
from utils.config import logger,INVENTORY_FILE
from utils.rabbitmq_consumer import ODConsumer
import traceback
from workload_utils import get_video_name_only
from vlm_metrics_logger import (
    log_start_time, 
    log_end_time, 
    log_custom_event,
    log_performance_metric
)
# ============================================================================
# GLOBAL VARIABLES AND QUEUES
# ============================================================================
BOLD = "\033[1m"
UNDERLINE = "\033[4m"
RESET = "\033[0m"
CYAN = "\033[34m"
RABBITMQ_USER = os.environ.get("RABBITMQ_USER")
RABBITMQ_PASSWORD = os.environ.get("RABBITMQ_PASSWORD")

vlm_queue = queue.Queue()
result_queue = queue.Queue()
od_message_queue = queue.Queue()
inventory_list = None
inventory_set = None

# ============================================================================
# Helper Function
# ============================================================================
def write_json_to_file(data, file_path):
    """
    Append a dict as a new line to a JSONL file.
    """
    try:
        with open(file_path, "a") as f:
            f.write(json.dumps(data) + "\n")

        logger.info(f"Appended JSONL record → {file_path}")

    except Exception as e:
        logger.error(f"Error writing JSONL to {file_path}: {e}+\n{traceback.format_exc()}")
        
def load_json_from_file(file_path):
    global inventory_list
    """
    Loads JSON data from a file and returns it as a Python object.

    Args:
        file_path: Path to the JSON file to read
    """
    try:
        with open(file_path, "r") as f:
            inventory_list = json.load(f)
            return inventory_list
    except Exception as e:
        logger.error(f"Pipeline Script - Error loading {file_path} file: %s", str(e)+"\n"+traceback.format_exc())
        return f"🤖 Agent: ❌ Failed - Could not load {file_path}"
    
        
# ============================================================================
# WORKER THREADS
# ============================================================================

def vlm_enhancer_consumer():
    """Consumer thread that processes VLM enhancement requests"""
    logger.info("Pipeline Script - [vlm_enhancer_consumer] Started")
    try:
        while True:
            payload = vlm_queue.get()
            if isinstance(payload, str):
                payload = json.loads(payload)
            
            if payload and "msg_type" in payload and payload["msg_type"] == "STREAM_END":
                logger.info("Pipeline Script - VLM Consumer received end of stream signal")
                result_queue.put(payload)
                break
            
            if payload and "data" in payload and len(payload["data"]) > 0:
                data = payload["data"]
                logger.info("Pipeline Script - Calling VLM with payload: %s", data)
                start_time = time.time()
                logger.info("⏳ [%s] Waiting for VLM call to finish ===", 
                            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time)))
                valid,result,err_msg = call_vlm(data, use_case=data.get("use_case", ""))
                logger.info("Pipeline Script - VLM Result: %s", result)
                payload["data"] = {"result": result, "valid": valid, "error": err_msg}
                result_queue.put(payload)
            vlm_queue.task_done()
            
            #print("⏳ Waiting for VLM call to finish")
    except Exception as e:
        logger.error("Pipeline Script - VLM Enhancer Consumer Error: %s", str(e))


# ============================================================================
# DATA STREAM READERS
# ============================================================================

def read_object_detection_stream():
    """Generator to read object detection messages from queue"""
    while True:
        while not od_message_queue.empty():
            item = od_message_queue.get(timeout=15)
            yield item
        time.sleep(0.1)


def read_vlm_results_stream():
    """Generator to read VLM results from queue"""
    while True:
        while not result_queue.empty():
            item = result_queue.get()
            yield item
        time.sleep(0.1)


# ============================================================================
# OBJECT DETECTION PIPELINE
# ============================================================================

def process_object_detection_results(video_file, use_case):
    """Process object detection results and prepare for VLM enhancement"""
    global result_queue, vlm_queue, inventory_list,inventory_set
    if not inventory_list:
        inventory_list = load_json_from_file(INVENTORY_FILE)
        inventory_set = set(item.strip().lower() for item in inventory_list)
    if video_file is None:
        logger.error("Pipeline Script - No video file provided for processing")
        yield "📹 Object Detection: ❌ Failed - No video uploaded", {}
        return
    
    try:
        # Process streaming results
        best_frames = defaultdict(dict)
        ui_items = []
        for payload in read_object_detection_stream():
            try:
                if isinstance(payload, str):
                    payload = json.loads(payload)
                
                if payload and "msg_type" in payload and payload["msg_type"] == "STREAM_END":
                    logger.info("Pipeline Script - Object Detection stream ended")
                    break
                
                if not payload or not "data" in payload or not len(payload["data"]) > 0:
                    continue
                data = payload["data"]
                item = data.get("item_name")
                frame_names = data.get("frames", [])
                #print("\n\nDATA:",data)
                
                if item in  inventory_set:
                    print(f"✅ Item found {BOLD}{CYAN}{item}{RESET} in inventory, ❌ skipping VLM call and best frame selection call")
                    logger.info("Pipeline Script - Item '%s' found in inventory, skipping VLM", item)
                    ui_items.append({"item_name":item,"match":True})
                    result_queue.put({"item_name": item})
                    continue
                import time

                log_start_time(f"USECASE_1")

                # compute time to get best frame
                best_frame, score = get_best_frame(frame_names, bucket_name=data.get("bucket", ""))
                
                print(f"🏆 Best frame for {BOLD}{CYAN}{item}{RESET}: {os.path.basename(best_frame)} | Stability score: {score:.4f}")

                presigned_url = get_presigned_url(best_frame, bucket_name=data.get("bucket", ""))
                
                if not presigned_url:
                    logger.warning("Pipeline Script - Could not generate presigned URL for frame: %s", best_frame)
                    continue
                
                best_frames[item] = {
                    "best_frame": presigned_url,
                    "stability_score": score
                }
                item_rec = {"item_name":item,"match":False}
                ui_items.append(item_rec)
                enhancer_payload = {"presigned_url": presigned_url, "use_case": use_case}
                payload["data"] = enhancer_payload

                vlm_queue.put(payload)
                logger.info("Pipeline Script - Sent to VLM queue: %s", enhancer_payload)

        
            except Exception as e:
                logger.error("Pipeline Script - Error processing OD payload: %s", str(e))
                continue
        write_json_to_file({"od_results": ui_items}, COMMON_RESULTS_DIR_FULL_PATH)
        yield "📹 Object Detection: ✅ Completed", {"od_results": ui_items}

    except Exception as e:
        logger.error("Pipeline Script - Error in object detection processing: %s", str(e))
        yield f"📹 Object Detection: ❌ Failed - {str(e)}", {}


# ============================================================================
# VLM ENHANCEMENT PIPELINE
# ============================================================================

def process_vlm_enhancement():
    """Process VLM enhancement results from the result queue"""
    global inventory_list, inventory_set
    if not inventory_list:
        inventory_list = load_json_from_file(INVENTORY_FILE)
        inventory_set = set(item.strip().lower() for item in inventory_list)
    try:
        for payload in read_vlm_results_stream():
            if isinstance(payload, str):
                    payload = json.loads(payload)
            if payload and "msg_type" in payload and payload["msg_type"] == "STREAM_END":
                logger.info("Pipeline Script - VLM enhancement stream ended")
                break
            
            if payload and "data" in payload and len(payload["data"]) > 0:
                data = payload["data"]

                if "error" in data and data["error"]:
                    logger.error("Pipeline Script - VLM enhancement error: %s", data["error"])
                    yield "🤖 VLM Enhancement: ❌ Failed - " + data["error"], []
                    return
                final_result = data.get("result", [])
                if final_result and len(final_result)>0:
                    for result in final_result:
                        item_name = result.get("item_name","").strip().lower()
                        if item_name in inventory_set:
                            result["match"] = True
                        else:
                            result["match"] = False
                logger.info("Pipeline Script - VLM enhancement result: %s", final_result)
                yield "🤖 VLM Enhancement: ⚡ Running", final_result
        time.sleep(0.5)  # Ensure all processing is done
        yield "🤖 VLM Enhancement: ✅ Completed", []
    
    except Exception as e:
        logger.error("Pipeline Script - Error in VLM enhancement processing: %s", str(e))
        yield f"🤖 VLM Enhancement: ❌ Failed - {str(e)}", []
        return 


# ============================================================================
# MAIN PIPELINE ORCHESTRATION
# ============================================================================

def execute_loss_prevention_pipeline(video_file):
    """Main orchestration function for the entire pipeline"""
    try:
        if video_file is None:
            logger.error("Pipeline Script - No video file uploaded")
            yield "📹 Object Detection: ❌ Failed - No video uploaded", {}, "🤖 VLM Enhancement: ⏳ Pending", [], "🤖 Agent: ⏳ Pending", []
            return
        
        # Phase 1: Object Detection
        od_completed = False
        final_od_status = ""
        final_od_results = {}
        final_vlm_results = []
        use_case = os.path.splitext(video_file)[0].lower()
        for od_status, od_results in process_object_detection_results(video_file, use_case):
            final_od_status = od_status
            final_od_results = od_results
            yield od_status, od_results, "🤖 VLM Enhancement: ⏳ Pending", [], "🤖 Agent: ⏳ Pending", []
            
            if "❌ Failed" in od_status:
                logger.error("Pipeline Script - Object detection failed, skipping VLM")
                yield od_status, od_results, "🤖 VLM Enhancement: ❌ Skipped", [], "🤖 Agent: ❌ Skipped", []
                return
            
            if "✅" in od_status and "Completed" in od_status:
                od_completed = True
                yield "📹 Object Detection: ✅ Completed", final_od_results, "🤖 VLM Enhancement: ⚡ Running", [], "🤖 Agent: ⏳ Pending", []
        
        # Phase 2: VLM Enhancement
        vlm_queue.put({"msg_type": "STREAM_END", "data": {}})
        
        for vlm_status, vlm_results in process_vlm_enhancement():
            final_vlm_results.extend(vlm_results)
            unique_results = list({d['item_name']: d for d in final_vlm_results}.values())
            yield "📹 Object Detection: ✅ Completed", final_od_results, vlm_status, unique_results, "🤖 Agent: ⏳ Pending", []
        
        write_json_to_file({"vlm_results":unique_results}, COMMON_RESULTS_DIR_FULL_PATH)
        
        
        yield "📹 Object Detection: ✅ Completed", final_od_results, "🤖 VLM Enhancement: ✅ Completed", unique_results, "🤖 Agent: ⚡ Running", []
        
        agent_results = []
        # Phase 3: Agent Call for inventory validation
        for record in unique_results:
            agent_status, agent_result = agent_call(record)
            if agent_status:
                agent_results.extend(agent_result)
            log_end_time(f"USECASE_1")
        write_json_to_file({"agent_results":agent_results}, COMMON_RESULTS_DIR_FULL_PATH)
        
        yield "🧠 Decision Agent: ✅ Completed", final_od_results, "🤖 VLM Enhancement: ✅ Completed", unique_results, agent_status, agent_results
        
    except Exception as e:
        error_message = f"Pipeline Error: {str(e)}"
        logger.error("Pipeline Script - Critical error in pipeline: %s", error_message)
        logger.error(traceback.format_exc())
        yield f"🧠 Decision Agent: ❌ Failed - {error_message}", {}, f"🤖 VLM Enhancement: ❌ Failed - {error_message}", [], f"🤖 Agent: ❌ Failed - {error_message}", []

# ============================================================================
# AGENT CALL FOR INVENTORY VALIDATION
# ============================================================================

def agent_call(item, use_case="decision_agent"):
    """
    Agent call function that validates items against inventory and calls VLM for unmatched items.
    
    Args:
        item: Single item from VLM enhancement
        use_case: The use case for the pipeline
    
    Returns:
        tuple: (status_message, updated_results)
    """
    global inventory_list, inventory_set
    
    try:
        logger.info(f"Pipeline Script - [agent_call] Starting inventory validation {item}")
        
        if inventory_list is None:
            inventory_list = load_json_from_file(INVENTORY_FILE)
            inventory_set = set(item.strip().lower() for item in inventory_list)
        

        
        item_name = item.get("item_name", "").strip().lower()
            
        if item_name in inventory_set:
            logger.info(f"Pipeline Script - [agent_call] Item '{item_name}' found in inventory")
            return True,[item]
        
        # Call VLM for unmatched items
        logger.info("Pipeline Script - [agent_call] Item '%s' NOT found in inventory, will validate with VLM", item_name)
        
        # Prepare data for VLM call
        vlm_data = {
            "items": item_name,
            "use_case": use_case
        }       
        valid, vlm_validation_result, err_msg = call_vlm(vlm_data, use_case=use_case)
        logger.info(f"Pipeline Script - [agent_call] result - {vlm_validation_result}-{valid}-{err_msg}")
        
        if not valid or err_msg or vlm_validation_result and not isinstance(vlm_validation_result, list):
            logger.error(f"Pipeline Script - [agent_call] VLM validation failed for item_name {item_name}: %s", err_msg)
            return False, []
        # Process VLM validation results
        logger.info("Pipeline Script - [agent_call] Agent validation completed. Item: %d, Validated: %d", 
                    item_name, vlm_validation_result)
        return True, vlm_validation_result
        
    except Exception as e:
        logger.error("Pipeline Script - [agent_call] Error in agent call: %s", str(e))
        logger.error(traceback.format_exc())
        return False, []
# ============================================================================
# INITIALIZATION
# ============================================================================

# Initialize all queues and consumers
def init_pipeline_components():
    """Initialize all necessary components for the pipeline"""
    global vlm_queue, result_queue, od_message_queue
        
    # Object Detection Consumer
    od_consumer = ODConsumer(od_message_queue,RABBITMQ_USER,RABBITMQ_PASSWORD)
    od_consumer.start_consumer()
    
    # VLM Enhancer Consumer
    vlm_enhancer_thread = threading.Thread(target=vlm_enhancer_consumer)
    vlm_enhancer_thread.start()
    
    return od_consumer, vlm_enhancer_thread

def main(video_file_name=None):
    """Main function to execute the loss prevention pipeline"""    
    if video_file_name is None:
        camera_stream = os.getenv("CAMERA_STREAM")
        logger.info("Pipeline Script - camera_stream file name===: %s", camera_stream)
        if not camera_stream:
            raise RuntimeError("CAMERA_STREAM environment variable is not set")

        camera_config_path = f"/app/lp/configs/{camera_stream}"
        video_file_name = get_video_name_only(camera_config_path)
    
    
    logger.info("Pipeline Script - VIDEO_NAME:======== %s", video_file_name)
    
    global od_results_shown, od_pipeline_status, vlm_pipeline_status
    
    agent_pipeline_status = False
    
    for step in execute_loss_prevention_pipeline(video_file_name):
        od_status, od_results, vlm_status, vlm_results, agent_status, agent_results = step
        
        # Print status updates
        if "pending" not in od_status.replace(" ","").lower() and not od_pipeline_status:
            print(f"{od_status}")
            od_pipeline_status = True
        if "pending" not in vlm_status.replace(" ","").lower() and not vlm_pipeline_status:
            print(f"{vlm_status}")
            vlm_pipeline_status = True
        if "pending" not in agent_status.replace(" ","").lower() and not agent_pipeline_status:
            print(f"{agent_status}")
            agent_pipeline_status = True
        
        # Log the pipeline step
        logger.info("Pipeline Script - Pipeline Step: OD=%s, VLM=%s, Agent=%s", od_status, vlm_status, agent_status)
        
        # Check and display Object Detection completion
        if "✅" in od_status and "Completed" in od_status and not od_results_shown:
            logger.info("Pipeline Script - Object Detection COMPLETED")
            logger.info("Pipeline Script - Object Detection Results: %s", od_results)
            print(f"{od_status}")
            print(f"📹 Object Detection Results:\n{json.dumps(od_results, indent=2)}\n\n")
            od_results_shown = True
        
        # Check and display VLM Enhancement completion
        if "✅" in vlm_status and "Completed" in vlm_status:
            logger.info("Pipeline Script - VLM Enhancement COMPLETED")
            logger.info("Pipeline Script - VLM Enhancement Results: %s", vlm_results)
            print(f"{vlm_status}")
            print(f"🤖 VLM Enhancement Results:\n{json.dumps(vlm_results, indent=2)}\n\n")
        
        # Check and display Agent completion
        if "✅" in agent_status and "completed" in agent_status.lower():
            logger.info("Pipeline Script - Agent COMPLETED")
            logger.info("Pipeline Script - Agent Results: %s", agent_results)
            print(f"{agent_status}")
            print(f"🤖 Agent Results:\n{json.dumps(agent_results, indent=2)}")
        
        # Break on any failures
        if "❌" in od_status or "Failed" in od_status or "❌" in vlm_status or "Failed" in vlm_status or "❌" in agent_status or "Failed" in agent_status:
            logger.error(f"Pipeline Script - Pipeline failed at step: OD=%s, VLM=%s, Agent=%s", od_status, vlm_status, agent_status)
            break
    
    return od_status, od_results, vlm_status, vlm_results, agent_status, agent_results


if __name__ == "__main__":
    # Check if VLM workload is enabled
    vlm_workload_enabled = os.environ.get("VLM_WORKLOAD_ENABLED", "0")
    
    if vlm_workload_enabled != "1":
        logger.info("VLM_WORKLOAD_ENABLED is not set to 1. Stopping container.")
        print("VLM workload is disabled. Exiting...")
        sys.exit(0)
    
    logger.info("VLM_WORKLOAD_ENABLED is set to 1. Starting pipeline...")
    
    # Initialize pipeline components
    od_consumer, vlm_enhancer_thread = init_pipeline_components()
    od_results_shown, od_pipeline_status, vlm_pipeline_status = False, False, False
    print("\n================ START OF PIPELINE RUN =================\n")
    
    result = main() 
    print(f"\n{'='*60}\nFinal Pipeline Results:\n{'='*60}")
    
    # Check if pipeline was successful
    od_status, od_results, vlm_status, vlm_results, agent_status, agent_results = result
    
    pipeline_successful = (
        "✅" in od_status and "Completed" in od_status and
        "✅" in vlm_status and "Completed" in vlm_status and
        "✅" in agent_status and "completed" in agent_status.lower()
    )
    
    if pipeline_successful:
        print(f"✅ Pipeline executed successfully!\n")
        print(f"OD Status: {od_status}")
        print(f"OD Results: {json.dumps(od_results, indent=2)}")
        print(f"\nVLM Status: {vlm_status}")
        print(f"VLM Results: {json.dumps(vlm_results, indent=2)}")
        print(f"\nAgent Status: {agent_status}")
        print(f"Agent Results: {json.dumps(agent_results, indent=2)}")
    else:
        print(f"❌ Pipeline execution failed or incomplete\n")
        print(f"OD Status: {od_status}")
        print(f"VLM Status: {vlm_status}")
        print(f"Agent Status: {agent_status}")

    vlm_enhancer_thread.join() 
    logger.info("=== VLM Enhancer finished ===")
    logger.info("=== END OF PIPELINE RUN ===\n\n\n")