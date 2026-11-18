import uuid
import json
import os
from datetime import datetime


class PersonReID:
    def __init__(self, stream_id="unknown_stream"):
        self.stream_id = stream_id

        self.frame_counter = 0

        # In-memory person DB: {person_id: bbox}
        self.person_db = {}

        print(f"[custom_reid] initialized stream_id={self.stream_id}")

    def iou(self, b1, b2):
        xA = max(b1[0], b2[0])
        yA = max(b1[1], b2[1])
        xB = min(b1[2], b2[2])
        yB = min(b1[3], b2[3])

        inter_area = max(0, xB - xA) * max(0, yB - yA)

        boxA_area = (b1[2] - b1[0]) * (b1[3] - b1[1])
        boxB_area = (b2[2] - b2[0]) * (b2[3] - b2[1])

        return inter_area / float(
            boxA_area + boxB_area - inter_area + 1e-6
        )

    def load_camera_config(self):
        camera_id = "camera_001"
        workload = "unknown"

        camera_stream = os.environ.get(
            "CAMERA_STREAM",
            "camera_to_workload.json"
        )

        config_path = (
            f"/home/pipeline-server/configs/{camera_stream}"
        )

        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)

                cameras = (
                    config.get("lane_config", {})
                    .get("cameras", [])
                )
                target_workload = "sweet_heartening"
                if cameras:
                    camera = next(
                                    (entry for entry in cameras
                                    if target_workload in entry.get("workloads", [])),
                                        None,
                                )

                    camera_id = camera.get(
                        "camera_id",
                        camera_id
                    )

                    workload = target_workload

            except Exception as e:
                print(
                    "[custom_reid] ERROR reading "
                    f"camera_to_workload.json: {e}"
                )

        return camera_id, workload

    def process_frame(self, frame):
        self.frame_counter += 1

        camera_id, workload = self.load_camera_config()

        timestamp = datetime.now().strftime(
            "%Y-%m-%dT%H:%M:%S.%f"
        )[:-3]

        output = {
            "event_id": str(uuid.uuid4()),
            "timestamp": timestamp,
            "frame_id": f"frame_{self.frame_counter:06d}",
            "stream_id": self.stream_id,
            "camera_id": camera_id,
            "workload": workload,
            "persons": []
        }

        for roi in frame.regions():
            rect = roi.rect()

            person_id = roi.object_id()

            bbox = [
                rect.x,
                rect.y,
                rect.x + rect.w,
                rect.y + rect.h
            ]

            assigned_id = None

            for pid, prev_bbox in self.person_db.items():
                if self.iou(bbox, prev_bbox) > 0.5:
                    assigned_id = pid
                    break

            if assigned_id is None:
                assigned_id = f"anon_{person_id}"

            self.person_db[assigned_id] = bbox

            output["persons"].append({
                "bbox": {
                    "x": rect.x,
                    "y": rect.y,
                    "w": rect.w,
                    "h": rect.h
                },
                "confidence": round(
                    roi.confidence(),
                    2
                ),
                "person_id": assigned_id
            })

        run_timestamp = os.environ.get(
            "TIMESTAMP",
            "unknown"
        )

        json_line = json.dumps(output)

        out_file = (
            f"/home/pipeline-server/results/"
            f"rs-{run_timestamp}-{self.stream_id}.jsonl"
        )

        try:
            with open(out_file, "a") as f:
                f.write(json_line + "\n")

        except Exception as e:
            print(
                "[custom_reid] ERROR: "
                f"Failed to write to {out_file}: {e}"
            )

        return True
