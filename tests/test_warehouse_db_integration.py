"""
Unit Tests for Warehouse Database Integration (Phase 1)
-------------------------------------------------------
Verifies schema initialization, logging warehouse events, querying, and stats.
"""

import os
import tempfile
import unittest
from pathlib import Path

from src.database.db_manager import DatabaseManager


class TestWarehouseDBIntegration(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_warehouse.db"
        self.db = DatabaseManager(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_log_and_retrieve_warehouse_event(self):
        """Verifies inserting a warehouse behaviour event and retrieving it."""
        rec_id = self.db.log_warehouse_event(
            event_id="WH-DROP-20260906-0001",
            behaviour_type="PRODUCT_DROPPED",
            risk_level="RED",
            confidence=0.95,
            start_timestamp="2026-09-06 14:00:00",
            end_timestamp="2026-09-06 14:00:02",
            duration_seconds=2.0,
            observed_behaviour="Carton #1 fell from 1.2m height onto concrete floor.",
            potential_risk="Internal electronics impact damage.",
            recommended_action="Quarantine and inspect carton contents.",
            product_track_id=1,
            person_track_id=2,
            evidence_frame_path="data/evidence/test_drop.jpg",
            video_source="bay3_loading.mp4",
            metadata_json='{"drop_height_m": 1.2}',
        )
        self.assertGreater(rec_id, 0)

        # Retrieve recent events
        events = self.db.get_recent_warehouse_events(limit=10)
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev.event_id, "WH-DROP-20260906-0001")
        self.assertEqual(ev.behaviour_type, "PRODUCT_DROPPED")
        self.assertEqual(ev.risk_level, "RED")
        self.assertEqual(ev.product_track_id, 1)
        self.assertEqual(ev.person_track_id, 2)
        self.assertIn("electronics", ev.potential_risk)

    def test_filter_by_risk_and_type(self):
        """Verifies filtering events by risk level and behaviour type."""
        self.db.log_warehouse_event(
            event_id="WH-DRAG-001",
            behaviour_type="PRODUCT_DRAGGED",
            risk_level="YELLOW",
            confidence=0.85,
            start_timestamp="2026-09-06 10:00:00",
            end_timestamp="2026-09-06 10:00:01",
            duration_seconds=1.0,
            observed_behaviour="Carton dragged along ground.",
            potential_risk="Bottom abrasion.",
            recommended_action="Use trolley.",
        )
        self.db.log_warehouse_event(
            event_id="WH-DROP-002",
            behaviour_type="PRODUCT_DROPPED",
            risk_level="ORANGE",
            confidence=0.90,
            start_timestamp="2026-09-06 11:00:00",
            end_timestamp="2026-09-06 11:00:02",
            duration_seconds=2.0,
            observed_behaviour="Carton dropped from stack.",
            potential_risk="Package damage.",
            recommended_action="Inspect item.",
        )

        drag_events = self.db.get_recent_warehouse_events(behaviour_type="PRODUCT_DRAGGED")
        self.assertEqual(len(drag_events), 1)
        self.assertEqual(drag_events[0].event_id, "WH-DRAG-001")

        orange_events = self.db.get_recent_warehouse_events(risk_level="ORANGE")
        self.assertEqual(len(orange_events), 1)
        self.assertEqual(orange_events[0].event_id, "WH-DROP-002")


if __name__ == "__main__":
    unittest.main()
