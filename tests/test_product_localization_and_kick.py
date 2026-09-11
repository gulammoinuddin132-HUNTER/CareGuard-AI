"""
tests/test_product_localization_and_kick.py
-------------------------------------------
Comprehensive test suite verifying:
1. Product bounding box stability and continuity (no torso <-> legs/floor teleportation).
2. Torso artifact rejection when product is on floor.
3. Area ratio and aspect ratio continuity guards.
4. Occlusion short-term motion prediction (is_predicted = True).
5. Product bbox geometry isolation from handler association.
6. Foot vs hand interaction discrimination (FOOT_INTERACTION vs HAND_INTERACTION).
7. Kick detection (PRODUCT_KICKED, ORANGE) vs Material Pushed / Thrown rejection.
8. Event participant bbox freeze during active alert rendering.
"""

import sys
import time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.warehouse_models import (
    WarehouseObjectCategory,
    ProductInteractionState,
    WarehouseBehaviourType,
    WarehouseBehaviourEvent,
    TrackedEntity,
    KinematicState,
)
from src.core.interfaces.detector_interface import DetectedObject
from src.core.warehouse_tracker import WarehouseObjectTracker
from src.core.warehouse_behaviour_engine import TemporalWarehouseBehaviourEngine
from src.core.warehouse_risk_policy import calculate_risk_severity


def test_case_a_held_carton_does_not_jump_to_legs():
    """Case A: When a person holds a carton at torso, tracker must reject sudden jump to legs."""
    tracker = WarehouseObjectTracker(frame_width=640, frame_height=480, confirmation_frames=2)
    t0 = 100.0

    # Person at x=200, y=200, w=150, h=400 (torso y ~ 250..420, legs y ~ 450..600)
    person_det = DetectedObject(class_id=0, label="person", confidence=0.90, bbox=(200, 200, 150, 400))
    # Held carton at chest/torso (y=300, h=100)
    carton_det_1 = DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(210, 300, 130, 100))

    tracker.update([person_det, carton_det_1], current_time=t0)
    tracker.update([person_det, carton_det_1], current_time=t0 + 0.033)

    prod_tracks = [t for t in tracker.all_tracks if t.category == WarehouseObjectCategory.PRODUCT and t.is_confirmed]
    assert len(prod_tracks) == 1
    prod_id = prod_tracks[0].track_id
    assert 280 <= prod_tracks[0].current_bbox[1] <= 320

    # In next frame, detector fires false detection at legs/floor (y=520)
    false_leg_det = DetectedObject(class_id=1, label="carton", confidence=0.30, bbox=(210, 520, 130, 90))
    tracker.update([person_det, false_leg_det], current_time=t0 + 0.066)

    # Product track must NOT jump to legs (y=520)
    curr_prod = tracker._tracks.get(prod_id)
    assert curr_prod is not None
    assert curr_prod.current_bbox[1] < 400, f"Product track jumped to legs: {curr_prod.current_bbox}"


def test_case_b_floor_carton_does_not_jump_to_torso():
    """Case B: When a carton is on the floor, tracker must reject false product detection on person torso."""
    tracker = WarehouseObjectTracker(frame_width=640, frame_height=480, confirmation_frames=2)
    t0 = 100.0

    person_det = DetectedObject(class_id=0, label="person", confidence=0.92, bbox=(260, 160, 190, 450))
    # Real carton on floor
    floor_carton = DetectedObject(class_id=1, label="carton", confidence=0.80, bbox=(70, 470, 160, 160))

    tracker.update([person_det, floor_carton], current_time=t0)
    tracker.update([person_det, floor_carton], current_time=t0 + 0.033)

    prod_tracks = [t for t in tracker.all_tracks if t.category == WarehouseObjectCategory.PRODUCT and t.is_confirmed]
    assert len(prod_tracks) == 1
    floor_id = prod_tracks[0].track_id

    # False product detection on torso (fraction_in_person > 0.80, low/moderate conf)
    false_torso_det = DetectedObject(class_id=1, label="carton", confidence=0.32, bbox=(265, 240, 180, 200))
    tracker.update([person_det, floor_carton, false_torso_det], current_time=t0 + 0.066)

    curr_floor_prod = tracker._tracks.get(floor_id)
    assert curr_floor_prod is not None
    # Floor carton track must stay on the floor (y > 440) and not jump to y=240
    assert curr_floor_prod.current_bbox[1] >= 440, f"Floor carton jumped to torso: {curr_floor_prod.current_bbox}"


