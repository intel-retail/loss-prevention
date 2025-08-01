
import uuid
import json
import math
import os

frame_counter = 0
# In-memory person DB: {person_id: bbox}
person_db = {}

def iou(b1, b2):
    # Intersection over Union for two bboxes
    xA = max(b1[0], b2[0])
    yA = max(b1[1], b2[1])
    xB = min(b1[2], b2[2])
    yB = min(b1[3], b2[3])
    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = (b1[2] - b1[0]) * (b1[3] - b1[1])
    boxBArea = (b2[2] - b2[0]) * (b2[3] - b2[1])
    iou = interArea / float(boxAArea + boxBArea - interArea + 1e-6)
    return iou

def process_frame(frame):
    global frame_counter, person_db
    frame_counter += 1

    # Load camera_id and workload from camera_to_workload.json    
    camera_id = "camera_001"
    workload = "unknown"
    config_path = "/home/pipeline-server/configs/camera_to_workload.json"
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            # Assume lane_config->cameras is a list of dicts with camera_id and workloads
            cameras = config.get("lane_config", {}).get("cameras", [])
            if cameras:
                camera_id = cameras[0].get("camera_id", camera_id)
                workload_list = cameras[0].get("workloads", [])
                workload = workload_list[0] if workload_list else workload
        except Exception as e:
            print(f"[custom_reid] ERROR reading camera_to_workload.json: {e}")
    from datetime import datetime
    # ISO 8601 format with milliseconds
    timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]
    output = {
        "event_id": str(uuid.uuid4()),
        "timestamp": timestamp,
        "frame_id": f"frame_{frame_counter:06d}",
        "station_id": "self_checkout_01",
        "camera_id": camera_id,
        "camera_name": "self_checkout_overhead",        
        "persons": []
    }

    # Optionally extract regions (ROIs) if available
    for roi in frame.regions():
        rect = roi.rect()  # returns normalized bbox
        person_id = roi.object_id() # person_id
        bbox = [rect.x, rect.y, rect.x + rect.w, rect.y + rect.h]
        assigned_id = None
        # Check for matching person in DB (simple IoU threshold)
        for pid, prev_bbox in person_db.items():
            if iou(bbox, prev_bbox) > 0.5:
                assigned_id = pid
                break
        if assigned_id is None:
            assigned_id = f"anon_{person_id}"
            person_db[assigned_id] = bbox
        else:
            person_db[assigned_id] = bbox  # update position
        output["persons"].append({
            "bbox": {
                "x": rect.x,
                "y": rect.y,
                "w": rect.w,
                "h": rect.h
            },
            "confidence": round(roi.confidence(), 2),
            "person_id": assigned_id
        })
    
    timestamp = os.environ.get("TIMESTAMP")
    json_line = json.dumps(output)
    # Use camera_id and workload in output filename
    out_file = f"/home/pipeline-server/results/person-data_{timestamp}.jsonl"
    try:
        with open(out_file, "a") as f:
            f.write(json_line + "\n")
    except Exception as e:
        print(f"[custom_reid] ERROR: Failed to write to {out_file}: {e}")
    return True
