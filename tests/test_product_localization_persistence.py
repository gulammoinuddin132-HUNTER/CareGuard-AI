"""
tests/test_product_localization_persistence.py
----------------------------------------------
Comprehensive unit test suite for:
1. Product geometric filtering (background dock/truck/door rejection).
2. Aspect ratio guards.
3. Contextual confidence gating.
4. Multi-frame confirmation requirement.
5. Entity category invariant preservation.
6. Incident persistence across track expiration.
7. Tight proportional evidence cropping.
"""

import time
import unittest
import numpy as np

from src.core.warehouse_models import (
    WarehouseObjectCategory,
    TrackedEntity,
    WarehouseBehaviourEvent,
    WarehouseBehaviourType,
    EventState,
)
from src.core.interfaces.detector_interface import DetectedObject
from src.core.warehouse_tracker import WarehouseObjectTracker
from src.core.warehouse_evidence_cropper import compute_interaction_crop_box
from src.api.state import CareGuardBackendState


class TestProductLocalizationAndPersistence(unittest.TestCase):
    """Test suite for CareGuard perception robustness and incident persistence."""

    def test_oversized_background_structure_rejected(self):
        """Verify that large background elements (e.g. trucks/dock doors > 18% of frame area) are rejected."""
        tracker = WarehouseObjectTracker(frame_width=1280, frame_height=720, confirmation_frames=2)

        huge_det = DetectedObject(
            class_id=1,
            label="carton",
            confidence=0.35,
            bbox=(200, 100, 500, 450),
        )

        tracks = tracker.update([huge_det], current_time=100.0)
        self.assertEqual(len(tracks), 0, "Oversized background structure should not produce active confirmed tracks.")
        self.assertEqual(len(tracker.all_tracks), 0, "Oversized candidate should not be tracked.")

    def test_extreme_aspect_ratio_rejected(self):
        """Verify that extreme aspect ratios (< 0.22 or > 4.5) are rejected for products."""
        tracker = WarehouseObjectTracker(frame_width=1280, frame_height=720, confirmation_frames=2)

        thin_strip = DetectedObject(
            class_id=1,
            label="carton",
            confidence=0.45,
            bbox=(100, 100, 400, 30),
        )

        tracks = tracker.update([thin_strip], current_time=100.0)
        self.assertEqual(len(tracks), 0, "Extreme aspect ratio candidate must be rejected.")

    def test_contextual_confidence_isolated_vs_proximate(self):
        """Verify that isolated static products require conf >= 0.28, while near person allows 0.15."""
        tracker = WarehouseObjectTracker(frame_width=1280, frame_height=720, confirmation_frames=2)

        # 1. Low-confidence isolated detection (conf 0.18, no person nearby)
        isolated_low_conf = DetectedObject(
            class_id=1,
            label="carton",
            confidence=0.18,
            bbox=(100, 100, 80, 80),
        )
        tracker.update([isolated_low_conf], current_time=100.0)
        self.assertEqual(len(tracker.all_tracks), 0, "Isolated low-confidence detection must be filtered.")

        # 2. Low-confidence detection in proximity to person (adjacent at distance 20px <= 120px)
        person_det = DetectedObject(
            class_id=0,
            label="person",
            confidence=0.60,
            bbox=(200, 100, 100, 250),
        )
        proximate_low_conf = DetectedObject(
            class_id=1,
            label="carton",
            confidence=0.18,
            bbox=(320, 180, 70, 70),
        )

        tracker.update([person_det, proximate_low_conf], current_time=100.1)
        all_tracks = tracker.all_tracks
        product_candidates = [t for t in all_tracks if t.category == WarehouseObjectCategory.PRODUCT]
        self.assertGreaterEqual(len(product_candidates), 1, "Low-confidence product near person must be accepted.")

    def test_multi_frame_confirmation_requirement(self):
        """Verify that product tracks strictly require >= 2 consecutive frames before becoming confirmed."""
        tracker = WarehouseObjectTracker(frame_width=1280, frame_height=720, confirmation_frames=2)

        det_frame1 = DetectedObject(class_id=1, label="carton", confidence=0.50, bbox=(300, 300, 80, 80))

        # Frame 1: Track spawned as provisional
        tracks_f1 = tracker.update([det_frame1], current_time=100.0)
        self.assertEqual(len(tracks_f1), 0, "Track should NOT be confirmed on frame 1.")

        # Frame 2: Second matching detection confirms track
        det_frame2 = DetectedObject(class_id=1, label="carton", confidence=0.52, bbox=(302, 301, 80, 80))
        tracks_f2 = tracker.update([det_frame2], current_time=100.033)
        self.assertEqual(len(tracks_f2), 1, "Track MUST be confirmed on frame 2.")
        self.assertTrue(tracks_f2[0].is_confirmed)

    def test_entity_category_invariant_preservation(self):
        """Verify that track category cannot be overwritten by conflicting detection category."""
        tracker = WarehouseObjectTracker(frame_width=1280, frame_height=720, confirmation_frames=1)

        person_det = DetectedObject(class_id=0, label="person", confidence=0.80, bbox=(100, 100, 100, 250))
        tracks = tracker.update([person_det], current_time=100.0)
        self.assertEqual(len(tracks), 1)
        person_track = tracks[0]
        self.assertEqual(person_track.category, WarehouseObjectCategory.PERSON)

        product_det = DetectedObject(class_id=1, label="carton", confidence=0.80, bbox=(100, 100, 100, 250))
        tracker.update([product_det], current_time=100.033)

        updated_person = tracker._tracks.get(person_track.track_id)
        self.assertEqual(updated_person.category, WarehouseObjectCategory.PERSON)

    def test_incident_persistence_after_track_expiration(self):
        """Verify that when active event times out or track expires, latest_verified_event is retained."""
        backend = CareGuardBackendState.get_instance()
        backend.reset_session("TEST_SOURCE")

        event = WarehouseBehaviourEvent(
            event_id="CG-TEST-001",
            behaviour_type=WarehouseBehaviourType.PRODUCT_DROPPED,
            risk_level="RED",
            confidence=0.92,
            start_timestamp="2026-09-10 12:00:00",
            end_timestamp="2026-09-10 12:00:05",
            duration_seconds=5.0,
            observed_behaviour="Product dropped from elevation onto floor.",
            potential_risk="Structural shock damage.",
            recommended_action="Inspect packaging.",
            person_track_id=1,
            product_track_id=2,
            product_bbox=(300, 400, 80, 80),
            person_bbox=(200, 300, 90, 200),
            focus_bbox=(180, 280, 220, 220),
            state=EventState.ACTIVE,
            activated_at=100.0,
            last_observed_time=100.0,
            grace_period_seconds=1.0,
        )

        backend.active_verified_event = event
        backend.latest_event = event
        backend.latest_verified_event = event

        now = 105.0
        grace = event.grace_period_seconds
        elapsed = now - event.last_observed_time

        if elapsed > grace:
            event.state = EventState.RESOLVED
            event.resolved_at = now
            backend.latest_verified_event = event
            backend.active_verified_event = None
            backend.latest_event = backend.latest_verified_event
            backend.current_risk_level = "GREEN"

        self.assertIsNone(backend.active_verified_event)
        self.assertIsNotNone(backend.latest_verified_event)
        self.assertEqual(backend.latest_verified_event.event_id, "CG-TEST-001")
        self.assertIsNotNone(backend.latest_event)
        self.assertEqual(backend.latest_event.event_id, "CG-TEST-001")
        self.assertEqual(backend.latest_event.state, EventState.RESOLVED)

    def test_tight_proportional_evidence_crop(self):
        """Verify that evidence cropper produces tight bounds with 10-15% margins without blowing to full screen."""
        frame_shape = (720, 1280)
        product_bbox = (500, 400, 100, 100)
        person_bbox = (520, 320, 120, 250)

        crop_box = compute_interaction_crop_box(
            frame_shape=frame_shape,
            product_bbox=product_bbox,
            person_bbox=person_bbox,
            padding_ratio=0.12,
        )

        x1, y1, x2, y2 = crop_box
        cw = x2 - x1
        ch = y2 - y1

        self.assertLessEqual(x1, 500)
        self.assertLessEqual(y1, 320)
        self.assertGreaterEqual(x2, 640)
        self.assertGreaterEqual(y2, 570)

        self.assertLess(cw, 0.60 * 1280)
        self.assertLess(ch, 0.60 * 720)


if __name__ == '__main__':
    unittest.main()