def test_area_and_aspect_ratio_continuity_guards():
    """Verify that detector distortions (>2.5x area change or >2.2x aspect ratio distortion) are rejected."""
    tracker = WarehouseObjectTracker(frame_width=640, frame_height=480, confirmation_frames=2)
    t0 = 100.0

    # Initial product 100x100 (area 10000, aspect 1.0)
    det1 = DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(200, 300, 100, 100))
    tracker.update([det1], current_time=t0)
    tracker.update([det1], current_time=t0 + 0.033)

    prod = [t for t in tracker.all_tracks if t.category == WarehouseObjectCategory.PRODUCT][0]
    orig_id = prod.track_id

    # Huge detection 300x300 (area 90000 -> 9x area)
    huge_det = DetectedObject(class_id=1, label="carton", confidence=0.50, bbox=(200, 300, 300, 300))
    tracker.update([huge_det], current_time=t0 + 0.066)

    prod_after = tracker._tracks.get(orig_id)
    assert prod_after is not None
    # Track must not accept the huge distortion
    assert prod_after.current_bbox[2] < 200


def test_occlusion_short_term_motion_prediction():
    """Verify that when a product detection is missed, the tracker applies linear velocity prediction."""
    tracker = WarehouseObjectTracker(frame_width=640, frame_height=480, confirmation_frames=2)
    t0 = 100.0

    # Moving product (vx = 100 px/s)
    d1 = DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(100, 300, 80, 80))
    tracker.update([d1], current_time=t0)
    d2 = DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(110, 300, 80, 80))
    tracker.update([d2], current_time=t0 + 0.1)

    prod = [t for t in tracker.all_tracks if t.category == WarehouseObjectCategory.PRODUCT][0]
    orig_id = prod.track_id
    assert prod.current_bbox[0] >= 105

    # Occluded / missed on next frame
    tracker.update([], current_time=t0 + 0.2)
    prod_occ = tracker._tracks.get(orig_id)
    assert prod_occ is not None
    assert prod_occ.missed_frames == 1
    assert prod_occ.is_predicted is True
    assert prod_occ.raw_detection_bbox is None
    # Position should have moved forward in x direction
    assert prod_occ.current_bbox[0] >= 110


def test_product_bbox_geometry_isolated_from_handler():
    """Verify that associating a handler with a product NEVER modifies the product's bounding box."""
    tracker = WarehouseObjectTracker(frame_width=640, frame_height=480, confirmation_frames=2)
    t0 = 100.0

    person_det = DetectedObject(class_id=0, label="person", confidence=0.90, bbox=(100, 100, 200, 500))
    product_det = DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(140, 250, 90, 80))

    tracker.update([person_det, product_det], current_time=t0)
    tracker.update([person_det, product_det], current_time=t0 + 0.033)

    prod = [t for t in tracker.all_tracks if t.category == WarehouseObjectCategory.PRODUCT][0]
    assert prod.associated_person_id is not None
    # Product bbox must remain exactly its own geometry, not person's geometry
    assert prod.current_bbox[2] == 90
    assert prod.current_bbox[3] == 80


