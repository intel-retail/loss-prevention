"""Unit tests for the LP durable SQLite store."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from events import make_loss_event
from store import DurableEventStore


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = DurableEventStore(
            str(Path(self.directory.name) / "lp.sqlite"), "loss_prevention", "store_001"
        )

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def test_append_is_idempotent_on_ref_id(self):
        event = make_loss_event("store_001", "hidden_items", "lane-1", ref_id="r1")
        seq1, created1 = self.store.append_once(event)
        seq2, created2 = self.store.append_once(event)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(seq1, seq2)
        self.assertEqual(len(self.store.read(event_type="loss_event")), 1)

    def test_ingest_offset_roundtrip(self):
        self.assertIsNone(self.store.get_ingest_offset("/results/rs-1.jsonl"))
        self.store.set_ingest_offset("/results/rs-1.jsonl", 120, 4)
        self.store.set_ingest_offset("/results/rs-1.jsonl", 240, 7)
        self.assertEqual(self.store.get_ingest_offset("/results/rs-1.jsonl"), (240, 7))

    def test_read_filters_by_type_and_time(self):
        self.store.append(make_loss_event("store_001", "hidden_items", "lane-1", ref_id="r1", ts_ms=1000))
        self.store.append(make_loss_event("store_001", "product_switching", "lane-2", ref_id="r2", ts_ms=5000))
        in_range = self.store.read(event_type="loss_event", start_ms=2000, end_ms=6000)
        self.assertEqual([e.ref_id for e in in_range], ["r2"])

    def test_replay_is_ordered(self):
        for index, ref in enumerate(("r1", "r2", "r3")):
            self.store.append(make_loss_event("store_001", "hidden_items", "lane-1", ref_id=ref, ts_ms=index))
        self.assertEqual([e.ref_id for e in self.store.replay()], ["r1", "r2", "r3"])


if __name__ == "__main__":
    unittest.main()
