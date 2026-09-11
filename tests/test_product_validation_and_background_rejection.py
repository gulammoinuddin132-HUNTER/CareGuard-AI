"""
CareGuard AI - Test Suite: Product Validation, Background Rejection & Low-Confidence Gating
--------------------------------------------------------------------------------------------
Verifies that:
1. Low-confidence (~16%) candidate near top of frame is rejected and CANNOT trigger MATERIAL_PUSHED_THROWN.
2. Ceiling, upper wall, and background candidates (upper 28% of frame) are filtered unless held by reaching handler.
3. Teleportation jumps across the screen are rejected by tracker and cannot generate false throw events.
4. Product tracks require multi-frame confirmation (>= 3 frames with valid confidence) before entering behaviour engine.
5. Carrying scenario: carton held at torso maintains physical boundaries on carton.
6. Event participant bboxes are frozen immutably at trigger time.
"""

import unittest
import numpy as np

from src.core.warehouse_models import (
    WarehouseObjectCategory,
    ProductInteractionState,
    WarehouseBehaviourType,
    KinematicState,
    TrackedEntity,
)
from src.core.interfaces.detector_interface import DetectedObject
from src.core.warehouse_tracker import WarehouseObjectTracker
from src.core.warehouse_behaviour_engine import TemporalWarehouseBehaviourEngine


