"""
CareGuard AI - Test Suite: Product Kicking Semantic Gating & Carrying State Immunity
-------------------------------------------------------------------------------------
Verifies that:
1. Operator walking while holding a carton at torso (e.g. 92.2 px/s) generates ZERO false PRODUCT_KICKED,
   PRODUCT_DROPPED, MATERIAL_PUSHED_THROWN, or UNSTABLE_STACKING events.
2. Operator standing with carton at torso maintains HELD carrying state.
3. Fast walk / jog with carton (120 px/s) produces zero false kicks or throws.
4. Stray lower-body/leg candidate product detections are suppressed when a carton is held at the torso.
5. Legitimate product kicks from a grounded stationary resting state trigger PRODUCT_KICKED.
6. Product rolling or moving without foot contact does NOT trigger PRODUCT_KICKED.
7. Dropping a carton from hands produces PRODUCT_DROPPED.
8. Throwing a carton produces MATERIAL_PUSHED_THROWN.
"""

import unittest
import numpy as np

from src.core.warehouse_models import (
    WarehouseObjectCategory,
    ProductInteractionState,
    WarehouseBehaviourType,
    KinematicState,
    TrackedEntity,
)
from src.core.interfaces.detector_interface import DetectedObject
from src.core.warehouse_tracker import WarehouseObjectTracker
from src.core.warehouse_behaviour_engine import TemporalWarehouseBehaviourEngine


def make_entity(
    track_id: int,
    category: WarehouseObjectCategory,
    bbox: tuple,
    velocities: list,
    timestamps: list,
    interaction_state: ProductInteractionState = ProductInteractionState.FREE,
    carrying_state: str = "NONE",
    interaction_source: str = "UNKNOWN",
    associated_person_id: int = None,
    is_confirmed: bool = True,
    confidence: float = 0.85,
    floor_y: int = 400,
) -> TrackedEntity:
    """Helper to construct a realistic TrackedEntity with kinematic history."""
    history = []
    for i, (v, ts) in enumerate(zip(velocities, timestamps)):
        vx, vy = v
        speed = float(np.sqrt(vx * vx + vy * vy))
        x, y, w, h = bbox
        bottom_y = y + h
        elevation = max(0.0, min(1.0, (480 - bottom_y) / 480.0))
        is_grounded = bottom_y >= floor_y

        state = KinematicState(
            timestamp=ts,
            bbox=bbox,
            centroid=(x + w / 2.0, y + h / 2.0),
            velocity=(vx, vy),
            speed=speed,
            vertical_accel=0.0,
            bottom_y=bottom_y,
            elevation_ratio=elevation,
            is_grounded=is_grounded,
        )
        history.append(state)

    entity = TrackedEntity(
        track_id=track_id,
        class_id=0,
        label="carton" if category == WarehouseObjectCategory.PRODUCT else "person",
        category=category,
        confidence=confidence,
        current_bbox=bbox,
        first_seen=timestamps[0],
        last_seen=timestamps[-1],
        last_detection_time=timestamps[-1],
        history=history,
        missed_frames=0,
        is_confirmed=is_confirmed,
        interaction_state=interaction_state,
        interaction_history=[interaction_state] * len(timestamps),
        interaction_source=interaction_source,
        raw_detection_bbox=bbox,
        is_predicted=False,
        carrying_state=carrying_state,
        associated_person_id=associated_person_id,
        detection_confidence=confidence,
        behaviour_confidence=confidence,
    )
    return entity


