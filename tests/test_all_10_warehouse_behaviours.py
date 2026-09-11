"""
tests/test_all_10_warehouse_behaviours.py
------------------------------------------
Comprehensive unit test suite verifying temporal detection for all 10
CareGuard AI warehouse handling behaviours.

1.  PRODUCT_DROPPED
2.  PRODUCT_DRAGGED
3.  ROUGH_HANDLING
4.  INCORRECT_STACKING
5.  UNSTABLE_STACKING
6.  PLACED_OUTSIDE_DESIGNATED_AREA
7.  HANDLED_WITHOUT_EQUIPMENT
8.  PALLET_POSITIONED_INCORRECTLY
9.  MATERIAL_PUSHED_THROWN
10. UNSAFE_LOADING_SEQUENCE
"""

import unittest
from src.core.warehouse_models import (
    WarehouseBehaviourType,
    WarehouseObjectCategory,
)
from src.core.warehouse_behaviour_engine import TemporalWarehouseBehaviourEngine
from src.core.warehouse_tracker import WarehouseObjectTracker
from src.core.interfaces.detector_interface import DetectedObject


class TestAll10WarehouseBehaviours(unittest.TestCase):

    def setUp(self):
        self.evidence_snapshots = []
        def mock_evidence_cb(prefix: str):
            path = f"data/evidence/mock_{prefix}.jpg"
            self.evidence_snapshots.append(path)
            return path

        self.tracker = WarehouseObjectTracker(frame_width=640, frame_height=480, confirmation_frames=1)
        self.engine = TemporalWarehouseBehaviourEngine(
            floor_y_threshold_ratio=0.82,  # 393px
            drop_velocity_threshold=100.0,
            drop_min_displacement_px=35.0,
            drag_speed_threshold=20.0,
            drag_min_duration_seconds=0.6,
            cooldown_seconds=1.0,
            evidence_capture_callback=mock_evidence_cb,
        )

    def test_01_product_dropped(self):
        """Behaviour 1: Sudden vertical drop exceeding threshold."""
        frames_data = [
            (0.0, (200, 100, 50, 50)),
            (0.1, (200, 180, 50, 50)),
            (0.2, (200, 280, 50, 50)),
            (0.3, (200, 350, 50, 50)),
            (0.4, (200, 350, 50, 50)),
        ]
        events = []
        for t, bbox in frames_data:
            det = DetectedObject(class_id=0, label="carton", confidence=0.92, bbox=bbox)
            tracks = self.tracker.update([det], current_time=t)
            evts = self.engine.evaluate_frame(tracks, current_time=t)
            events.extend(evts)

        drop_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.PRODUCT_DROPPED]
        self.assertGreaterEqual(len(drop_events), 1)
        self.assertIn(drop_events[0].risk_level, ("ORANGE", "RED"))
        self.assertIn("free-fall descent", drop_events[0].observed_behaviour.lower())
        self.assertIn("damage", drop_events[0].potential_risk.lower())
        self.assertIn("inspect", drop_events[0].recommended_action.lower())

    def test_02_product_dragged(self):
        """Behaviour 2: Package dragged across floor by worker."""
        frames_data = [
            (0.0, (50, 350, 50, 50)),
            (0.2, (90, 350, 50, 50)),
            (0.4, (130, 350, 50, 50)),
            (0.6, (170, 350, 50, 50)),
            (0.8, (210, 350, 50, 50)),
            (1.0, (250, 350, 50, 50)),
        ]
        events = []
        for t, bbox in frames_data:
            det = DetectedObject(class_id=0, label="package", confidence=0.88, bbox=bbox)
            tracks = self.tracker.update([det], current_time=t)
            evts = self.engine.evaluate_frame(tracks, current_time=t)
            events.extend(evts)

        drag_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.PRODUCT_DRAGGED]
        self.assertGreaterEqual(len(drag_events), 1)
        self.assertIn(drag_events[0].risk_level, ("YELLOW", "ORANGE"))
        self.assertIn("dragged along", drag_events[0].observed_behaviour.lower())

    def test_03_rough_handling(self):
        """Behaviour 3: Sudden deceleration impact spike without clean free-fall drop."""
        # Moving moderately fast then sharp deceleration impact (e.g. slammed down)
        frames_data = [
            (0.0, (200, 200, 50, 50)),
            (0.1, (200, 230, 50, 50)), # speed = 300 px/s
            (0.2, (200, 260, 50, 50)), # speed = 300 px/s
            (0.3, (200, 262, 50, 50)), # sharp stop: decel = (300 - 20) / 0.1 = 2800 px/s^2 >= 300
            (0.4, (200, 262, 50, 50)),
        ]
        events = []
        for t, bbox in frames_data:
            det = DetectedObject(class_id=0, label="package", confidence=0.90, bbox=bbox)
            tracks = self.tracker.update([det], current_time=t)
            evts = self.engine.evaluate_frame(tracks, current_time=t)
            events.extend(evts)

        rough_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.ROUGH_HANDLING]
        self.assertGreaterEqual(len(rough_events), 1)
        self.assertEqual(rough_events[0].risk_level, "ORANGE")
        self.assertIn("impact deceleration", rough_events[0].observed_behaviour.lower())

    def test_04_incorrect_stacking(self):
        """Behaviour 4: Heavy/larger package placed on top of smaller package."""
        # Bottom small package: (200, 300, 60, 60) -> area 3600
        # Top large package: (200, 220, 100, 80) -> area 8000 (ratio 2.22 >= 1.25)
        # gap_y = abs((220+80) - 300) = 0 <= 30
        dets = [
            DetectedObject(class_id=0, label="box", confidence=0.90, bbox=(200, 300, 60, 60)),
            DetectedObject(class_id=0, label="box", confidence=0.90, bbox=(200, 220, 100, 80)),
        ]
        events = []
        for t in [0.0, 0.1]:
            tracks = self.tracker.update(dets, current_time=t)
            evts = self.engine.evaluate_frame(tracks, current_time=t)
            events.extend(evts)

        stack_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.INCORRECT_STACKING]
        self.assertGreaterEqual(len(stack_events), 1)
        self.assertEqual(stack_events[0].risk_level, "ORANGE")
        self.assertIn("stacked on top of smaller", stack_events[0].observed_behaviour.lower())

    def test_05_unstable_stacking(self):
        """Behaviour 5: Severe tilt / center of gravity lateral offset in vertical stack."""
        # Bottom package: (200, 300, 80, 80) -> center_x = 240
        # Top package: (240, 225, 80, 75) -> center_x = 280, gap_y = abs(300 - 300) = 0, tilt = 40px >= 18px
        dets = [
            DetectedObject(class_id=0, label="box", confidence=0.90, bbox=(200, 300, 80, 80)),
            DetectedObject(class_id=0, label="box", confidence=0.90, bbox=(240, 225, 80, 75)),
        ]
        events = []
        for t in [0.0, 0.1]:
            tracks = self.tracker.update(dets, current_time=t)
            evts = self.engine.evaluate_frame(tracks, current_time=t)
            events.extend(evts)

        tilt_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.UNSTABLE_STACKING]
        self.assertGreaterEqual(len(tilt_events), 1)
        self.assertEqual(tilt_events[0].risk_level, "ORANGE")
        self.assertIn("tilting", tilt_events[0].observed_behaviour.lower())

    def test_06_placed_outside_designated_area(self):
        """Behaviour 6: Material placed stationary in pedestrian walkway exceeding dwell time."""
        # Walkway is default x: 0..256px (0.0 to 0.40 * 640), y: 240..480px (0.50 to 1.0 * 480)
        # Position box at (100, 300, 50, 50) -> centroid (125, 325) inside walkway
        events = []
        for i in range(35):
            t = i * 0.1  # 0.0 to 3.4 seconds (> 2.5s dwell)
            det = DetectedObject(class_id=0, label="box", confidence=0.90, bbox=(100, 300, 50, 50))
            tracks = self.tracker.update([det], current_time=t)
            evts = self.engine.evaluate_frame(tracks, current_time=t)
            events.extend(evts)

        walkway_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.PLACED_OUTSIDE_DESIGNATED_AREA]
        self.assertGreaterEqual(len(walkway_events), 1)
        self.assertEqual(walkway_events[0].risk_level, "ORANGE")
        self.assertIn("walkway", walkway_events[0].observed_behaviour.lower())

    def test_07_handled_without_equipment(self):
        """Behaviour 7: Worker manually carrying oversized/heavy box without MHE."""
        # Heavy cargo: bbox area >= 12000 px^2 (e.g. 120x110 = 13200)
        # Worker adjacent and carrying over distance >= 70px
        events = []
        for i in range(15):
            t = i * 0.1
            x = 200 + i * 10  # moves 140px
            worker_det = DetectedObject(class_id=1, label="person", confidence=0.92, bbox=(x, 180, 60, 160))
            box_det = DetectedObject(class_id=0, label="box", confidence=0.90, bbox=(x + 20, 200, 120, 110))
            tracks = self.tracker.update([worker_det, box_det], current_time=t)
            evts = self.engine.evaluate_frame(tracks, current_time=t)
            events.extend(evts)

        no_equip_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.HANDLED_WITHOUT_EQUIPMENT]
        self.assertGreaterEqual(len(no_equip_events), 1)
        self.assertEqual(no_equip_events[0].risk_level, "YELLOW")
        self.assertIn("transported manually", no_equip_events[0].observed_behaviour.lower())

    def test_08_pallet_positioned_incorrectly(self):
        """Behaviour 8: Pallet protruding into walkway corridor."""
        # Walkway is x: 0..256px, y: 240..480px
        # Place pallet at (200, 300, 120, 60): x from 200 to 320 -> overlap with walkway is [200, 256] = 56px (> 25px threshold)
        det = DetectedObject(class_id=2, label="pallet", confidence=0.90, bbox=(200, 300, 120, 60))
        tracks = self.tracker.update([det], current_time=0.0)
        events = self.engine.evaluate_frame(tracks, current_time=0.0)

        pallet_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.PALLET_POSITIONED_INCORRECTLY]
        self.assertGreaterEqual(len(pallet_events), 1)
        self.assertEqual(pallet_events[0].risk_level, "YELLOW")
        self.assertIn("protruding", pallet_events[0].observed_behaviour.lower())

    def test_09_material_pushed_thrown(self):
        """Behaviour 9: Package propelled with ballistic horizontal speed while elevated."""
        # Elevated (y=150, elevation_ratio > 0.10) with horizontal velocity vx = 250 px/s
        frames_data = [
            (0.0, (100, 150, 50, 50)),
            (0.1, (125, 150, 50, 50)),
            (0.2, (150, 150, 50, 50)),
            (0.3, (175, 150, 50, 50)),
        ]
        events = []
        for t, bbox in frames_data:
            det = DetectedObject(class_id=0, label="box", confidence=0.92, bbox=bbox)
            tracks = self.tracker.update([det], current_time=t)
            evts = self.engine.evaluate_frame(tracks, current_time=t)
            events.extend(evts)

        thrown_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.MATERIAL_PUSHED_THROWN]
        self.assertGreaterEqual(len(thrown_events), 1)
        self.assertEqual(thrown_events[0].risk_level, "RED")
        self.assertIn("thrown/launched", thrown_events[0].observed_behaviour.lower())

    def test_10_unsafe_loading_sequence(self):
        """Behaviour 10: Worker pulling out bottom item from underneath a stacked pile."""
        # Frame 0 to 3: Stack exists with worker next to bottom box
        # Frame 4: Worker pulls bottom box horizontally at speed >= 30 px/s while top box remains stationary
        events = []
        for i in range(6):
            t = i * 0.1
            worker_x = 100 - i * 8
            bottom_x = 180 - i * 8 # moving horizontally (~80 px/s)
            top_x = 180            # stationary

            dets = [
                DetectedObject(class_id=1, label="person", confidence=0.90, bbox=(worker_x, 260, 50, 120)),
                DetectedObject(class_id=0, label="box", confidence=0.90, bbox=(bottom_x, 320, 80, 60)),
                DetectedObject(class_id=0, label="box", confidence=0.90, bbox=(top_x, 260, 80, 60)),
            ]
            tracks = self.tracker.update(dets, current_time=t)
            evts = self.engine.evaluate_frame(tracks, current_time=t)
            events.extend(evts)

        seq_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.UNSAFE_LOADING_SEQUENCE]
        self.assertGreaterEqual(len(seq_events), 1)
        self.assertEqual(seq_events[0].risk_level, "RED")
        self.assertIn("pulled from stack", seq_events[0].observed_behaviour.lower())


if __name__ == "__main__":
    unittest.main()