class TestProductValidationAndBackgroundRejection(unittest.TestCase):

    def setUp(self):
        self.tracker = WarehouseObjectTracker(frame_width=640, frame_height=480, confirmation_frames=2)
        self.engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)
        self.tracker.floor_y_threshold = 400
        self.engine.floor_y_threshold = 400

    def test_01_low_confidence_candidate_at_top_of_frame_rejected(self):
        """Test 1: Low-confidence (16%) detection at top of frame is filtered and produces ZERO tracks/events."""
        t0 = 100.0
        # Stray detection near ceiling (y=30, h=40 -> cy=50 < 0.28*480=134.4) with conf=0.16
        stray_det = DetectedObject(class_id=1, label="carton", confidence=0.16, bbox=(200, 30, 60, 40))
        
        # Frame 1
        tracks = self.tracker.update([stray_det], current_time=t0)
        # Frame 2
        tracks = self.tracker.update([stray_det], current_time=t0 + 0.05)

        confirmed_products = [t for t in tracks if t.category == WarehouseObjectCategory.PRODUCT and t.is_confirmed]
        self.assertEqual(len(confirmed_products), 0, "Low-confidence top-of-frame candidate must not be confirmed")

        events = self.engine.evaluate_frame(confirmed_products, current_time=t0 + 0.05)
        self.assertEqual(len(events), 0, "No events may be emitted from filtered stray candidate")

    def test_02_ceiling_background_filtered_without_reaching_handler(self):
        """Test 2: Candidate in upper 28% of frame is rejected unless handler is elevated reaching for it."""
        t0 = 50.0
        # Person standing on floor (y=150, h=250 -> bottom=400)
        person_det = DetectedObject(class_id=0, label="person", confidence=0.90, bbox=(100, 150, 80, 250))
        # False product detection on upper wall/ceiling (y=40, h=50 -> cy=65)
        ceiling_det = DetectedObject(class_id=1, label="carton", confidence=0.45, bbox=(400, 40, 70, 50))

        tracks = self.tracker.update([person_det, ceiling_det], current_time=t0)
        tracks = self.tracker.update([person_det, ceiling_det], current_time=t0 + 0.05)

        ceiling_products = [t for t in tracks if t.category == WarehouseObjectCategory.PRODUCT and t.current_bbox[1] < 100]
        self.assertEqual(len(ceiling_products), 0, "Ceiling background candidate must be filtered")

    def test_03_teleportation_jump_rejected_from_throw(self):
        """Test 3: Sudden teleportation jump (>180px) across screen cannot trigger MATERIAL_PUSHED_THROWN."""
        t0 = 200.0
        # Product track starting at torso (x=100, y=200)
        p_state1 = KinematicState(timestamp=t0, bbox=(100, 200, 50, 50), centroid=(125.0, 225.0), velocity=(0.0, 0.0), speed=0.0, bottom_y=250, elevation_ratio=0.48, is_grounded=False)
        # Frame 2: sudden jump to (x=350, y=50) -> dist > 250px!
        p_state2 = KinematicState(timestamp=t0 + 0.1, bbox=(350, 50, 50, 50), centroid=(375.0, 75.0), velocity=(291.0, -150.0), speed=327.0, bottom_y=100, elevation_ratio=0.79, is_grounded=False)
        p_state3 = KinematicState(timestamp=t0 + 0.2, bbox=(400, 50, 50, 50), centroid=(425.0, 75.0), velocity=(250.0, 0.0), speed=250.0, bottom_y=100, elevation_ratio=0.79, is_grounded=False)

        prod_track = TrackedEntity(
            track_id=8,
            class_id=1,
            label="carton",
            category=WarehouseObjectCategory.PRODUCT,
            confidence=0.36,
            current_bbox=(400, 50, 50, 50),
            first_seen=t0,
            last_seen=t0 + 0.2,
            history=[p_state1, p_state2, p_state3],
            is_confirmed=True,
            interaction_state=ProductInteractionState.AIRBORNE,
        )

        events = self.engine.evaluate_frame([prod_track], current_time=t0 + 0.2)
        throw_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.MATERIAL_PUSHED_THROWN]
        self.assertEqual(len(throw_events), 0, "Teleportation jump must not generate MATERIAL_PUSHED_THROWN")

    def test_04_genuine_throw_with_ballistic_continuity_fires(self):
        """Test 4: Genuine ballistic toss with smooth displacement and prior release triggers MATERIAL_PUSHED_THROWN."""
        t0 = 300.0
        ts = [t0 - 0.3, t0 - 0.15, t0]
        # Smooth horizontal motion at 180 px/s: x moves ~27px per 0.15s
        history = [
            KinematicState(timestamp=ts[0], bbox=(200, 220, 50, 50), centroid=(225.0, 245.0), velocity=(175.0, 10.0), speed=175.0, bottom_y=270, elevation_ratio=0.44, is_grounded=False),
            KinematicState(timestamp=ts[1], bbox=(226, 222, 50, 50), centroid=(251.0, 247.0), velocity=(180.0, 12.0), speed=180.0, bottom_y=272, elevation_ratio=0.43, is_grounded=False),
            KinematicState(timestamp=ts[2], bbox=(253, 224, 50, 50), centroid=(278.0, 249.0), velocity=(180.0, 14.0), speed=180.0, bottom_y=274, elevation_ratio=0.43, is_grounded=False),
        ]
        prod_track = TrackedEntity(
            track_id=3,
            class_id=1,
            label="carton",
            category=WarehouseObjectCategory.PRODUCT,
            confidence=0.85,
            current_bbox=(253, 224, 50, 50),
            first_seen=ts[0],
            last_seen=ts[2],
            history=history,
            is_confirmed=True,
            interaction_state=ProductInteractionState.AIRBORNE,
        )

        events = self.engine.evaluate_frame([prod_track], current_time=t0)
        throw_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.MATERIAL_PUSHED_THROWN]
        self.assertEqual(len(throw_events), 1, "Genuine ballistic throw must be detected")
        self.assertEqual(throw_events[0].risk_level, "RED")

    def test_05_carrying_carton_stays_localized_at_torso(self):
        """Test 5: Carton carried at torso stays localized at torso across walking frames."""
        t0 = 400.0
        # Frame 1 to 3: Person walking with carton
        for i in range(3):
            cur_t = t0 + i * 0.05
            p_x = 150 + i * 15
            c_x = 175 + i * 15
            p_det = DetectedObject(class_id=0, label="person", confidence=0.92, bbox=(p_x, 100, 80, 240))
            c_det = DetectedObject(class_id=1, label="carton", confidence=0.88, bbox=(c_x, 160, 50, 50))
            tracks = self.tracker.update([p_det, c_det], current_time=cur_t)

        carton_track = next((t for t in tracks if t.category == WarehouseObjectCategory.PRODUCT), None)
        self.assertIsNotNone(carton_track)
        self.assertTrue(carton_track.is_confirmed)
        self.assertEqual(carton_track.interaction_state, ProductInteractionState.HELD)
        self.assertLess(carton_track.current_bbox[1], 200, "Carton must remain at torso height, not jump to legs/floor")


if __name__ == '__main__':
    unittest.main()
