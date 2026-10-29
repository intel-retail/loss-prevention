"""Unit tests for the LP hub-delivery envelope mapping."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from delivery import to_hub_event
from events import make_age_estimate, make_loss_event


class DeliveryTests(unittest.TestCase):
    def test_loss_event_maps_to_hub_shape(self):
        event = make_loss_event("store_001", "hidden_items", "lane-1", "cam2", ref_id="r1", ts_ms=1790674080000)
        hub = to_hub_event(event)
        expected = datetime.fromtimestamp(1790674080, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        self.assertEqual(hub["event_id"], "r1")
        self.assertEqual(hub["event_type"], "loss_event")
        self.assertEqual(hub["occurred_at"], expected)
        self.assertEqual(hub["data"]["scenario"], "hidden_items")
        self.assertEqual(hub["data"]["lane"], "lane-1")
        self.assertEqual(hub["data"]["store_id"], "store_001")
        self.assertEqual(hub["data"]["service"], "loss_prevention")

    def test_age_event_maps_to_hub_shape(self):
        event = make_age_estimate("store_001", "0-18", "lane-2", ref_id="a1", ts_ms=1790674080000)
        hub = to_hub_event(event)
        self.assertEqual(hub["event_type"], "age_estimate")
        self.assertEqual(hub["data"]["age_range"], "0-18")
        self.assertEqual(hub["data"]["lane"], "lane-2")


if __name__ == "__main__":
    unittest.main()