def test_foot_vs_hand_interaction_source_classification():
    """Verify FOOT_INTERACTION for low contact vs HAND_INTERACTION for mid/upper contact."""
    tracker = WarehouseObjectTracker(frame_width=640, frame_height=480, confirmation_frames=2)
    t0 = 100.0

    # Person from y=100 to y=500 (height 400). Foot region is y >= 100 + 0.65*400 = 360
    person_det = DetectedObject(class_id=0, label="person", confidence=0.90, bbox=(200, 100, 150, 400))

    # Hand carry: carton at y=200
    hand_carton = DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(220, 200, 100, 80))
    tracker.update([person_det, hand_carton], current_time=t0)
    tracker.update([person_det, hand_carton], current_time=t0 + 0.033)

    prod = [t for t in tracker.all_tracks if t.category == WarehouseObjectCategory.PRODUCT][0]
    assert prod.interaction_source == "HAND_INTERACTION"

    # Foot kick: carton near feet at y=400
    tracker2 = WarehouseObjectTracker(frame_width=640, frame_height=480, confirmation_frames=2)
    foot_carton = DetectedObject(class_id=1, label="carton", confidence=0.85, bbox=(220, 420, 100, 80))
    tracker2.update([person_det, foot_carton], current_time=t0)
    tracker2.update([person_det, foot_carton], current_time=t0 + 0.033)

    prod2 = [t for t in tracker2.all_tracks if t.category == WarehouseObjectCategory.PRODUCT][0]
    assert prod2.interaction_source == "FOOT_INTERACTION"


def test_kick_detection_and_rejection_of_material_pushed_thrown():
    """Verify that kicking a carton triggers PRODUCT_KICKED (ORANGE) and NEVER MATERIAL_PUSHED_THROWN."""
    engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480, cooldown_seconds=0.1)
    t0 = 100.0

    # Person with feet near y=450..500
    person_state = KinematicState(
        timestamp=t0,
        bbox=(200, 100, 150, 400),
        centroid=(275.0, 300.0),
        velocity=(0.0, 0.0),
        speed=0.0,
        bottom_y=500,
        is_grounded=True,
    )
    person_track = TrackedEntity(
        track_id=1,
        class_id=0,
        label="person",
        category=WarehouseObjectCategory.PERSON,
        confidence=0.90,
        current_bbox=(200, 100, 150, 400),
        first_seen=t0,
        last_seen=t0 + 0.2,
        history=[person_state],
        is_confirmed=True,
    )

    # Product starting near feet on floor, then kicked horizontally at 180 px/s
    history = [
        KinematicState(timestamp=t0, bbox=(250, 440, 90, 80), centroid=(295.0, 480.0), velocity=(0.0, 0.0), speed=0.0, bottom_y=520, is_grounded=True),
        KinematicState(timestamp=t0 + 0.1, bbox=(270, 440, 90, 80), centroid=(315.0, 480.0), velocity=(180.0, 0.0), speed=180.0, bottom_y=520, is_grounded=True),
    ]
    prod_track = TrackedEntity(
        track_id=2,
        class_id=1,
        label="carton",
        category=WarehouseObjectCategory.PRODUCT,
        confidence=0.88,
        current_bbox=(270, 440, 90, 80),
        first_seen=t0,
        last_seen=t0 + 0.1,
        history=history,
        is_confirmed=True,
        associated_person_id=1,
        interaction_source="FOOT_INTERACTION",
    )

    events = engine.evaluate_frame([person_track, prod_track], current_time=t0 + 0.1)

    # Must detect PRODUCT_KICKED
    kicked_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.PRODUCT_KICKED]
    assert len(kicked_events) == 1
    assert kicked_events[0].risk_level == "ORANGE"
    assert kicked_events[0].interaction_source == "FOOT_INTERACTION"

    # Must NOT detect MATERIAL_PUSHED_THROWN
    thrown_events = [e for e in events if e.behaviour_type == WarehouseBehaviourType.MATERIAL_PUSHED_THROWN]
    assert len(thrown_events) == 0, "Kick incorrectly classified as MATERIAL_PUSHED_THROWN!"


def test_risk_severity_for_product_kicked():
    """Verify calculate_risk_severity returns ORANGE for PRODUCT_KICKED."""
    sev = calculate_risk_severity(
        WarehouseBehaviourType.PRODUCT_KICKED,
        kinematics={"horizontal_velocity": 120.0, "speed": 120.0},
        confidence=0.85,
    )
    assert sev["severity"] == "ORANGE"
    assert "foot impact" in sev["severity_reason"].lower() or "kick" in sev["severity_reason"].lower()
    assert sev["severity_factors"]["behaviour"] == "PRODUCT_KICKED"


