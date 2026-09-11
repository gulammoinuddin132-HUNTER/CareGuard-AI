"""
Comprehensive test suite verifying:
1. Pause Persistence: Pausing feed keeps active verified event, severity, and frozen frame intact.
2. Session Continuity: Resume continues the exact same session ID without resetting.
3. Audit Log Immutability: Event logs remain immutable across pause, resume, and controls.
4. Tight Evidence Cropping: Interaction crop tightly encloses handler + product with 10-15% contextual margin.
5. Semantic Stacking Gating: Single product, thrown product, or carried product cannot trigger UNSTABLE_STACKING.
6. Genuine Stacking Verification: Two resting products in sustained contact with lateral offset trigger UNSTABLE_STACKING.
7. Airborne Throw Discrimination: Thrown products trigger MATERIAL_PUSHED_THROWN, rejecting false stack events.
"""

import unittest
import numpy as np
import os
import tempfile
import time
from unittest.mock import MagicMock

from src.core.warehouse_models import (
    WarehouseBehaviourType,
    WarehouseBehaviourEvent,
    EventState,
    TrackedEntity,
    KinematicState,
    ProductInteractionState,
)
from src.core.interfaces.detector_interface import DetectedObject
from src.core.warehouse_behaviour_engine import TemporalWarehouseBehaviourEngine
from src.core.warehouse_tracker import WarehouseObjectTracker
from src.core.warehouse_evidence_cropper import (
    compute_interaction_crop_box,
    create_interaction_evidence_crop,
)
from src.api.state import CareGuardBackendState
from src.database.db_manager import DatabaseManager


