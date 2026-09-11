"""
Unit Tests for Warehouse Multi-Object Tracker (Phase 1)
-------------------------------------------------------
Verifies persistent track IDs, kinematic calculations, category mapping,
and person-to-product spatial associations.
"""

import unittest
from src.core.warehouse_models import WarehouseObjectCategory
from src.core.warehouse_tracker import WarehouseObjectTracker
from src.core.interfaces.detector_interface import DetectedObject


class TestWarehouseTracker(unittest.TestCase):

    def setUp(self):
        self.tracker = WarehouseObjectTracker(
            frame_width=640,
            frame_height=480,
            confirmation_frames=2,
            max_missed_frames=5,
        )

    def test_category_mapping(self):
        """Verifies mapping COCO and custom labels to warehouse categories."""
        self.assertEqual(self.tracker.map_category("person"), WarehouseObjectCategory.PERSON)
        self.assertEqual(self.tracker.map_category("worker"), WarehouseObjectCategory.PERSON)
        self.assertEqual(self.tracker.map_category("carton"), WarehouseObjectCategory.PRODUCT)
        self.assertEqual(self.tracker.map_category("box"), WarehouseObjectCategory.PRODUCT)
        self.assertEqual(self.tracker.map_category("package"), WarehouseObjectCategory.PRODUCT)
        self.assertEqual(self.tracker.map_category("parcel"), WarehouseObjectCategory.PRODUCT)
        self.assertEqual(self.tracker.map_category("crate"), WarehouseObjectCategory.PRODUCT)
        self.assertEqual(self.tracker.map_category("suitcase"), WarehouseObjectCategory.OTHER)
        self.assertEqual(self.tracker.map_category("laptop"), WarehouseObjectCategory.OTHER)
        self.assertEqual(self.tracker.map_category("cell_phone"), WarehouseObjectCategory.OTHER)
        self.assertEqual(self.tracker.map_category("pallet"), WarehouseObjectCategory.PALLET)
        self.assertEqual(self.tracker.map_category("trolley"), WarehouseObjectCategory.MHE)
        self.assertEqual(self.tracker.map_category("forklift"), WarehouseObjectCategory.MHE)

    def test_stable_track_id_persistence(self):
        """Verifies that moving objects retain the same track_id across frames."""
        # Frame 1: Detection at (100, 100, 60, 60)
        det1 = DetectedObject(class_id=0, label="box", confidence=0.85, bbox=(100, 100, 60, 60))
        self.tracker.update([det1], current_time=1.0)

        # Frame 2: Object moves slightly to (105, 102, 60, 60)
        det2 = DetectedObject(class_id=0, label="box", confidence=0.88, bbox=(105, 102, 60, 60))
        tracks = self.tracker.update([det2], current_time=1.04)

        self.assertEqual(len(tracks), 1)
        track_id = tracks[0].track_id
        self.assertTrue(tracks[0].is_confirmed)

        # Frame 3: Object moves further to (110, 104, 60, 60)
        det3 = DetectedObject(class_id=0, label="box", confidence=0.90, bbox=(110, 104, 60, 60))
        tracks3 = self.tracker.update([det3], current_time=1.08)

        self.assertEqual(len(tracks3), 1)
        self.assertEqual(tracks3[0].track_id, track_id)
        self.assertEqual(tracks3[0].category, WarehouseObjectCategory.PRODUCT)

    def test_kinematics_calculation(self):
        """Verifies velocity, speed, and bottom_y calculation."""
        # Frame 1 at t=0.0: (100, 100, 50, 50) -> centroid (125, 125)
        d1 = DetectedObject(class_id=0, label="carton", confidence=0.9, bbox=(100, 100, 50, 50))
        self.tracker.update([d1], current_time=0.0)

        # Frame 2 at t=0.5: (200, 100, 50, 50) -> centroid (225, 125) -> dx = 100px over 0.5s = 200px/s vx
        d2 = DetectedObject(class_id=0, label="carton", confidence=0.9, bbox=(200, 100, 50, 50))
        tracks = self.tracker.update([d2], current_time=0.5)

        self.assertEqual(len(tracks), 1)
        cur_state = tracks[0].current_state
        self.assertIsNotNone(cur_state)
        self.assertAlmostEqual(cur_state.velocity[0], 200.0, delta=1.0)
        self.assertAlmostEqual(cur_state.velocity[1], 0.0, delta=1.0)
        self.assertAlmostEqual(cur_state.speed, 200.0, delta=1.0)
        self.assertEqual(cur_state.bottom_y, 150) # y + h = 100 + 50

    def test_person_product_carrying_association(self):
        """Verifies that a person holding a product above ground is marked as HOLDING."""
        # Person at (100, 150, 80, 200) bottom=350
        # Product at (110, 200, 40, 40) bottom=240 (inside person chest height)
        person_det = DetectedObject(class_id=0, label="person", confidence=0.95, bbox=(100, 150, 80, 200))
        prod_det = DetectedObject(class_id=1, label="carton", confidence=0.90, bbox=(110, 200, 40, 40))

        self.tracker.update([person_det, prod_det], current_time=1.0)
        tracks = self.tracker.update([person_det, prod_det], current_time=1.04)

        person_trk = next(t for t in tracks if t.category == WarehouseObjectCategory.PERSON)
        prod_trk = next(t for t in tracks if t.category == WarehouseObjectCategory.PRODUCT)

        self.assertEqual(prod_trk.associated_person_id, person_trk.track_id)
        self.assertIn(prod_trk.track_id, person_trk.associated_product_ids)
        self.assertEqual(prod_trk.carrying_state, "HOLDING")


if __name__ == "__main__":
    unittest.main()
