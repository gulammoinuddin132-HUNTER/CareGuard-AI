"""
tests/test_priority_corrections.py
----------------------------------
Automated test suite validating all five priority corrections for CareGuard AI:
  1. Priority 1: Multi-upload stability (5 consecutive uploads without hang)
  2. Priority 2: Action Discrimination (Rolling carton rejected for PRODUCT_DROPPED; Free-fall accepted)
  3. Priority 3: Multi-product tracking (stacked/adjacent cartons tracked simultaneously)
  4. Priority 4: Event Participant Focus (tight union + 15% margin, no whole-frame / road fallbacks)
  5. Priority 5: Stepping on Carton (foot-on-top-surface geometry and temporal persistence)
"""

import unittest
import time
from pathlib import Path
from fastapi.testclient import TestClient

from config import WAREHOUSE_FLOOR_Y_RATIO
from src.core.warehouse_models import (
    WarehouseObjectCategory,
    ProductInteractionState,
    WarehouseBehaviourType,
    KinematicState,
    TrackedEntity,
    WarehouseBehaviourEvent,
)
from src.core.warehouse_tracker import WarehouseObjectTracker, DetectedObject
from src.core.warehouse_behaviour_engine import TemporalWarehouseBehaviourEngine
from src.core.warehouse_evidence_cropper import compute_interaction_crop_box
from src.core.warehouse_risk_policy import calculate_risk_severity, WarehouseRiskTier
from src.api.app import app
from src.api.state import CareGuardBackendState


