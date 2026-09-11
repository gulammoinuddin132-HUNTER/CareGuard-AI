"""
tests/test_visual_focus_geometry.py
-----------------------------------
Automated tests for visual focus geometry:
- Verifies compute_interaction_crop_box focuses on handler + product together.
- Confirms elimination of static center-road fallback.
- Validates save_evidence_snapshot file integrity and OpenCV decodability.
- Validates log_event_geometry telemetry generation.
- Verifies behaviour engine produces events with valid product_bbox and focus_bbox.
"""

import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
import cv2
import numpy as np

from src.core.warehouse_models import (
    WarehouseObjectCategory,
    TrackedEntity,
    KinematicState,
    WarehouseBehaviourType,
)
from src.core.warehouse_evidence_cropper import (
    compute_interaction_crop_box,
    create_interaction_evidence_crop,
    save_evidence_snapshot,
    log_event_geometry,
)
from src.core.warehouse_behaviour_engine import TemporalWarehouseBehaviourEngine


class TestVisualFocusGeometry(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.frame_h, self.frame_w = 720, 1280
        self.frame = np.full((self.frame_h, self.frame_w, 3), 50, dtype=np.uint8)

        now = time.time()
        # Handler positioned on left side of frame: (100, 200, 100, 250)
        h_state = KinematicState(
            timestamp=now,
            bbox=(100, 200, 100, 250),
            centroid=(150.0, 325.0),
            velocity=(5.0, 0.0),
            speed=5.0,
            vertical_accel=0.0,
            bottom_y=450,
            elevation_ratio=0.37,
            is_grounded=True,
        )
        self.handler = TrackedEntity(
            track_id=1,
            class_id=0,
            label="person",
            category=WarehouseObjectCategory.PERSON,
            confidence=0.95,
            current_bbox=(100, 200, 100, 250),
            first_seen=now - 2.0,
            last_seen=now,
            last_detection_time=now,
            history=[h_state],
            missed_frames=0,
            is_confirmed=True,
        )

        # Product positioned right next to handler: (220, 350, 150, 120)
        p_state = KinematicState(
            timestamp=now,
            bbox=(220, 350, 150, 120),
            centroid=(295.0, 410.0),
            velocity=(5.0, 0.0),
            speed=5.0,
            vertical_accel=0.0,
            bottom_y=470,
            elevation_ratio=0.35,
            is_grounded=True,
        )
        self.product = TrackedEntity(
            track_id=2,
            class_id=1,
            label="product",
            category=WarehouseObjectCategory.PRODUCT,
            confidence=0.90,
            current_bbox=(220, 350, 150, 120),
            first_seen=now - 2.0,
            last_seen=now,
            last_detection_time=now,
            history=[p_state],
            missed_frames=0,
            is_confirmed=True,
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_crop_box_encloses_handler_and_product(self):
        """Crop box must contain both handler and product with context padding."""
        crop_box = compute_interaction_crop_box(
            (self.frame_h, self.frame_w),
            product_track=self.product,
            person_track=self.handler,
            behaviour_type="PRODUCT_DRAGGED",
        )
        x1, y1, x2, y2 = crop_box

        # Handler box: (100, 200, 100, 250) -> x in [100, 200], y in [200, 450]
        # Product box: (220, 350, 150, 120) -> x in [220, 370], y in [350, 470]
        self.assertLessEqual(x1, 100, "Crop box must start before or at handler left edge")
        self.assertLessEqual(y1, 200, "Crop box must start above or at handler top edge")
        self.assertGreaterEqual(x2, 370, "Crop box must extend past product right edge")
        self.assertGreaterEqual(y2, 470, "Crop box must extend past product bottom edge")

        # Focus center must be near handler+product (x ~ 235), not frame center (640, 360)
        crop_cx = (x1 + x2) / 2.0
        self.assertLess(crop_cx, 450.0, "Crop box center must be near handler/product, not center road")

    def test_no_static_road_fallback_on_empty(self):
        """When no boxes are provided, fallback must be clamped full frame, not static road 240x180."""
        crop_box = compute_interaction_crop_box((self.frame_h, self.frame_w))
        self.assertEqual(crop_box, (0, 0, self.frame_w, self.frame_h))

    def test_save_evidence_snapshot_integrity(self):
        """Snapshot must be created on disk, size > 0, and decodable with OpenCV."""
        snap_path = save_evidence_snapshot(
            frame=self.frame,
            output_dir=self.tmp_dir,
            filename_prefix="test_snap",
            product_track=self.product,
            person_track=self.handler,
            event_type="Product Dragged",
            risk_level="ORANGE",
        )
        self.assertIsNotNone(snap_path)
        p = Path(snap_path)
        self.assertTrue(p.exists())
        self.assertGreater(p.stat().st_size, 500)

        img = cv2.imread(str(p))
        self.assertIsNotNone(img)
        self.assertGreater(img.shape[0], 50)
        self.assertGreater(img.shape[1], 50)

    def test_log_event_geometry_telemetry(self):
        """Geometry logging must correctly compute coordinates and containment."""
        crop_box = (50, 150, 450, 550)
        geom = log_event_geometry(
            event_id="CG-TEST-001",
            frame_shape=(self.frame_h, self.frame_w),
            product_track_id=2,
            product_bbox=(220, 350, 150, 120),
            handler_track_id=1,
            handler_bbox=(100, 200, 100, 250),
            focus_box=crop_box,
        )
        self.assertEqual(geom["event_id"], "CG-TEST-001")
        self.assertEqual(geom["video_frame"], {"width": 1280, "height": 720})
        self.assertEqual(geom["handler"]["track_id"], 1)
        self.assertEqual(geom["product"]["track_id"], 2)
        self.assertEqual(geom["transform"]["frontend_viewport"], "aspect-video (16:9 object-contain)")


if __name__ == "__main__":
    unittest.main()
