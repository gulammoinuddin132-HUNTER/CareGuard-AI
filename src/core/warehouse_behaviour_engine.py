"""
CareGuard AI - 10 Warehouse Handling & Damage Prevention Temporal Behaviour Engine
----------------------------------------------------------------------------------
Evaluates multi-frame action sequences, kinematics, and spatial stacking relationships
to detect damage risks and unsafe handling practices across 10 core behaviours:

1. Product Dropped (Elevated -> Free Fall Velocity Spike -> Floor Impact -> Stationary)
2. Product Dragged (Grounded -> Sustained Horizontal Ground Motion -> No Clearance)
3. Rough Handling / Excessive Impact (Sudden high deceleration spike upon contact/placement)
4. Incorrect Stacking (Heavy on top of fragile / severe horizontal overhang)
5. Unstable Stacking (Leaning column / center-of-mass lateral displacement)
6. Placed Outside Designated Area (Material left stationary in pedestrian walkway/exit)
7. Handled Without Equipment (Manual transport of bulky cargo without trolley)
8. Pallet Positioned Incorrectly (Misaligned or protruding into traffic corridors)
9. Material Pushed / Thrown (High horizontal velocity ballistic release)
10. Unsafe Loading / Unloading Sequence (Removing bottom item from stack before upper load)
"""

from datetime import datetime
import logging
import math
import time
from typing import Dict, Any, List, Optional, Tuple, Callable

import numpy as np

from config import (
    WAREHOUSE_FLOOR_Y_RATIO,
    WAREHOUSE_DROP_VELOCITY_THRESHOLD,
    WAREHOUSE_DROP_MIN_DISPLACEMENT_PX,
    WAREHOUSE_DRAG_SPEED_THRESHOLD,
    WAREHOUSE_DRAG_MIN_DURATION_SECONDS,
    WAREHOUSE_ROUGH_IMPACT_DECEL_THRESHOLD,
    WAREHOUSE_ROUGH_IMPACT_MIN_SPEED_PX,
    WAREHOUSE_INCORRECT_STACK_AREA_RATIO,
    WAREHOUSE_INCORRECT_STACK_OVERHANG_RATIO,
    WAREHOUSE_UNSTABLE_STACK_TILT_PX,
    WAREHOUSE_WALKWAY_DWELL_SECONDS,
    WAREHOUSE_HEAVY_CARGO_AREA_PX,
    WAREHOUSE_MANUAL_CARRY_DISTANCE_PX,
    WAREHOUSE_PALLET_PROTRUSION_PX,
    WAREHOUSE_THROW_HORIZONTAL_VELOCITY,
    WAREHOUSE_UNSAFE_UNLOAD_GAP_PX,
    WAREHOUSE_BEHAVIOUR_COOLDOWN_SECONDS,
    DEFAULT_ZONES,
)
from src.core.warehouse_models import (
    WarehouseObjectCategory,
    ProductInteractionState,
    WarehouseBehaviourType,
    KinematicState,
    TrackedEntity,
    WarehouseBehaviourEvent,
)
from src.core.warehouse_tracker import compute_centroid_dist, compute_bbox_min_dist
from src.core.warehouse_evidence_cropper import compute_interaction_crop_box
from src.core.warehouse_risk_policy import calculate_risk_severity, WarehouseRiskTier

logger = logging.getLogger("CareGuard.BehaviourEngine")