class TestPriorityCorrections(unittest.TestCase):

    def setUp(self):
        self.engine = TemporalWarehouseBehaviourEngine(
            floor_y_threshold_ratio=0.80,
            frame_width=640,
            frame_height=480,
        )
        self.tracker = WarehouseObjectTracker(
            frame_width=640,
            frame_height=480,
            confirmation_frames=2,
            floor_y_threshold_ratio=0.80,
        )

    # -------------------------------------------------------------------------
    # Priority 5: STEPPING ON PRODUCT
    # -------------------------------------------------------------------------

    def test_stepping_on_product_detection(self):
        """Handler standing on top surface of carton for >= 0.35s triggers STEPPING_ON_PRODUCT."""
        t_base = 100.0
        prod = TrackedEntity(
            track_id=1,
            class_id=1,
            label="carton",
            category=WarehouseObjectCategory.PRODUCT,
            confidence=0.85,
            current_bbox=(200, 360, 80, 60),
            first_seen=t_base,
            last_seen=t_base + 0.5,
            is_confirmed=True,
        )
        person = TrackedEntity(
            track_id=2,
            class_id=0,
            label="person",
            category=WarehouseObjectCategory.PERSON,
            confidence=0.90,
            current_bbox=(210, 200, 60, 165),
            first_seen=t_base,
            last_seen=t_base + 0.5,
            is_confirmed=True,
        )

        evs1 = self.engine.evaluate_frame([prod, person], current_time=t_base)
        self.assertEqual(len(evs1), 0, "Should not trigger on frame 1 before persistence window")

        evs2 = self.engine.evaluate_frame([prod, person], current_time=t_base + 0.40)
        self.assertEqual(len(evs2), 1, "Should trigger STEPPING_ON_PRODUCT after sustained contact")
        ev = evs2[0]
        self.assertEqual(ev.behaviour_type, WarehouseBehaviourType.STEPPING_ON_PRODUCT)
        self.assertEqual(ev.risk_level, WarehouseRiskTier.ORANGE.value)
        self.assertEqual(ev.product_track_id, 1)
        self.assertEqual(ev.person_track_id, 2)
        self.assertIsNotNone(ev.focus_bbox)

    def test_stepping_rejected_when_walking_alongside(self):
        """Person walking beside carton without foot-on-top overlap must NOT trigger STEPPING_ON_PRODUCT."""
        t_base = 100.0
        prod = TrackedEntity(
            track_id=1,
            class_id=1,
            label="carton",
            category=WarehouseObjectCategory.PRODUCT,
            confidence=0.85,
            current_bbox=(200, 360, 80, 60),
            first_seen=t_base,
            last_seen=t_base + 0.5,
            is_confirmed=True,
        )
        person = TrackedEntity(
            track_id=2,
            class_id=0,
            label="person",
            category=WarehouseObjectCategory.PERSON,
            confidence=0.90,
            current_bbox=(320, 200, 60, 165),
            first_seen=t_base,
            last_seen=t_base + 0.5,
            is_confirmed=True,
        )

        self.engine.evaluate_frame([prod, person], current_time=t_base)
        evs = self.engine.evaluate_frame([prod, person], current_time=t_base + 0.5)
        self.assertEqual(len(evs), 0, "Must not trigger stepping when walking alongside")

    # -------------------------------------------------------------------------
    # Priority 2: FALSE PRODUCT_DROPPED REJECTION & ACTION DISCRIMINATION
    # -------------------------------------------------------------------------

    def test_rolling_carton_rejected_for_product_dropped(self):
        """A carton rolling horizontally across the floor must NOT trigger PRODUCT_DROPPED."""
        prod = TrackedEntity(
            track_id=1,
            class_id=1,
            label="carton",
            category=WarehouseObjectCategory.PRODUCT,
            confidence=0.85,
            current_bbox=(200, 380, 60, 40),
            first_seen=100.0,
            last_seen=101.5,
            is_confirmed=True,
            interaction_state=ProductInteractionState.FREE,
        )
        for i in range(10):
            t = 100.0 + i * 0.15
            x = int(100 + i * 15)
            y = int(370 + (i % 3) * 5)
            prod.history.append(KinematicState(
                timestamp=t,
                bbox=(x, y, 60, 45),
                centroid=(x + 30.0, y + 22.5),
                velocity=(90.0, 15.0),
                speed=91.0,
                bottom_y=y + 45,
                is_grounded=True,
                elevation_ratio=0.04,
            ))
            prod.last_seen = t

        ev = self.engine._check_product_dropped(prod, now=101.5, video_source="test.mp4")
        self.assertIsNone(ev, "Rolling carton must NOT trigger PRODUCT_DROPPED")

    def test_controlled_lowering_rejected_for_product_dropped(self):
        """A carton held and lowered by a person must NOT trigger PRODUCT_DROPPED."""
        prod = TrackedEntity(
            track_id=1,
            class_id=1,
            label="carton",
            category=WarehouseObjectCategory.PRODUCT,
            confidence=0.85,
            current_bbox=(200, 340, 60, 60),
            first_seen=100.0,
            last_seen=101.2,
            is_confirmed=True,
            interaction_state=ProductInteractionState.HELD,
            associated_person_id=2,
            relative_motion=(5.0, 20.0, 21.0),
        )
        for i in range(6):
            t = 100.0 + i * 0.2
            y = int(250 + i * 15)
            prod.history.append(KinematicState(
                timestamp=t,
                bbox=(200, y, 60, 60),
                centroid=(230.0, y + 30.0),
                velocity=(0.0, 45.0),
                speed=45.0,
                bottom_y=y + 60,
                is_grounded=False,
                elevation_ratio=0.30 - i * 0.04,
            ))

        ev = self.engine._check_product_dropped(prod, now=101.2, video_source="test.mp4")
        self.assertIsNone(ev, "Controlled lowering while held must NOT trigger PRODUCT_DROPPED")

    def test_genuine_drop_accepted(self):
        """A free-fall drop with prior elevation, separation, high downward velocity and floor impact triggers PRODUCT_DROPPED."""
        prod = TrackedEntity(
            track_id=1,
            class_id=1,
            label="carton",
            category=WarehouseObjectCategory.PRODUCT,
            confidence=0.88,
            current_bbox=(200, 360, 60, 50),
            first_seen=100.0,
            last_seen=100.8,
            is_confirmed=True,
            interaction_state=ProductInteractionState.GROUND_CONTACT,
            associated_person_id=None,
        )
        prod.interaction_history = [
            ProductInteractionState.AIRBORNE,
            ProductInteractionState.AIRBORNE,
            ProductInteractionState.GROUND_CONTACT,
        ]
        prod.history.append(KinematicState(
            timestamp=100.0,
            bbox=(200, 230, 60, 50),
            centroid=(230.0, 255.0),
            velocity=(5.0, 40.0),
            speed=40.0,
            bottom_y=280,
            is_grounded=False,
            elevation_ratio=0.35,
        ))
        prod.history.append(KinematicState(
            timestamp=100.4,
            bbox=(202, 300, 60, 50),
            centroid=(232.0, 325.0),
            velocity=(5.0, 180.0),
            speed=180.0,
            bottom_y=350,
            is_grounded=False,
            elevation_ratio=0.18,
        ))
        prod.history.append(KinematicState(
            timestamp=100.8,
            bbox=(203, 360, 60, 50),
            centroid=(233.0, 385.0),
            velocity=(2.0, 25.0),
            speed=25.0,
            bottom_y=410,
            is_grounded=True,
            elevation_ratio=0.05,
        ))

        ev = self.engine._check_product_dropped(prod, now=100.8, video_source="test.mp4")
        self.assertIsNotNone(ev, "Genuine free-fall drop must be detected")
        self.assertEqual(ev.behaviour_type, WarehouseBehaviourType.PRODUCT_DROPPED)
        self.assertIn("Inspect the product for possible damage", ev.recommended_action)
        self.assertIn("separated from carry/elevation", ev.observed_behaviour)

    def test_drop_after_carry_sequence(self):
        """Handler carries carton, releases it, and it drops to floor -> triggers PRODUCT_DROPPED."""
        person = TrackedEntity(
            track_id=36,
            class_id=0,
            label="person",
            category=WarehouseObjectCategory.PERSON,
            confidence=0.92,
            current_bbox=(180, 150, 70, 220),
            first_seen=10.0,
            last_seen=11.2,
            is_confirmed=True,
        )
        person.history.append(KinematicState(
            timestamp=11.2,
            bbox=(180, 150, 70, 220),
            centroid=(215.0, 260.0),
            velocity=(10.0, 0.0),
            speed=10.0,
            bottom_y=370,
            is_grounded=True,
            elevation_ratio=0.10,
        ))

        prod = TrackedEntity(
            track_id=37,
            class_id=1,
            label="carton",
            category=WarehouseObjectCategory.PRODUCT,
            confidence=0.88,
            current_bbox=(200, 340, 65, 55),
            first_seen=10.0,
            last_seen=11.2,
            is_confirmed=True,
            associated_person_id=36,
            carrying_state="NONE",
            interaction_state=ProductInteractionState.GROUND_CONTACT,
            relative_motion=(0.0, 60.0, 60.0),
        )
        prod.interaction_history = [
            ProductInteractionState.HELD,
            ProductInteractionState.HELD,
            ProductInteractionState.AIRBORNE,
            ProductInteractionState.GROUND_CONTACT,
        ]
        # Frame 1: Elevated in carry
        prod.history.append(KinematicState(
            timestamp=10.0,
            bbox=(200, 210, 65, 55),
            centroid=(232.5, 237.5),
            velocity=(15.0, 5.0),
            speed=15.8,
            bottom_y=265,
            is_grounded=False,
            elevation_ratio=0.45,
        ))
        # Frame 2: Released and in free-fall descent
        prod.history.append(KinematicState(
            timestamp=10.6,
            bbox=(205, 275, 65, 55),
            centroid=(237.5, 302.5),
            velocity=(10.0, 175.0),
            speed=175.3,
            bottom_y=330,
            is_grounded=False,
            elevation_ratio=0.31,
        ))
        # Frame 3: Floor contact and stopped
        prod.history.append(KinematicState(
            timestamp=11.2,
            bbox=(208, 340, 65, 55),
            centroid=(240.5, 367.5),
            velocity=(2.0, 20.0),
            speed=20.1,
            bottom_y=395,
            is_grounded=True,
            elevation_ratio=0.08,
        ))

        evs = self.engine.evaluate_frame([person, prod], current_time=11.2, video_source="test.mp4")
        drop_events = [e for e in evs if e.behaviour_type == WarehouseBehaviourType.PRODUCT_DROPPED]
        self.assertEqual(len(drop_events), 1, "Drop after carry sequence must trigger PRODUCT_DROPPED")
        self.assertEqual(drop_events[0].product_track_id, 37)
        self.assertEqual(drop_events[0].person_track_id, 36)

    def test_walking_carry_does_not_trigger_drop(self):
        """Handler walking steadily while carrying a carton must NOT trigger PRODUCT_DROPPED."""
        person = TrackedEntity(
            track_id=10,
            class_id=0,
            label="person",
            category=WarehouseObjectCategory.PERSON,
            confidence=0.90,
            current_bbox=(200, 100, 80, 250),
            first_seen=20.0,
            last_seen=21.5,
            is_confirmed=True,
        )
        prod = TrackedEntity(
            track_id=11,
            class_id=1,
            label="carton",
            category=WarehouseObjectCategory.PRODUCT,
            confidence=0.85,
            current_bbox=(220, 180, 50, 50),
            first_seen=20.0,
            last_seen=21.5,
            is_confirmed=True,
            associated_person_id=10,
            carrying_state="HOLDING",
            interaction_state=ProductInteractionState.HELD,
            relative_motion=(2.0, 5.0, 5.4),
        )
        prod.interaction_history = [ProductInteractionState.HELD] * 6
        for i in range(5):
            t = 20.0 + i * 0.3
            x = 220 + i * 15
            y = 180 + (i % 2) * 3
            prod.history.append(KinematicState(
                timestamp=t,
                bbox=(x, y, 50, 50),
                centroid=(x + 25.0, y + 25.0),
                velocity=(50.0, 10.0),
                speed=51.0,
                bottom_y=y + 50,
                is_grounded=False,
                elevation_ratio=0.50,
            ))
        ev = self.engine._check_product_dropped(prod, now=21.5, video_source="test.mp4")
        self.assertIsNone(ev, "Steady walking carry must NOT trigger PRODUCT_DROPPED")

    # -------------------------------------------------------------------------
    # Priority 3: MULTI-PRODUCT TRACKING (Stacked & Touching Cartons)
    # -------------------------------------------------------------------------

    def test_multi_product_adjacent_cartons_tracked_simultaneously(self):
        """Two cartons placed adjacent/touching must both be tracked as distinct entities."""
        det1 = DetectedObject(class_id=1, label="carton", confidence=0.40, bbox=(100, 250, 80, 70))
        det2 = DetectedObject(class_id=1, label="carton", confidence=0.22, bbox=(115, 310, 80, 70))

        self.tracker.update([det1, det2], current_time=10.0)
        confirmed = self.tracker.update([det1, det2], current_time=10.1)

        product_tracks = [t for t in confirmed if t.category == WarehouseObjectCategory.PRODUCT]
        self.assertEqual(len(product_tracks), 2, "Both touching/stacked cartons must be tracked simultaneously")
        track_ids = {t.track_id for t in product_tracks}
        self.assertEqual(len(track_ids), 2, "Cartons must have distinct track IDs")

    # -------------------------------------------------------------------------
    # Priority 4: EVENT PARTICIPANT FOCUS BOUNDING BOX
    # -------------------------------------------------------------------------

    def test_event_focus_bbox_is_focused_union(self):
        """Focus bbox must be tightly bounded around handler and product plus 15% margin, NOT whole frame."""
        p_bbox = (200, 300, 60, 50)
        h_bbox = (180, 150, 80, 170)

        crop = compute_interaction_crop_box(
            frame_shape=(480, 640),
            product_bbox=p_bbox,
            person_bbox=h_bbox,
            padding_ratio=0.15,
        )
        x1, y1, x2, y2 = crop
        crop_w = x2 - x1
        crop_h = y2 - y1

        self.assertLessEqual(x1, 180)
        self.assertGreaterEqual(x2, 260)
        self.assertLessEqual(y1, 150)
        self.assertGreaterEqual(y2, 350)
        self.assertLess(crop_w, 350, f"Crop width {crop_w} should be focused, not entire frame")
        self.assertLess(crop_h, 350, f"Crop height {crop_h} should be focused, not entire frame")

    # -------------------------------------------------------------------------
    # Priority 1: MULTI-UPLOAD STABILITY (5 Sequential Uploads)
    # -------------------------------------------------------------------------

    def test_five_sequential_uploads_without_hang(self):
        """Simulate 5 sequential video upload calls through API route to verify zero socket or file lock deadlocks."""
        client = TestClient(app)
        test_video_path = Path("data/videos/Rolling and dropping carton.mp4")
        if not test_video_path.exists():
            self.skipTest("Test video not found")

        with open(test_video_path, "rb") as f:
            video_bytes = f.read()

        for upload_idx in range(1, 6):
            t0 = time.time()
            res = client.post(
                "/api/video/upload",
                files={"file": (f"test_seq_upload_{upload_idx}.mp4", video_bytes, "video/mp4")},
            )
            elapsed = time.time() - t0
            self.assertEqual(res.status_code, 200, f"Upload #{upload_idx} failed: {res.text}")
            self.assertLess(elapsed, 5.0, f"Upload #{upload_idx} took too long ({elapsed:.2f}s)")

    # -------------------------------------------------------------------------
    # Priority 6: UNSAFE_LOADING_SEQUENCE Hardening & Walking Carry Discrimination
    # -------------------------------------------------------------------------

    def test_walking_past_background_object_does_not_trigger_unsafe_loading_sequence(self):
        """Handler walking with carried carton past a background stationary carton must NOT trigger UNSAFE_LOADING_SEQUENCE."""
        # Static background product (Track 8) on a shelf/floor above the walking path
        bg_prod = TrackedEntity(
            track_id=8,
            class_id=1,
            label="carton",
            category=WarehouseObjectCategory.PRODUCT,
            confidence=0.88,
            current_bbox=(220, 140, 60, 50),
            first_seen=10.0,
            last_seen=10.5,
            is_confirmed=True,
            interaction_state=ProductInteractionState.FREE,
        )
        bg_prod.history.append(KinematicState(
            timestamp=10.5,
            bbox=(220, 140, 60, 50),
            centroid=(250.0, 165.0),
            velocity=(0.0, 0.0),
            speed=0.0,
            bottom_y=190,
            is_grounded=False,
            elevation_ratio=0.60,
        ))

        # Walking handler (Track 9) carrying carton (Track 10) passing under Track 8 for one frame
        person = TrackedEntity(
            track_id=9,
            class_id=0,
            label="person",
            category=WarehouseObjectCategory.PERSON,
            confidence=0.92,
            current_bbox=(200, 120, 80, 220),
            first_seen=10.0,
            last_seen=10.5,
            is_confirmed=True,
        )
        carried_prod = TrackedEntity(
            track_id=10,
            class_id=1,
            label="carton",
            category=WarehouseObjectCategory.PRODUCT,
            confidence=0.89,
            current_bbox=(220, 195, 60, 50),
            first_seen=10.0,
            last_seen=10.5,
            is_confirmed=True,
            associated_person_id=9,
            carrying_state="HOLDING",
            interaction_state=ProductInteractionState.HELD,
        )
        carried_prod.history.append(KinematicState(
            timestamp=10.5,
            bbox=(220, 195, 60, 50),
            centroid=(250.0, 220.0),
            velocity=(45.0, 0.0),
            speed=45.0,
            bottom_y=245,
            is_grounded=False,
            elevation_ratio=0.48,
        ))

        # Evaluate single passing frame (gap_y = |190 - 195| = 5px <= 35px)
        events = self.engine.evaluate_frame([person, carried_prod, bg_prod], current_time=10.5, video_source="test.mp4")
        loading_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.UNSAFE_LOADING_SEQUENCE]
        self.assertEqual(len(loading_events), 0, "Walking past a background object must NOT trigger UNSAFE_LOADING_SEQUENCE")

    def test_genuine_unsafe_loading_sequence_requires_prior_stable_stack(self):
        """Extracting a lower carton after verified resting stack history triggers UNSAFE_LOADING_SEQUENCE."""
        engine = TemporalWarehouseBehaviourEngine(floor_y_threshold_ratio=0.80, frame_width=640, frame_height=480)
        events = []

        # Frames 0-3: Resting stacked boxes (bottom at 320, top at 260) with handler nearby
        for i in range(4):
            t = 20.0 + i * 0.1
            top = TrackedEntity(
                track_id=1, class_id=1, label="carton", category=WarehouseObjectCategory.PRODUCT,
                confidence=0.90, current_bbox=(180, 260, 80, 60), first_seen=20.0, last_seen=t, is_confirmed=True,
            )
            top.history.append(KinematicState(timestamp=t, bbox=(180, 260, 80, 60), centroid=(220.0, 290.0), velocity=(0.0, 0.0), speed=0.0, bottom_y=320, is_grounded=False, elevation_ratio=0.33))
            bot = TrackedEntity(
                track_id=2, class_id=1, label="carton", category=WarehouseObjectCategory.PRODUCT,
                confidence=0.90, current_bbox=(180, 320, 80, 60), first_seen=20.0, last_seen=t, is_confirmed=True,
                associated_person_id=3, carrying_state="HOLDING",
            )
            bot.history.append(KinematicState(timestamp=t, bbox=(180, 320, 80, 60), centroid=(220.0, 350.0), velocity=(0.0, 0.0), speed=0.0, bottom_y=380, is_grounded=True, elevation_ratio=0.20))
            person = TrackedEntity(
                track_id=3, class_id=0, label="person", category=WarehouseObjectCategory.PERSON,
                confidence=0.92, current_bbox=(100, 250, 60, 150), first_seen=20.0, last_seen=t, is_confirmed=True,
            )
            evs = engine.evaluate_frame([person, top, bot], current_time=t)
            events.extend(evs)

        # Frame 4: Bottom box extracted horizontally at 60 px/s while top remains stationary
        t = 20.4
        top = TrackedEntity(
            track_id=1, class_id=1, label="carton", category=WarehouseObjectCategory.PRODUCT,
            confidence=0.90, current_bbox=(180, 260, 80, 60), first_seen=20.0, last_seen=t, is_confirmed=True,
        )
        top.history.append(KinematicState(timestamp=t, bbox=(180, 260, 80, 60), centroid=(220.0, 290.0), velocity=(0.0, 0.0), speed=0.0, bottom_y=320, is_grounded=False, elevation_ratio=0.33))
        bot = TrackedEntity(
            track_id=2, class_id=1, label="carton", category=WarehouseObjectCategory.PRODUCT,
            confidence=0.90, current_bbox=(130, 320, 80, 60), first_seen=20.0, last_seen=t, is_confirmed=True,
            associated_person_id=3, carrying_state="HOLDING",
        )
        bot.history.append(KinematicState(timestamp=t, bbox=(130, 320, 80, 60), centroid=(170.0, 350.0), velocity=(-60.0, 0.0), speed=60.0, bottom_y=380, is_grounded=True, elevation_ratio=0.20))
        person = TrackedEntity(
            track_id=3, class_id=0, label="person", category=WarehouseObjectCategory.PERSON,
            confidence=0.92, current_bbox=(80, 250, 60, 150), first_seen=20.0, last_seen=t, is_confirmed=True,
        )
        evs = engine.evaluate_frame([person, top, bot], current_time=t)
        events.extend(evs)

        seq_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.UNSAFE_LOADING_SEQUENCE]
        self.assertGreaterEqual(len(seq_events), 1, "Genuine bottom extraction after resting stack MUST trigger UNSAFE_LOADING_SEQUENCE")
        self.assertEqual(seq_events[0].risk_level, "RED")

    def test_dynamic_handling_quality_score_scenarios(self):
        """Validates controlled Handling Quality scenarios A-F: No collapse to 0 and logical recovery."""
        from src.database.db_manager import DatabaseManager
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db_path = f.name

        try:
            db = DatabaseManager(db_path=temp_db_path)
            
            # Scenario A: No events -> 100
            stats_a = db.get_warehouse_stats_summary()
            self.assertEqual(stats_a["handling_quality_score"], 100)

            # Scenario B: 1 YELLOW warning event in 10 events -> 98
            for i in range(9):
                db.log_warehouse_event(
                    event_id=f"EVT-G-{i}", behaviour_type="SAFE_HANDLING",
                    risk_level="GREEN", confidence=0.95, start_timestamp="2026-09-21 10:00:00",
                    end_timestamp="2026-09-21 10:00:01", duration_seconds=1.0, observed_behaviour="Safe",
                    potential_risk="None", recommended_action="None",
                )
            db.log_warehouse_event(
                event_id="EVT-Y-1", behaviour_type="UNSTABLE_STACKING",
                risk_level="YELLOW", confidence=0.85, start_timestamp="2026-09-21 10:00:02",
                end_timestamp="2026-09-21 10:00:03", duration_seconds=1.0, observed_behaviour="Tilt",
                potential_risk="Risk", recommended_action="Fix",
            )
            stats_b = db.get_warehouse_stats_summary()
            self.assertGreaterEqual(stats_b["handling_quality_score"], 95)
            self.assertLessEqual(stats_b["handling_quality_score"], 99)

            # Scenario D: 1 RED critical event in 10 events -> ~91
            db.log_warehouse_event(
                event_id="EVT-R-1", behaviour_type="PRODUCT_DROPPED",
                risk_level="RED", confidence=0.95, start_timestamp="2026-09-21 10:00:04",
                end_timestamp="2026-09-21 10:00:05", duration_seconds=1.0, observed_behaviour="Dropped",
                potential_risk="Damage", recommended_action="Inspect",
            )
            stats_d = db.get_warehouse_stats_summary()
            self.assertGreaterEqual(stats_d["handling_quality_score"], 85)
            self.assertLessEqual(stats_d["handling_quality_score"], 95)

            # Scenario F: Subsequent safe events enter window -> score recovers
            for i in range(15):
                db.log_warehouse_event(
                    event_id=f"EVT-RECOVER-{i}", behaviour_type="SAFE_HANDLING",
                    risk_level="GREEN", confidence=0.95, start_timestamp=f"2026-09-21 10:01:{i:02d}",
                    end_timestamp=f"2026-09-21 10:01:{i:02d}", duration_seconds=1.0, observed_behaviour="Safe",
                    potential_risk="None", recommended_action="None",
                )
            stats_f = db.get_warehouse_stats_summary()
            self.assertGreaterEqual(stats_f["handling_quality_score"], 95, "Score must recover to >= 95 after safe handling operations")
        finally:
            if os.path.exists(temp_db_path):
                try:
                    os.remove(temp_db_path)
                except Exception:
                    pass


if __name__ == "__main__":
    unittest.main()

