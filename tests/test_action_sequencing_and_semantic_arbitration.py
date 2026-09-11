"""
Unit tests for CareGuard AI Action Sequencing, Semantic Arbitration (Kick vs Throw vs Drop vs Drag),
and Precise Participant Focus Geometry (20 Test Criteria).
"""

import unittest
import time
from typing import Tuple, List

from src.core.warehouse_models import (
    WarehouseObjectCategory,
    ProductInteractionState,
    WarehouseBehaviourType,
    KinematicState,
    TrackedEntity,
    WarehouseBehaviourEvent,
    EventState,
)
from src.core.warehouse_tracker import WarehouseObjectTracker
from src.core.warehouse_behaviour_engine import TemporalWarehouseBehaviourEngine
from src.core.warehouse_evidence_cropper import compute_interaction_crop_box
from src.core.interfaces.detector_interface import DetectedObject


class TestActionSequencingAndSemanticArbitration(unittest.TestCase):

    def setUp(self):
        self.tracker = WarehouseObjectTracker(frame_width=640, frame_height=480)
        self.engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)

    def _create_product_track(
        self,
        track_id: int,
        bbox: Tuple[int, int, int, int],
        confidence: float = 0.85,
        interaction_state: ProductInteractionState = ProductInteractionState.FREE,
        history_states: List[KinematicState] = None,
        now_t: float = 100.0,
    ) -> TrackedEntity:
        if history_states:
            first_t = history_states[0].timestamp
            last_t = history_states[-1].timestamp
        else:
            first_t = now_t - 1.0
            last_t = now_t
            cx = bbox[0] + bbox[2] / 2.0
            cy = bbox[1] + bbox[3] / 2.0
            history_states = [
                KinematicState(
                    timestamp=now_t,
                    bbox=bbox,
                    centroid=(cx, cy),
                    velocity=(0.0, 0.0),
                    speed=0.0,
                    bottom_y=bbox[1] + bbox[3],
                    is_grounded=True,
                )
            ]

        t = TrackedEntity(
            track_id=track_id,
            class_id=1,
            label="carton",
            category=WarehouseObjectCategory.PRODUCT,
            confidence=confidence,
            current_bbox=bbox,
            first_seen=first_t,
            last_seen=last_t,
            last_detection_time=last_t,
            is_confirmed=True,
            interaction_state=interaction_state,
            raw_bbox=bbox,
            validated_bbox=bbox,
            tracked_bbox=bbox,
            smoothed_bbox=bbox,
            history=history_states,
        )
        return t

    def _create_person_track(
        self,
        track_id: int,
        bbox: Tuple[int, int, int, int],
        confidence: float = 0.90,
        now_t: float = 100.0,
    ) -> TrackedEntity:
        return TrackedEntity(
            track_id=track_id,
            class_id=0,
            label="person",
            category=WarehouseObjectCategory.PERSON,
            confidence=confidence,
            current_bbox=bbox,
            first_seen=now_t - 2.0,
            last_seen=now_t,
            last_detection_time=now_t,
            is_confirmed=True,
            raw_bbox=bbox,
            validated_bbox=bbox,
            tracked_bbox=bbox,
            smoothed_bbox=bbox,
        )

    # 1. DROP -> KICK -> DRAG creates three distinct event instances
    def test_01_drop_kick_drag_three_distinct_events(self):
        engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)
        t0 = 100.0
        h1 = [
            KinematicState(t0, (300, 200, 60, 50), (330.0, 225.0), (0.0, 0.0), 0.0, bottom_y=250, elevation_ratio=0.5, is_grounded=False),
            KinematicState(t0 + 0.1, (300, 260, 60, 50), (330.0, 285.0), (0.0, 250.0), 250.0, bottom_y=310, elevation_ratio=0.35, is_grounded=False),
            KinematicState(t0 + 0.2, (300, 360, 60, 50), (330.0, 385.0), (0.0, 290.0), 290.0, bottom_y=410, elevation_ratio=0.15, is_grounded=True),
        ]
        prod = self._create_product_track(7, (300, 360, 60, 50), history_states=h1, now_t=t0 + 0.2)
        person = self._create_person_track(1, (240, 180, 80, 240), now_t=t0 + 0.2)
        prod.interaction_history = [ProductInteractionState.HELD, ProductInteractionState.AIRBORNE, ProductInteractionState.GROUND_CONTACT]
        prod.interaction_state = ProductInteractionState.GROUND_CONTACT

        ev1 = engine.evaluate_frame([prod, person], current_time=t0 + 0.2)
        self.assertEqual(len(ev1), 1)
        self.assertEqual(ev1[0].behaviour_type, WarehouseBehaviourType.PRODUCT_DROPPED)

        # 2. Product settles, then Handler kicks carton
        t1 = 103.0
        h2 = [
            KinematicState(t1 - 0.2, (300, 360, 60, 50), (330.0, 385.0), (0.0, 0.0), 0.0, bottom_y=410, is_grounded=True),
            KinematicState(t1, (380, 360, 60, 50), (410.0, 385.0), (120.0, 0.0), 120.0, bottom_y=410, is_grounded=True),
        ]
        prod.history = h2
        prod.first_seen = h2[0].timestamp
        prod.last_seen = h2[-1].timestamp
        prod.current_bbox = (380, 360, 60, 50)
        prod.interaction_state = ProductInteractionState.FREE
        person.current_bbox = (280, 200, 80, 240)
        person.last_seen = t1

        ev2 = engine.evaluate_frame([prod, person], current_time=t1)
        self.assertEqual(len(ev2), 1)
        self.assertEqual(ev2[0].behaviour_type, WarehouseBehaviourType.PRODUCT_KICKED)

        # 3. Product settles into sustained floor drag
        t2 = 106.0
        h3 = [
            KinematicState(t2 - 1.2, (380, 360, 60, 50), (410.0, 385.0), (40.0, 0.0), 40.0, bottom_y=410, is_grounded=True),
            KinematicState(t2 - 0.9, (410, 360, 60, 50), (440.0, 385.0), (40.0, 0.0), 40.0, bottom_y=410, is_grounded=True),
            KinematicState(t2 - 0.6, (440, 360, 60, 50), (470.0, 385.0), (40.0, 0.0), 40.0, bottom_y=410, is_grounded=True),
            KinematicState(t2 - 0.3, (470, 360, 60, 50), (500.0, 385.0), (40.0, 0.0), 40.0, bottom_y=410, is_grounded=True),
            KinematicState(t2, (500, 360, 60, 50), (530.0, 385.0), (40.0, 0.0), 40.0, bottom_y=410, is_grounded=True),
        ]
        prod.history = h3
        prod.first_seen = h3[0].timestamp
        prod.last_seen = h3[-1].timestamp
        prod.current_bbox = (500, 360, 60, 50)
        person.last_seen = t2

        ev3 = engine.evaluate_frame([prod, person], current_time=t2)
        self.assertEqual(len(ev3), 1)
        self.assertEqual(ev3[0].behaviour_type, WarehouseBehaviourType.PRODUCT_DRAGGED)

        # Verify distinct IDs
        self.assertNotEqual(ev1[0].event_id, ev2[0].event_id)
        self.assertNotEqual(ev2[0].event_id, ev3[0].event_id)

    # 2. Same DROP repeated on adjacent frames remains 1 event
    def test_02_same_drop_adjacent_frames_deduplicated(self):
        engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)
        t0 = 100.0
        h1 = [
            KinematicState(t0, (300, 200, 60, 50), (330.0, 225.0), (0.0, 0.0), 0.0, bottom_y=250, elevation_ratio=0.5, is_grounded=False),
            KinematicState(t0 + 0.1, (300, 260, 60, 50), (330.0, 285.0), (0.0, 250.0), 250.0, bottom_y=310, elevation_ratio=0.35, is_grounded=False),
            KinematicState(t0 + 0.2, (300, 360, 60, 50), (330.0, 385.0), (0.0, 290.0), 290.0, bottom_y=410, elevation_ratio=0.15, is_grounded=True),
        ]
        prod = self._create_product_track(7, (300, 360, 60, 50), history_states=h1, now_t=t0 + 0.2)
        person = self._create_person_track(1, (240, 180, 80, 240), now_t=t0 + 0.2)
        prod.interaction_history = [ProductInteractionState.HELD, ProductInteractionState.AIRBORNE, ProductInteractionState.GROUND_CONTACT]

        ev_first = engine.evaluate_frame([prod, person], current_time=t0 + 0.2)
        self.assertEqual(len(ev_first), 1)

        # Adjacent frame at +0.033s (same continuous impact)
        ev_next = engine.evaluate_frame([prod, person], current_time=t0 + 0.233)
        self.assertEqual(len(ev_next), 0)

    # 3. DROP does not suppress later KICK
    def test_03_drop_does_not_suppress_later_kick(self):
        engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)
        t0 = 100.0
        h1 = [
            KinematicState(t0, (300, 200, 60, 50), (330.0, 225.0), (0.0, 0.0), 0.0, bottom_y=250, elevation_ratio=0.5, is_grounded=False),
            KinematicState(t0 + 0.1, (300, 260, 60, 50), (330.0, 285.0), (0.0, 250.0), 250.0, bottom_y=310, elevation_ratio=0.35, is_grounded=False),
            KinematicState(t0 + 0.2, (300, 360, 60, 50), (330.0, 385.0), (0.0, 290.0), 290.0, bottom_y=410, elevation_ratio=0.15, is_grounded=True),
        ]
        prod = self._create_product_track(7, (300, 360, 60, 50), history_states=h1, now_t=t0 + 0.2)
        person = self._create_person_track(1, (240, 180, 80, 240), now_t=t0 + 0.2)
        prod.interaction_history = [ProductInteractionState.HELD, ProductInteractionState.AIRBORNE, ProductInteractionState.GROUND_CONTACT]
        ev1 = engine.evaluate_frame([prod, person], current_time=t0 + 0.2)
        self.assertEqual(len(ev1), 1)

        t1 = 102.5
        h2 = [
            KinematicState(t1 - 0.2, (300, 360, 60, 50), (330.0, 385.0), (0.0, 0.0), 0.0, bottom_y=410, is_grounded=True),
            KinematicState(t1, (380, 360, 60, 50), (410.0, 385.0), (120.0, 0.0), 120.0, bottom_y=410, is_grounded=True),
        ]
        prod.history = h2
        prod.first_seen = h2[0].timestamp
        prod.last_seen = h2[-1].timestamp
        prod.current_bbox = (380, 360, 60, 50)
        person.current_bbox = (280, 200, 80, 240)
        person.last_seen = t1
        ev2 = engine.evaluate_frame([prod, person], current_time=t1)
        self.assertEqual(len(ev2), 1)
        self.assertEqual(ev2[0].behaviour_type, WarehouseBehaviourType.PRODUCT_KICKED)

    # 4. KICK does not suppress later DRAG
    def test_04_kick_does_not_suppress_later_drag(self):
        engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)
        t1 = 100.0
        h2 = [
            KinematicState(t1 - 0.2, (300, 360, 60, 50), (330.0, 385.0), (0.0, 0.0), 0.0, bottom_y=410, is_grounded=True),
            KinematicState(t1, (380, 360, 60, 50), (410.0, 385.0), (120.0, 0.0), 120.0, bottom_y=410, is_grounded=True),
        ]
        prod = self._create_product_track(7, (380, 360, 60, 50), history_states=h2, now_t=t1)
        person = self._create_person_track(1, (280, 200, 80, 240), now_t=t1)
        ev1 = engine.evaluate_frame([prod, person], current_time=t1)
        self.assertEqual(len(ev1), 1)

        t2 = 103.0
        h3 = [
            KinematicState(t2 - 1.2, (380, 360, 60, 50), (410.0, 385.0), (40.0, 0.0), 40.0, bottom_y=410, is_grounded=True),
            KinematicState(t2 - 0.9, (410, 360, 60, 50), (440.0, 385.0), (40.0, 0.0), 40.0, bottom_y=410, is_grounded=True),
            KinematicState(t2 - 0.6, (440, 360, 60, 50), (470.0, 385.0), (40.0, 0.0), 40.0, bottom_y=410, is_grounded=True),
            KinematicState(t2 - 0.3, (470, 360, 60, 50), (500.0, 385.0), (40.0, 0.0), 40.0, bottom_y=410, is_grounded=True),
            KinematicState(t2, (500, 360, 60, 50), (530.0, 385.0), (40.0, 0.0), 40.0, bottom_y=410, is_grounded=True),
        ]
        prod.history = h3
        prod.first_seen = h3[0].timestamp
        prod.last_seen = h3[-1].timestamp
        prod.current_bbox = (500, 360, 60, 50)
        person.last_seen = t2
        ev2 = engine.evaluate_frame([prod, person], current_time=t2)
        self.assertEqual(len(ev2), 1)
        self.assertEqual(ev2[0].behaviour_type, WarehouseBehaviourType.PRODUCT_DRAGGED)

    # 5. KICK requires foot contact
    def test_05_kick_requires_foot_contact(self):
        engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)
        t1 = 100.0
        h = [
            KinematicState(t1 - 0.2, (300, 360, 60, 50), (330.0, 385.0), (0.0, 0.0), 0.0, bottom_y=410, is_grounded=True),
            KinematicState(t1, (380, 360, 60, 50), (410.0, 385.0), (120.0, 0.0), 120.0, bottom_y=410, is_grounded=True),
        ]
        prod = self._create_product_track(7, (380, 360, 60, 50), history_states=h, now_t=t1)
        person = self._create_person_track(1, (100, 100, 80, 240), now_t=t1)
        ev = engine.evaluate_frame([prod, person], current_time=t1)
        self.assertEqual(len(ev), 0)

    # 6. Product moving quickly while carried is NOT a kick
    def test_06_carried_product_not_kicked(self):
        engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)
        t1 = 100.0
        h = [
            KinematicState(t1 - 0.2, (250, 250, 60, 50), (280.0, 275.0), (95.0, 0.0), 95.0, bottom_y=300, is_grounded=False),
            KinematicState(t1, (300, 250, 60, 50), (330.0, 275.0), (95.0, 0.0), 95.0, bottom_y=300, is_grounded=False),
        ]
        prod = self._create_product_track(7, (300, 250, 60, 50), interaction_state=ProductInteractionState.HELD, history_states=h, now_t=t1)
        prod.carrying_state = "HOLDING"
        person = self._create_person_track(1, (290, 200, 80, 240), now_t=t1)
        ev = engine.evaluate_frame([prod, person], current_time=t1)
        self.assertEqual(len(ev), 0)

    # 7. Airborne product with release evidence becomes THROW, not KICK
    def test_07_airborne_product_becomes_throw(self):
        engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)
        t1 = 100.0
        h = [
            KinematicState(t1 - 0.2, (200, 200, 60, 50), (230.0, 225.0), (160.0, 0.0), 160.0, bottom_y=250, elevation_ratio=0.48, is_grounded=False),
            KinematicState(t1 - 0.1, (275, 200, 60, 50), (305.0, 225.0), (160.0, 0.0), 160.0, bottom_y=250, elevation_ratio=0.48, is_grounded=False),
            KinematicState(t1, (350, 200, 60, 50), (380.0, 225.0), (160.0, 0.0), 160.0, bottom_y=250, elevation_ratio=0.48, is_grounded=False),
        ]
        prod = self._create_product_track(7, (350, 200, 60, 50), confidence=0.88, history_states=h, now_t=t1)
        person = self._create_person_track(1, (180, 180, 80, 240), now_t=t1)
        ev = engine.evaluate_frame([prod, person], current_time=t1)
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0].behaviour_type, WarehouseBehaviourType.MATERIAL_PUSHED_THROWN)

    # 8. Grounded product with foot impact becomes KICK, not THROW
    def test_08_grounded_foot_impact_becomes_kick_not_throw(self):
        engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)
        t1 = 100.0
        h = [
            KinematicState(t1 - 0.2, (300, 360, 60, 50), (330.0, 385.0), (0.0, 0.0), 0.0, bottom_y=410, is_grounded=True),
            KinematicState(t1, (380, 360, 60, 50), (410.0, 385.0), (180.0, 0.0), 180.0, bottom_y=410, is_grounded=True),
        ]
        prod = self._create_product_track(7, (380, 360, 60, 50), confidence=0.88, history_states=h, now_t=t1)
        person = self._create_person_track(1, (280, 200, 80, 240), now_t=t1)
        ev = engine.evaluate_frame([prod, person], current_time=t1)
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0].behaviour_type, WarehouseBehaviourType.PRODUCT_KICKED)

    # 9. Pure horizontal floor motion becomes DRAG
    def test_09_pure_horizontal_floor_motion_becomes_drag(self):
        engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)
        t = 100.0
        h = [
            KinematicState(t - 1.2, (200, 380, 60, 50), (230.0, 405.0), (45.0, 0.0), 45.0, bottom_y=430, is_grounded=True),
            KinematicState(t - 0.9, (230, 380, 60, 50), (260.0, 405.0), (45.0, 0.0), 45.0, bottom_y=430, is_grounded=True),
            KinematicState(t - 0.6, (260, 380, 60, 50), (290.0, 405.0), (45.0, 0.0), 45.0, bottom_y=430, is_grounded=True),
            KinematicState(t - 0.3, (290, 380, 60, 50), (320.0, 405.0), (45.0, 0.0), 45.0, bottom_y=430, is_grounded=True),
            KinematicState(t, (320, 380, 60, 50), (350.0, 405.0), (45.0, 0.0), 45.0, bottom_y=430, is_grounded=True),
        ]
        prod = self._create_product_track(7, (320, 380, 60, 50), history_states=h, now_t=t)
        person = self._create_person_track(1, (280, 240, 80, 200), now_t=t)
        ev = engine.evaluate_frame([prod, person], current_time=t)
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0].behaviour_type, WarehouseBehaviourType.PRODUCT_DRAGGED)

    # 10. Low-confidence false product cannot create critical event
    def test_10_low_confidence_cannot_create_critical_event(self):
        engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)
        t1 = 100.0
        h = [
            KinematicState(t1 - 0.2, (200, 100, 60, 50), (230.0, 125.0), (200.0, 0.0), 200.0, bottom_y=150, elevation_ratio=0.7, is_grounded=False),
            KinematicState(t1, (350, 100, 60, 50), (380.0, 125.0), (200.0, 0.0), 200.0, bottom_y=150, elevation_ratio=0.7, is_grounded=False),
        ]
        prod = self._create_product_track(8, (350, 100, 60, 50), confidence=0.18, history_states=h, now_t=t1)
        person = self._create_person_track(1, (180, 180, 80, 240), now_t=t1)
        ev = engine.evaluate_frame([prod, person], current_time=t1)
        self.assertEqual(len(ev), 0)

    # 11. Product bbox cannot teleport from carton to ceiling
    def test_11_product_bbox_cannot_teleport_to_ceiling(self):
        tracker = WarehouseObjectTracker(frame_width=640, frame_height=480)
        tracker.update([DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(300, 360, 60, 50))], current_time=1.0)
        tracker.update([DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(300, 360, 60, 50))], current_time=1.05)
        self.assertEqual(len(tracker.active_tracks), 1)
        orig_tid = tracker.active_tracks[0].track_id

        # Jump to ceiling (y=30)
        tracker.update([DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(300, 30, 60, 50))], current_time=1.1)
        # Bbox should not teleport to ceiling
        t = tracker._tracks[orig_tid]
        self.assertGreater(t.current_bbox[1], 200)

    # 12. Product bbox cannot teleport from carton to truck
    def test_12_product_bbox_cannot_teleport_to_truck(self):
        tracker = WarehouseObjectTracker(frame_width=640, frame_height=480)
        tracker.update([DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(300, 360, 60, 50))], current_time=1.0)
        tracker.update([DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(300, 360, 60, 50))], current_time=1.05)
        t = tracker.active_tracks[0]

        # Sudden oversized candidate (truck/trailer at 400x300)
        tracker.update([DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(100, 100, 400, 300))], current_time=1.1)
        self.assertNotEqual(t.current_bbox, (100, 100, 400, 300))

    # 13. Product bbox cannot become handler bbox
    def test_13_product_bbox_cannot_become_handler_bbox(self):
        tracker = WarehouseObjectTracker(frame_width=640, frame_height=480)
        tracker.update([DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(300, 360, 60, 50))], current_time=1.0)
        tracker.update([DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(300, 360, 60, 50))], current_time=1.05)
        p_track = tracker.active_tracks[0]

        # Handler appears at (260, 200, 90, 240)
        tracker.update([
            DetectedObject(class_id=0, label="person", confidence=0.90, bbox=(260, 200, 90, 240)),
            DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(300, 360, 60, 50)),
        ], current_time=1.1)
        self.assertEqual(p_track.category, WarehouseObjectCategory.PRODUCT)
        self.assertNotEqual(p_track.current_bbox, (260, 200, 90, 240))

    # 14. Handler bbox and product bbox refer to separate tracks
    def test_14_handler_and_product_are_separate_tracks(self):
        prod = self._create_product_track(7, (300, 360, 60, 50))
        person = self._create_person_track(1, (260, 200, 90, 240))
        self.assertNotEqual(prod.track_id, person.track_id)
        self.assertEqual(prod.category, WarehouseObjectCategory.PRODUCT)
        self.assertEqual(person.category, WarehouseObjectCategory.PERSON)

    # 15. Focus crop is centered around actual handler + product
    def test_15_focus_crop_centered_around_handler_and_product(self):
        prod = self._create_product_track(7, (300, 380, 50, 40))
        person = self._create_person_track(1, (240, 180, 80, 240))
        crop_box = compute_interaction_crop_box(
            (480, 640),
            product_track=prod,
            person_track=person,
            product_bbox=prod.current_bbox,
            person_bbox=person.current_bbox,
            behaviour_type="PRODUCT_DROPPED",
        )
        x1, y1, x2, y2 = crop_box
        self.assertLessEqual(x1, 240)
        self.assertGreaterEqual(x2, 350)
        self.assertGreaterEqual(y2, 420)

    # 16. Focus crop does not include unnecessary truck/background
    def test_16_focus_crop_excludes_distant_background(self):
        prod = self._create_product_track(7, (300, 380, 40, 30))
        person = self._create_person_track(1, (280, 340, 40, 70))
        crop_box = compute_interaction_crop_box(
            (480, 640),
            product_track=prod,
            person_track=person,
            product_bbox=prod.current_bbox,
            person_bbox=person.current_bbox,
            behaviour_type="PRODUCT_DRAGGED",
        )
        w = crop_box[2] - crop_box[0]
        h = crop_box[3] - crop_box[1]
        self.assertLess(w, 200)
        self.assertLess(h, 200)

    # 17. Event focus remains frozen after product leaves camera
    def test_17_event_focus_remains_frozen_after_product_expires(self):
        engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)
        t1 = 100.0
        h = [
            KinematicState(t1 - 0.2, (300, 360, 60, 50), (330.0, 385.0), (0.0, 0.0), 0.0, bottom_y=410, is_grounded=True),
            KinematicState(t1, (380, 360, 60, 50), (410.0, 385.0), (120.0, 0.0), 120.0, bottom_y=410, is_grounded=True),
        ]
        prod = self._create_product_track(7, (380, 360, 60, 50), history_states=h, now_t=t1)
        person = self._create_person_track(1, (280, 200, 80, 240), now_t=t1)
        ev = engine.evaluate_frame([prod, person], current_time=t1)
        self.assertEqual(len(ev), 1)

        # Later frame where product has moved off screen
        prod.current_bbox = (620, 360, 60, 50)
        self.assertEqual(ev[0].product_bbox_at_event, (380, 360, 60, 50))

    # 18. Incident remains in audit after product track expires
    def test_18_incident_remains_in_audit_after_track_expires(self):
        prod = self._create_product_track(7, (300, 360, 60, 50))
        event = WarehouseBehaviourEvent(
            event_id="CG-TEST-001",
            behaviour_type=WarehouseBehaviourType.PRODUCT_KICKED,
            risk_level="ORANGE",
            confidence=0.88,
            start_timestamp="2026-09-11 23:00:00",
            end_timestamp="2026-09-11 23:00:02",
            duration_seconds=2.0,
            observed_behaviour="Kicked",
            potential_risk="Crushing",
            recommended_action="Do not kick",
            product_track_id=7,
            person_track_id=1,
            product_bbox=(300, 360, 60, 50),
            state=EventState.ACTIVE,
        )
        # When track is deleted, event retains its attributes
        del prod
        self.assertEqual(event.product_track_id, 7)
        self.assertEqual(event.behaviour_type, WarehouseBehaviourType.PRODUCT_KICKED)

    # 19. Evidence frame corresponds to the frozen event geometry
    def test_19_evidence_frame_matches_frozen_geometry(self):
        prod = self._create_product_track(7, (300, 380, 50, 40))
        person = self._create_person_track(1, (240, 180, 80, 240))
        crop_box = compute_interaction_crop_box(
            (480, 640),
            product_track=prod,
            person_track=person,
            product_bbox=prod.current_bbox,
            person_bbox=person.current_bbox,
            behaviour_type="PRODUCT_KICKED",
        )
        event = WarehouseBehaviourEvent(
            event_id="CG-TEST-002",
            behaviour_type=WarehouseBehaviourType.PRODUCT_KICKED,
            risk_level="ORANGE",
            confidence=0.90,
            start_timestamp="2026-09-11 23:00:00",
            end_timestamp="2026-09-11 23:00:01",
            duration_seconds=1.0,
            observed_behaviour="Kicked",
            potential_risk="Crushing",
            recommended_action="No kicking",
            product_bbox=(300, 380, 50, 40),
            focus_bbox=crop_box,
        )
        self.assertEqual(event.focus_bbox_at_event, crop_box)

    # 20. Multiple visible products retain separate tracks
    def test_20_multiple_visible_products_retain_separate_tracks(self):
        tracker = WarehouseObjectTracker(frame_width=640, frame_height=480)
        # Frame 1: Two adjacent cartons touching at x=200 and x=260
        tracker.update([
            DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(200, 360, 60, 50)),
            DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(260, 360, 60, 50)),
        ], current_time=1.0)
        tracker.update([
            DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(200, 360, 60, 50)),
            DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(260, 360, 60, 50)),
        ], current_time=1.05)
        self.assertEqual(len(tracker.active_tracks), 2)
        tids = {t.track_id for t in tracker.active_tracks}
        self.assertEqual(len(tids), 2)


    # 21. Walking while holding carton immunity to rough handling
    def test_21_walking_while_holding_carton_immunity_to_rough_handling(self):
        engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)
        t = 10.0
        h = [
            KinematicState(t - 0.3, (200, 200, 60, 50), (230.0, 225.0), (80.0, 0.0), 80.0, bottom_y=250, is_grounded=False),
            KinematicState(t - 0.2, (208, 200, 60, 50), (238.0, 225.0), (220.0, 0.0), 220.0, bottom_y=250, is_grounded=False),
            KinematicState(t - 0.1, (230, 200, 60, 50), (260.0, 225.0), (250.0, 0.0), 250.0, bottom_y=250, is_grounded=False),
            KinematicState(t, (232, 200, 60, 50), (262.0, 225.0), (30.0, 0.0), 30.0, bottom_y=250, is_grounded=False),
        ]
        prod = self._create_product_track(3, (232, 200, 60, 50), interaction_state=ProductInteractionState.HELD, history_states=h, now_t=t)
        prod.carrying_state = "HOLDING"
        prod.associated_person_id = 1
        person = self._create_person_track(1, (180, 150, 100, 280), now_t=t)
        evts = engine.evaluate_frame([prod, person], current_time=t)
        rough = [e for e in evts if e.behaviour_type == WarehouseBehaviourType.ROUGH_HANDLING]
        self.assertEqual(len(rough), 0)

    # 22. Carried carton direction change immunity
    def test_22_carried_carton_direction_change_immunity(self):
        engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)
        t = 20.0
        h = [
            KinematicState(t - 0.3, (300, 220, 60, 50), (330.0, 245.0), (100.0, 0.0), 100.0, bottom_y=270, is_grounded=False),
            KinematicState(t - 0.2, (310, 220, 60, 50), (340.0, 245.0), (100.0, 0.0), 100.0, bottom_y=270, is_grounded=False),
            KinematicState(t - 0.1, (308, 220, 60, 50), (338.0, 245.0), (-20.0, 0.0), 20.0, bottom_y=270, is_grounded=False),
            KinematicState(t, (300, 220, 60, 50), (330.0, 245.0), (-80.0, 0.0), 80.0, bottom_y=270, is_grounded=False),
        ]
        prod = self._create_product_track(4, (300, 220, 60, 50), interaction_state=ProductInteractionState.HELD, history_states=h, now_t=t)
        prod.carrying_state = "HOLDING"
        prod.associated_person_id = 1
        person = self._create_person_track(1, (260, 160, 100, 270), now_t=t)
        evts = engine.evaluate_frame([prod, person], current_time=t)
        rough = [e for e in evts if e.behaviour_type == WarehouseBehaviourType.ROUGH_HANDLING]
        self.assertEqual(len(rough), 0)

    # 23. Carried carton stopping immunity
    def test_23_carried_carton_stopping_immunity(self):
        engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)
        t = 30.0
        h = [
            KinematicState(t - 0.3, (200, 200, 60, 50), (230.0, 225.0), (150.0, 0.0), 150.0, bottom_y=250, is_grounded=False),
            KinematicState(t - 0.2, (215, 200, 60, 50), (245.0, 225.0), (150.0, 0.0), 150.0, bottom_y=250, is_grounded=False),
            KinematicState(t - 0.1, (225, 200, 60, 50), (255.0, 225.0), (50.0, 0.0), 50.0, bottom_y=250, is_grounded=False),
            KinematicState(t, (225, 200, 60, 50), (255.0, 225.0), (0.0, 0.0), 0.0, bottom_y=250, is_grounded=False),
        ]
        prod = self._create_product_track(5, (225, 200, 60, 50), interaction_state=ProductInteractionState.HELD, history_states=h, now_t=t)
        prod.carrying_state = "HOLDING"
        prod.associated_person_id = 1
        person = self._create_person_track(1, (180, 150, 100, 280), now_t=t)
        evts = engine.evaluate_frame([prod, person], current_time=t)
        rough = [e for e in evts if e.behaviour_type == WarehouseBehaviourType.ROUGH_HANDLING]
        self.assertEqual(len(rough), 0)

    # 24. Ground touchdown rough slam accepted
    def test_24_ground_touchdown_rough_slam_accepted(self):
        engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)
        t = 40.0
        h = [
            KinematicState(t - 0.3, (200, 250, 60, 50), (230.0, 275.0), (0.0, 250.0), 250.0, bottom_y=300, is_grounded=False),
            KinematicState(t - 0.2, (200, 275, 60, 50), (230.0, 300.0), (0.0, 250.0), 250.0, bottom_y=325, is_grounded=False),
            KinematicState(t - 0.1, (200, 370, 60, 50), (230.0, 395.0), (0.0, 250.0), 250.0, bottom_y=420, is_grounded=True),
            KinematicState(t, (200, 370, 60, 50), (230.0, 395.0), (0.0, 0.0), 0.0, bottom_y=420, is_grounded=True),
        ]
        prod = self._create_product_track(6, (200, 370, 60, 50), interaction_state=ProductInteractionState.GROUND_CONTACT, history_states=h, now_t=t)
        evts = engine.evaluate_frame([prod], current_time=t)
        rough = [e for e in evts if e.behaviour_type == WarehouseBehaviourType.ROUGH_HANDLING]
        self.assertEqual(len(rough), 1)
        self.assertEqual(rough[0].risk_level, "ORANGE")

    # 25. Localization quality low rejects false rough handling
    def test_25_localization_quality_low_rejects_rough_handling(self):
        engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)
        t = 50.0
        h = [
            KinematicState(t - 0.2, (200, 370, 60, 50), (230.0, 395.0), (0.0, 250.0), 250.0, bottom_y=420, is_grounded=True),
            KinematicState(t - 0.1, (200, 370, 60, 50), (230.0, 395.0), (0.0, 250.0), 250.0, bottom_y=420, is_grounded=True),
            KinematicState(t, (200, 370, 60, 50), (230.0, 395.0), (0.0, 0.0), 0.0, bottom_y=420, is_grounded=True),
        ]
        prod = self._create_product_track(7, (200, 370, 60, 50), interaction_state=ProductInteractionState.GROUND_CONTACT, history_states=h, now_t=t)
        prod.localization_quality = 0.40  # Below 0.60 threshold
        evts = engine.evaluate_frame([prod], current_time=t)
        rough = [e for e in evts if e.behaviour_type == WarehouseBehaviourType.ROUGH_HANDLING]
        self.assertEqual(len(rough), 0)


    # 26. Hard Negative Test: Person walking with carton held at chest height produces ZERO false risks
    def test_26_carrying_carton_chest_height_hard_immunity_all_events(self):
        tracker = WarehouseObjectTracker(frame_width=640, frame_height=480)
        engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)

        # Simulate person walking from x=150 to x=300 holding carton at chest (y=180, person py=140, ph=280)
        all_events = []
        for step in range(15):
            t = step * 0.1
            px = 150 + step * 10
            py = 140
            pw, ph = 100, 280
            # Carton at chest: x=px+20, y=py+40=180, w=60, h=50 (bottom_y = 230 << floor_y=408)
            bx = px + 20
            by = py + 40
            bw, bh = 60, 50

            person_det = DetectedObject(class_id=0, label="person", confidence=0.92, bbox=(px, py, pw, ph))
            carton_det = DetectedObject(class_id=1, label="carton", confidence=0.88, bbox=(bx, by, bw, bh))

            tracks = tracker.update([person_det, carton_det], current_time=t)
            evts = engine.evaluate_frame(tracks, current_time=t)
            all_events.extend(evts)

        # Confirm product track is recognized as HELD
        prod_tracks = [t for t in tracker.active_tracks if t.category == WarehouseObjectCategory.PRODUCT]
        self.assertGreaterEqual(len(prod_tracks), 1)
        held_prod = prod_tracks[0]
        self.assertEqual(held_prod.interaction_state, ProductInteractionState.HELD)
        self.assertEqual(held_prod.carrying_state, "HOLDING")
        self.assertIsNotNone(held_prod.associated_person_id)

        # Verify ZERO false alarms
        stepping = [e for e in all_events if e.behaviour_type == WarehouseBehaviourType.STEPPING_ON_PRODUCT]
        kicks = [e for e in all_events if e.behaviour_type == WarehouseBehaviourType.PRODUCT_KICKED]
        drops = [e for e in all_events if e.behaviour_type == WarehouseBehaviourType.PRODUCT_DROPPED]
        throws = [e for e in all_events if e.behaviour_type == WarehouseBehaviourType.MATERIAL_PUSHED_THROWN]
        rough = [e for e in all_events if e.behaviour_type == WarehouseBehaviourType.ROUGH_HANDLING]
        stacking = [e for e in all_events if e.behaviour_type in (WarehouseBehaviourType.INCORRECT_STACKING, WarehouseBehaviourType.UNSTABLE_STACKING)]

        self.assertEqual(len(stepping), 0, "Carried carton must never trigger STEPPING_ON_PRODUCT")
        self.assertEqual(len(kicks), 0, "Carried carton must never trigger PRODUCT_KICKED")
        self.assertEqual(len(drops), 0, "Carried carton must never trigger PRODUCT_DROPPED")
        self.assertEqual(len(throws), 0, "Carried carton must never trigger MATERIAL_PUSHED_THROWN")
        self.assertEqual(len(rough), 0, "Carried carton must never trigger ROUGH_HANDLING")
        self.assertEqual(len(stacking), 0, "Carried carton must never trigger UNSTABLE_STACKING")

    # 27. Hard Negative Test: Leg/foot motion during walking must NOT create synthetic floor product
    def test_27_person_walking_leg_motion_no_synthetic_floor_product(self):
        tracker = WarehouseObjectTracker(frame_width=640, frame_height=480)
        
        # Person walking while holding carton at torso, with stray candidate noise at feet
        for step in range(5):
            t = step * 0.1
            px = 150 + step * 10
            py = 140
            pw, ph = 100, 280
            # Carton at chest
            bx, by, bw, bh = px + 20, py + 40, 60, 50
            # Stray candidate detection near feet (y=380, lower 20% of person)
            stray_foot_det = DetectedObject(class_id=1, label="carton", confidence=0.28, bbox=(px + 10, py + 220, 45, 45))

            person_det = DetectedObject(class_id=0, label="person", confidence=0.92, bbox=(px, py, pw, ph))
            carton_det = DetectedObject(class_id=1, label="carton", confidence=0.88, bbox=(bx, by, bw, bh))

            tracks = tracker.update([person_det, carton_det, stray_foot_det], current_time=t)

        # Ensure only 1 product track (the true chest carton) is created/active; zero foot products
        prod_tracks = [t for t in tracker.active_tracks if t.category == WarehouseObjectCategory.PRODUCT]
        self.assertEqual(len(prod_tracks), 1)
        self.assertLess(prod_tracks[0].current_bbox[1], 260)


if __name__ == "__main__":
    unittest.main()

