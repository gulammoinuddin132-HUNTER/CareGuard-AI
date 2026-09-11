"""
tests/test_yolo26_detector.py
-----------------------------
Unit and integration tests for YOLO26n Warehouse Perception detector in CareGuard AI.
Tests:
  1. YOLO26WarehouseDetector initialization and properties.
  2. 4-class warehouse taxonomy verification (person, carton, pallet, mhe).
  3. Frame detection output format (DetectedObject schema, bounding boxes, confidences).
  4. Integration with ObjectDetectionEngine facade.
  5. Integration with WarehouseClassMapper and WarehouseObjectTracker.
"""

import unittest
import numpy as np
import cv2
from pathlib import Path

from config import (
    YOLO26N_BASE_MODEL_PATH,
    YOLO26N_WAREHOUSE_MODEL_PATH,
    YOLO26N_WAREHOUSE_ONNX_PATH,
    WAREHOUSE_CLASSES,
)
from src.core.interfaces.detector_interface import DetectedObject
from src.core.object_detection import (
    YOLO26WarehouseDetector,
    ObjectDetectionEngine,
)
from src.core.warehouse_class_mapper import WarehouseClassMapper
from src.core.warehouse_models import WarehouseObjectCategory
from src.core.warehouse_tracker import WarehouseObjectTracker


class TestYOLO26WarehouseDetector(unittest.TestCase):
    """Test suite for YOLO26n Warehouse Perception Detector."""

    def setUp(self):
        self.detector = YOLO26WarehouseDetector()
        self.detector.initialize()

    def tearDown(self):
        if self.detector:
            self.detector.release()

    def test_detector_classes(self):
        """Verify the 4 core warehouse classes."""
        classes = self.detector.class_names
        self.assertEqual(classes, list(WAREHOUSE_CLASSES))
        self.assertIn("person", classes)
        self.assertIn("product", classes)
        self.assertIn("pallet", classes)
        self.assertIn("mhe", classes)

    def test_detector_mode_name(self):
        """Verify mode name reports YOLO26n."""
        self.assertIn("YOLO26", self.detector.mode_name)

    def test_detect_empty_or_invalid_frame(self):
        """Verify detector handles None or empty frames gracefully."""
        res_none = self.detector.detect(None)
        self.assertEqual(res_none, [])

        empty_img = np.zeros((0, 0, 3), dtype=np.uint8)
        res_empty = self.detector.detect(empty_img)
        self.assertEqual(res_empty, [])

    def test_detect_synthetic_frame(self):
        """Verify detection returns structured DetectedObject instances."""
        # Create synthetic test frame (640x480) with simulated warehouse scene
        frame = np.full((480, 640, 3), 120, dtype=np.uint8)
        # Add a mock brown carton box
        cv2.rectangle(frame, (200, 200), (350, 350), (42, 85, 140), -1)
        # Add a mock wooden pallet
        cv2.rectangle(frame, (180, 360), (380, 420), (30, 110, 160), -1)

        results = self.detector.detect(frame)
        self.assertIsInstance(results, list)
        for obj in results:
            self.assertIsInstance(obj, DetectedObject)
            self.assertIn(obj.label, WAREHOUSE_CLASSES)
            self.assertGreaterEqual(obj.confidence, 0.0)
            self.assertLessEqual(obj.confidence, 1.0)
            self.assertEqual(len(obj.bbox), 4)
            x, y, w, h = obj.bbox
            self.assertGreaterEqual(x, 0)
            self.assertGreaterEqual(y, 0)
            self.assertGreater(w, 0)
            self.assertGreater(h, 0)

    def test_engine_facade_integration(self):
        """Verify ObjectDetectionEngine integrates with YOLO26."""
        engine = ObjectDetectionEngine(detector_mode="yolo26_warehouse")
        self.assertTrue(engine.initialize())
        self.assertIn("YOLO26", engine.active_mode)

        frame = np.full((480, 640, 3), 100, dtype=np.uint8)
        out = engine.process_frame(frame)
        self.assertIn("detected", out)
        self.assertIn("count", out)
        self.assertIn("objects", out)
        self.assertIn("detector_mode", out)
        self.assertIn("YOLO26", out["detector_mode"])

    def test_class_mapper_compatibility(self):
        """Verify WarehouseClassMapper accurately maps YOLO26 labels."""
        mapper = WarehouseClassMapper()
        
        self.assertEqual(mapper.map_category("person"), WarehouseObjectCategory.PERSON)
        self.assertEqual(mapper.map_category("carton"), WarehouseObjectCategory.PRODUCT)
        self.assertEqual(mapper.map_category("pallet"), WarehouseObjectCategory.PALLET)
        self.assertEqual(mapper.map_category("mhe"), WarehouseObjectCategory.MHE)
        
        # Test exclusions
        self.assertEqual(mapper.map_category("cell_phone"), WarehouseObjectCategory.OTHER)
        self.assertEqual(mapper.map_category("chair"), WarehouseObjectCategory.OTHER)

    def test_tracker_integration_with_yolo26(self):
        """Verify WarehouseObjectTracker ingests YOLO26 detections properly."""
        tracker = WarehouseObjectTracker(frame_width=640, frame_height=480, confirmation_frames=1)
        
        raw_objs = [
            DetectedObject(class_id=0, label="person", confidence=0.88, bbox=(100, 100, 80, 200)),
            DetectedObject(class_id=1, label="carton", confidence=0.82, bbox=(220, 250, 60, 60)),
            DetectedObject(class_id=2, label="pallet", confidence=0.79, bbox=(200, 320, 100, 40)),
            DetectedObject(class_id=3, label="mhe", confidence=0.75, bbox=(400, 200, 120, 150)),
        ]
        
        tracks = tracker.update(raw_objs)
        self.assertEqual(len(tracks), 4)
        
        categories = {t.category for t in tracks}
        self.assertIn(WarehouseObjectCategory.PERSON, categories)
        self.assertIn(WarehouseObjectCategory.PRODUCT, categories)
        self.assertIn(WarehouseObjectCategory.PALLET, categories)
        self.assertIn(WarehouseObjectCategory.MHE, categories)


if __name__ == "__main__":
    unittest.main()