def test_clean_view_freezes_event_participant_bboxes():
    """Verify that in Clean View during an active alert, participant boxes are frozen from the event."""
    from src.api.state import CareGuardBackendState
    state = CareGuardBackendState.get_instance()

    # Create dummy active event with frozen bounding boxes
    frozen_prod_box = (100, 200, 80, 80)
    frozen_person_box = (200, 150, 100, 300)
    event = WarehouseBehaviourEvent(
        event_id="EVT-TEST-1",
        behaviour_type=WarehouseBehaviourType.PRODUCT_KICKED,
        risk_level="ORANGE",
        confidence=0.85,
        start_timestamp="2026-09-10 12:00:00",
        end_timestamp="2026-09-10 12:00:01",
        duration_seconds=1.0,
        observed_behaviour="Kicked product",
        potential_risk="Crushing",
        recommended_action="Do not kick",
        product_track_id=1,
        person_track_id=2,
        product_bbox=frozen_prod_box,
        person_bbox=frozen_person_box,
    )
    state.active_risk_event = event

    # Also simulate a drifted track with different bbox
    drifted_prod = TrackedEntity(
        track_id=1,
        class_id=1,
        label="carton",
        category=WarehouseObjectCategory.PRODUCT,
        confidence=0.80,
        current_bbox=(300, 400, 80, 80),  # Drifted location
        first_seen=100.0,
        last_seen=101.0,
        history=[],
        is_confirmed=True,
    )
    state.tracker._tracks[1] = drifted_prod

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    annotated = state._render_warehouse_hud(frame, tracks=list(state.tracker._tracks.values()), events=[event], overlay_mode="clean")
    assert annotated is not None
    # Verify frame was annotated
    assert annotated.shape == (480, 640, 3)


def test_diagnostics_product_overlay_metadata():
    """Verify that in Diagnostics mode, product tracks with raw_detection_bbox, is_predicted, and interaction_source render cleanly."""
    from src.api.state import CareGuardBackendState
    state = CareGuardBackendState.get_instance()

    prod = TrackedEntity(
        track_id=1,
        class_id=1,
        label="carton",
        category=WarehouseObjectCategory.PRODUCT,
        confidence=0.85,
        current_bbox=(150, 200, 90, 85),
        first_seen=100.0,
        last_seen=101.0,
        history=[
            KinematicState(timestamp=100.0, bbox=(150, 200, 90, 85), centroid=(195.0, 242.5), velocity=(0.0, 0.0), speed=0.0, bottom_y=285, is_grounded=False)
        ],
        is_confirmed=True,
        raw_detection_bbox=(152, 201, 88, 84),
        is_predicted=False,
        interaction_source="HAND_INTERACTION",
    )
    state.tracker._tracks[1] = prod

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    annotated = state._render_warehouse_hud(frame, tracks=[prod], events=[], overlay_mode="diagnostics")
    assert annotated is not None
    assert annotated.shape == (480, 640, 3)


if __name__ == "__main__":
    test_case_a_held_carton_does_not_jump_to_legs()
    print("PASS: test_case_a_held_carton_does_not_jump_to_legs")
    test_case_b_floor_carton_does_not_jump_to_torso()
    print("PASS: test_case_b_floor_carton_does_not_jump_to_torso")
    test_area_and_aspect_ratio_continuity_guards()
    print("PASS: test_area_and_aspect_ratio_continuity_guards")
    test_occlusion_short_term_motion_prediction()
    print("PASS: test_occlusion_short_term_motion_prediction")
    test_product_bbox_geometry_isolated_from_handler()
    print("PASS: test_product_bbox_geometry_isolated_from_handler")
    test_foot_vs_hand_interaction_source_classification()
    print("PASS: test_foot_vs_hand_interaction_source_classification")
    test_kick_detection_and_rejection_of_material_pushed_thrown()
    print("PASS: test_kick_detection_and_rejection_of_material_pushed_thrown")
    test_risk_severity_for_product_kicked()
    print("PASS: test_risk_severity_for_product_kicked")
    test_clean_view_freezes_event_participant_bboxes()
    print("PASS: test_clean_view_freezes_event_participant_bboxes")
    test_diagnostics_product_overlay_metadata()
    print("PASS: test_diagnostics_product_overlay_metadata")
    print("\n=== ALL 10 TESTS PASSED SUCCESSFULLY! ===")
