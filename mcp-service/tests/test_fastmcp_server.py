"""In-memory FastMCP tests: describe + read tools, no subscribe/actions."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

# Point the module-level store at a temp log before importing tools.
_TMP = tempfile.TemporaryDirectory()
os.environ["LP_LOG_PATH"] = str(Path(_TMP.name) / "lp.sqlite")

from fastmcp import Client  # noqa: E402

from tools import mcp, record_age_estimate, record_item_verification, record_loss_event  # noqa: E402


def _rows(result) -> list:
    """Unwrap FastMCP structured output; list tools arrive as {"result": [...]}."""
    content = result.structured_content
    if isinstance(content, dict) and set(content) == {"result"}:
        return content["result"]
    return content


class FastMcpServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_describe_exposes_read_tools_and_no_actions(self):
        async with Client(mcp) as client:
            result = await client.call_tool("describe")
        data = result.data
        self.assertEqual(data["service"], "loss_prevention")
        self.assertEqual(data["act_tools"], [])
        self.assertEqual(data["subscribe"], "disabled")
        self.assertIn("loss_event", data["event_types"])
        self.assertIn("age_estimate", data["event_types"])
        self.assertIn("item_verification", data["event_types"])
        for tool in ("Get_loss_history", "Get_age_range_counts", "Get_loss_event_count", "Get_lanes",
                     "Get_item_verifications", "Get_item_verification_summary"):
            self.assertIn(tool, data["read_tools"])

    async def test_only_read_tools_are_registered(self):
        async with Client(mcp) as client:
            names = {tool.name for tool in await client.list_tools()}
        self.assertEqual(
            names,
            {"describe", "Get_loss_history", "Get_age_range_counts", "Get_loss_event_count", "Get_lanes",
             "Get_item_verifications", "Get_item_verification_summary"},
        )

    async def test_item_verification_tools(self):
        record_item_verification("Green Apple", True, "lane-1", "cam1", ref_id="t-item-1")
        record_item_verification("Mystery Can", False, "lane-1", "cam1", ref_id="t-item-2")
        async with Client(mcp) as client:
            unmatched = await client.call_tool("Get_item_verifications", {"matched": False})
            summary = await client.call_tool("Get_item_verification_summary", {})
        self.assertEqual([row["item_name"] for row in _rows(unmatched)], ["Mystery Can"])
        self.assertEqual(summary.structured_content["unmatched_items"], ["Mystery Can"])
        self.assertEqual(summary.structured_content["matched"], 1)

    async def test_read_tools_return_recorded_events(self):
        record_loss_event("hidden_items", "lane-1", "cam2", ref_id="t-loss-1")
        record_age_estimate("18-25", "lane-1", "cam1", ref_id="t-age-1")
        async with Client(mcp) as client:
            loss = await client.call_tool("Get_loss_history", {})
            counts = await client.call_tool("Get_age_range_counts", {})
            lanes = await client.call_tool("Get_lanes", {})
        self.assertTrue(any(row["scenario"] == "hidden_items" for row in _rows(loss)))
        self.assertIn({"age_range": "18-25", "detections": 1}, _rows(counts))
        self.assertIn("lane-1", _rows(lanes))


if __name__ == "__main__":
    unittest.main()