class TestEventSemanticGatingAndPause(unittest.TestCase):
    def setUp(self):
        self.tracker = WarehouseObjectTracker(frame_width=640, frame_height=480, confirmation_frames=1)
        self.engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480, cooldown_seconds=0.0)

    # ---------------------------------------------------------
    # TEST 1: PAUSE DOES NOT CLEAR ACTIVE EVENT
    # -------------------------------------------------------------------------
    def test_01_pause_preserves_active_verified_event(self):
        """Pausing the feed must freeze playback without clearing active alert or resetting risk."""
        state = CareGuardBackendState()
        event = WarehouseBehaviourEvent(
            event_id="CG-TEST-0001",
            behaviour_type=WarehouseBehaviourType.ROUGH_HANDLING,
            risk_level="RED",
            confidence=0.92,
            start_timestamp="2026-09-10 12:00:00",
            end_timestamp="2026-09-10 12:00:01",
            duration_seconds=1.0,
            observed_behaviour="High-impact carton slam against hard surface.",
            potential_risk="Structural container fatigue and inner component shatter.",
            recommended_action="Cease rough handling; utilize mechanical assistance.",
            product_track_id=1,
            person_track_id=2,
            product_bbox=(200, 200, 80, 80),
            person_bbox=(180, 150, 100, 150),
            focus_bbox=(160, 140, 140, 160),
            handler_relationship="HELD",
            severity_reason="Extreme downward impact deceleration exceeding 900 px/s^2",
            severity_factors={"deceleration": 1200.0},
        )
        dummy_frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        state.active_verified_event = event
        state.latest_event = event.to_dict()
        state.current_risk_level = "RED"
        state.latest_processed_frame = dummy_frame
        state.latest_jpeg_bytes = b"fake_jpeg_data"

        # Act: Pause the backend
        state.pause()

        # Assert: Everything remains frozen and intact
        self.assertTrue(state.is_paused)
        self.assertIsNotNone(state.active_verified_event)
        self.assertEqual(state.active_verified_event.event_id, "CG-TEST-0001")
        self.assertEqual(state.current_risk_level, "RED")
        self.assertIsNotNone(state.latest_processed_frame)
        self.assertEqual(state.latest_jpeg_bytes, b"fake_jpeg_data")
        self.assertEqual(state.latest_event["severity_reason"], "Extreme downward impact deceleration exceeding 900 px/s^2")

    # -------------------------------------------------------------------------
    # TEST 2: RESUME CONTINUES EXACT SAME SESSION
    # -------------------------------------------------------------------------
    def test_02_resume_maintains_session_continuity(self):
        """Resuming after pause must maintain the identical session ID and continue state."""
        state = CareGuardBackendState()
        initial_session = state.active_session_id

        state.pause()
        self.assertTrue(state.is_paused)
        self.assertEqual(state.active_session_id, initial_session)

        state.resume()
        self.assertFalse(state.is_paused)
        self.assertEqual(state.active_session_id, initial_session, "Session ID must not change upon resume!")

    # -------------------------------------------------------------------------
    # TEST 3: AUDIT LOG IMMUTABILITY ACROSS PAUSE AND CONTROLS
    # -------------------------------------------------------------------------
    def test_03_audit_log_immutability(self):
        """Audit log records written to the database remain permanent across pause and resume."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            db = DatabaseManager(db_path=db_path)
            db.log_warehouse_event(
                event_id="CG-AUDIT-001",
                behaviour_type="STEPPING_ON_PRODUCT",
                risk_level="RED",
                confidence=0.95,
                start_timestamp="2026-09-10 14:00:00",
                end_timestamp="2026-09-10 14:00:02",
                duration_seconds=2.0,
                observed_behaviour="Worker foot placed directly onto corrugated package surface.",
                potential_risk="Crush damage to fragile internal contents.",
                recommended_action="Enforce strict anti-stepping policy.",
                product_track_id=3,
                person_track_id=4,
                severity_reason="Direct weight-bearing load on package",
                severity_factors={"load_duration": 2.0},
            )

            logs_before = db.get_recent_warehouse_events(limit=10)
            self.assertEqual(len(logs_before), 1)
            self.assertEqual(logs_before[0].event_id, "CG-AUDIT-001")

            # Simulate pause and resume on backend state
            state = CareGuardBackendState()
            state.pause()
            state.resume()

            logs_after = db.get_recent_warehouse_events(limit=10)
            self.assertEqual(len(logs_after), 1, "Audit log records must be immutable!")
            self.assertEqual(logs_after[0].event_id, "CG-AUDIT-001")
            self.assertEqual(logs_after[0].behaviour_type, "STEPPING_ON_PRODUCT")
        finally:
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                except Exception:
                    pass

    # -------------------------------------------------------------------------
    # TEST 4: TIGHT EVIDENCE CROP CONTAINS HANDLER + PRODUCT WITH 10-15% MARGIN
    # -------------------------------------------------------------------------
    def test_04_tight_evidence_crop(self):
        """Evidence crop must tightly enclose handler and product union with ~12% margin, avoiding scene inflation."""
        frame_shape = (720, 1280)
        product_bbox = (500, 300, 100, 100)   # Product: x=500..600, y=300..400
        handler_bbox = (450, 200, 120, 220)   # Person:  x=450..570, y=200..420

        # Union is: x in [450, 600] -> w=150, y in [200, 420] -> h=220
        crop = compute_interaction_crop_box(
            frame_shape=frame_shape,
            product_bbox=product_bbox,
            person_bbox=handler_bbox,
            behaviour_type="ROUGH_HANDLING",
            padding_ratio=0.12,
        )
        x1, y1, x2, y2 = crop
        cw = x2 - x1
        ch = y2 - y1

        # Crop must enclose both boxes completely
        self.assertLessEqual(x1, 450)
        self.assertLessEqual(y1, 200)
        self.assertGreaterEqual(x2, 600)
        self.assertGreaterEqual(y2, 420)

        # Contextual margin should be tight: width should not blow up to entire scene width
        self.assertLess(cw, 350, f"Crop width {cw} is excessively loose; expected <= 350px")
        self.assertLess(ch, 450, f"Crop height {ch} is excessively loose; expected <= 450px")

        # Floor / background exclusion: crop area should be a fraction of full frame area (1280x720 = 921600)
        crop_area = cw * ch
        frame_area = frame_shape[0] * frame_shape[1]
        self.assertLess(crop_area, frame_area * 0.25, "Crop should not encompass > 25% of entire frame for a local interaction!")

    # -------------------------------------------------------------------------
    # TEST 5: SINGLE PRODUCT IN MOTION CANNOT TRIGGER UNSTABLE_STACKING
    # -------------------------------------------------------------------------
    def test_05_single_product_cannot_trigger_stacking(self):
        """A single carton moving, rolling, or airborne cannot trigger UNSTABLE_STACKING or INCORRECT_STACKING."""
        # 1. Single moving carton on floor
        events = []
        for i in range(5):
            t = i * 0.1
            det = DetectedObject(class_id=0, label="box", confidence=0.92, bbox=(200 + i * 15, 380, 70, 70))
            tracks = self.tracker.update([det], current_time=t)
            evts = self.engine.evaluate_frame(tracks, current_time=t)
            events.extend(evts)

        stacking_evts = [e for e in events if e.behaviour_type in (WarehouseBehaviourType.UNSTABLE_STACKING, WarehouseBehaviourType.INCORRECT_STACKING)]
        self.assertEqual(len(stacking_evts), 0, "Single moving carton cannot trigger stacking alerts!")

        # 2. Single carried carton
        events = []
        for i in range(5):
            t = 0.5 + i * 0.1
            p_det = DetectedObject(class_id=1, label="person", confidence=0.90, bbox=(180 + i * 10, 200, 80, 180))
            b_det = DetectedObject(class_id=0, label="box", confidence=0.92, bbox=(190 + i * 10, 260, 60, 60))
            tracks = self.tracker.update([p_det, b_det], current_time=t)
            evts = self.engine.evaluate_frame(tracks, current_time=t)
            events.extend(evts)

        stacking_evts = [e for e in events if e.behaviour_type in (WarehouseBehaviourType.UNSTABLE_STACKING, WarehouseBehaviourType.INCORRECT_STACKING)]
        self.assertEqual(len(stacking_evts), 0, "Carried carton cannot trigger stacking alerts!")

    # -------------------------------------------------------------------------
    # TEST 6: GENUINE STACK TRIGGER REQUIRES STACK_CONTEXT AND PERSISTENT TILT
    # -------------------------------------------------------------------------
    def test_06_genuine_stacking_tilt_verification(self):
        """Two genuine resting stacked cartons with significant tilt trigger UNSTABLE_STACKING with Responsible AI telemetry."""
        # Base package resting on ground: (200, 300, 80, 80) -> center_x = 240
        # Upper package on top: (240, 225, 80, 75) -> center_x = 280, tilt = 40px >= 18px threshold
        dets = [
            DetectedObject(class_id=0, label="box", confidence=0.90, bbox=(200, 300, 80, 80)),
            DetectedObject(class_id=0, label="box", confidence=0.90, bbox=(240, 225, 80, 75)),
        ]

        events = []
        # Frame 1 (t=0.0): Stack context begins tracking (persistence = 1 < 2)
        tracks = self.tracker.update(dets, current_time=0.0)
        evts_0 = self.engine.evaluate_frame(tracks, current_time=0.0)
        events.extend(evts_0)
        # Should not trigger on single initial frame
        tilt_0 = [e for e in evts_0 if e.behaviour_type == WarehouseBehaviourType.UNSTABLE_STACKING]
        self.assertEqual(len(tilt_0), 0)

        # Frame 2 (t=0.1): Stack context verified across 2 consecutive frames -> triggers UNSTABLE_STACKING
        tracks = self.tracker.update(dets, current_time=0.1)
        evts_1 = self.engine.evaluate_frame(tracks, current_time=0.1)
        events.extend(evts_1)

        tilt_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.UNSTABLE_STACKING]
        self.assertGreaterEqual(len(tilt_events), 1)
        tilt_ev = tilt_events[0]
        self.assertEqual(tilt_ev.risk_level, "ORANGE")
        self.assertTrue(tilt_ev.metadata.get("stack_context"), "Responsible AI telemetry must confirm stack_context=True")
        self.assertIn("tilting", tilt_ev.observed_behaviour.lower())
        self.assertGreaterEqual(tilt_ev.metadata.get("tilt_offset_px", 0), 18.0)

    # -------------------------------------------------------------------------
    # TEST 7: THROWN PRODUCT TRIGGERS MATERIAL_PUSHED_THROWN, NOT UNSTABLE_STACKING
    # -------------------------------------------------------------------------
    def test_07_thrown_product_semantic_discrimination(self):
        """A carton launched/thrown through the air above resting cartons triggers MATERIAL_PUSHED_THROWN, rejecting false stack alerts."""
        events = []
        for i in range(6):
            t = i * 0.1
            fly_x = 100 + i * 35 # vx = 350 px/s
            floor_det = DetectedObject(class_id=0, label="box", confidence=0.92, bbox=(250, 380, 80, 60))
            thrown_det = DetectedObject(class_id=0, label="box", confidence=0.92, bbox=(fly_x, 220, 70, 50))
            tracks = self.tracker.update([floor_det, thrown_det], current_time=t)
            evts = self.engine.evaluate_frame(tracks, current_time=t)
            events.extend(evts)

        # UNSTABLE_STACKING must be 0
        unstable_evts = [e for e in events if e.behaviour_type == WarehouseBehaviourType.UNSTABLE_STACKING]
        self.assertEqual(len(unstable_evts), 0, "Airborne thrown carton must NEVER trigger UNSTABLE_STACKING!")

        # MATERIAL_PUSHED_THROWN must be triggered
        thrown_evts = [e for e in events if e.behaviour_type == WarehouseBehaviourType.MATERIAL_PUSHED_THROWN]
        self.assertGreaterEqual(len(thrown_evts), 1, "High horizontal airborne flight must trigger MATERIAL_PUSHED_THROWN!")
        self.assertEqual(thrown_evts[0].risk_level, "RED")


if __name__ == "__main__":
    unittest.main()
