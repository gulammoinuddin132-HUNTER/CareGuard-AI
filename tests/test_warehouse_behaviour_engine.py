"""
Unit Tests for Warehouse Temporal Behaviour Engine (Phase 1)
------------------------------------------------------------
Verifies multi-frame sequence detection for:
- Behaviour 1: Product Dropped
- Behaviour 2: Product Dragged
- Negative controls: normal stationary, gentle handling
"""

import unittest
from src.core.warehouse_models import WarehouseObjectCategory, WarehouseBehaviourType
from src.core.warehouse_tracker import WarehouseObjectTracker
from src.core.warehouse_behaviour_engine import TemporalWarehouseBehaviourEngine
from src.core.interfaces.detector_interface import DetectedObject


class TestWarehouseBehaviourEngine(unittest.TestCase):

    def setUp(self):
        self.evidence_snapshots = []
        def mock_evidence_cb(prefix: str):
            path = f"data/evidence/mock_{prefix}.jpg"
            self.evidence_snapshots.append(path)
            return path

        self.tracker = WarehouseObjectTracker(frame_width=640, frame_height=480, confirmation_frames=1)
        self.engine = TemporalWarehouseBehaviourEngine(
            floor_y_threshold_ratio=0.82, # floor_y = 393px
            drop_velocity_threshold=100.0,
            drop_min_displacement_px=35.0,
            drag_speed_threshold=20.0,
            drag_min_duration_seconds=0.6,
            cooldown_seconds=1.0,
            evidence_capture_callback=mock_evidence_cb,
        )

    def test_product_dropped_sequence_detection(self):
        """
        Simulates drop sequence:
        t=0.0: Carton held at height y=100 (bottom=150)
        t=0.1: Carton falling at y=180 (bottom=230, vy=800 px/s)
        t=0.2: Carton falling at y=280 (bottom=330, vy=1000 px/s)
        t=0.3: Carton impacts floor at y=350 (bottom=400 >= floor_y)
        t=0.4: Carton rests stationary at y=350 (bottom=400)
        """
        frames_data = [
            (0.0, (200, 100, 50, 50)),
            (0.1, (200, 180, 50, 50)),
            (0.2, (200, 280, 50, 50)),
            (0.3, (200, 350, 50, 50)),
            (0.4, (200, 350, 50, 50)),
        ]

        triggered_events = []
        for t, bbox in frames_data:
            det = DetectedObject(class_id=0, label="carton", confidence=0.92, bbox=bbox)
            tracks = self.tracker.update([det], current_time=t)
            evts = self.engine.evaluate_frame(tracks, current_time=t)
            triggered_events.extend(evts)

        self.assertEqual(len(triggered_events), 1)
        event = triggered_events[0]
        self.assertEqual(event.behaviour_type, WarehouseBehaviourType.PRODUCT_DROPPED)
        self.assertIn(event.risk_level, ("ORANGE", "RED"))
        self.assertIn("free-fall descent", event.observed_behaviour.lower())
        self.assertIn("internal product", event.potential_risk.lower())
        self.assertIn("inspect", event.recommended_action.lower())
        self.assertEqual(len(self.evidence_snapshots), 1)

    def test_product_dragged_sequence_detection(self):
        """
        Simulates dragging sequence along floor:
        t=0.0 to t=1.0: Carton stays grounded (bottom=400 >= 393) while moving horizontally from x=50 to x=250
        """
        frames_data = [
            (0.0, (50, 350, 50, 50)),
            (0.2, (90, 350, 50, 50)),
            (0.4, (130, 350, 50, 50)),
            (0.6, (170, 350, 50, 50)),
            (0.8, (210, 350, 50, 50)),
            (1.0, (250, 350, 50, 50)),
        ]

        triggered_events = []
        for t, bbox in frames_data:
            det = DetectedObject(class_id=0, label="package", confidence=0.88, bbox=bbox)
            tracks = self.tracker.update([det], current_time=t)
            evts = self.engine.evaluate_frame(tracks, current_time=t)
            triggered_events.extend(evts)

        self.assertEqual(len(triggered_events), 1)
        event = triggered_events[0]
        self.assertEqual(event.behaviour_type, WarehouseBehaviourType.PRODUCT_DRAGGED)
        self.assertIn(event.risk_level, ("YELLOW", "ORANGE"))
        self.assertIn("dragged along", event.observed_behaviour.lower())
        self.assertIn("abrasion", event.potential_risk.lower())
        self.assertIn("trolley", event.recommended_action.lower())

    def test_negative_control_stationary_carton(self):
        """Verifies that a stationary carton on the floor generates no false alarms."""
        frames_data = [
            (0.0, (100, 350, 50, 50)),
            (0.2, (100, 350, 50, 50)),
            (0.4, (100, 350, 50, 50)),
            (0.6, (100, 350, 50, 50)),
        ]

        triggered_events = []
        for t, bbox in frames_data:
            det = DetectedObject(class_id=0, label="box", confidence=0.90, bbox=bbox)
            tracks = self.tracker.update([det], current_time=t)
            evts = self.engine.evaluate_frame(tracks, current_time=t)
            triggered_events.extend(evts)

        self.assertEqual(len(triggered_events), 0)


if __name__ == "__main__":
    unittest.main()