class TemporalWarehouseBehaviourEngine:
    """
    Evaluates temporal sequence transitions over track history buffers to detect
    damage risks and unsafe handling practices across 10 warehouse behaviours.
    """

    def __init__(
        self,
        floor_y_threshold_ratio: float = WAREHOUSE_FLOOR_Y_RATIO,
        frame_height: int = 480,
        frame_width: int = 640,
        drop_velocity_threshold: float = WAREHOUSE_DROP_VELOCITY_THRESHOLD,
        drop_min_displacement_px: float = WAREHOUSE_DROP_MIN_DISPLACEMENT_PX,
        drag_speed_threshold: float = WAREHOUSE_DRAG_SPEED_THRESHOLD,
        drag_min_duration_seconds: float = WAREHOUSE_DRAG_MIN_DURATION_SECONDS,
        cooldown_seconds: float = WAREHOUSE_BEHAVIOUR_COOLDOWN_SECONDS,
        evidence_capture_callback: Optional[Callable[[str], Optional[str]]] = None,
    ):
        self.floor_y_threshold_ratio = floor_y_threshold_ratio
        self.floor_y_threshold = int(frame_height * floor_y_threshold_ratio)
        self.frame_height = frame_height
        self.frame_width = frame_width
        self.drop_velocity_threshold = drop_velocity_threshold
        self.drop_min_displacement_px = drop_min_displacement_px
        self.drag_speed_threshold = drag_speed_threshold
        self.drag_min_duration_seconds = drag_min_duration_seconds
        self.cooldown_seconds = cooldown_seconds
        self.evidence_callback = evidence_capture_callback

        # Configurable thresholds
        self.rough_impact_decel_threshold = WAREHOUSE_ROUGH_IMPACT_DECEL_THRESHOLD
        self.rough_impact_min_speed = WAREHOUSE_ROUGH_IMPACT_MIN_SPEED_PX
        self.incorrect_stack_area_ratio = WAREHOUSE_INCORRECT_STACK_AREA_RATIO
        self.incorrect_stack_overhang_ratio = WAREHOUSE_INCORRECT_STACK_OVERHANG_RATIO
        self.unstable_stack_tilt_px = WAREHOUSE_UNSTABLE_STACK_TILT_PX
        self.walkway_dwell_seconds = WAREHOUSE_WALKWAY_DWELL_SECONDS
        self.heavy_cargo_area_px = WAREHOUSE_HEAVY_CARGO_AREA_PX
        self.manual_carry_distance_px = WAREHOUSE_MANUAL_CARRY_DISTANCE_PX
        self.pallet_protrusion_px = WAREHOUSE_PALLET_PROTRUSION_PX
        self.throw_velocity_threshold = WAREHOUSE_THROW_HORIZONTAL_VELOCITY
        self.unsafe_unload_gap_px = WAREHOUSE_UNSAFE_UNLOAD_GAP_PX
        self.stack_min_persistence_frames = 2

        # Walkway Zone definition in pixel coordinates
        walkway_norm = DEFAULT_ZONES.get("PEDESTRIAN_WALKWAY", {}).get("rect_norm", (0.0, 0.50, 0.40, 0.50))
        self.walkway_rect = (
            int(walkway_norm[0] * frame_width),
            int(walkway_norm[1] * frame_height),
            int(walkway_norm[2] * frame_width),
            int(walkway_norm[3] * frame_height),
        )

        self._last_event_time: Dict[str, float] = {}
        self._event_counter = 1
        self._active_events: List[WarehouseBehaviourEvent] = []
        self._stepping_start: Dict[str, float] = {}
        self._stack_relationship_frames: Dict[Tuple[int, int], int] = {}
        self._stack_tilt_frames: Dict[Tuple[int, int], int] = {}
        self._stable_stack_rest_frames: Dict[Tuple[int, int], int] = {}

    def set_frame_dimensions(self, width: int, height: int) -> None:
        """Dynamically calibrates behaviour thresholds and zones to native video resolution."""
        if width <= 0 or height <= 0:
            return
        self.frame_width = width
        self.frame_height = height
        self.floor_y_threshold = int(height * self.floor_y_threshold_ratio)
        walkway_norm = DEFAULT_ZONES.get("PEDESTRIAN_WALKWAY", {}).get("rect_norm", (0.0, 0.50, 0.40, 0.50))
        self.walkway_rect = (
            int(walkway_norm[0] * width),
            int(walkway_norm[1] * height),
            int(walkway_norm[2] * width),
            int(walkway_norm[3] * height),
        )
        logger.debug(f"[BEHAVIOUR_ENGINE] Calibrated dimensions: {width}x{height}, floor_y={self.floor_y_threshold}")

    def _resolve_handler(
        self,
        product: TrackedEntity,
        person_tracks: Optional[List[TrackedEntity]] = None,
    ) -> Tuple[Optional[int], Optional[Tuple[int, int, int, int]], Optional[TrackedEntity]]:
        """Resolves handler track ID, bounding box, and entity for a product."""
        if not person_tracks:
            return product.associated_person_id, None, None
        if product.associated_person_id:
            h = next((p for p in person_tracks if p.track_id == product.associated_person_id), None)
            if h:
                return h.track_id, h.current_bbox, h
        if product.current_bbox and person_tracks:
            nearest_h = min(person_tracks, key=lambda p: compute_centroid_dist(p.current_bbox, product.current_bbox))
            dist = compute_centroid_dist(nearest_h.current_bbox, product.current_bbox)
            if dist < max(300.0, self.frame_width * 0.40):
                return nearest_h.track_id, nearest_h.current_bbox, nearest_h
        return product.associated_person_id, None, None

    def reset(self) -> None:
        """Resets all temporal event buffers, cooldown timers, and active tracking state."""
        self._last_event_time.clear()
        self._active_events.clear()
        self._stepping_start.clear()
        self._stack_relationship_frames.clear()
        self._stack_tilt_frames.clear()
        self._stable_stack_rest_frames.clear()

    def _generate_event_id(self, behaviour: WarehouseBehaviourType) -> str:
        prefix = "CG"
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        eid = f"{prefix}-{behaviour.name[:4]}-{ts}-{self._event_counter:04d}"
        self._event_counter += 1
        return eid

    def _get_evidence_snapshot(self, prefix: str) -> Optional[str]:
        if self.evidence_callback:
            try:
                return self.evidence_callback(prefix)
            except Exception:
                return None
        return None

    def _build_event_traces(
        self,
        event_id: str,
        behaviour_type: WarehouseBehaviourType,
        risk_level: str,
        video_source: Optional[str],
        product: TrackedEntity,
        person_id: Optional[int],
        start_time: float,
        trigger_time: float,
        trigger_conditions: Dict[str, Any],
        failed_conditions: Optional[Dict[str, Any]] = None,
        extra_kinematics: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """Constructs auditable temporal, kinematic, rule, and debug event traces."""
        start_iso = datetime.fromtimestamp(max(0.0, start_time)).strftime("%Y-%m-%d %H:%M:%S")
        trigger_iso = datetime.fromtimestamp(max(0.0, trigger_time)).strftime("%Y-%m-%d %H:%M:%S")
        dt = max(0.01, trigger_time - start_time)

        temporal_trace = {
            "start_frame": None,
            "trigger_frame": None,
            "end_frame": None,
            "timestamp_start": start_iso,
            "timestamp_trigger": trigger_iso,
            "timestamp_end": trigger_iso,
            "duration_seconds": round(dt, 2),
        }

        curr_state = product.current_state
        kinematics_trace = {
            "product_vx": round(curr_state.velocity[0], 1) if curr_state else 0.0,
            "product_vy": round(curr_state.velocity[1], 1) if curr_state else 0.0,
            "product_speed": round(curr_state.speed, 1) if curr_state else 0.0,
            "product_acceleration": round(curr_state.vertical_accel, 1) if curr_state else 0.0,
            "product_grounded": bool(curr_state.is_grounded) if curr_state else True,
            "product_elevation": round(curr_state.elevation_ratio, 2) if curr_state else 0.0,
            "product_displacement": round(extra_kinematics.get("displacement", 0.0), 1) if extra_kinematics else 0.0,
            "handler_product_distance": round(extra_kinematics.get("handler_distance", 0.0), 1) if extra_kinematics and "handler_distance" in extra_kinematics else None,
            "handler_product_relationship": product.carrying_state or "ISOLATED",
        }
        if extra_kinematics:
            for k, v in extra_kinematics.items():
                if k not in kinematics_trace:
                    kinematics_trace[k] = v

        rule_trace = {
            "trigger_conditions": trigger_conditions,
            "failed_conditions": failed_conditions or {},
            "evaluation_result": True,
        }

        debug_trace = {
            "event_id": event_id,
            "session_id": None,
            "source": video_source or "UNKNOWN",
            "handler_track_id": person_id,
            "product_track_id": product.track_id,
            "relationship": product.carrying_state or "ISOLATED",
            "kinematics": kinematics_trace,
            "trigger_conditions": trigger_conditions,
            "failed_conditions": failed_conditions or {},
            "behaviour": behaviour_type.value,
            "risk": risk_level,
        }

        return temporal_trace, kinematics_trace, rule_trace, debug_trace

    def evaluate_frame(
        self,
        tracks: List[TrackedEntity],
        current_time: Optional[float] = None,
        video_source: Optional[str] = None,
    ) -> List[WarehouseBehaviourEvent]:
        """
        Evaluates all active tracked entities for the 10 target temporal behaviour patterns.
        Returns a list of newly triggered WarehouseBehaviourEvents.
        """
        now = current_time if current_time is not None else time.time()
        new_events: List[WarehouseBehaviourEvent] = []

        product_tracks = [t for t in tracks if t.category == WarehouseObjectCategory.PRODUCT and t.is_confirmed]
        pallet_tracks = [t for t in tracks if t.category == WarehouseObjectCategory.PALLET and t.is_confirmed]
        person_tracks = [t for t in tracks if t.category == WarehouseObjectCategory.PERSON and t.is_confirmed]
        mhe_tracks = [t for t in tracks if t.category == WarehouseObjectCategory.MHE and t.is_confirmed]

        # 1. Evaluate per-product single and sequential behaviours
        for product in product_tracks:
            # Universal Product Event Validation Gate:
            # Must be confirmed product track, plausible confidence (>= 0.25), and have valid spatial bounding box
            if not product.is_confirmed or product.category != WarehouseObjectCategory.PRODUCT:
                continue
            det_conf = product.detection_confidence or product.confidence
            if det_conf < 0.25:
                continue
            if not product.current_bbox:
                continue

            # Behaviour 1: Product Dropped (Evaluated first to prevent falling cartons from false stepping triggers)
            drop_ev = self._check_product_dropped(product, now, video_source, person_tracks=person_tracks)
            if drop_ev:
                new_events.append(drop_ev)
                continue

            # Behaviour: Stepping on Product (Priority 5)
            step_ev = self._check_stepping_on_product(product, person_tracks, now, video_source)
            if step_ev:
                new_events.append(step_ev)
                continue

            # Behaviour 12: Product Kicked / Foot Impact (Evaluated before throw to prevent misclassification)
            kick_ev = self._check_product_kicked(product, person_tracks, now, video_source)
            if kick_ev:
                new_events.append(kick_ev)
                continue

            # Behaviour 9: Material Pushed / Thrown
            throw_ev = self._check_material_pushed_thrown(product, now, video_source, person_tracks=person_tracks)
            if throw_ev:
                new_events.append(throw_ev)
                continue

            # Behaviour 3: Rough Handling / Excessive Impact
            impact_ev = self._check_rough_handling(product, now, video_source, person_tracks=person_tracks)
            if impact_ev:
                new_events.append(impact_ev)
                continue

            # Behaviour 2: Product Dragged
            drag_ev = self._check_product_dragged(product, now, video_source, person_tracks=person_tracks)
            if drag_ev:
                new_events.append(drag_ev)
                continue

            # Behaviour 6: Placed Outside Designated Area (Walkway Obstruction)
            walkway_ev = self._check_placed_outside_designated_area(product, now, video_source, person_tracks=person_tracks)
            if walkway_ev:
                new_events.append(walkway_ev)

            # Behaviour 7: Handled Without Equipment (Heavy Manual Carry)
            no_equip_ev = self._check_handled_without_equipment(product, mhe_tracks, now, video_source, person_tracks=person_tracks)
            if no_equip_ev:
                new_events.append(no_equip_ev)

        # 2. Evaluate Pallet Positioning (Behaviour 8)
        for pallet in pallet_tracks:
            pallet_ev = self._check_pallet_positioned_incorrectly(pallet, now, video_source)
            if pallet_ev:
                new_events.append(pallet_ev)

        # 3. Evaluate Multi-Item Stacking Relationships (Behaviours 4, 5, 10)
        confirmed_products = [p for p in product_tracks if p.is_confirmed]
        stack_events = self._evaluate_stacking_relationships(confirmed_products, now, video_source)
        new_events.extend(stack_events)

        self._active_events.extend(new_events)
        return new_events

    # =========================================================================
    # BEHAVIOUR 11: STEPPING ON PRODUCT
    # =========================================================================

    def _check_stepping_on_product(
        self,
        product: TrackedEntity,
        person_tracks: List[TrackedEntity],
        now: float,
        video_source: Optional[str],
    ) -> Optional[WarehouseBehaviourEvent]:
        """
        Detects operator standing, walking, or placing foot weight directly on top of cartons/packages.
        Criteria:
          1. Product is NOT held/carried at torso height (Hard Carrying Immunity).
          2. Product is genuinely grounded/resting on the floor plane.
          3. Person lower body / feet vertical extent contacts product top surface:
             person_bottom in [box_top - 25, box_top + 0.35 * h_box].
          4. Person torso is strictly above the box (py + 0.65 * ph <= box_top).
          5. Horizontal intersection between person and product bounding boxes >= 20px.
          6. Sustained contact across >= 0.35s (temporal persistence filter).
        """
        if not product.is_confirmed or not product.current_bbox:
            return None

        # HARD IMMUNITY 1: If product is held/carried at torso height, STEPPING is physically impossible
        if product.interaction_state == ProductInteractionState.HELD or product.carrying_state in ("HOLDING", "TOWING"):
            return None
        if product.associated_person_id is not None and not getattr(product.current_state, "is_grounded", False) and product.current_bbox[1] < (self.floor_y_threshold - 60):
            return None

        # HARD IMMUNITY 2: Product must be physically grounded/resting on the floor plane
        is_grounded = (product.current_state and product.current_state.is_grounded) or (product.current_bbox[1] + product.current_bbox[3] >= self.floor_y_threshold - 30) or (product.interaction_state == ProductInteractionState.GROUND_CONTACT)
        if not is_grounded:
            return None

        cooldown_key = f"STEP_{product.track_id}"
        if cooldown_key in self._last_event_time and (now - self._last_event_time[cooldown_key]) < self.cooldown_seconds:
            return None

        bx, by, bw, bh = product.current_bbox
        box_top = by
        box_cy = by + bh / 2.0

        for person in person_tracks:
            if not person.is_confirmed or not person.current_bbox:
                continue

            px, py, pw, ph = person.current_bbox
            person_bottom = py + ph
            person_cy = py + ph / 2.0

            # 1. Vertical alignment: Person body is strictly above product
            if person_cy >= box_cy:
                continue
            is_above_box = (py + 0.65 * ph) <= (box_top + 15)
            if not is_above_box:
                continue

            # 2. Foot contact directly on box top surface
            foot_near_top = (box_top - 25 <= person_bottom <= box_top + max(20.0, 0.35 * bh))
            if not foot_near_top:
                continue

            # 3. Horizontal overlap
            ox1 = max(px, bx)
            ox2 = min(px + pw, bx + bw)
            overlap_w = max(0, ox2 - ox1)
            min_overlap = max(20.0, 0.20 * min(pw, bw))
            if overlap_w < min_overlap:
                continue

            # 4. Temporal persistence check
            pair_key = f"{product.track_id}_{person.track_id}"
            first_contact = self._stepping_start.get(pair_key)
            if first_contact is None:
                self._stepping_start[pair_key] = now
                continue

            duration = now - first_contact
            if duration < 0.35:
                continue

            # Criteria met! Trigger event
            self._last_event_time[cooldown_key] = now
            self._stepping_start.pop(pair_key, None)

            product.interaction_state = ProductInteractionState.STEPPED_ON
            if hasattr(product, "carry_telemetry") and isinstance(product.carry_telemetry, dict):
                product.carry_telemetry["stepping"] = True

            det_conf = round(product.detection_confidence or product.confidence, 3)
            p_conf = round(person.detection_confidence or person.confidence, 3)
            beh_conf = 0.88
            overall_conf = round(0.50 * det_conf + 0.50 * beh_conf, 3)

            sev_info = calculate_risk_severity(
                WarehouseBehaviourType.STEPPING_ON_PRODUCT,
                kinematics={
                    "foot_overlap_px": overlap_w,
                    "duration_s": duration,
                    "person_bottom_y": person_bottom,
                    "box_top_y": box_top,
                },
                confidence=overall_conf,
            )
            risk_level = sev_info["severity"]
            sev_reason = sev_info["severity_reason"]
            sev_factors = sev_info["severity_factors"]

            start_iso = datetime.fromtimestamp(max(0.0, first_contact)).strftime("%Y-%m-%d %H:%M:%S")
            end_iso = datetime.fromtimestamp(max(0.0, now)).strftime("%Y-%m-%d %H:%M:%S")
            event_id = self._generate_event_id(WarehouseBehaviourType.STEPPING_ON_PRODUCT)

            focus_box = compute_interaction_crop_box(
                (self.frame_height, self.frame_width),
                product_track=product,
                person_track=person,
                product_bbox=product.current_bbox,
                person_bbox=person.current_bbox,
                behaviour_type="STEPPING_ON_PRODUCT",
            )

            trig_conds = {
                "foot_contact_surface": f"Person #{person.track_id} feet ({person_bottom}px) on Product #{product.track_id} top ({box_top}px)",
                "horizontal_overlap": f"{overlap_w:.1f} px",
                "duration_sustained": f"{duration:.2f}s (min: 0.35s)",
                "detection_confidence": f"{int(det_conf * 100)}%",
                "handler_confidence": f"{int(p_conf * 100)}%",
            }

            temp_trace, kin_trace, rule_trace, debug_trace = self._build_event_traces(
                event_id=event_id,
                behaviour_type=WarehouseBehaviourType.STEPPING_ON_PRODUCT,
                risk_level=risk_level,
                video_source=video_source,
                product=product,
                person_id=person.track_id,
                start_time=first_contact,
                trigger_time=now,
                trigger_conditions=trig_conds,
                extra_kinematics={
                    "foot_overlap_px": overlap_w,
                    "duration_s": duration,
                },
            )

            return WarehouseBehaviourEvent(
                event_id=event_id,
                behaviour_type=WarehouseBehaviourType.STEPPING_ON_PRODUCT,
                risk_level=risk_level,
                confidence=overall_conf,
                detection_confidence=det_conf,
                behaviour_confidence=beh_conf,
                start_timestamp=start_iso,
                end_timestamp=end_iso,
                duration_seconds=round(duration, 2),
                observed_behaviour=f"Handler #{person.track_id} stepped and stood on top surface of Product #{product.track_id} for {duration:.1f}s.",
                potential_risk="Direct bodily load on corrugated packaging causes carton crushing, structural failure, and damage to packaged goods.",
                recommended_action="Instruct operators to use step stools or access ladders; prohibit stepping or standing directly on packaged merchandise.",
                product_track_id=product.track_id,
                person_track_id=person.track_id,
                product_bbox=product.current_bbox,
                person_bbox=person.current_bbox,
                focus_bbox=focus_box,
                handler_relationship="STEPPING_ON_PRODUCT",
                severity_reason=sev_reason,
                severity_factors=sev_factors,
                evidence_frame_path=self._get_evidence_snapshot("stepping"),
                video_source=video_source,
                temporal_trace=temp_trace,
                kinematics_trace=kin_trace,
                rule_trace=rule_trace,
                debug_trace=debug_trace,
                metadata={
                    "foot_overlap_px": round(overlap_w, 1),
                    "duration_seconds": round(duration, 2),
                    "person_track_id": person.track_id,
                    "product_track_id": product.track_id,
                },
            )

        return None

    # =========================================================================
    # BEHAVIOUR 1: PRODUCT DROPPED
    # =========================================================================

    def _check_product_dropped(
        self,
        product: TrackedEntity,
        now: float,
        video_source: Optional[str],
        person_tracks: Optional[List[TrackedEntity]] = None,
    ) -> Optional[WarehouseBehaviourEvent]:
        cooldown_key = f"DROP_{product.track_id}"
        if cooldown_key in self._last_event_time and (now - self._last_event_time[cooldown_key]) < self.cooldown_seconds:
            return None

        # Drop requires confirmed product track
        if not product.is_confirmed:
            return None

        history = product.get_recent_history(window_seconds=1.8)
        if len(history) < 3:
            return None

        curr_state = history[-1]
        current_y = curr_state.bottom_y

        # Compute apex (highest elevated point / minimum bottom_y) across history window
        min_bottom_y = min(s.bottom_y for s in history)
        apex_index = next((i for i, s in enumerate(history) if s.bottom_y == min_bottom_y), 0)
        total_descent = current_y - min_bottom_y

        # 1. GROUNDED / ROLLING / SLIDING REJECTION:
        # If product has remained continuously at floor level without vertical descent (< 25px),
        # it was never elevated or dropped. It is rolling, sliding, or resting on floor.
        is_continuously_grounded = (total_descent < 25.0) and all(
            (s.bottom_y >= (self.floor_y_threshold - 15) or s.is_grounded) for s in history
        )
        if is_continuously_grounded:
            return None

        # Measure horizontal displacement after the apex
        post_apex_history = history[apex_index:]
        if len(post_apex_history) > 1:
            total_dx = abs(post_apex_history[-1].centroid[0] - post_apex_history[0].centroid[0])
        else:
            total_dx = abs(curr_state.centroid[0] - history[0].centroid[0])

        max_downward_vy = max((s.velocity[1] for s in history), default=0.0)
        max_vx = max((abs(s.velocity[0]) for s in post_apex_history), default=0.0)

        # 2. Reject if product is currently HELD or moving with handler (lowering under control)
        if product.interaction_state == ProductInteractionState.HELD:
            return None
        rel_dy = abs(product.relative_motion[1])
        if product.associated_person_id and rel_dy <= 60.0 and curr_state.speed < 80.0 and not curr_state.is_grounded:
            return None

        # 3. HORIZONTAL TRANSLATION / ROLLING DOMINANCE REJECTION:
        # In pure rolling or dragging without vertical drop, horizontal translation dominates.
        # If significant vertical descent occurred (>= 35px), allow accompanying forward momentum from walking release.
        if total_descent < self.drop_min_displacement_px and total_dx >= 1.25 * max(1.0, total_descent):
            return None
        if max_downward_vy < self.drop_velocity_threshold and max_vx > 1.40 * max(1.0, max_downward_vy):
            return None

        # 4. SEQUENCE CHECK: Was genuinely elevated / airborne prior to descent
        recent_interactions = product.get_recent_interaction_history(8)
        early_history = history[:max(1, len(history) // 2)]
        was_elevated_in_history = any(
            (s.bottom_y < (self.floor_y_threshold - 20) or s.elevation_ratio > 0.08) for s in early_history
        )
        was_held_or_airborne = (
            ProductInteractionState.HELD in recent_interactions
            or ProductInteractionState.AIRBORNE in recent_interactions
            or ProductInteractionState.HELD in getattr(product, "interaction_history", [])
            or getattr(product, "carrying_state", "NONE") in ("HOLDING", "ADJACENT", "TOWING")
            or (product.associated_person_id is not None and (was_elevated_in_history or total_descent >= 35.0))
        )
        if not was_held_or_airborne:
            return None

        # 5. SEPARATION FROM HANDLER:
        is_separated = (
            product.interaction_state in (ProductInteractionState.AIRBORNE, ProductInteractionState.FREE, ProductInteractionState.GROUND_CONTACT)
            or product.associated_person_id is None
            or product.relative_motion[1] > 45.0
            or max_downward_vy >= self.drop_velocity_threshold
        )
        if not is_separated:
            return None

        # 6. DOWNWARD VELOCITY & FREEFALL DISPLACEMENT:
        is_freefall = (max_downward_vy >= self.drop_velocity_threshold) and (total_descent >= self.drop_min_displacement_px)
        if not is_freefall:
            return None

        # 7. GROUND IMPACT & SETTLEMENT:
        hit_ground = (curr_state.bottom_y >= (self.floor_y_threshold - 25)) or (curr_state.is_grounded) or (product.interaction_state == ProductInteractionState.GROUND_CONTACT)
        is_landing_or_stopped = (curr_state.speed < 70.0) or (curr_state.velocity[1] <= max_downward_vy * 0.65) or (curr_state.bottom_y >= min_bottom_y + total_descent * 0.75)

        if not (hit_ground and is_landing_or_stopped):
            return None

        self._last_event_time[cooldown_key] = now
        est_drop_height_m = round((total_descent / max(1, self.frame_height)) * 2.0, 2)
            
        # Compute distinct Detection Confidence vs Behaviour Evidence Confidence
        det_conf = round(product.detection_confidence or product.confidence, 3)
        sep_score = 0.30 if ProductInteractionState.HELD in recent_interactions else 0.25
        desc_score = 0.35 if (max_downward_vy >= self.drop_velocity_threshold * 1.1 and total_descent >= self.drop_min_displacement_px) else 0.25
        impact_score = 0.35 if hit_ground and is_landing_or_stopped else 0.25
        beh_conf = round(min(0.98, max(0.60, sep_score + desc_score + impact_score)), 3)
        overall_conf = round(0.40 * det_conf + 0.60 * beh_conf, 3)

        sev_info = calculate_risk_severity(
            WarehouseBehaviourType.PRODUCT_DROPPED,
            kinematics={"max_downward_vy": max_downward_vy, "displacement": total_descent},
            metadata={"drop_height_m": est_drop_height_m},
            confidence=overall_conf,
        )
        risk_level = sev_info["severity"]
        sev_reason = sev_info["severity_reason"]
        sev_factors = sev_info["severity_factors"]

        start_iso = datetime.fromtimestamp(max(0.0, history[0].timestamp)).strftime("%Y-%m-%d %H:%M:%S")
        end_iso = datetime.fromtimestamp(max(0.0, now)).strftime("%Y-%m-%d %H:%M:%S")
        event_id = self._generate_event_id(WarehouseBehaviourType.PRODUCT_DROPPED)

        h_id, h_bbox, h_track = self._resolve_handler(product, person_tracks)
        focus_box = compute_interaction_crop_box(
            (self.frame_height, self.frame_width),
            product_track=product,
            person_track=h_track,
            product_bbox=product.current_bbox,
            person_bbox=h_bbox,
            behaviour_type="PRODUCT_DROPPED",
        )

        interaction_seq = [s.value if hasattr(s, "value") else str(s) for s in product.get_recent_interaction_history(5)]
        trig_conds = {
            "sequence_verified": "HELD/ELEVATED -> SEPARATED -> AIRBORNE -> GROUND_CONTACT",
            "interaction_sequence": interaction_seq,
            "separated_from_handler": bool(is_separated),
            "downward_velocity": f"{max_downward_vy:.1f} px/s (thresh: {self.drop_velocity_threshold} px/s)",
            "vertical_descent": f"{total_descent:.1f} px (thresh: {self.drop_min_displacement_px} px)",
            "ground_contact": bool(hit_ground),
            "detection_confidence": f"{int(det_conf * 100)}%",
            "behaviour_confidence": f"{int(beh_conf * 100)}%",
        }
        temp_trace, kin_trace, rule_trace, debug_trace = self._build_event_traces(
            event_id=event_id,
            behaviour_type=WarehouseBehaviourType.PRODUCT_DROPPED,
            risk_level=risk_level,
            video_source=video_source,
            product=product,
            person_id=h_id,
            start_time=history[0].timestamp,
            trigger_time=now,
            trigger_conditions=trig_conds,
            extra_kinematics={
                "displacement": total_descent,
                "relative_motion": list(product.relative_motion),
                "detection_confidence": det_conf,
                "behaviour_confidence": beh_conf,
            },
        )

        return WarehouseBehaviourEvent(
            event_id=event_id,
            behaviour_type=WarehouseBehaviourType.PRODUCT_DROPPED,
            risk_level=risk_level,
            confidence=overall_conf,
            detection_confidence=det_conf,
            behaviour_confidence=beh_conf,
            interaction_state_sequence=interaction_seq,
            start_timestamp=start_iso,
            end_timestamp=end_iso,
            duration_seconds=round(history[-1].timestamp - history[0].timestamp, 2),
            observed_behaviour=f"Product Track #{product.track_id} separated from carry/elevation, underwent vertical free-fall descent ({max_downward_vy:.0f} px/s, ~{est_drop_height_m}m drop), and impacted floor at {curr_state.bottom_y}px.",
            potential_risk="Impact deceleration can damage internal product mechanisms and compromise container structural integrity.",
            recommended_action="Inspect the product for possible damage and review the handling sequence; verify packaging integrity before dispatch.",
            product_track_id=product.track_id,
            person_track_id=h_id,
            product_bbox=product.current_bbox,
            person_bbox=h_bbox,
            focus_bbox=focus_box,
            handler_relationship=product.carrying_state or ("HOLDING" if h_id else "ISOLATED"),
            severity_reason=sev_reason,
            severity_factors=sev_factors,
            evidence_frame_path=self._get_evidence_snapshot("event"),
            video_source=video_source,
            temporal_trace=temp_trace,
            kinematics_trace=kin_trace,
            rule_trace=rule_trace,
            debug_trace=debug_trace,
            metadata={
                "drop_height_px": int(total_descent),
                "max_downward_velocity_px_s": round(max_downward_vy, 1),
                "detection_confidence": det_conf,
                "behaviour_confidence": beh_conf,
                "interaction_sequence": interaction_seq,
                "debug_trace": debug_trace,
            },
        )
        return None

    # =========================================================================
    # BEHAVIOUR 2: PRODUCT DRAGGED
    # =========================================================================

    def _check_product_dragged(
        self,
        product: TrackedEntity,
        now: float,
        video_source: Optional[str],
        person_tracks: Optional[List[TrackedEntity]] = None,
    ) -> Optional[WarehouseBehaviourEvent]:
        cooldown_key = f"DRAG_{product.track_id}"
        if cooldown_key in self._last_event_time and (now - self._last_event_time[cooldown_key]) < self.cooldown_seconds:
            return None

        history = product.get_recent_history(window_seconds=2.5)
        if len(history) < 5:
            return None

        grounded_states = [s for s in history if s.bottom_y >= (self.floor_y_threshold - 20) or s.is_grounded]
        if len(grounded_states) < len(history) * 0.75:
            return None

        first_s, last_s = history[0], history[-1]
        dt = max(0.1, last_s.timestamp - first_s.timestamp)
        dx = abs(last_s.centroid[0] - first_s.centroid[0])
        avg_speed = sum(s.speed for s in history) / len(history)

        if dt >= self.drag_min_duration_seconds and dx >= 30.0 and avg_speed >= self.drag_speed_threshold:
            self._last_event_time[cooldown_key] = now
            
            sev_info = calculate_risk_severity(
                WarehouseBehaviourType.PRODUCT_DRAGGED,
                kinematics={"duration": dt, "displacement": dx, "speed": avg_speed},
                confidence=product.confidence,
            )
            risk_level = sev_info["severity"]
            sev_reason = sev_info["severity_reason"]
            sev_factors = sev_info["severity_factors"]

            start_iso = datetime.fromtimestamp(max(0.0, first_s.timestamp)).strftime("%Y-%m-%d %H:%M:%S")
            end_iso = datetime.fromtimestamp(max(0.0, now)).strftime("%Y-%m-%d %H:%M:%S")
            event_id = self._generate_event_id(WarehouseBehaviourType.PRODUCT_DRAGGED)

            h_id, h_bbox, h_track = self._resolve_handler(product, person_tracks)
            focus_box = compute_interaction_crop_box(
                (self.frame_height, self.frame_width),
                product_track=product,
                person_track=h_track,
                product_bbox=product.current_bbox,
                person_bbox=h_bbox,
                behaviour_type="PRODUCT_DRAGGED",
            )

            trig_conds = {
                "grounded": True,
                "horizontal_translation": True,
                "duration": f"{dt:.2f}s (min: {self.drag_min_duration_seconds}s)",
                "displacement": f"{dx:.1f} px (min: 30.0 px)",
                "speed": f"{avg_speed:.1f} px/s (min: {self.drag_speed_threshold} px/s)",
                "trolley": False,
            }
            temp_trace, kin_trace, rule_trace, debug_trace = self._build_event_traces(
                event_id=event_id,
                behaviour_type=WarehouseBehaviourType.PRODUCT_DRAGGED,
                risk_level=risk_level,
                video_source=video_source,
                product=product,
                person_id=h_id,
                start_time=first_s.timestamp,
                trigger_time=now,
                trigger_conditions=trig_conds,
                extra_kinematics={"displacement": dx, "duration": dt},
            )

            return WarehouseBehaviourEvent(
                event_id=event_id,
                behaviour_type=WarehouseBehaviourType.PRODUCT_DRAGGED,
                risk_level=risk_level,
                confidence=min(0.95, max(0.70, product.confidence)),
                start_timestamp=start_iso,
                end_timestamp=end_iso,
                duration_seconds=round(dt, 2),
                observed_behaviour=f"Product Track #{product.track_id} dragged along floor ({dx:.0f}px displacement over {dt:.2f}s) without trolley clearance.",
                potential_risk="Floor dragging causes surface friction abrasion, potentially weakening lower carton seams and exposing contents to moisture or ingress.",
                recommended_action="Deploy hand trolley, pallet jack, or two-person team lift; eliminate unassisted floor dragging across concrete surfaces.",
                product_track_id=product.track_id,
                person_track_id=h_id,
                product_bbox=product.current_bbox,
                person_bbox=h_bbox,
                focus_bbox=focus_box,
                handler_relationship=product.carrying_state or ("TOWING" if h_id else "ISOLATED"),
                severity_reason=sev_reason,
                severity_factors=sev_factors,
                evidence_frame_path=self._get_evidence_snapshot("event"),
                video_source=video_source,
                temporal_trace=temp_trace,
                kinematics_trace=kin_trace,
                rule_trace=rule_trace,
                debug_trace=debug_trace,
                metadata={
                    "drag_distance_px": int(dx),
                    "drag_duration_seconds": round(dt, 2),
                    "debug_trace": debug_trace,
                },
            )
        return None

    # =========================================================================
    # BEHAVIOUR 3: ROUGH HANDLING / EXCESSIVE IMPACT
    # =========================================================================

    def _check_rough_handling(
        self,
        product: TrackedEntity,
        now: float,
        video_source: Optional[str],
        person_tracks: Optional[List[TrackedEntity]] = None,
    ) -> Optional[WarehouseBehaviourEvent]:
        cooldown_key = f"ROUGH_{product.track_id}"
        if cooldown_key in self._last_event_time and (now - self._last_event_time[cooldown_key]) < self.cooldown_seconds:
            return None

        # Touchdown deceleration from a drop is captured by PRODUCT_DROPPED
        drop_key = f"DROP_{product.track_id}"
        if drop_key in self._last_event_time and (now - self._last_event_time[drop_key]) < 2.5:
            return None

        # Must be confirmed track with sufficient history
        if not product.is_confirmed:
            return None

        history = product.get_recent_history(window_seconds=1.2)
        if len(history) < 4:
            return None

        # Find peak prior speed in recent history
        peak_idx = 0
        max_prior_speed = 0.0
        for i, s in enumerate(history[:-1]):
            if s.speed > max_prior_speed:
                max_prior_speed = s.speed
                peak_idx = i

        recent_state = history[-1]
        recent_speed = recent_state.speed
        peak_state = history[peak_idx]

        # HARD IMMUNITY 1: Carried walking motion is normal material handling
        if product.interaction_state == ProductInteractionState.HELD:
            return None
        if product.carrying_state in ("HOLDING", "TOWING"):
            return None
        if product.associated_person_id is not None and product.interaction_state != ProductInteractionState.GROUND_CONTACT:
            # Handler is actively holding/transporting the item - no surface impact
            return None

        # Localization quality and geometric stability protection
        if getattr(product, "localization_quality", 1.0) < 0.60:
            return None
        peak_area = peak_state.bbox[2] * peak_state.bbox[3]
        recent_area = recent_state.bbox[2] * recent_state.bbox[3]
        area_distortion = abs(recent_area - peak_area) / max(1.0, peak_area)
        if area_distortion > 0.50:
            return None

        # Calculate actual physical deceleration over the time between peak and current state
        dt_decel = max(0.05, recent_state.timestamp - peak_state.timestamp)
        decel = (max_prior_speed - recent_speed) / dt_decel

        # Contextual Impact criteria:
        # 1. Surface touchdown (floor, pallet, staging surface) or unheld physical slam
        is_ground_impact = recent_state.is_grounded or any(s.is_grounded for s in history[-3:]) or product.interaction_state == ProductInteractionState.GROUND_CONTACT or (recent_state.bottom_y >= (self.floor_y_threshold - 30))
        is_unheld = product.interaction_state in (ProductInteractionState.FREE, ProductInteractionState.AIRBORNE, ProductInteractionState.GROUND_CONTACT)
        
        if not (is_ground_impact or is_unheld):
            return None

        # Reject normal rolling/sliding friction stops on floor
        is_continuously_grounded = all((s.bottom_y >= (self.floor_y_threshold - 30) or s.is_grounded) for s in history)
        if is_continuously_grounded and decel < 750.0:
            return None

        is_valid_impact = recent_speed <= 35.0 or (max_prior_speed - recent_speed) >= 120.0

        if max_prior_speed >= self.rough_impact_min_speed and decel >= self.rough_impact_decel_threshold and is_valid_impact:
            self._last_event_time[cooldown_key] = now

            det_conf = round(product.detection_confidence or product.confidence, 3)
            beh_conf = round(min(0.95, max(0.65, 0.40 + (decel / 2000.0) * 0.40 + (max_prior_speed / 400.0) * 0.20)), 3)
            overall_conf = round(0.40 * det_conf + 0.60 * beh_conf, 3)

            sev_info = calculate_risk_severity(
                WarehouseBehaviourType.ROUGH_HANDLING,
                kinematics={"deceleration": decel, "peak_speed": max_prior_speed},
                confidence=overall_conf,
            )
            risk_level = sev_info["severity"]
            sev_reason = sev_info["severity_reason"]
            sev_factors = sev_info["severity_factors"]

            start_iso = datetime.fromtimestamp(max(0.0, peak_state.timestamp)).strftime("%Y-%m-%d %H:%M:%S")
            end_iso = datetime.fromtimestamp(max(0.0, now)).strftime("%Y-%m-%d %H:%M:%S")
            event_id = self._generate_event_id(WarehouseBehaviourType.ROUGH_HANDLING)

            h_id, h_bbox, h_track = self._resolve_handler(product, person_tracks)
            focus_box = compute_interaction_crop_box(
                (self.frame_height, self.frame_width),
                product_track=product,
                person_track=h_track,
                product_bbox=product.current_bbox,
                person_bbox=h_bbox,
                behaviour_type="ROUGH_HANDLING",
            )

            interaction_seq = [s.value if hasattr(s, "value") else str(s) for s in product.get_recent_interaction_history(5)]
            trig_conds = {
                "peak_speed": f"{max_prior_speed:.1f} px/s (thresh: {self.rough_impact_min_speed} px/s)",
                "impact_deceleration": f"{decel:.1f} px/s^2 (thresh: {self.rough_impact_decel_threshold} px/s^2)",
                "valid_impact_stop": True,
                "is_ground_impact": bool(is_ground_impact),
                "is_unheld": bool(is_unheld),
                "detection_confidence": f"{int(det_conf * 100)}%",
                "behaviour_confidence": f"{int(beh_conf * 100)}%",
            }
            temp_trace, kin_trace, rule_trace, debug_trace = self._build_event_traces(
                event_id=event_id,
                behaviour_type=WarehouseBehaviourType.ROUGH_HANDLING,
                risk_level=risk_level,
                video_source=video_source,
                product=product,
                person_id=h_id,
                start_time=peak_state.timestamp,
                trigger_time=now,
                trigger_conditions=trig_conds,
                extra_kinematics={
                    "deceleration": decel,
                    "peak_speed": max_prior_speed,
                    "detection_confidence": det_conf,
                    "behaviour_confidence": beh_conf,
                },
            )

            return WarehouseBehaviourEvent(
                event_id=event_id,
                behaviour_type=WarehouseBehaviourType.ROUGH_HANDLING,
                risk_level=risk_level,
                confidence=overall_conf,
                detection_confidence=det_conf,
                behaviour_confidence=beh_conf,
                interaction_state_sequence=interaction_seq,
                start_timestamp=start_iso,
                end_timestamp=end_iso,
                duration_seconds=round(recent_state.timestamp - peak_state.timestamp, 2),
                observed_behaviour=f"Product Track #{product.track_id} experienced sharp impact deceleration ({decel:.0f} px/s^2) upon touchdown/contact from initial velocity of {max_prior_speed:.0f} px/s.",
                potential_risk="Abrupt impact generates kinetic shock that may damage sensitive internal mechanisms or compromise packaging integrity.",
                recommended_action="Exercise controlled deceleration during set-down; stage items onto impact-absorbing staging mats or pallets.",
                product_track_id=product.track_id,
                person_track_id=h_id,
                product_bbox=product.current_bbox,
                person_bbox=h_bbox,
                focus_bbox=focus_box,
                handler_relationship=product.carrying_state or ("HOLDING" if h_id else "ISOLATED"),
                severity_reason=sev_reason,
                severity_factors=sev_factors,
                evidence_frame_path=self._get_evidence_snapshot("event"),
                video_source=video_source,
                temporal_trace=temp_trace,
                kinematics_trace=kin_trace,
                rule_trace=rule_trace,
                debug_trace=debug_trace,
                metadata={
                    "impact_deceleration_px_s2": round(decel, 1),
                    "prior_speed_px_s": round(max_prior_speed, 1),
                    "detection_confidence": det_conf,
                    "behaviour_confidence": beh_conf,
                    "interaction_sequence": interaction_seq,
                    "debug_trace": debug_trace,
                },
            )
        return None

    # =========================================================================
    # BEHAVIOUR 6: PLACED OUTSIDE DESIGNATED AREA (WALKWAY OBSTRUCTION)
    # =========================================================================

    def _check_placed_outside_designated_area(
        self,
        product: TrackedEntity,
        now: float,
        video_source: Optional[str],
        person_tracks: Optional[List[TrackedEntity]] = None,
    ) -> Optional[WarehouseBehaviourEvent]:
        cooldown_key = f"WALKWAY_{product.track_id}"
        if cooldown_key in self._last_event_time and (now - self._last_event_time[cooldown_key]) < self.cooldown_seconds:
            return None

        # Check if centroid is inside walkway rectangle
        cx, cy = product.current_bbox[0] + product.current_bbox[2] / 2.0, product.current_bbox[1] + product.current_bbox[3] / 2.0
        wx, wy, ww, wh = self.walkway_rect

        is_in_walkway = (wx <= cx <= wx + ww) and (wy <= cy <= wy + wh)
        if not is_in_walkway:
            return None

        # Check if stationary inside walkway
        history = product.get_recent_history(window_seconds=self.walkway_dwell_seconds + 0.5)
        if len(history) < 4:
            return None

        dt = history[-1].timestamp - history[0].timestamp
        avg_speed = sum(s.speed for s in history) / len(history)

        if dt >= self.walkway_dwell_seconds and avg_speed < 12.0:
            self._last_event_time[cooldown_key] = now

            sev_info = calculate_risk_severity(
                WarehouseBehaviourType.PLACED_OUTSIDE_DESIGNATED_AREA,
                kinematics={"dwell_time": dt, "avg_speed": avg_speed},
                confidence=product.confidence,
            )
            risk_level = sev_info["severity"]
            sev_reason = sev_info["severity_reason"]
            sev_factors = sev_info["severity_factors"]

            start_iso = datetime.fromtimestamp(max(0.0, history[0].timestamp)).strftime("%Y-%m-%d %H:%M:%S")
            end_iso = datetime.fromtimestamp(max(0.0, now)).strftime("%Y-%m-%d %H:%M:%S")
            event_id = self._generate_event_id(WarehouseBehaviourType.PLACED_OUTSIDE_DESIGNATED_AREA)

            h_id, h_bbox, h_track = self._resolve_handler(product, person_tracks)
            focus_box = compute_interaction_crop_box(
                (self.frame_height, self.frame_width),
                product_track=product,
                person_track=h_track,
                product_bbox=product.current_bbox,
                person_bbox=h_bbox,
                behaviour_type="PLACED_OUTSIDE_DESIGNATED_AREA",
            )

            trig_conds = {
                "in_walkway_zone": True,
                "walkway_rect": list(self.walkway_rect),
                "dwell_duration": f"{dt:.2f}s (thresh: {self.walkway_dwell_seconds:.1f}s)",
                "avg_speed": f"{avg_speed:.1f} px/s (stationary thresh: <12.0 px/s)",
            }
            temp_trace, kin_trace, rule_trace, debug_trace = self._build_event_traces(
                event_id=event_id,
                behaviour_type=WarehouseBehaviourType.PLACED_OUTSIDE_DESIGNATED_AREA,
                risk_level=risk_level,
                video_source=video_source,
                product=product,
                person_id=h_id,
                start_time=history[0].timestamp,
                trigger_time=now,
                trigger_conditions=trig_conds,
                extra_kinematics={"dwell_time": dt, "avg_speed": avg_speed},
            )

            return WarehouseBehaviourEvent(
                event_id=event_id,
                behaviour_type=WarehouseBehaviourType.PLACED_OUTSIDE_DESIGNATED_AREA,
                risk_level=risk_level,
                confidence=min(0.95, max(0.70, product.confidence)),
                start_timestamp=start_iso,
                end_timestamp=end_iso,
                duration_seconds=round(dt, 2),
                observed_behaviour=f"Product Track #{product.track_id} left stationary ({dt:.1f}s dwell) inside pedestrian walkway transit corridor.",
                potential_risk="Transit pathway obstruction creates tripping hazards and increases collision risk with personnel or mobile warehouse machinery.",
                recommended_action="Relocate package immediately to demarcated staging bays or pallet racking; maintain designated walkway clearance.",
                product_track_id=product.track_id,
                person_track_id=h_id,
                product_bbox=product.current_bbox,
                person_bbox=h_bbox,
                focus_bbox=focus_box,
                handler_relationship=product.carrying_state or ("HOLDING" if h_id else "ISOLATED"),
                severity_reason=sev_reason,
                severity_factors=sev_factors,
                evidence_frame_path=self._get_evidence_snapshot("event"),
                video_source=video_source,
                temporal_trace=temp_trace,
                kinematics_trace=kin_trace,
                rule_trace=rule_trace,
                debug_trace=debug_trace,
                metadata={"dwell_seconds": round(dt, 1), "zone": "PEDESTRIAN_WALKWAY", "debug_trace": debug_trace},
            )
        return None

    # =========================================================================
    # BEHAVIOUR 7: HANDLED WITHOUT REQUIRED EQUIPMENT (HEAVY MANUAL CARRY)
    # =========================================================================

    def _check_handled_without_equipment(
        self,
        product: TrackedEntity,
        mhe_tracks: List[TrackedEntity],
        now: float,
        video_source: Optional[str],
        person_tracks: Optional[List[TrackedEntity]] = None,
    ) -> Optional[WarehouseBehaviourEvent]:
        cooldown_key = f"NO_EQUIP_{product.track_id}"
        if cooldown_key in self._last_event_time and (now - self._last_event_time[cooldown_key]) < self.cooldown_seconds:
            return None

        # Check if cargo area is large (bulky/heavy)
        area_px = product.current_bbox[2] * product.current_bbox[3]
        if area_px < self.heavy_cargo_area_px or product.carrying_state not in ("HOLDING", "TOWING"):
            return None

        history = product.get_recent_history(window_seconds=2.0)
        if len(history) < 4:
            return None

        dx = abs(history[-1].centroid[0] - history[0].centroid[0])
        dy = abs(history[-1].centroid[1] - history[0].centroid[1])
        dist = math.sqrt(dx * dx + dy * dy)

        # Check if any MHE (trolley/forklift) is in close proximity
        has_nearby_mhe = any(
            math.sqrt((m.current_bbox[0] - product.current_bbox[0])**2 + (m.current_bbox[1] - product.current_bbox[1])**2) < 180.0
            for m in mhe_tracks
        )

        if dist >= self.manual_carry_distance_px and not has_nearby_mhe:
            self._last_event_time[cooldown_key] = now

            sev_info = calculate_risk_severity(
                WarehouseBehaviourType.HANDLED_WITHOUT_EQUIPMENT,
                kinematics={"displacement": dist, "cargo_area": area_px},
                confidence=product.confidence,
            )
            risk_level = sev_info["severity"]
            sev_reason = sev_info["severity_reason"]
            sev_factors = sev_info["severity_factors"]

            start_iso = datetime.fromtimestamp(max(0.0, history[0].timestamp)).strftime("%Y-%m-%d %H:%M:%S")
            end_iso = datetime.fromtimestamp(max(0.0, now)).strftime("%Y-%m-%d %H:%M:%S")
            event_id = self._generate_event_id(WarehouseBehaviourType.HANDLED_WITHOUT_EQUIPMENT)

            h_id, h_bbox, h_track = self._resolve_handler(product, person_tracks)
            focus_box = compute_interaction_crop_box(
                (self.frame_height, self.frame_width),
                product_track=product,
                person_track=h_track,
                product_bbox=product.current_bbox,
                person_bbox=h_bbox,
                behaviour_type="HANDLED_WITHOUT_EQUIPMENT",
            )

            trig_conds = {
                "cargo_area": f"{area_px} px^2 (thresh: {self.heavy_cargo_area_px} px^2)",
                "manual_carry_distance": f"{dist:.1f} px (thresh: {self.manual_carry_distance_px} px)",
                "carrying_state": product.carrying_state,
                "nearby_mhe": False,
            }
            temp_trace, kin_trace, rule_trace, debug_trace = self._build_event_traces(
                event_id=event_id,
                behaviour_type=WarehouseBehaviourType.HANDLED_WITHOUT_EQUIPMENT,
                risk_level=risk_level,
                video_source=video_source,
                product=product,
                person_id=h_id,
                start_time=history[0].timestamp,
                trigger_time=now,
                trigger_conditions=trig_conds,
                extra_kinematics={"displacement": dist, "cargo_area": area_px},
            )

            return WarehouseBehaviourEvent(
                event_id=event_id,
                behaviour_type=WarehouseBehaviourType.HANDLED_WITHOUT_EQUIPMENT,
                risk_level=risk_level,
                confidence=min(0.95, max(0.70, product.confidence)),
                start_timestamp=start_iso,
                end_timestamp=end_iso,
                duration_seconds=round(history[-1].timestamp - history[0].timestamp, 2),
                observed_behaviour=f"Large cargo (Track #{product.track_id}, area: {area_px}px^2) transported manually {dist:.0f}px without mechanical handling equipment.",
                potential_risk="Extended manual carry of bulky loads increases worker ergonomic fatigue and risk of accidental drop.",
                recommended_action="Utilize hand truck, platform trolley, or team lifting protocol for bulky product transport.",
                product_track_id=product.track_id,
                person_track_id=h_id,
                product_bbox=product.current_bbox,
                person_bbox=h_bbox,
                focus_bbox=focus_box,
                handler_relationship=product.carrying_state or ("HOLDING" if h_id else "ISOLATED"),
                severity_reason=sev_reason,
                severity_factors=sev_factors,
                evidence_frame_path=self._get_evidence_snapshot("event"),
                video_source=video_source,
                temporal_trace=temp_trace,
                kinematics_trace=kin_trace,
                rule_trace=rule_trace,
                debug_trace=debug_trace,
                metadata={"package_area_px": area_px, "carry_distance_px": round(dist, 1), "debug_trace": debug_trace},
            )
        return None

    # =========================================================================
    # BEHAVIOUR 8: PALLET POSITIONED INCORRECTLY
    # =========================================================================

    def _check_pallet_positioned_incorrectly(
        self,
        pallet: TrackedEntity,
        now: float,
        video_source: Optional[str],
    ) -> Optional[WarehouseBehaviourEvent]:
        cooldown_key = f"PALLET_{pallet.track_id}"
        if cooldown_key in self._last_event_time and (now - self._last_event_time[cooldown_key]) < self.cooldown_seconds:
            return None

        # Check if pallet overlaps with walkway boundary line (protrusion)
        px, py, pw, ph = pallet.current_bbox
        wx, wy, ww, wh = self.walkway_rect

        overlap_x = max(0, min(px + pw, wx + ww) - max(px, wx))
        overlap_y = max(0, min(py + ph, wy + wh) - max(py, wy))

        if overlap_x > self.pallet_protrusion_px and overlap_y > 20:
            self._last_event_time[cooldown_key] = now

            sev_info = calculate_risk_severity(
                WarehouseBehaviourType.PALLET_POSITIONED_INCORRECTLY,
                kinematics={"protrusion_px": overlap_x},
                confidence=pallet.confidence,
            )
            risk_level = sev_info["severity"]
            sev_reason = sev_info["severity_reason"]
            sev_factors = sev_info["severity_factors"]

            start_iso = datetime.fromtimestamp(max(0.0, now)).strftime("%Y-%m-%d %H:%M:%S")
            end_iso = start_iso
            event_id = self._generate_event_id(WarehouseBehaviourType.PALLET_POSITIONED_INCORRECTLY)

            focus_box = compute_interaction_crop_box(
                (self.frame_height, self.frame_width),
                product_track=pallet,
                product_bbox=pallet.current_bbox,
                behaviour_type="PALLET_POSITIONED_INCORRECTLY",
            )

            trig_conds = {
                "protrusion_x": f"{overlap_x} px (thresh: {self.pallet_protrusion_px} px)",
                "overlap_y": f"{overlap_y} px",
                "pallet_bbox": list(pallet.current_bbox),
                "walkway_rect": list(self.walkway_rect),
            }
            temp_trace, kin_trace, rule_trace, debug_trace = self._build_event_traces(
                event_id=event_id,
                behaviour_type=WarehouseBehaviourType.PALLET_POSITIONED_INCORRECTLY,
                risk_level=risk_level,
                video_source=video_source,
                product=pallet,
                person_id=None,
                start_time=now,
                trigger_time=now,
                trigger_conditions=trig_conds,
                extra_kinematics={"protrusion_px": overlap_x},
            )

            return WarehouseBehaviourEvent(
                event_id=event_id,
                behaviour_type=WarehouseBehaviourType.PALLET_POSITIONED_INCORRECTLY,
                risk_level=risk_level,
                confidence=min(0.95, max(0.70, pallet.confidence)),
                start_timestamp=start_iso,
                end_timestamp=end_iso,
                duration_seconds=1.0,
                observed_behaviour=f"Pallet (Track #{pallet.track_id}) positioned misaligned, protruding {overlap_x}px into active transit aisle.",
                potential_risk="Protrusion into transit lanes exposes pallet corners to MHE impact and creates pedestrian snag hazard.",
                recommended_action="Re-align pallet squarely within painted bay markings to preserve lane clearance.",
                product_track_id=pallet.track_id,
                person_track_id=None,
                product_bbox=pallet.current_bbox,
                person_bbox=None,
                focus_bbox=focus_box,
                handler_relationship="ISOLATED",
                severity_reason=sev_reason,
                severity_factors=sev_factors,
                evidence_frame_path=self._get_evidence_snapshot("event"),
                video_source=video_source,
                temporal_trace=temp_trace,
                kinematics_trace=kin_trace,
                rule_trace=rule_trace,
                debug_trace=debug_trace,
                metadata={"protrusion_px": overlap_x, "debug_trace": debug_trace},
            )
        return None

    # =========================================================================
    # BEHAVIOUR 12: PRODUCT KICKED / FOOT IMPACT
    # =========================================================================

    def _check_product_kicked(
        self,
        product: TrackedEntity,
        person_tracks: Optional[List[TrackedEntity]],
        now: float,
        video_source: Optional[str],
    ) -> Optional[WarehouseBehaviourEvent]:
        cooldown_key = f"KICK_{product.track_id}"
        if cooldown_key in self._last_event_time and (now - self._last_event_time[cooldown_key]) < self.cooldown_seconds:
            return None

        if not product.is_confirmed:
            return None

        # ---------------------------------------------------------------------
        # PREREQUISITE 2: CARRYING IMMUNITY (HELD / CARRYING STATE CANNOT BE KICKED)
        # ---------------------------------------------------------------------
        if product.interaction_state == ProductInteractionState.HELD or product.carrying_state in ("HOLDING", "TOWING"):
            return None
        if getattr(product, "interaction_source", None) == "HAND_INTERACTION":
            return None
        if product.associated_person_id is not None and not (product.current_state and product.current_state.is_grounded):
            return None

        history = product.get_recent_history(window_seconds=1.5)
        if len(history) < 2:
            return None

        curr_s = history[-1]
        vx = abs(curr_s.velocity[0])
        speed = curr_s.speed

        # ---------------------------------------------------------------------
        # PREREQUISITE 1: PRE-IMPACT RESTING / GROUNDED STATE
        # Product must have had a stationary resting phase on floor (v < 35 px/s)
        # ---------------------------------------------------------------------
        is_near_floor = curr_s.is_grounded or curr_s.bottom_y >= (self.floor_y_threshold - 30)
        if not is_near_floor:
            return None

        prior_states = history[:-1]
        had_resting_phase = any(
            s.speed < 35.0 and (s.is_grounded or s.bottom_y >= (self.floor_y_threshold - 30))
            for s in prior_states
        )
        if not had_resting_phase:
            return None

        # ---------------------------------------------------------------------
        # PREREQUISITE 4: ACCELERATION / IMPULSE SPIKE (Delta v >= 45 px/s from rest/contact)
        # ---------------------------------------------------------------------
        min_prior_speed = min(s.speed for s in prior_states)
        delta_v = speed - min_prior_speed
        max_inter_frame_accel = max(
            abs(history[k].speed - history[k - 1].speed)
            for k in range(1, len(history))
        )
        if delta_v < 40.0 and max_inter_frame_accel < 35.0:
            return None

        # Kick speed threshold: horizontal impulse along floor (must be horizontal motion, not vertical free-fall)
        kick_speed_thresh = 45.0
        if vx < kick_speed_thresh or vx < abs(curr_s.velocity[1]):
            return None

        # ---------------------------------------------------------------------
        # PREREQUISITE 3: FOOT APPROACH & CONTACT SEQUENCE
        # ---------------------------------------------------------------------
        h_id, h_bbox, h_track = self._resolve_handler(product, person_tracks)
        is_foot_contact = False
        foot_dist = 9999.0

        if h_track:
            hx, hy, hw, hh = h_track.current_bbox
            # Reject if product is actually in upper torso region of this person
            pr_cy = product.current_bbox[1] + product.current_bbox[3] / 2.0
            if pr_cy < (hy + 0.60 * hh):
                return None

            foot_y = hy + int(hh * 0.65)
            foot_bbox = (hx, foot_y, hw, int(hh * 0.35))
            foot_dist = compute_bbox_min_dist(foot_bbox, product.current_bbox)
            if foot_dist <= 110.0 or product.interaction_source == "FOOT_INTERACTION":
                is_foot_contact = True
        elif product.interaction_source == "FOOT_INTERACTION":
            is_foot_contact = True

        if not is_foot_contact:
            return None

        # ---------------------------------------------------------------------
        # PREREQUISITE 5: POST-IMPACT SEPARATION & CONFIRMATION
        # ---------------------------------------------------------------------
        self._last_event_time[cooldown_key] = now

        det_conf = round(product.detection_confidence or product.confidence, 3)
        beh_conf = round(min(0.96, max(0.72, 0.55 + (delta_v / 200.0) * 0.40)), 3)
        overall_conf = round(0.40 * det_conf + 0.60 * beh_conf, 3)

        sev_info = calculate_risk_severity(
            WarehouseBehaviourType.PRODUCT_KICKED,
            kinematics={"horizontal_velocity": vx, "speed": speed, "foot_distance": foot_dist, "impulse_delta_v": delta_v},
            confidence=overall_conf,
        )
        risk_level = sev_info["severity"]
        sev_reason = sev_info["severity_reason"]
        sev_factors = sev_info["severity_factors"]

        start_iso = datetime.fromtimestamp(max(0.0, history[0].timestamp)).strftime("%Y-%m-%d %H:%M:%S")
        end_iso = datetime.fromtimestamp(max(0.0, now)).strftime("%Y-%m-%d %H:%M:%S")
        event_id = self._generate_event_id(WarehouseBehaviourType.PRODUCT_KICKED)

        # Frozen participant bounding boxes at event trigger
        frozen_prod_bbox = product.current_bbox
        frozen_person_bbox = h_bbox or (h_track.current_bbox if h_track else None)

        focus_box = compute_interaction_crop_box(
            (self.frame_height, self.frame_width),
            product_track=product,
            person_track=h_track,
            product_bbox=frozen_prod_bbox,
            person_bbox=frozen_person_bbox,
            behaviour_type="PRODUCT_KICKED",
        )

        trig_conds = {
            "kick_speed": f"{speed:.1f} px/s (thresh: {kick_speed_thresh} px/s)",
            "impulse_delta_v": f"{delta_v:.1f} px/s (min: 40.0 px/s)",
            "pre_impact_resting": had_resting_phase,
            "carrying_immune": False,
            "foot_proximity": f"{foot_dist:.1f} px",
            "interaction_source": "FOOT_INTERACTION",
            "near_floor": is_near_floor,
            "detection_confidence": f"{int(det_conf * 100)}%",
            "behaviour_confidence": f"{int(beh_conf * 100)}%",
        }
        temp_trace, kin_trace, rule_trace, debug_trace = self._build_event_traces(
            event_id=event_id,
            behaviour_type=WarehouseBehaviourType.PRODUCT_KICKED,
            risk_level=risk_level,
            video_source=video_source,
            product=product,
            person_id=h_id,
            start_time=history[0].timestamp,
            trigger_time=now,
            trigger_conditions=trig_conds,
            extra_kinematics={
                "kick_speed": speed,
                "horizontal_velocity": vx,
                "impulse_delta_v": delta_v,
                "foot_distance": foot_dist,
            },
        )

        return WarehouseBehaviourEvent(
            event_id=event_id,
            behaviour_type=WarehouseBehaviourType.PRODUCT_KICKED,
            risk_level=risk_level,
            confidence=overall_conf,
            detection_confidence=det_conf,
            behaviour_confidence=beh_conf,
            interaction_source="FOOT_INTERACTION",
            start_timestamp=start_iso,
            end_timestamp=end_iso,
            duration_seconds=round(history[-1].timestamp - history[0].timestamp, 2),
            observed_behaviour=f"Product Track #{product.track_id} kicked / impacted by handler's foot across the floor at {speed:.0f} px/s (impulse Delta v: {delta_v:.0f} px/s).",
            potential_risk="Kinetic foot impact creates localized crushing of carton walls, seam bursting, and internal product component damage.",
            recommended_action="Prohibit kicking or nudging cargo with feet; mandate manual lifting or MHE transport for all pallet and carton movements.",
            product_track_id=product.track_id,
            person_track_id=h_id,
            product_bbox=frozen_prod_bbox,
            person_bbox=frozen_person_bbox,
            focus_bbox=focus_box,
            handler_relationship="FOOT_INTERACTION",
            severity_reason=sev_reason,
            severity_factors=sev_factors,
            evidence_frame_path=self._get_evidence_snapshot("event"),
            video_source=video_source,
            temporal_trace=temp_trace,
            kinematics_trace=kin_trace,
            rule_trace=rule_trace,
            debug_trace=debug_trace,
            metadata={
                "kick_speed": round(speed, 1),
                "horizontal_velocity": round(vx, 1),
                "impulse_delta_v": round(delta_v, 1),
                "foot_distance": round(foot_dist, 1),
            },
        )

    # =========================================================================
    # BEHAVIOUR 9: MATERIAL PUSHED / THROWN
    # =========================================================================

    def _check_material_pushed_thrown(
        self,
        product: TrackedEntity,
        now: float,
        video_source: Optional[str],
        person_tracks: Optional[List[TrackedEntity]] = None,
    ) -> Optional[WarehouseBehaviourEvent]:
        cooldown_key = f"THROW_{product.track_id}"
        if cooldown_key in self._last_event_time and (now - self._last_event_time[cooldown_key]) < self.cooldown_seconds:
            return None

        # Reject kick / foot interaction immediately from throw
        if getattr(product, "interaction_source", None) == "FOOT_INTERACTION":
            return None

        # If any handler is in foot proximity/contact with product below mid-body, this is a kick, NOT a throw
        if person_tracks and product.current_bbox:
            for p in person_tracks:
                if p.is_confirmed and p.current_bbox:
                    px, py, pw, ph = p.current_bbox
                    foot_y = py + int(ph * 0.55)
                    foot_bbox = (px, foot_y, pw, int(ph * 0.45))
                    dist_to_foot = compute_bbox_min_dist(foot_bbox, product.current_bbox)
                    prod_cy = product.current_bbox[1] + product.current_bbox[3] / 2.0
                    if dist_to_foot <= 110.0 and prod_cy >= (py + 0.55 * ph):
                        return None

        # Must be confirmed track with solid confidence (>= 0.35 required for critical throw event)
        if not product.is_confirmed:
            return None
        det_conf = round(product.detection_confidence or product.confidence, 3)
        if det_conf < 0.35:
            return None

        history = product.get_recent_history(window_seconds=1.0)
        if len(history) < 3:
            return None

        curr_s = history[-1]
        vx = abs(curr_s.velocity[0])
        vy = curr_s.velocity[1]

        # In flight: strictly not on or near floor (not grounded), elevated, high horizontal velocity dominating vertical velocity
        is_on_floor = curr_s.is_grounded or curr_s.bottom_y >= (self.floor_y_threshold - 15)
        is_horizontal_dominant = (vx >= self.throw_velocity_threshold) and (vx >= 1.25 * abs(vy))
        is_unsupported_flight = not is_on_floor and curr_s.elevation_ratio > 0.08

        # Reject ceiling/top-of-frame noise artifact (unless handler is elevated at that height)
        h_id, h_bbox, h_track = self._resolve_handler(product, person_tracks)
        if curr_s.bottom_y < 0.28 * self.frame_height:
            if not h_track or h_track.current_bbox[1] > 0.30 * self.frame_height:
                return None

        # Trajectory continuity check: reject teleportation jumps across frames (>180px in 1 frame)
        has_teleportation_jump = any(
            compute_centroid_dist(history[k].bbox, history[k - 1].bbox) > 180.0
            for k in range(1, len(history))
        )
        if has_teleportation_jump:
            return None

        # If product is currently HELD with small relative speed, it's carried, NOT thrown
        if product.interaction_state == ProductInteractionState.HELD and product.relative_motion[2] <= 80.0:
            return None

        if is_horizontal_dominant and is_unsupported_flight:
            product.interaction_state = ProductInteractionState.AIRBORNE
            self._last_event_time[cooldown_key] = now

            det_conf = round(product.detection_confidence or product.confidence, 3)
            beh_conf = round(min(0.96, max(0.70, 0.50 + (vx / 400.0) * 0.45)), 3)
            overall_conf = round(0.40 * det_conf + 0.60 * beh_conf, 3)

            sev_info = calculate_risk_severity(
                WarehouseBehaviourType.MATERIAL_PUSHED_THROWN,
                kinematics={"horizontal_velocity": vx, "speed": curr_s.speed, "product_grounded": False},
                confidence=overall_conf,
            )
            risk_level = sev_info["severity"]
            sev_reason = sev_info["severity_reason"]
            sev_factors = sev_info["severity_factors"]

            start_iso = datetime.fromtimestamp(max(0.0, history[0].timestamp)).strftime("%Y-%m-%d %H:%M:%S")
            end_iso = datetime.fromtimestamp(max(0.0, now)).strftime("%Y-%m-%d %H:%M:%S")
            event_id = self._generate_event_id(WarehouseBehaviourType.MATERIAL_PUSHED_THROWN)

            h_id, h_bbox, h_track = self._resolve_handler(product, person_tracks)
            focus_box = compute_interaction_crop_box(
                (self.frame_height, self.frame_width),
                product_track=product,
                person_track=h_track,
                product_bbox=product.current_bbox,
                person_bbox=h_bbox,
                behaviour_type="MATERIAL_PUSHED_THROWN",
            )

            interaction_seq = [s.value if hasattr(s, "value") else str(s) for s in product.get_recent_interaction_history(5)]
            trig_conds = {
                "horizontal_velocity": f"{vx:.1f} px/s (thresh: {self.throw_velocity_threshold} px/s)",
                "horizontal_dominance": f"Vx ({vx:.1f}) >= 1.25 * |Vy| ({abs(vy):.1f})",
                "in_flight": not is_on_floor,
                "elevation_ratio": f"{curr_s.elevation_ratio:.2f} (>0.08)",
                "is_grounded": False,
                "detection_confidence": f"{int(det_conf * 100)}%",
                "behaviour_confidence": f"{int(beh_conf * 100)}%",
            }
            temp_trace, kin_trace, rule_trace, debug_trace = self._build_event_traces(
                event_id=event_id,
                behaviour_type=WarehouseBehaviourType.MATERIAL_PUSHED_THROWN,
                risk_level=risk_level,
                video_source=video_source,
                product=product,
                person_id=h_id,
                start_time=history[0].timestamp,
                trigger_time=now,
                trigger_conditions=trig_conds,
                extra_kinematics={
                    "horizontal_velocity": vx,
                    "speed": curr_s.speed,
                    "detection_confidence": det_conf,
                    "behaviour_confidence": beh_conf,
                },
            )

            return WarehouseBehaviourEvent(
                event_id=event_id,
                behaviour_type=WarehouseBehaviourType.MATERIAL_PUSHED_THROWN,
                risk_level=risk_level,
                confidence=overall_conf,
                detection_confidence=det_conf,
                behaviour_confidence=beh_conf,
                interaction_state_sequence=interaction_seq,
                start_timestamp=start_iso,
                end_timestamp=end_iso,
                duration_seconds=round(history[-1].timestamp - history[0].timestamp, 2),
                observed_behaviour=f"Product Track #{product.track_id} thrown/launched horizontally through the air at {vx:.0f} px/s in unsupported trajectory.",
                potential_risk="Uncontrolled trajectory may lead to high-energy impact, product internal component damage, or worker injury from airborne items.",
                recommended_action="Ensure continuous manual support during transfer; enforce zero-throwing safety standards across staging areas.",
                product_track_id=product.track_id,
                person_track_id=h_id,
                product_bbox=product.current_bbox,
                person_bbox=h_bbox,
                focus_bbox=focus_box,
                handler_relationship=product.carrying_state or ("RELEASED" if h_id else "ISOLATED"),
                severity_reason=sev_reason,
                severity_factors=sev_factors,
                evidence_frame_path=self._get_evidence_snapshot("event"),
                video_source=video_source,
                temporal_trace=temp_trace,
                kinematics_trace=kin_trace,
                rule_trace=rule_trace,
                debug_trace=debug_trace,
                metadata={
                    "horizontal_velocity_px_s": round(vx, 1),
                    "speed_px_s": round(curr_s.speed, 1),
                    "detection_confidence": det_conf,
                    "behaviour_confidence": beh_conf,
                    "interaction_sequence": interaction_seq,
                    "debug_trace": debug_trace,
                },
            )
        return None

    # =========================================================================
    # MULTI-ITEM STACKING: BEHAVIOURS 4, 5, 10
    # =========================================================================

    def _establish_stack_context(
        self,
        top: TrackedEntity,
        bot: TrackedEntity,
    ) -> bool:
        """
        Hard prerequisite for evaluating stacking behaviours (Behaviours 4 & 5).
        Returns True ONLY when:
          1. Both entities are confirmed product tracks.
          2. Neither product is airborne, in free-fall, or being thrown.
          3. Neither product is being carried / held in active motion.
          4. Both products are in low-speed/quasi-static state (speed <= 95 px/s).
          5. Relative speed between products is low (rel_speed <= 60 px/s).
          6. Spatial vertical contact: top touches bot top-edge within tolerance (gap_y <= 35),
             top is above bot, and horizontal overlap >= 40% of min item width.
          7. Temporal persistence: stack contact sustained for >= stack_min_persistence_frames (default 2).
        """
        pair_key = (top.track_id, bot.track_id)

        if not top.is_confirmed or not bot.is_confirmed:
            self._stack_relationship_frames[pair_key] = 0
            self._stack_tilt_frames[pair_key] = 0
            return False

        # Exclude airborne / flying / free-fall items
        if top.interaction_state == ProductInteractionState.AIRBORNE or bot.interaction_state == ProductInteractionState.AIRBORNE:
            self._stack_relationship_frames[pair_key] = 0
            self._stack_tilt_frames[pair_key] = 0
            return False

        # Exclude items being actively carried / held in motion
        if top.interaction_state == ProductInteractionState.HELD and top.current_state and top.current_state.speed > 35.0:
            self._stack_relationship_frames[pair_key] = 0
            self._stack_tilt_frames[pair_key] = 0
            return False
        if bot.interaction_state == ProductInteractionState.HELD and bot.current_state and bot.current_state.speed > 35.0:
            self._stack_relationship_frames[pair_key] = 0
            self._stack_tilt_frames[pair_key] = 0
            return False

        top_s = top.current_state.speed if top.current_state else 0.0
        bot_s = bot.current_state.speed if bot.current_state else 0.0
        if top_s > 95.0 or bot_s > 95.0:
            self._stack_relationship_frames[pair_key] = 0
            self._stack_tilt_frames[pair_key] = 0
            return False

        if top.current_state and bot.current_state:
            vx_diff = top.current_state.velocity[0] - bot.current_state.velocity[0]
            vy_diff = top.current_state.velocity[1] - bot.current_state.velocity[1]
            rel_speed = (vx_diff ** 2 + vy_diff ** 2) ** 0.5
            if rel_speed > 60.0:
                self._stack_relationship_frames[pair_key] = 0
                self._stack_tilt_frames[pair_key] = 0
                return False

        top_b = top.current_bbox
        bot_b = bot.current_bbox
        if not top_b or not bot_b:
            self._stack_relationship_frames[pair_key] = 0
            self._stack_tilt_frames[pair_key] = 0
            return False

        # Top item must be vertically above bottom item
        if top_b[1] >= bot_b[1]:
            self._stack_relationship_frames[pair_key] = 0
            self._stack_tilt_frames[pair_key] = 0
            return False

        top_bottom_y = top_b[1] + top_b[3]
        bot_top_y = bot_b[1]
        gap_y = abs(top_bottom_y - bot_top_y)
        if gap_y > 35:
            self._stack_relationship_frames[pair_key] = 0
            self._stack_tilt_frames[pair_key] = 0
            return False

        x_overlap = max(0, min(top_b[0] + top_b[2], bot_b[0] + bot_b[2]) - max(top_b[0], bot_b[0]))
        min_w = min(top_b[2], bot_b[2])
        if min_w <= 0 or x_overlap < (min_w * 0.40):
            self._stack_relationship_frames[pair_key] = 0
            self._stack_tilt_frames[pair_key] = 0
            return False

        # Temporal persistence
        frames = self._stack_relationship_frames.get(pair_key, 0) + 1
        self._stack_relationship_frames[pair_key] = frames
        return frames >= self.stack_min_persistence_frames

    def _evaluate_stacking_relationships(
        self,
        products: List[TrackedEntity],
        now: float,
        video_source: Optional[str],
    ) -> List[WarehouseBehaviourEvent]:
        """Evaluates pairwise vertical stacking for Incorrect Stacking, Unstable Stacking, and Unsafe Unloading."""
        events: List[WarehouseBehaviourEvent] = []
        if len(products) < 2:
            return events

        for i in range(len(products)):
            for j in range(len(products)):
                if i == j:
                    continue
                top = products[i]
                bot = products[j]

                top_b = top.current_bbox
                bot_b = bot.current_bbox
                if not top_b or not bot_b:
                    continue

                top_bottom_y = top_b[1] + top_b[3]
                bot_top_y = bot_b[1]
                gap_y = abs(top_bottom_y - bot_top_y)

                # Horizontal alignment overlap
                x_overlap = max(0, min(top_b[0] + top_b[2], bot_b[0] + bot_b[2]) - max(top_b[0], bot_b[0]))
                min_w = min(top_b[2], bot_b[2])

                combined_x = min(top_b[0], bot_b[0])
                combined_y = min(top_b[1], bot_b[1])
                combined_w = max(top_b[0] + top_b[2], bot_b[0] + bot_b[2]) - combined_x
                combined_h = max(top_b[1] + top_b[3], bot_b[1] + bot_b[3]) - combined_y
                stack_bbox = (combined_x, combined_y, combined_w, combined_h)

                pair_key = (top.track_id, bot.track_id)
                top_speed = top.current_state.speed if top.current_state else 0.0
                bot_speed = bot.current_state.speed if bot.current_state else 0.0

                # Track confirmed resting stack configuration history
                is_vertically_stacked = (top_b[1] < bot_b[1]) and (gap_y <= 35) and (min_w > 0 and x_overlap >= min_w * 0.35)
                is_resting_together = is_vertically_stacked and (top_speed < 20.0) and (bot_speed < 20.0) and (
                    top.interaction_state != ProductInteractionState.AIRBORNE and
                    bot.interaction_state != ProductInteractionState.AIRBORNE
                )
                if is_resting_together:
                    self._stable_stack_rest_frames[pair_key] = self._stable_stack_rest_frames.get(pair_key, 0) + 1
                elif gap_y > 80 or x_overlap <= 0:
                    self._stable_stack_rest_frames[pair_key] = 0

                # -------------------------------------------------------------
                # BEHAVIOUR 10: UNSAFE LOADING / UNLOADING SEQUENCE
                # -------------------------------------------------------------
                # Strict multi-object requirement:
                # 1. (top, bot) MUST have a validated resting stack history (>= 2 frames at rest together)
                # 2. Bottom box is extracted/pulled away (speed >= 30 px/s with handler interaction)
                # 3. Upper box remained overhead (top_speed < 20 px/s)
                prior_rest_frames = self._stable_stack_rest_frames.get(pair_key, 0)
                is_extraction_motion = (bot_speed >= 30.0) and (
                    bot.carrying_state in ("HOLDING", "TOWING") or bot.associated_person_id is not None
                )
                is_upper_overhead = (top_speed < 20.0) and (top_b[1] < bot_b[1])
                has_stable_stack_history = prior_rest_frames >= 2

                if has_stable_stack_history and is_extraction_motion and is_upper_overhead and (gap_y <= 60) and (x_overlap >= min_w * 0.15):
                    cooldown_key_10 = f"UNSAFE_UNLOAD_{top.track_id}_{bot.track_id}"
                    if cooldown_key_10 not in self._last_event_time or (now - self._last_event_time[cooldown_key_10]) >= self.cooldown_seconds:
                        self._last_event_time[cooldown_key_10] = now
                        self._stable_stack_rest_frames[pair_key] = 0

                        sev_info_10 = calculate_risk_severity(
                            WarehouseBehaviourType.UNSAFE_LOADING_SEQUENCE,
                            kinematics={"bot_speed": bot_speed, "top_speed": top_speed, "prior_rest_frames": prior_rest_frames},
                            confidence=bot.confidence,
                        )
                        risk_level_10 = sev_info_10["severity"]
                        sev_reason_10 = sev_info_10["severity_reason"]
                        sev_factors_10 = sev_info_10["severity_factors"]

                        event_id_10 = self._generate_event_id(WarehouseBehaviourType.UNSAFE_LOADING_SEQUENCE)
                        focus_box_10 = compute_interaction_crop_box(
                            (self.frame_height, self.frame_width),
                            product_track=bot,
                            product_bbox=stack_bbox,
                            behaviour_type="UNSAFE_LOADING_SEQUENCE",
                        )

                        trig_conds_10 = {
                            "bot_speed": f"{bot_speed:.1f} px/s (thresh: 30 px/s)",
                            "top_speed": f"{top_speed:.1f} px/s (overhead thresh: <20 px/s)",
                            "carrying_state": bot.carrying_state,
                            "prior_rest_stack_frames": prior_rest_frames,
                        }
                        temp_trace, kin_trace, rule_trace, debug_trace = self._build_event_traces(
                            event_id=event_id_10,
                            behaviour_type=WarehouseBehaviourType.UNSAFE_LOADING_SEQUENCE,
                            risk_level=risk_level_10,
                            video_source=video_source,
                            product=bot,
                            person_id=bot.associated_person_id,
                            start_time=now,
                            trigger_time=now,
                            trigger_conditions=trig_conds_10,
                            extra_kinematics={"bot_speed": bot_speed, "top_speed": top_speed, "prior_rest_frames": prior_rest_frames},
                        )

                        events.append(WarehouseBehaviourEvent(
                            event_id=event_id_10,
                            behaviour_type=WarehouseBehaviourType.UNSAFE_LOADING_SEQUENCE,
                            risk_level=risk_level_10,
                            confidence=min(0.95, max(0.70, bot.confidence)),
                            start_timestamp=datetime.fromtimestamp(max(0.0, now)).strftime("%Y-%m-%d %H:%M:%S"),
                            end_timestamp=datetime.fromtimestamp(max(0.0, now)).strftime("%Y-%m-%d %H:%M:%S"),
                            duration_seconds=1.0,
                            observed_behaviour=f"Base package #{bot.track_id} pulled from stack while upper package #{top.track_id} remained overhead.",
                            potential_risk="Removal of foundational support risks abrupt, uncontrolled freefall of elevated items.",
                            recommended_action="De-stack packages strictly top-to-bottom; never extract lower supporting units first.",
                            product_track_id=bot.track_id,
                            person_track_id=bot.associated_person_id,
                            product_bbox=bot.current_bbox,
                            person_bbox=top.current_bbox,
                            focus_bbox=focus_box_10,
                            handler_relationship="DISLODGED_STACK",
                            severity_reason=sev_reason_10,
                            severity_factors=sev_factors_10,
                            evidence_frame_path=self._get_evidence_snapshot("event"),
                            video_source=video_source,
                            temporal_trace=temp_trace,
                            kinematics_trace=kin_trace,
                            rule_trace=rule_trace,
                            debug_trace=debug_trace,
                            metadata={"bot_speed_px_s": round(bot_speed, 1), "debug_trace": debug_trace},
                        ))

                # -------------------------------------------------------------
                # HARD PREREQUISITE: STACK_CONTEXT for Behaviour 4 & 5
                # -------------------------------------------------------------
                if not self._establish_stack_context(top, bot):
                    continue

                pair_key = (top.track_id, bot.track_id)

                # -------------------------------------------------------------
                # BEHAVIOUR 4: INCORRECT STACKING (Heavy on light / Overhang)
                # -------------------------------------------------------------
                top_area = top_b[2] * top_b[3]
                bot_area = bot_b[2] * bot_b[3]
                overhang_px = max(0, (top_b[0] + top_b[2]) - (bot_b[0] + bot_b[2])) + max(0, bot_b[0] - top_b[0])

                cooldown_key_4 = f"INC_STACK_{top.track_id}_{bot.track_id}"
                if (top_area >= bot_area * self.incorrect_stack_area_ratio or overhang_px >= bot_b[2] * self.incorrect_stack_overhang_ratio):
                    if cooldown_key_4 not in self._last_event_time or (now - self._last_event_time[cooldown_key_4]) >= self.cooldown_seconds:
                        self._last_event_time[cooldown_key_4] = now

                        sev_info_4 = calculate_risk_severity(
                            WarehouseBehaviourType.INCORRECT_STACKING,
                            kinematics={"top_area": top_area, "bot_area": bot_area, "overhang_px": overhang_px},
                            confidence=top.confidence,
                        )
                        risk_level_4 = sev_info_4["severity"]
                        sev_reason_4 = sev_info_4["severity_reason"]
                        sev_factors_4 = sev_info_4["severity_factors"]

                        event_id_4 = self._generate_event_id(WarehouseBehaviourType.INCORRECT_STACKING)
                        focus_box_4 = compute_interaction_crop_box(
                            (self.frame_height, self.frame_width),
                            product_track=top,
                            product_bbox=stack_bbox,
                            behaviour_type="INCORRECT_STACKING",
                        )

                        trig_conds_4 = {
                            "stack_context": True,
                            "top_area": top_area,
                            "bot_area": bot_area,
                            "overhang_px": overhang_px,
                            "area_ratio": round(top_area / max(1, bot_area), 2),
                        }
                        temp_trace, kin_trace, rule_trace, debug_trace = self._build_event_traces(
                            event_id=event_id_4,
                            behaviour_type=WarehouseBehaviourType.INCORRECT_STACKING,
                            risk_level=risk_level_4,
                            video_source=video_source,
                            product=top,
                            person_id=top.associated_person_id,
                            start_time=now,
                            trigger_time=now,
                            trigger_conditions=trig_conds_4,
                            extra_kinematics={"top_area": top_area, "bot_area": bot_area, "overhang_px": overhang_px},
                        )

                        events.append(WarehouseBehaviourEvent(
                            event_id=event_id_4,
                            behaviour_type=WarehouseBehaviourType.INCORRECT_STACKING,
                            risk_level=risk_level_4,
                            confidence=min(0.95, max(0.70, top.confidence)),
                            start_timestamp=datetime.fromtimestamp(max(0.0, now)).strftime("%Y-%m-%d %H:%M:%S"),
                            end_timestamp=datetime.fromtimestamp(max(0.0, now)).strftime("%Y-%m-%d %H:%M:%S"),
                            duration_seconds=1.0,
                            observed_behaviour=f"Larger package #{top.track_id} (area: {top_area}px^2) stacked on top of smaller base package #{bot.track_id} (area: {bot_area}px^2).",
                            potential_risk="Disproportionate top-weight may crush lower container walls, resulting in structural collapse.",
                            recommended_action="Restack column with heaviest and widest base items at the bottom.",
                            product_track_id=top.track_id,
                            person_track_id=top.associated_person_id,
                            product_bbox=top.current_bbox,
                            person_bbox=bot.current_bbox,
                            focus_bbox=focus_box_4,
                            handler_relationship="STACKED",
                            severity_reason=sev_reason_4,
                            severity_factors=sev_factors_4,
                            evidence_frame_path=self._get_evidence_snapshot("event"),
                            video_source=video_source,
                            temporal_trace=temp_trace,
                            kinematics_trace=kin_trace,
                            rule_trace=rule_trace,
                            debug_trace=debug_trace,
                            metadata={"stack_context": True, "top_area": top_area, "bot_area": bot_area, "overhang_px": overhang_px, "debug_trace": debug_trace},
                        ))

                # -------------------------------------------------------------
                # BEHAVIOUR 5: UNSTABLE STACKING (Leaning / Tilt)
                # -------------------------------------------------------------
                top_cx = top_b[0] + top_b[2] / 2.0
                bot_cx = bot_b[0] + bot_b[2] / 2.0
                tilt_offset = abs(top_cx - bot_cx)

                cooldown_key_5 = f"UNSTABLE_STACK_{top.track_id}_{bot.track_id}"
                if tilt_offset >= self.unstable_stack_tilt_px:
                    if cooldown_key_5 not in self._last_event_time or (now - self._last_event_time[cooldown_key_5]) >= self.cooldown_seconds:
                        self._last_event_time[cooldown_key_5] = now

                        sev_info_5 = calculate_risk_severity(
                            WarehouseBehaviourType.UNSTABLE_STACKING,
                            kinematics={"tilt_offset_px": tilt_offset},
                            confidence=top.confidence,
                        )
                        risk_level_5 = sev_info_5["severity"]
                        sev_reason_5 = sev_info_5["severity_reason"]
                        sev_factors_5 = sev_info_5["severity_factors"]

                        event_id_5 = self._generate_event_id(WarehouseBehaviourType.UNSTABLE_STACKING)
                        focus_box_5 = compute_interaction_crop_box(
                            (self.frame_height, self.frame_width),
                            product_track=top,
                            product_bbox=stack_bbox,
                            behaviour_type="UNSTABLE_STACKING",
                        )

                        trig_conds_5 = {
                            "stack_context": True,
                            "base_product_id": bot.track_id,
                            "upper_product_id": top.track_id,
                            "tilt_offset_px": round(tilt_offset, 1),
                            "tilt_threshold": self.unstable_stack_tilt_px,
                            "persistent_frames": self._stack_tilt_frames.get(pair_key, 0),
                        }
                        temp_trace, kin_trace, rule_trace, debug_trace = self._build_event_traces(
                            event_id=event_id_5,
                            behaviour_type=WarehouseBehaviourType.UNSTABLE_STACKING,
                            risk_level=risk_level_5,
                            video_source=video_source,
                            product=top,
                            person_id=top.associated_person_id,
                            start_time=now,
                            trigger_time=now,
                            trigger_conditions=trig_conds_5,
                            extra_kinematics={"tilt_offset_px": tilt_offset},
                        )

                        events.append(WarehouseBehaviourEvent(
                            event_id=event_id_5,
                            behaviour_type=WarehouseBehaviourType.UNSTABLE_STACKING,
                            risk_level=risk_level_5,
                            confidence=min(0.95, max(0.70, top.confidence)),
                            start_timestamp=datetime.fromtimestamp(max(0.0, now)).strftime("%Y-%m-%d %H:%M:%S"),
                            end_timestamp=datetime.fromtimestamp(max(0.0, now)).strftime("%Y-%m-%d %H:%M:%S"),
                            duration_seconds=1.0,
                            observed_behaviour=f"Stack column tilting with {tilt_offset:.0f}px lateral center offset between upper package #{top.track_id} and base #{bot.track_id}.",
                            potential_risk="Center-of-gravity misalignment creates tipping instability, risking column toppling.",
                            recommended_action="Re-align and straighten stack column immediately; interlock stacked layers.",
                            product_track_id=top.track_id,
                            person_track_id=top.associated_person_id,
                            product_bbox=top.current_bbox,
                            person_bbox=bot.current_bbox,
                            focus_bbox=focus_box_5,
                            handler_relationship="STACKED",
                            severity_reason=sev_reason_5,
                            severity_factors=sev_factors_5,
                            evidence_frame_path=self._get_evidence_snapshot("event"),
                            video_source=video_source,
                            temporal_trace=temp_trace,
                            kinematics_trace=kin_trace,
                            rule_trace=rule_trace,
                            debug_trace=debug_trace,
                            metadata={"stack_context": True, "base_product_id": bot.track_id, "upper_product_id": top.track_id, "tilt_offset_px": round(tilt_offset, 1), "debug_trace": debug_trace},
                        ))

        return events
