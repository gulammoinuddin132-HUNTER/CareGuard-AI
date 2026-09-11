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

        res_cam = client.post("/api/video/source", data={"source_type": "camera", "camera_index": "0"})
        self.assertEqual(res_cam.status_code, 200)


if __name__ == "__main__":
    unittest.main()
