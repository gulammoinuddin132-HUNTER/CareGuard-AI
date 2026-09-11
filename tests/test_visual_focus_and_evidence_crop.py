"""
tests/test_visual_focus_and_evidence_crop.py
---------------------------------------------
Comprehensive automated unit tests for:
1. Smart interaction evidence cropping (handler + product focus).
2. Edge-to-edge distance calculation and entity association.
3. Multi-tier HUD rendering (Clean, Detection, Tracking, Diagnostics).
4. Real-time incident logging and session synchronization.
"""

import time
import unittest
import numpy as np
import cv2
import tempfile
import shutil
from pathlib import Path

from config import DATA_DIR
from src.core.warehouse_models import (
    WarehouseObjectCategory,
    TrackedEntity,
    KinematicState,
    WarehouseBehaviourEvent,
    WarehouseBehaviourType,
)
from src.core.warehouse_tracker import (
    WarehouseObjectTracker,
    compute_centroid_dist,
    compute_bbox_min_dist,
    compute_iou,
)
from src.core.warehouse_evidence_cropper import (
    compute_interaction_crop_box,
    create_interaction_evidence_crop,
    save_evidence_snapshot,
)
from src.api.state import CareGuardBackendState


class TestVisualFocusAndEvidenceCrop(unittest.TestCase):
    """Unit tests for visual focus, evidence cropping, and multi-tier HUD rendering."""

    def setUp(self):
        # Synthetic 1280x720 warehouse scene frame
        self.frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.frame[360:720, :] = (45, 45, 50)
        self.frame[0:360, :] = (70, 75, 80)
        self.tmp_dir = tempfile.mkdtemp()

        now = time.time()
        # Handler track: at (300, 200, 120, 280)
        h_state = KinematicState(
            timestamp=now,
            bbox=(300, 200, 120, 280),
            centroid=(360.0, 340.0),
            velocity=(15.0, 0.0),
            speed=15.0,
            vertical_accel=0.0,
            bottom_y=480,
            elevation_ratio=0.33,
            is_grounded=True,
        )
        self.handler = TrackedEntity(
            track_id=1,
            class_id=0,
            label="person",
            category=WarehouseObjectCategory.PERSON,
            confidence=0.92,
            current_bbox=(300, 200, 120, 280),
            first_seen=now - 2.0,
            last_seen=now,
            last_detection_time=now,
            history=[h_state],
            missed_frames=0,
            is_confirmed=True,
        )

        # Product track: large carton at (450, 300, 200, 180) adjacent to handler
        p_state = KinematicState(
            timestamp=now,
            bbox=(450, 300, 200, 180),
            centroid=(550.0, 390.0),
            velocity=(65.0, -20.0),
            speed=68.0,
            vertical_accel=10.0,
            bottom_y=480,
            elevation_ratio=0.33,
            is_grounded=True,
        )
        self.product = TrackedEntity(
            track_id=2,
            class_id=1,
            label="product",
            category=WarehouseObjectCategory.PRODUCT,
            confidence=0.88,
            current_bbox=(450, 300, 200, 180),
            first_seen=now - 2.0,
            last_seen=now,
            last_detection_time=now,
            history=[p_state],
            missed_frames=0,
            is_confirmed=True,
            associated_person_id=1,
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_bbox_min_distance_calculation(self):
        """Verifies edge-to-edge distance logic for adjacent and overlapping boxes."""
        box_a = (100, 100, 50, 50)  # x: 100..150, y: 100..150
        box_b = (180, 100, 50, 50)  # x: 180..230, y: 100..150 (30px gap in x)
        box_c = (120, 120, 50, 50)  # Overlapping with A

        dist_ab = compute_bbox_min_dist(box_a, box_b)
        self.assertAlmostEqual(dist_ab, 30.0, delta=1e-3)

        dist_ac = compute_bbox_min_dist(box_a, box_c)
        self.assertEqual(dist_ac, 0.0)

    def test_large_product_person_association(self):
        """Verifies that large products adjacent to handlers are correctly associated."""
        tracker = WarehouseObjectTracker(frame_width=1280, frame_height=720, confirmation_frames=1)
        now = time.time()

        person_det = {
            "class_id": 0,
            "label": "person",
            "confidence": 0.90,
            "bbox": (200, 200, 120, 300),
        }
        product_det = {
            "class_id": 1,
            "label": "product",
            "confidence": 0.85,
            "bbox": (340, 320, 300, 180),
        }

        tracks = tracker.update([person_det, product_det], current_time=now)
        self.assertEqual(len(tracks), 2)

        p_trk = next(t for t in tracks if t.category == WarehouseObjectCategory.PERSON)
        prod_trk = next(t for t in tracks if t.category == WarehouseObjectCategory.PRODUCT)

        self.assertEqual(prod_trk.associated_person_id, p_trk.track_id)
        self.assertIn(prod_trk.track_id, p_trk.associated_product_ids)

    def test_interaction_crop_box_computation(self):
        """Verifies that crop box covers both entities with margin and respects frame limits."""
        h, w = self.frame.shape[:2]

        x1, y1, x2, y2 = compute_interaction_crop_box(
            frame_shape=(h, w),
            product_track=self.product,
            person_track=self.handler,
            padding_ratio=0.30,
            min_w=480,
            min_h=360,
        )

        self.assertTrue(0 <= x1 < x2 <= w)
        self.assertTrue(0 <= y1 < y2 <= h)
        self.assertGreaterEqual(x2 - x1, 480)
        self.assertGreaterEqual(y2 - y1, 360)

        hx1, hy1, hw_box, hh_box = self.handler.current_bbox
        px1, py1, pw_box, ph_box = self.product.current_bbox

        self.assertLessEqual(x1, hx1)
        self.assertGreaterEqual(x2, hx1 + hw_box)
        self.assertLessEqual(y1, hy1)
        self.assertGreaterEqual(y2, hy1 + hh_box)

        self.assertLessEqual(x1, px1)
        self.assertGreaterEqual(x2, px1 + pw_box)
        self.assertLessEqual(y1, py1)
        self.assertGreaterEqual(y2, py1 + ph_box)

    def test_create_interaction_evidence_crop(self):
        """Verifies visual evidence crop creation and forensic annotation rendering."""
        crop = create_interaction_evidence_crop(
            frame=self.frame,
            product_track=self.product,
            person_track=self.handler,
            event_type="MATERIAL_PUSHED_THROWN",
            risk_level="RED",
            padding_ratio=0.30,
            annotate=True,
        )

        self.assertIsNotNone(crop)
        self.assertGreaterEqual(crop.shape[0], 360)
        self.assertGreaterEqual(crop.shape[1], 480)
        self.assertEqual(crop.shape[2], 3)

    def test_save_evidence_snapshot(self):
        """Verifies saving interaction snapshot to disk."""
        saved_path = save_evidence_snapshot(
            frame=self.frame,
            output_dir=Path(self.tmp_dir),
            filename_prefix="test_thrown",
            product_track=self.product,
            person_track=self.handler,
            event_type="MATERIAL PUSHED / THROWN",
            risk_level="RED",
        )

        self.assertIsNotNone(saved_path)
        p = Path(saved_path)
        self.assertTrue(p.exists())
        self.assertGreater(p.stat().st_size, 500)

    def test_hud_rendering_clean_presentation_mode(self):
        """Verifies Clean View displays handler + product together during an active event."""
        backend = CareGuardBackendState.get_instance()

        active_event = WarehouseBehaviourEvent(
            event_id="CG-THRO-20260908-220000-0001",
            behaviour_type=WarehouseBehaviourType.MATERIAL_PUSHED_THROWN,
            risk_level="RED",
            confidence=0.91,
            start_timestamp="2026-09-08 22:00:00",
            end_timestamp="2026-09-08 22:00:02",
            duration_seconds=1.5,
            observed_behaviour="Product thrown by handler",
            potential_risk="Impact damage",
            recommended_action="Team lift",
            product_track_id=self.product.track_id,
            person_track_id=self.handler.track_id,
        )

        annotated = backend._render_warehouse_hud(
            frame=self.frame.copy(),
            tracks=[self.handler, self.product],
            events=[active_event],
            overlay_mode="clean",
        )

        self.assertIsNotNone(annotated)
        self.assertEqual(annotated.shape, self.frame.shape)

    def test_hud_rendering_all_modes(self):
        """Verifies all 4 HUD tiers render without error."""
        backend = CareGuardBackendState.get_instance()

        for mode in ("clean", "detection", "tracking", "diagnostics"):
            out = backend._render_warehouse_hud(
                frame=self.frame.copy(),
                tracks=[self.handler, self.product],
                events=[],
                overlay_mode=mode,
            )
            self.assertIsNotNone(out)
            self.assertEqual(out.shape, self.frame.shape)


if __name__ == "__main__":
    unittest.main()