class TestProductKickingAndCarrying(unittest.TestCase):

    def setUp(self):
        self.engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)
        self.engine.floor_y_threshold = 400
        self.tracker = WarehouseObjectTracker(frame_width=640, frame_height=480)
        self.tracker.floor_y_threshold = 400

    def test_scenario_1_walking_while_holding_carton_zero_false_kicks(self):
        """Scenario 1: Operator walking at 92.2 px/s carrying carton at torso height produces ZERO false kick/drop/throw."""
        now = 100.0
        ts = [now - 0.6, now - 0.3, now]
        # Operator walking horizontally at 92.2 px/s
        person = make_entity(
            track_id=1,
            category=WarehouseObjectCategory.PERSON,
            bbox=(200, 100, 80, 240),
            velocities=[(92.2, 0.0), (92.2, 0.0), (92.2, 0.0)],
            timestamps=ts,
            floor_y=400,
        )
        # Carton held in front of torso (y=160, h=60 -> bottom_y=220 << 400)
        carton = make_entity(
            track_id=2,
            category=WarehouseObjectCategory.PRODUCT,
            bbox=(220, 160, 50, 50),
            velocities=[(92.2, 0.0), (92.2, 0.0), (92.2, 0.0)],
            timestamps=ts,
            interaction_state=ProductInteractionState.HELD,
            carrying_state="HOLDING",
            associated_person_id=1,
            floor_y=400,
        )

        events = self.engine.evaluate_frame([person, carton], current_time=now)
        kick_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.PRODUCT_KICKED]
        drop_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.PRODUCT_DROPPED]
        throw_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.MATERIAL_PUSHED_THROWN]

        self.assertEqual(len(kick_events), 0, f"Expected 0 PRODUCT_KICKED events, got {len(kick_events)}")
        self.assertEqual(len(drop_events), 0, f"Expected 0 PRODUCT_DROPPED events, got {len(drop_events)}")
        self.assertEqual(len(throw_events), 0, f"Expected 0 MATERIAL_PUSHED_THROWN events, got {len(throw_events)}")

    def test_scenario_2_standing_with_held_carton(self):
        """Scenario 2: Standing still with carton at torso correctly classifies interaction state as HELD."""
        now = 50.0
        # Frame 1
        p_det = DetectedObject(class_id=0, label="person", confidence=0.90, bbox=(200, 100, 80, 240))
        c_det = DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(220, 160, 50, 50))
        tracks = self.tracker.update([p_det, c_det], current_time=now)

        # Frame 2 (confirmed)
        tracks = self.tracker.update([p_det, c_det], current_time=now + 0.05)
        carton_track = next((t for t in tracks if t.category == WarehouseObjectCategory.PRODUCT), None)

        self.assertIsNotNone(carton_track)
        self.assertEqual(carton_track.interaction_state, ProductInteractionState.HELD)
        self.assertEqual(carton_track.carrying_state, "HOLDING")
        self.assertIsNotNone(carton_track.associated_person_id)

    def test_scenario_3_fast_walk_with_carton(self):
        """Scenario 3: Fast walk at 120 px/s with carton does not trigger kick or throw."""
        now = 100.0
        ts = [now - 0.4, now - 0.2, now]
        person = make_entity(
            track_id=1,
            category=WarehouseObjectCategory.PERSON,
            bbox=(200, 100, 80, 240),
            velocities=[(120.0, 0.0), (120.0, 0.0), (120.0, 0.0)],
            timestamps=ts,
            floor_y=400,
        )
        carton = make_entity(
            track_id=2,
            category=WarehouseObjectCategory.PRODUCT,
            bbox=(220, 160, 50, 50),
            velocities=[(120.0, 0.0), (120.0, 0.0), (120.0, 0.0)],
            timestamps=ts,
            interaction_state=ProductInteractionState.HELD,
            carrying_state="HOLDING",
            associated_person_id=1,
            floor_y=400,
        )
        events = self.engine.evaluate_frame([person, carton], current_time=now)
        self.assertEqual(len(events), 0, f"Expected 0 events during fast walk, got {len(events)}")

    def test_scenario_4_suppress_leg_product_detection_when_carton_held(self):
        """Scenario 4: When a person has a held carton at torso, stray leg-level candidate product detection is filtered."""
        now = 10.0
        # Initialize confirmed person and torso product
        p_det = DetectedObject(class_id=0, label="person", confidence=0.90, bbox=(200, 100, 80, 240))
        c_det = DetectedObject(class_id=1, label="carton", confidence=0.88, bbox=(220, 160, 50, 50))
        self.tracker.update([p_det, c_det], current_time=now)
        self.tracker.update([p_det, c_det], current_time=now + 0.05)

        # Now detector produces a stray detection around the legs/knees (y=260, h=50 -> inside person lower half)
        leg_det = DetectedObject(class_id=1, label="carton", confidence=0.40, bbox=(215, 260, 45, 45))
        tracks = self.tracker.update([p_det, c_det, leg_det], current_time=now + 0.10)

        product_tracks = [t for t in tracks if t.category == WarehouseObjectCategory.PRODUCT]
        # Should only have 1 product track (the torso carton), not a phantom leg product
        self.assertEqual(len(product_tracks), 1)
        self.assertLess(product_tracks[0].current_bbox[1], 200)

    def test_scenario_5_legitimate_product_kick_fires(self):
        """Scenario 5: Legitimate grounded product kicked from rest by approaching foot triggers PRODUCT_KICKED."""
        now = 200.0
        ts = [now - 0.6, now - 0.3, now]

        # Handler standing near floor, foot kicks carton
        person = make_entity(
            track_id=1,
            category=WarehouseObjectCategory.PERSON,
            bbox=(100, 150, 80, 250), # bottom = 400 (floor)
            velocities=[(20.0, 0.0), (35.0, 0.0), (40.0, 0.0)],
            timestamps=ts,
            floor_y=400,
        )

        # Carton was resting on floor (v=0), then receives foot impact spike (v=95.0 px/s along floor)
        carton = make_entity(
            track_id=2,
            category=WarehouseObjectCategory.PRODUCT,
            bbox=(160, 360, 40, 40), # bottom = 400 (grounded)
            velocities=[(0.0, 0.0), (10.0, 0.0), (95.0, 0.0)], # Impulse spike Delta v = 95 - 0 = 95
            timestamps=ts,
            interaction_state=ProductInteractionState.GROUND_CONTACT,
            carrying_state="NONE",
            interaction_source="FOOT_INTERACTION",
            associated_person_id=1,
            floor_y=400,
        )

        events = self.engine.evaluate_frame([person, carton], current_time=now)
        kick_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.PRODUCT_KICKED]

        self.assertEqual(len(kick_events), 1, "Expected 1 PRODUCT_KICKED event for real foot strike")
        ev = kick_events[0]
        self.assertEqual(ev.product_track_id, 2)
        self.assertEqual(ev.person_track_id, 1)
        self.assertIn("kicked", ev.observed_behaviour.lower())
        self.assertGreaterEqual(ev.metadata["kick_speed"], 90.0)

    def test_scenario_6_rolling_product_without_foot_no_kick(self):
        """Scenario 6: Product rolling/sliding across floor far from any foot does NOT trigger PRODUCT_KICKED."""
        now = 300.0
        ts = [now - 0.6, now - 0.3, now]
        # Product rolling at 80 px/s on floor, no person nearby
        carton = make_entity(
            track_id=5,
            category=WarehouseObjectCategory.PRODUCT,
            bbox=(300, 360, 40, 40),
            velocities=[(80.0, 0.0), (80.0, 0.0), (80.0, 0.0)],
            timestamps=ts,
            interaction_state=ProductInteractionState.GROUND_CONTACT,
            floor_y=400,
        )

        events = self.engine.evaluate_frame([carton], current_time=now)
        kick_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.PRODUCT_KICKED]
        self.assertEqual(len(kick_events), 0, "Rolling carton without foot contact must not trigger kick alert")

    def test_scenario_7_carton_dropped_from_hands(self):
        """Scenario 7: Carton released from hands in free-fall descent triggers PRODUCT_DROPPED."""
        now = 400.0
        ts = [now - 0.6, now - 0.3, now]
        # Carton starts elevated at torso (y=150), falls rapidly (vy=140), impacts floor (y=360)
        carton = make_entity(
            track_id=3,
            category=WarehouseObjectCategory.PRODUCT,
            bbox=(200, 360, 40, 40), # current at floor (bottom=400)
            velocities=[(0.0, 10.0), (5.0, 140.0), (0.0, 10.0)], # high downward velocity in middle
            timestamps=ts,
            interaction_state=ProductInteractionState.GROUND_CONTACT,
            floor_y=400,
        )
        # Mock earlier history states for free-fall descent from y=150 to y=360
        carton.history[0].bottom_y = 190
        carton.history[0].elevation_ratio = 0.60
        carton.history[0].is_grounded = False
        carton.history[1].bottom_y = 300
        carton.history[1].elevation_ratio = 0.30
        carton.history[1].is_grounded = False
        carton.history[2].bottom_y = 400
        carton.history[2].elevation_ratio = 0.0
        carton.history[2].is_grounded = True
        carton.interaction_history = [ProductInteractionState.HELD, ProductInteractionState.AIRBORNE, ProductInteractionState.GROUND_CONTACT]

        events = self.engine.evaluate_frame([carton], current_time=now)
        drop_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.PRODUCT_DROPPED]
        self.assertEqual(len(drop_events), 1, "Expected 1 PRODUCT_DROPPED event for released carton")

    def test_scenario_8_carton_thrown_from_hands(self):
        """Scenario 8: Carton pushed horizontally in airborne flight triggers MATERIAL_PUSHED_THROWN."""
        now = 500.0
        ts = [now - 0.4, now - 0.2, now]
        # Airborne flight: elevated (bottom=250), high horizontal velocity (vx=180, vy=15)
        carton = make_entity(
            track_id=4,
            category=WarehouseObjectCategory.PRODUCT,
            bbox=(250, 200, 50, 50),
            velocities=[(165.0, 10.0), (175.0, 15.0), (180.0, 15.0)],
            timestamps=ts,
            interaction_state=ProductInteractionState.AIRBORNE,
            floor_y=400,
        )
        for s in carton.history:
            s.is_grounded = False
            s.elevation_ratio = 0.45
            s.bottom_y = 250

        events = self.engine.evaluate_frame([carton], current_time=now)
        throw_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.MATERIAL_PUSHED_THROWN]
        self.assertEqual(len(throw_events), 1, "Expected 1 MATERIAL_PUSHED_THROWN event for airborne throw")


if __name__ == '__main__':
    unittest.main()
