"""Unit tests for the background JSONL watcher."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from events import AGE_EVENT, ITEM_EVENT, LOSS_EVENT, make_age_estimate, make_item_verification, make_loss_event
from jsonl_watch import JsonlWatcher
from store import DurableEventStore

SECOND_NS = 1_000_000_000
CAMERA_CONFIG = {"lane_config": {"cameras": [
    {"camera_id": "cam1", "workloads": ["age_prediction"]},
    {"camera_id": "cam2", "workloads": ["hidden_items"]},
]}}


def _line(ts_ns: int, objects: list[dict]) -> str:
    return json.dumps({"timestamp": ts_ns, "objects": objects}) + "\n"


class JsonlWatcherTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.results = self.root / "results"
        self.results.mkdir()
        self.config_path = self.root / "camera.json"
        self.config_path.write_text(json.dumps(CAMERA_CONFIG), encoding="utf-8")
        self.db_path = str(self.root / "lp.sqlite")
        self.store = DurableEventStore(self.db_path, "loss_prevention", "store_001")

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def _watcher(self, store: DurableEventStore, start_ms: int = 0) -> JsonlWatcher:
        def record_age(age_range, lane, camera_id, **kwargs):
            store.append_once(make_age_estimate("store_001", age_range, lane, camera_id, **kwargs))

        def record_loss(scenario, lane, camera_id, **kwargs):
            store.append_once(make_loss_event("store_001", scenario, lane, camera_id, **kwargs))

        def record_item(item_name, matched, lane, camera_id, **kwargs):
            store.append_once(make_item_verification("store_001", item_name, matched, lane, camera_id, **kwargs))

        return JsonlWatcher(store, str(self.results), str(self.config_path), "lane-1",
                            record_age, record_loss, sample_seconds=1.0, start_ms=start_ms,
                            record_item=record_item)

    def test_vlm_results_become_item_verifications_once_finished(self):
        self.config_path.write_text(json.dumps({"lane_config": {"cameras": [
            {"camera_id": "cam1", "workloads": ["lp_vlm"]}]}}), encoding="utf-8")
        vlm_dir = self.results / "vlm-results"
        vlm_dir.mkdir()
        path = vlm_dir / "results_20261022111838.jsonl"
        path.write_text(json.dumps({"vlm_results": [
            {"item_name": "Green Apple", "match": True},
            {"item_name": "Mystery Can", "match": False}]}) + "\n", encoding="utf-8")
        watcher = self._watcher(self.store)

        self.assertEqual(watcher.poll_vlm_once(), 0)  # run not finished yet
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"agent_results": [{"item_name": "Green Apple", "match": True}]}) + "\n")
        self.assertEqual(watcher.poll_vlm_once(), 2)
        self.assertEqual(watcher.poll_vlm_once(), 0)  # unchanged file is not re-read

        events = self.store.read(event_type=ITEM_EVENT)
        self.assertEqual({(e.payload["item_name"], e.payload["matched"]) for e in events},
                         {("Green Apple", True), ("Mystery Can", False)})
        self.assertEqual({e.payload["camera_id"] for e in events}, {"cam1"})

    def test_ingests_incrementally_and_waits_for_partial_lines(self):
        path = self.results / "rs-1_1__1_2026.jsonl"
        partial = _line(SECOND_NS, [{"id": 2, "age": {"label": "20"}}])
        path.write_text(_line(0, [{"id": 1, "age": {"label": "40"}}]) + partial[:10], encoding="utf-8")
        watcher = self._watcher(self.store)

        self.assertEqual(watcher.poll_once(), (1, 0))
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(partial[10:])
        self.assertEqual(watcher.poll_once(), (1, 0))
        self.assertEqual(watcher.poll_once(), (0, 0))

        ranges = [e.payload["age_range"] for e in self.store.read(event_type=AGE_EVENT)]
        self.assertEqual(ranges, ["35-45", "18-25"])
        self.assertEqual(self.store.get_ingest_offset(str(path)), (path.stat().st_size, 1))

    def test_restart_resumes_without_duplicates(self):
        path = self.results / "rs-1_1__1_2026.jsonl"
        path.write_text(_line(0, [{"id": 1, "age": {"label": "40"}}]), encoding="utf-8")
        self._watcher(self.store).poll_once()
        self.store.close()

        # Restart: new store handle on the same DB, newer start time than the file.
        self.store = DurableEventStore(self.db_path, "loss_prevention", "store_001")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(_line(0, [{"id": 1, "age": {"label": "41"}}]))  # same sampled window
            handle.write(_line(2 * SECOND_NS, [{"id": 3, "age": {"label": "70"}}]))
        watcher = self._watcher(self.store, start_ms=10**15)
        self.assertEqual(watcher.poll_once(), (1, 0))
        ranges = [e.payload["age_range"] for e in self.store.read(event_type=AGE_EVENT)]
        self.assertEqual(ranges, ["35-45", "60+"])

    def test_ignores_files_older_than_watcher_start(self):
        old = self.results / "rs-1_1__1_old.jsonl"
        new = self.results / "rs-1_1__2_new.jsonl"
        old.write_text(_line(0, [{"id": 1, "age": {"label": "40"}}]), encoding="utf-8")
        new.write_text(_line(0, [{"id": 2, "age": {"label": "20"}}]), encoding="utf-8")
        os.utime(old, (100, 100))
        os.utime(new, (300, 300))

        self.assertEqual(self._watcher(self.store, start_ms=200_000).poll_once(), (1, 0))
        self.assertIsNone(self.store.get_ingest_offset(str(old)))
        self.assertEqual([e.payload["age_range"] for e in self.store.read(event_type=AGE_EVENT)], ["18-25"])

    def test_loss_scenario_from_camera_workload(self):
        path = self.results / "rs-2_1__1_2026.jsonl"
        path.write_text(_line(0, [{"id": 5}]) + _line(2 * SECOND_NS, [{"id": 5}, {"id": 6}]), encoding="utf-8")
        self.assertEqual(self._watcher(self.store).poll_once(), (0, 2))
        events = self.store.read(event_type=LOSS_EVENT)
        self.assertEqual({e.payload["scenario"] for e in events}, {"hidden_items"})
        self.assertEqual({e.payload["camera_id"] for e in events}, {"cam2"})

    def test_idle_without_files_or_config(self):
        watcher = self._watcher(self.store)
        self.assertEqual(watcher.poll_once(), (0, 0))
        (self.results / "rs-1_1__1_2026.jsonl").write_text(_line(0, [{"id": 1, "age": {"label": "40"}}]))
        self.config_path.unlink()
        self.assertEqual(watcher.poll_once(), (0, 0))


if __name__ == "__main__":
    unittest.main()
