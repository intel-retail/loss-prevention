"""Unit tests for the JSONL importer parsing/aggregation logic."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import jsonl_ingest


class JsonlIngestTests(unittest.TestCase):
    def test_bucket_age_boundaries(self):
        cases = {10: "0-18", 17: "0-18", 18: "18-25", 24: "18-25", 25: "25-35",
                 34: "25-35", 40: "35-45", 55: "45-60", 60: "60+", 73: "60+"}
        for age, label in cases.items():
            self.assertEqual(jsonl_ingest.bucket_age(age), label)

    def test_branch_index_from_filename(self):
        self.assertEqual(jsonl_ingest.branch_index_from_filename("rs-1_1__3_2026.jsonl"), 0)
        self.assertEqual(jsonl_ingest.branch_index_from_filename("rs-2_1__6_2026.jsonl"), 1)
        self.assertIsNone(jsonl_ingest.branch_index_from_filename("other.jsonl"))

    def test_filter_files_since_excludes_previous_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            old = Path(directory) / "rs-1_old.jsonl"
            new = Path(directory) / "rs-1_new.jsonl"
            old.touch()
            new.touch()
            os.utime(old, (100, 100))
            os.utime(new, (200, 200))
            self.assertEqual(jsonl_ingest.filter_files_since([str(old), str(new)], 150_000), [str(new)])
            self.assertEqual(jsonl_ingest.filter_files_since([str(old), str(new)], None), [str(old), str(new)])

    def test_camera_index_map(self):
        config = {"lane_config": {"cameras": [
            {"camera_id": "cam1", "workloads": ["asc_obj_detection_age_prediction_face_detection"]},
            {"camera_id": "cam2", "workloads": ["hidden_items"]},
        ]}}
        mapping = jsonl_ingest.camera_index_map(config)
        self.assertEqual(mapping[0]["camera_id"], "cam1")
        self.assertEqual(mapping[1]["workloads"], ["hidden_items"])

    def test_vlm_items_wait_for_agent_results_and_merge_verdicts(self):
        od = json.dumps({"od_results": [{"item_name": "bottle", "match": False}]})
        vlm = json.dumps({"vlm_results": [
            {"item_name": "Coca-Cola Bottle Large", "match": True},
            {"item_name": "Mystery Can", "match": False},
        ]})
        agent = json.dumps({"agent_results": [{"item_name": "Coca-Cola Bottle Large", "match": True}]})
        self.assertIsNone(jsonl_ingest.vlm_items_from_results([od, vlm]))
        items = jsonl_ingest.vlm_items_from_results([od, vlm, agent])
        self.assertEqual(items, [
            {"item_name": "Coca-Cola Bottle Large", "matched": True},
            {"item_name": "Mystery Can", "matched": False},
        ])

    def test_read_complete_lines_leaves_partial_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rs-1_1__1_2026.jsonl"
            path.write_bytes(b'{"a":1}\n{"b":2}\n{"c":')
            lines, offset = jsonl_ingest.read_complete_lines(path, 0)
            self.assertEqual(lines, ['{"a":1}', '{"b":2}'])
            self.assertEqual(offset, 16)
            self.assertEqual(jsonl_ingest.read_complete_lines(path, offset), ([], offset))
            with open(path, "ab") as handle:
                handle.write(b'3}\n')
            lines, offset = jsonl_ingest.read_complete_lines(path, offset)
            self.assertEqual(lines, ['{"c":3}'])
            self.assertEqual(offset, path.stat().st_size)

    def test_parse_record_skips_blank_and_bad_lines(self):
        self.assertIsNone(jsonl_ingest.parse_record(""))
        self.assertIsNone(jsonl_ingest.parse_record("not-json"))
        self.assertIsNone(jsonl_ingest.parse_record("[1, 2]"))
        self.assertEqual(jsonl_ingest.parse_record('{"timestamp": 5, "objects": [{"id": 1}]}'),
                         (5, [{"id": 1}]))

    def test_events_from_lines_samples_and_buckets_age(self):
        lines = [json.dumps(r) for r in (
            {"timestamp": 0, "objects": [{"id": 1, "age": {"label": "40"}, "gender": {"label": "Male"}}]},
            {"timestamp": 300_000_000, "objects": [{"id": 2, "age": {"label": "20"}}]},  # same window
            {"timestamp": 1_200_000_000, "objects": [{"id": 3, "age": {"label": "20"}}, {"id": 4}]},
        )]
        camera = {"camera_id": "cam1", "workloads": ["age_prediction"]}
        age, loss, window = jsonl_ingest.events_from_lines("rs-1", lines, camera, 1_000_000_000, None)
        self.assertEqual([e["age_range"] for e in age], ["35-45", "18-25"])
        self.assertEqual(age[0]["gender"], "male")
        self.assertEqual(age[1]["ref_id"], "rs-1-age-1200000000-0")
        self.assertEqual(loss, [])
        self.assertEqual(window, 1)
        # Resuming with the carried window drops already-sampled windows.
        age, _, _ = jsonl_ingest.events_from_lines("rs-1", lines, camera, 1_000_000_000, window)
        self.assertEqual(age, [])

    def test_events_from_lines_maps_loss_scenario_once_per_track(self):
        lines = [json.dumps({"timestamp": t, "objects": [{"id": 7}]}) for t in (0, 2_000_000_000)]
        camera = {"camera_id": "cam2", "workloads": ["hidden_items"]}
        _, loss, _ = jsonl_ingest.events_from_lines("rs-2", lines, camera, 1_000_000_000, None)
        self.assertEqual(loss, [{"scenario": "hidden_items", "tracking_id": "7",
                                 "ref_id": "rs-2-loss-hidden_items-7"}])


if __name__ == "__main__":
    unittest.main()
