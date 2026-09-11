"""
tests/test_warehouse_classification_regression.py
--------------------------------------------------
Regression test suite for warehouse object classification, confidence thresholds,
stale track expiration, and simulator isolation.
"""

import unittest
import time
from src.core.warehouse_models import WarehouseObjectCategory, TrackedEntity
from src.core.warehouse_class_mapper import WarehouseClassMapper, EXCLUDED_NON_WAREHOUSE_LABELS
from src.core.warehouse_tracker import WarehouseObjectTracker
from src.core.interfaces.detector_interface import DetectedObject
from src.api.state import CareGuardBackendState


class TestWarehouseClassificationRegression(unittest.TestCase):

    def setUp(self):
        self.class_mapper = WarehouseClassMapper(
            person_conf_threshold=0.35,
            product_conf_threshold=0.40,
            pallet_conf_threshold=0.35,
            mhe_conf_threshold=0.35,
            other_conf_threshold=0.45,
        )
        self.tracker = WarehouseObjectTracker(
            frame_width=640,
            frame_height=480,
            confirmation_frames=1,
            max_missed_frames=3,
            max_track_age_seconds=0.5,
            class_mapper=self.class_mapper,
        )

    def test_1_unrelated_coco_objects_not_mapped_to_package(self):
        """Regression Test 1: Raw unrelated COCO objects must NOT be mapped to PRODUCT / PACKAGE."""
        unrelated_labels = [
            "cell phone",
            "cell_phone",
            "handbag",
            "backpack",
            "suitcase",
            "bottle",
            "book",
            "laptop",
            "mouse",
            "chair",
            "potted plant",
            "dining table",
            "tv",
            "remote",
            "cup",
        ]
        for lbl in unrelated_labels:
            cat = self.class_mapper.map_category(lbl)
            self.assertNotEqual(
                cat,
                WarehouseObjectCategory.PRODUCT,
                f"Label '{lbl}' was incorrectly mapped to PRODUCT/PACKAGE!"
            )
            self.assertEqual(
                cat,
                WarehouseObjectCategory.OTHER,
                f"Label '{lbl}' should be mapped to OTHER, got {cat}"
            )

            # Check display label
            display_text, color = self.class_mapper.get_display_label(cat, raw_label=lbl, track_id=8)
            self.assertNotIn("PACKAGE", display_text, f"Display text for '{lbl}' contains 'PACKAGE'!")

    def test_2_low_confidence_object_rejected(self):
        """Regression Test 2: Objects below category confidence threshold are rejected."""
        # Product threshold is 0.40; confidence 0.25 should be rejected
        low_conf_det = DetectedObject(class_id=1, label="carton", confidence=0.25, bbox=(100, 100, 50, 50))
        self.assertFalse(self.class_mapper.is_valid_confidence(low_conf_det.label, low_conf_det.confidence))

        tracks = self.tracker.update([low_conf_det], current_time=1.0)
        self.assertEqual(len(tracks), 0, "Low-confidence detection was erroneously tracked!")

        # High-confidence product (0.65) should be accepted
        high_conf_det = DetectedObject(class_id=1, label="carton", confidence=0.65, bbox=(100, 100, 50, 50))
        self.assertTrue(self.class_mapper.is_valid_confidence(high_conf_det.label, high_conf_det.confidence))

        tracks_high = self.tracker.update([high_conf_det], current_time=1.05)
        self.assertEqual(len(tracks_high), 1, "Valid high-confidence product was not tracked!")
        self.assertEqual(tracks_high[0].category, WarehouseObjectCategory.PRODUCT)

    def test_3_stale_package_track_expires(self):
        """Regression Test 3: Propagated tracks must expire when detections disappear."""
        # Initial detection
        det = DetectedObject(class_id=1, label="box", confidence=0.85, bbox=(120, 120, 60, 60))
        tracks = self.tracker.update([det], current_time=1.0)
        self.assertEqual(len(tracks), 1)
        track_id = tracks[0].track_id

        # Missing detection for 1 frame
        self.tracker.update([], current_time=1.05)
        # Missing detection for 2 frames
        self.tracker.update([], current_time=1.10)
        # Missing detection for 3 frames
        self.tracker.update([], current_time=1.15)
        # Missing detection for 4 frames (> max_missed_frames = 3)
        tracks_after = self.tracker.update([], current_time=1.20)

        self.assertEqual(len(tracks_after), 0, "Stale track failed to expire after missed frames!")
        self.assertNotIn(track_id, self.tracker._tracks, "Expired track was not pruned from memory!")

    def test_3b_propagate_tracks_expires_on_timeout(self):
        """Regression Test 3B: propagate_tracks prunes stale tracks when time elapsed exceeds max_age."""
        det = DetectedObject(class_id=1, label="box", confidence=0.85, bbox=(120, 120, 60, 60))
        self.tracker.update([det], current_time=1.0)

        # Propagate within valid window
        tracks_prop = self.tracker.propagate_tracks(current_time=1.2)
        self.assertEqual(len(tracks_prop), 1)

        # Propagate after max_track_age_seconds (0.5s timeout: 1.0 + 0.6s = 1.6s)
        tracks_expired = self.tracker.propagate_tracks(current_time=1.65)
        self.assertEqual(len(tracks_expired), 0, "propagate_tracks kept a stale track alive past max age!")

    def test_4_real_package_carton_supported(self):
        """Regression Test 4: Real cartons, boxes, packages, crates are correctly mapped to PRODUCT / PACKAGE."""
        valid_product_labels = ["carton", "box", "package", "parcel", "product", "cargo", "crate", "cardboard_box"]
        for lbl in valid_product_labels:
            cat = self.class_mapper.map_category(lbl)
            self.assertEqual(cat, WarehouseObjectCategory.PRODUCT, f"Valid product '{lbl}' not mapped to PRODUCT!")
            label_text, color = self.class_mapper.get_display_label(cat, raw_label=lbl, track_id=1)
            self.assertEqual(label_text, "PRODUCT #1")
            self.assertEqual(color, (70, 200, 100))

    def test_5_person_remains_handler_and_suppresses_duplicates(self):
        """Regression Test 5: Person remains HANDLER and duplicate boxes are suppressed without becoming PACKAGE."""
        person1 = DetectedObject(class_id=0, label="person", confidence=0.92, bbox=(200, 100, 100, 250))
        person1_dup = DetectedObject(class_id=0, label="person", confidence=0.70, bbox=(205, 102, 95, 248))

        tracks = self.tracker.update([person1, person1_dup], current_time=1.0)
        self.assertEqual(len(tracks), 1, "Duplicate person detection was not suppressed!")
        self.assertEqual(tracks[0].category, WarehouseObjectCategory.PERSON)

        label_text, color = self.class_mapper.get_display_label(tracks[0].category, raw_label=tracks[0].label, track_id=tracks[0].track_id)
        self.assertEqual(label_text, f"HANDLER #{tracks[0].track_id}")
        self.assertEqual(color, (255, 140, 30))

    def test_6_simulator_isolation(self):
        """Regression Test 6: Simulator events/tracks do not contaminate real physical tracker tracks."""
        # Ensure fresh tracker
        self.tracker.reset()
        self.assertEqual(len(self.tracker.all_tracks), 0)

        # A real detection arrives
        real_det = DetectedObject(class_id=0, label="person", confidence=0.90, bbox=(150, 100, 80, 200))
        self.tracker.update([real_det], current_time=1.0)

        # Tracker only contains real physical track
        all_trks = self.tracker.all_tracks
        self.assertEqual(len(all_trks), 1)
        self.assertEqual(all_trks[0].track_id, 1)
        self.assertEqual(all_trks[0].category, WarehouseObjectCategory.PERSON)


if __name__ == "__main__":
    unittest.main()
