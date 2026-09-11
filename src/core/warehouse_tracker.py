"""
Godrej AI Video Intelligence for Warehouse Handling - Object Tracker
---------------------------------------------------------------------
Multi-object tracking engine providing:
- Persistent, stable track IDs across video frames
- Warehouse category aliasing (Person, Product/Carton, Pallet, MHE/Trolley)
- Kinematic calculations (velocity vectors, vertical acceleration, floor elevation)
- Person-to-Product spatial association and holding/towing state classification
"""

import logging
import math
import time
from typing import Dict, Any, List, Optional, Tuple

import numpy as np

from src.core.warehouse_models import (
    WarehouseObjectCategory,
    ProductInteractionState,
    KinematicState,
    TrackedEntity,
)
from src.core.warehouse_class_mapper import (
    WarehouseClassMapper,
    PRODUCT_LABELS,
    PERSON_LABELS,
    PALLET_LABELS,
    MHE_LABELS,
)
from config import (
    WAREHOUSE_FLOOR_Y_RATIO,
    WAREHOUSE_PERSON_CONF_THRESHOLD,
    WAREHOUSE_PRODUCT_CONF_THRESHOLD,
    WAREHOUSE_PALLET_CONF_THRESHOLD,
    WAREHOUSE_MHE_CONF_THRESHOLD,
    WAREHOUSE_OTHER_CONF_THRESHOLD,
    WAREHOUSE_TRACK_MAX_MISSED_FRAMES,
    WAREHOUSE_TRACK_MAX_AGE_SECONDS,
)
from src.core.interfaces.detector_interface import DetectedObject

logger = logging.getLogger("GodrejWarehouse.Tracker")

# Backward-compatible category map reference
WAREHOUSE_CATEGORY_MAP = {
    "person": WarehouseObjectCategory.PERSON,
    "human": WarehouseObjectCategory.PERSON,
    "worker": WarehouseObjectCategory.PERSON,
    "operator": WarehouseObjectCategory.PERSON,
    "handler": WarehouseObjectCategory.PERSON,
    
    # Products / Cartons / Packages
    "carton": WarehouseObjectCategory.PRODUCT,
    "box": WarehouseObjectCategory.PRODUCT,
    "product": WarehouseObjectCategory.PRODUCT,
    "package": WarehouseObjectCategory.PRODUCT,
    "parcel": WarehouseObjectCategory.PRODUCT,
    "cargo": WarehouseObjectCategory.PRODUCT,
    "crate": WarehouseObjectCategory.PRODUCT,
    "cardboard_box": WarehouseObjectCategory.PRODUCT,
    
    # Pallets
    "pallet": WarehouseObjectCategory.PALLET,
    "wooden_pallet": WarehouseObjectCategory.PALLET,
    "plastic_pallet": WarehouseObjectCategory.PALLET,
    
    # Material Handling Equipment
    "trolley": WarehouseObjectCategory.MHE,
    "mhe": WarehouseObjectCategory.MHE,
    "forklift": WarehouseObjectCategory.MHE,
    "pallet_jack": WarehouseObjectCategory.MHE,
    "hand_truck": WarehouseObjectCategory.MHE,
    "reach_truck": WarehouseObjectCategory.MHE,
    "stacker": WarehouseObjectCategory.MHE,
    "cart": WarehouseObjectCategory.MHE,
    "bopt": WarehouseObjectCategory.MHE,
    "tow_tractor": WarehouseObjectCategory.MHE,
    "truck": WarehouseObjectCategory.MHE,
}


def compute_iou(box1: Tuple[int, int, int, int], box2: Tuple[int, int, int, int]) -> float:
    """Calculates Intersection-over-Union between two (x, y, w, h) bounding boxes."""
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2

    xi1 = max(x1, x2)
    yi1 = max(y1, y2)
    xi2 = min(x1 + w1, x2 + w2)
    yi2 = min(y1 + h1, y2 + h2)

    inter_w = max(0, xi2 - xi1)
    inter_h = max(0, yi2 - yi1)
    inter_area = inter_w * inter_h

    union_area = (w1 * h1) + (w2 * h2) - inter_area
    if union_area <= 0:
        return 0.0
    return float(inter_area / union_area)


def compute_centroid_dist(box1: Tuple[int, int, int, int], box2: Tuple[int, int, int, int]) -> float:
    """Calculates Euclidean distance between centers of two boxes."""
    c1x = box1[0] + box1[2] / 2.0
    c1y = box1[1] + box1[3] / 2.0
    c2x = box2[0] + box2[2] / 2.0
    c2y = box2[1] + box2[3] / 2.0
    return math.sqrt((c1x - c2x) ** 2 + (c1y - c2y) ** 2)


def compute_bbox_min_dist(box1: Tuple[int, int, int, int], box2: Tuple[int, int, int, int]) -> float:
    """Calculates minimum Euclidean distance between the boundaries of two (x, y, w, h) boxes (0.0 if overlapping)."""
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2

    r1_x2, r1_y2 = x1 + w1, y1 + h1
    r2_x2, r2_y2 = x2 + w2, y2 + h2

    dx = max(0, max(x1, x2) - min(r1_x2, r2_x2))
    dy = max(0, max(y1, y2) - min(r1_y2, r2_y2))
    return math.sqrt(dx * dx + dy * dy)


class WarehouseObjectTracker:
    """
    Maintains persistent multi-object tracking and kinematic state histories
    for warehouse video streams.
    """

    def __init__(
        self,
        frame_width: int = 640,
        frame_height: int = 480,
        confirmation_frames: int = 2,
        max_missed_frames: int = WAREHOUSE_TRACK_MAX_MISSED_FRAMES,
        max_track_age_seconds: float = WAREHOUSE_TRACK_MAX_AGE_SECONDS,
        iou_match_threshold: float = 0.25,
        max_dist_px: float = 120.0,
        floor_y_threshold_ratio: float = WAREHOUSE_FLOOR_Y_RATIO,
        history_window_seconds: float = 5.0,
        class_mapper: Optional[WarehouseClassMapper] = None,
    ):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.confirmation_frames = confirmation_frames
        self.max_missed_frames = max_missed_frames
        self.max_track_age_seconds = max_track_age_seconds
        self.iou_match_threshold = iou_match_threshold
        self.max_dist_px = max_dist_px
        self.floor_y_threshold_ratio = floor_y_threshold_ratio
        self.floor_y_threshold = int(frame_height * floor_y_threshold_ratio)
        self.history_window_seconds = history_window_seconds
        self.class_mapper = class_mapper or WarehouseClassMapper(
            person_conf_threshold=WAREHOUSE_PERSON_CONF_THRESHOLD,
            product_conf_threshold=WAREHOUSE_PRODUCT_CONF_THRESHOLD,
            pallet_conf_threshold=WAREHOUSE_PALLET_CONF_THRESHOLD,
            mhe_conf_threshold=WAREHOUSE_MHE_CONF_THRESHOLD,
            other_conf_threshold=WAREHOUSE_OTHER_CONF_THRESHOLD,
        )

        self._next_track_id = 1
        self._tracks: Dict[int, TrackedEntity] = {}

    def set_frame_dimensions(self, width: int, height: int) -> None:
        """Dynamically calibrates tracker coordinate space and thresholds to native video resolution."""
        if width <= 0 or height <= 0:
            return
        self.frame_width = width
        self.frame_height = height
        self.floor_y_threshold = int(height * self.floor_y_threshold_ratio)
        scale = width / 640.0
        self.max_dist_px = max(120.0, 120.0 * scale)
        logger.debug(f"[TRACKER] Calibrated dimensions: {width}x{height}, floor_y={self.floor_y_threshold}, max_dist_px={self.max_dist_px:.1f}")

    @property
    def active_tracks(self) -> List[TrackedEntity]:
        """Returns all currently active and confirmed tracks."""
        return [t for t in self._tracks.values() if t.is_confirmed and t.missed_frames == 0]

    @property
    def all_tracks(self) -> List[TrackedEntity]:
        """Returns all tracked entities in memory."""
        return list(self._tracks.values())

    def reset(self) -> None:
        """Clears all track states."""
        self._tracks.clear()
        self._next_track_id = 1

    def map_category(self, label: str) -> WarehouseObjectCategory:
        """Maps an object detection label to a canonical warehouse category."""
        return self.class_mapper.map_category(label)

    def update(
        self,
        detections: List[Any],
        current_time: Optional[float] = None,
    ) -> List[TrackedEntity]:
        """
        Ingests raw detections for the current frame, associates them with existing
        tracks, updates kinematic states, and associates person-product interactions.
        """
        now = current_time if current_time is not None else time.time()

        # Deduplicate overlapping detections per category and apply person-product geometric validation
        norm_dets: List[DetectedObject] = []
        for det in (detections or []):
            if isinstance(det, DetectedObject):
                norm_dets.append(det)
            elif isinstance(det, dict):
                norm_dets.append(DetectedObject(
                    class_id=int(det.get("class_id", 0)),
                    label=str(det.get("label", det.get("class_name", "product"))),
                    confidence=float(det.get("confidence", 0.5)),
                    bbox=tuple(det.get("bbox", (0, 0, 10, 10))),
                ))
            elif hasattr(det, "bbox") and hasattr(det, "label"):
                norm_dets.append(DetectedObject(
                    class_id=int(getattr(det, "class_id", 0)),
                    label=str(det.label),
                    confidence=float(getattr(det, "confidence", 0.5)),
                    bbox=tuple(det.bbox),
                ))

        deduped: List[DetectedObject] = []
        norm_dets.sort(key=lambda d: d.confidence, reverse=True)
        for d in norm_dets:
            # Enforce category-specific minimum confidence threshold
            if not self.class_mapper.is_valid_confidence(d.label, d.confidence):
                continue
            cat = self.map_category(d.label)
            overlap = False
            for keep in deduped:
                if self.map_category(keep.label) == cat:
                    iou = compute_iou(d.bbox, keep.bbox)
                    dist = compute_centroid_dist(d.bbox, keep.bbox)
                    # Suppress duplicate person boxes
                    if cat == WarehouseObjectCategory.PERSON and (iou > 0.35 or dist < 45.0):
                        overlap = True
                        break
                    # For products, preserve adjacent or stacked cartons (only suppress if nearly identical duplicate)
                    elif cat == WarehouseObjectCategory.PRODUCT:
                        if iou > 0.75 and dist < 25.0:
                            overlap = True
                            break
                    elif iou > 0.60:
                        overlap = True
                        break
            if not overlap:
                deduped.append(d)

        # Product Geometric and Contextual Validation (Filter background structures, trucks, dock doors, extreme aspect ratios)
        valid_detections: List[DetectedObject] = []
        person_dets = [d for d in deduped if self.map_category(d.label) == WarehouseObjectCategory.PERSON]
        frame_area = max(1, self.frame_width * self.frame_height)

        for d in deduped:
            cat = self.map_category(d.label)
            if cat == WarehouseObjectCategory.PRODUCT:
                dx, dy, dw, dh = d.bbox
                d_area = dw * dh
                area_ratio = d_area / frame_area
                aspect = dw / max(1.0, dh)

                # Check if this detection is already associated with an established confirmed moving track
                is_existing_confirmed_track = any(
                    t.category == WarehouseObjectCategory.PRODUCT and t.is_confirmed and compute_iou(t.current_bbox, d.bbox) > 0.25
                    for t in self._tracks.values()
                )

                # 0. Reject ceiling / top-of-frame background noise (upper 28% of the frame)
                # A true product is never floating in the upper 28% of frame unless directly held by a person reaching up,
                # or continuing an established confirmed moving track.
                is_held_at_top = any(
                    (p.bbox[1] <= dy + dh <= p.bbox[1] + 0.70 * p.bbox[3]) and compute_bbox_min_dist(d.bbox, p.bbox) <= 70.0
                    for p in person_dets
                ) if person_dets else False
                if (dy + dh < 0.28 * self.frame_height or (dy + dh / 2.0) < 0.25 * self.frame_height) and not is_held_at_top and not is_existing_confirmed_track:
                    logger.debug(f"[TRACKER] Filtered top-of-frame background candidate (cy={dy+dh/2.0:.1f}, conf={d.confidence:.2f}): {d.bbox}")
                    continue

                # 1. Reject giant background structures (e.g. whole dock doors, trucks, trailers, walls)
                # A true product carton rarely exceeds 18% of frame area or 60% of frame width
                if (area_ratio > 0.18 or dw > 0.60 * self.frame_width or dh > 0.65 * self.frame_height) and not is_existing_confirmed_track:
                    logger.debug(f"[TRACKER] Filtered oversized background product candidate ({dw}x{dh}, {area_ratio*100:.1f}% frame): {d.bbox}")
                    continue

                # 2. Reject extreme aspect ratios (e.g. thin horizontal floor strips or vertical door frames)
                if (aspect < 0.22 or aspect > 4.5) and not is_existing_confirmed_track:
                    logger.debug(f"[TRACKER] Filtered product candidate with extreme aspect ratio ({aspect:.2f}): {d.bbox}")
                    continue

                # 3. Contextual Confidence Validation:
                # Isolated static product candidates (far from any person > 120px and far from any existing/candidate product > 80px)
                # require higher confidence (>= 0.35) to prevent false background/ceiling/road noise triggers.
                is_near_person = any(
                    compute_bbox_min_dist(d.bbox, p.bbox) <= 120.0 for p in person_dets
                ) if person_dets else False

                is_near_product_track = any(
                    t.category == WarehouseObjectCategory.PRODUCT and compute_bbox_min_dist(d.bbox, t.current_bbox) <= 100.0
                    for t in self._tracks.values()
                )

                is_near_other_product_det = any(
                    self.map_category(other.label) == WarehouseObjectCategory.PRODUCT and other is not d and compute_bbox_min_dist(d.bbox, other.bbox) <= 100.0
                    for other in deduped
                )

                if not is_near_person and not is_near_product_track and not is_near_other_product_det and not is_existing_confirmed_track:
                    if d.confidence < 0.35:
                        logger.debug(f"[TRACKER] Filtered low-confidence isolated product candidate (conf={d.confidence:.2f} < 0.35): {d.bbox}")
                        continue

            # Person-Product Geometric Overlap Validation (Reject suspicious false product boxes)
            if cat == WarehouseObjectCategory.PRODUCT and person_dets:
                cx = d.bbox[0] + d.bbox[2] / 2.0
                cy = d.bbox[1] + d.bbox[3] / 2.0
                d_area = d.bbox[2] * d.bbox[3]
                suspicious = False

                for p in person_dets:
                    px, py, pw, ph = p.bbox
                    p_area = pw * ph
                    iou_with_person = compute_iou(d.bbox, p.bbox)

                    # Compute intersection with person bounding box
                    ix1 = max(d.bbox[0], px)
                    iy1 = max(d.bbox[1], py)
                    ix2 = min(d.bbox[0] + d.bbox[2], px + pw)
                    iy2 = min(d.bbox[1] + d.bbox[3], py + ph)
                    inter_w = max(0, ix2 - ix1)
                    inter_h = max(0, iy2 - iy1)
                    inter_area = inter_w * inter_h
                    fraction_in_person = inter_area / max(1.0, d_area)

                    # 1. Reject product bbox centered on person head/face region
                    if (px <= cx <= px + pw) and (cy < py + 0.22 * ph) and ph >= 70:
                        if iou_with_person > 0.12 or d_area < p_area * 0.25:
                            suspicious = True
                            logger.debug(f"[TRACKER] Filtered suspicious product detection on person head/face: {d.bbox}")
                            break

                    # 2. Reject product bbox covering almost the entire person body (duplicate detector artifact)
                    if iou_with_person > 0.65 or (d_area > 0.80 * p_area and compute_centroid_dist(d.bbox, p.bbox) < 35.0):
                        suspicious = True
                        logger.debug(f"[TRACKER] Filtered duplicate product box covering entire person body: {d.bbox}")
                        break

                    # 3. Suppress false product detections located on person's body/torso/legs when:
                    #    - The box is heavily inside the person silhouette (fraction_in_person > 0.80)
                    #    - AND there is an established product track elsewhere (e.g. on floor, or being held)
                    #    - AND this detection does NOT match an established held track at this location
                    has_other_active_product = any(
                        t.category == WarehouseObjectCategory.PRODUCT and t.is_confirmed and compute_bbox_min_dist(t.current_bbox, p.bbox) > 45.0
                        for t in self._tracks.values()
                    )
                    is_existing_track_here = any(
                        t.category == WarehouseObjectCategory.PRODUCT and t.is_confirmed and compute_iou(t.current_bbox, d.bbox) > 0.25
                        for t in self._tracks.values()
                    )
                    if fraction_in_person > 0.80 and has_other_active_product and not is_existing_track_here:
                        suspicious = True
                        logger.debug(f"[TRACKER] Filtered false torso/body product artifact while product is on floor: {d.bbox}")
                        break

                    # 4. Low confidence torso artifact rejection (detection conf < 0.35 fully inside person torso)
                    if fraction_in_person > 0.85 and d.confidence < 0.35 and not is_existing_track_here:
                        w_ratio = d.bbox[2] / max(1.0, pw)
                        if 0.70 <= w_ratio <= 1.20:
                            suspicious = True
                            logger.debug(f"[TRACKER] Filtered low-confidence torso/shorts artifact: {d.bbox}")
                            break

                    # 5. Suppress false lower-body / leg / shorts artifacts when person has a product held at torso:
                    # Check if person already has a held product track or upper-body candidate carton directly overlapping torso
                    has_torso_held_product = any(
                        t.category == WarehouseObjectCategory.PRODUCT and (
                            t.carrying_state == "HOLDING"
                            or (t.interaction_state == ProductInteractionState.HELD and compute_bbox_min_dist(t.current_bbox, p.bbox) <= 40.0)
                            or (compute_iou(t.current_bbox, p.bbox) > 0.15 and t.current_bbox[1] + t.current_bbox[3] / 2.0 < py + 0.65 * ph)
                        )
                        for t in self._tracks.values()
                    )
                    has_torso_candidate_det = any(
                        self.map_category(other.label) == WarehouseObjectCategory.PRODUCT
                        and other is not d
                        and (other.bbox[1] + other.bbox[3] / 2.0 < py + 0.65 * ph)
                        and (compute_iou(other.bbox, p.bbox) > 0.15 or (compute_bbox_min_dist(other.bbox, p.bbox) <= 25.0 and px - 20 <= other.bbox[0] + other.bbox[2] / 2.0 <= px + pw + 20))
                        for other in deduped
                    )

                    # If candidate detection is directly overlapping the person's leg column while carton is carried at torso:
                    is_in_leg_column = (cy >= py + 0.50 * ph) and (px - 20 <= cx <= px + pw + 20)
                    is_overlapping_legs = (fraction_in_person > 0.30 or compute_bbox_min_dist(d.bbox, p.bbox) <= 15.0)
                    if is_in_leg_column and is_overlapping_legs:
                        if (has_torso_held_product or has_torso_candidate_det) and not is_existing_track_here:
                            suspicious = True
                            logger.debug(f"[TRACKER] Filtered false leg/shorts artifact while carton is held at torso: {d.bbox}")
                            break
                        # Suppress stray leg detections during walking if overlapping person and low confidence
                        if fraction_in_person > 0.40 and d.confidence < 0.45 and not is_existing_track_here:
                            suspicious = True
                            logger.debug(f"[TRACKER] Filtered low-confidence walking leg artifact: {d.bbox}")
                            break

                if not suspicious:
                    valid_detections.append(d)
            else:
                valid_detections.append(d)

        detections = valid_detections
        
        # 1. Match Detections to Existing Tracks
        unmatched_detections = list(range(len(detections)))
        matched_track_ids = set()

        # Prioritize confirmed tracks and established tracks to prevent track stealing
        sorted_tracks = sorted(
            self._tracks.values(),
            key=lambda t: (1 if t.is_confirmed else 0, t.duration_seconds),
            reverse=True,
        )

        # Score matching: IoU prioritized, centroid distance fallback + Motion Continuity & Geometry Bounds
        for track in sorted_tracks:
            track_id = track.track_id
            best_det_idx = None
            best_score = -1.0
            trk_x, trk_y, trk_w, trk_h = track.current_bbox
            trk_area = trk_w * trk_h
            trk_cx = trk_x + trk_w / 2.0
            trk_cy = trk_y + trk_h / 2.0

            dt = max(0.001, min(0.2, now - track.last_seen))
            curr_s = track.current_state
            vx, vy = curr_s.velocity if curr_s else (0.0, 0.0)
            speed = curr_s.speed if curr_s else 0.0

            # Predicted position for continuity checking
            pred_cx = trk_cx + vx * dt
            pred_cy = trk_cy + vy * dt
            pred_bbox = (int(trk_x + vx * dt), int(trk_y + vy * dt), trk_w, trk_h)

            for det_idx in unmatched_detections:
                det = detections[det_idx]
                det_cat = self.map_category(det.label)
                if det_cat != track.category and det.label != track.label:
                    continue

                det_x, det_y, det_w, det_h = det.bbox
                det_area = det_w * det_h
                det_cx = det_x + det_w / 2.0
                det_cy = det_y + det_h / 2.0

                # Product Bounding Box Stability: Strict continuity gating to reject teleportation and distortions
                if track.category == WarehouseObjectCategory.PRODUCT and track.is_confirmed:
                    # 1. Area ratio continuity guard (cannot suddenly shrink < 0.40 or grow > 2.5)
                    area_ratio = det_area / max(1.0, trk_area)
                    if (area_ratio > 2.5 or area_ratio < 0.40) and compute_iou(track.current_bbox, det.bbox) < 0.25:
                        continue

                    # 2. Aspect ratio continuity guard (cannot suddenly distort orientation)
                    trk_aspect = trk_w / max(1.0, trk_h)
                    det_aspect = det_w / max(1.0, det_h)
                    aspect_ratio = det_aspect / max(0.01, trk_aspect)
                    if (aspect_ratio > 2.2 or aspect_ratio < 0.45) and compute_iou(track.current_bbox, det.bbox) < 0.25:
                        continue

                    # 3. Maximum plausible displacement from predicted position
                    pred_dist = math.sqrt((pred_cx - det_cx) ** 2 + (pred_cy - det_cy) ** 2)
                    iou = compute_iou(track.current_bbox, det.bbox)
                    pred_iou = compute_iou(pred_bbox, det.bbox)

                    # For pure vertical descent (downward free-fall with minimal horizontal drift),
                    # allow gravitational acceleration up to 130px between frames
                    is_pure_vertical_descent = (det_cy >= pred_cy) and (abs(det_cx - pred_cx) <= max(35.0, 0.60 * trk_w))
                    if is_pure_vertical_descent:
                        max_allowed_jump = max(130.0, 3.0 * max(speed, 150.0) * dt + 0.80 * trk_h)
                        max_vert_jump = max_allowed_jump
                    else:
                        max_allowed_jump = max(45.0, 2.5 * max(speed, 60.0) * dt + 0.40 * min(trk_w, trk_h))
                        max_vert_jump = max(40.0, 2.5 * abs(vy) * dt + 0.45 * trk_h)

                    if pred_dist > max_allowed_jump and iou < 0.15 and pred_iou < 0.15:
                        continue

                    # 4. Vertical jump guard (prevents torso <-> legs/floor teleportation)
                    vert_jump = abs(det_cy - pred_cy)
                    if vert_jump > max_vert_jump and iou < 0.15 and pred_iou < 0.15:
                        continue

                iou = compute_iou(track.current_bbox, det.bbox)
                dist = compute_centroid_dist(track.current_bbox, det.bbox)

                if iou >= self.iou_match_threshold:
                    score = 1.0 + iou
                elif dist <= self.max_dist_px:
                    score = 1.0 - (dist / self.max_dist_px)
                else:
                    score = 0.0

                # Prefer confirmed product tracks to prevent track fragmentation on small shifts
                if score > 0.0 and track.is_confirmed and track.category == WarehouseObjectCategory.PRODUCT:
                    score += 0.25

                if score > 0.0 and score > best_score:
                    best_score = score
                    best_det_idx = det_idx

            if best_det_idx is not None:
                matched_det = detections[best_det_idx]
                self._update_track_state(track, matched_det, now)
                matched_track_ids.add(track_id)
                unmatched_detections.remove(best_det_idx)
            else:
                track.missed_frames += 1
                # Short-term motion prediction for occluded / momentarily missed confirmed product tracks
                if track.category == WarehouseObjectCategory.PRODUCT and track.current_state and track.missed_frames <= self.max_missed_frames:
                    dt = max(0.001, min(0.1, now - track.last_seen))
                    track.last_seen = now
                    vx, vy = track.current_state.velocity
                    if 1.0 < track.current_state.speed < 400.0:
                        x, y, w, h = track.current_bbox
                        new_x = int(max(0, min(self.frame_width - w, x + vx * dt)))
                        new_y = int(max(0, min(self.frame_height - h, y + vy * dt)))
                        track.current_bbox = (new_x, new_y, w, h)
                        track.is_predicted = True
                        track.raw_detection_bbox = None

        # 2. Spawn New Tracks for Unmatched Detections
        for det_idx in unmatched_detections:
            det = detections[det_idx]
            new_track = self._create_new_track(det, now)
            self._tracks[new_track.track_id] = new_track

        # 3. Clean Up Expired Tracks
        expired_ids = [
            tid for tid, trk in self._tracks.items()
            if trk.missed_frames > self.max_missed_frames or (now - trk.last_detection_time > self.max_track_age_seconds)
        ]
        for tid in expired_ids:
            del self._tracks[tid]

        # 4. Spatial Person-Product Relationships & Carrying States
        self._compute_person_product_associations()

        return [t for t in self._tracks.values() if t.is_confirmed]

    def _create_new_track(self, det: DetectedObject, timestamp: float) -> TrackedEntity:
        """Initializes a new TrackedEntity."""
        track_id = self._next_track_id
        self._next_track_id += 1

        category = self.map_category(det.label)
        cx = det.bbox[0] + det.bbox[2] / 2.0
        cy = det.bbox[1] + det.bbox[3] / 2.0
        bottom_y = det.bbox[1] + det.bbox[3]
        elevation = max(0.0, min(1.0, (self.frame_height - bottom_y) / max(1, self.frame_height)))
        is_grounded = bottom_y >= self.floor_y_threshold

        initial_state = KinematicState(
            timestamp=timestamp,
            bbox=det.bbox,
            centroid=(cx, cy),
            velocity=(0.0, 0.0),
            speed=0.0,
            vertical_accel=0.0,
            bottom_y=bottom_y,
            elevation_ratio=elevation,
            is_grounded=is_grounded,
        )

        is_confirmed = (self.confirmation_frames <= 1)
        init_interaction = ProductInteractionState.GROUND_CONTACT if is_grounded else ProductInteractionState.FREE

        entity = TrackedEntity(
            track_id=track_id,
            class_id=det.class_id,
            label=det.label,
            category=category,
            confidence=det.confidence,
            current_bbox=det.bbox,
            first_seen=timestamp,
            last_seen=timestamp,
            last_detection_time=timestamp,
            history=[initial_state],
            missed_frames=0,
            is_confirmed=is_confirmed,
            interaction_state=init_interaction,
            interaction_history=[init_interaction],
            interaction_source="UNKNOWN",
            raw_detection_bbox=det.bbox,
            raw_bbox=det.bbox,
            validated_bbox=det.bbox,
            tracked_bbox=det.bbox,
            smoothed_bbox=det.bbox,
            is_predicted=False,
            relative_motion=(0.0, 0.0, 0.0),
            detection_confidence=det.confidence,
            behaviour_confidence=det.confidence,
        )
        return entity

    def _update_track_state(self, track: TrackedEntity, det: DetectedObject, timestamp: float) -> None:
        """Updates kinematic state and history for an existing track."""
        det_cat = self.map_category(det.label)
        if det_cat != track.category:
            logger.warning(f"[TRACKER] Invariant violation: Cannot update track #{track.track_id} ({track.category}) with detection ({det_cat})")
            return

        dt = max(0.001, timestamp - track.last_seen)
        track.last_seen = timestamp
        track.last_detection_time = timestamp
        # Adaptive EMA bounding box smoothing (smooth visual box without lag during real movement)
        prev_x, prev_y, prev_w, prev_h = track.current_bbox
        det_x, det_y, det_w, det_h = det.bbox
        displacement = math.sqrt((det_x - prev_x) ** 2 + (det_y - prev_y) ** 2)

        if displacement > 35.0:
            alpha = 0.85  # Fast motion: immediate tracking response
        elif displacement > 12.0:
            alpha = 0.70  # Moderate motion: balanced smoothing
        else:
            alpha = 0.55  # Small jitter: strong visual stabilization

        smooth_x = int(round(alpha * det_x + (1.0 - alpha) * prev_x))
        smooth_y = int(round(alpha * det_y + (1.0 - alpha) * prev_y))
        smooth_w = int(round(alpha * det_w + (1.0 - alpha) * prev_w))
        smooth_h = int(round(alpha * det_h + (1.0 - alpha) * prev_h))

        smoothed_bbox = (smooth_x, smooth_y, smooth_w, smooth_h)
        track.raw_detection_bbox = det.bbox
        track.raw_bbox = det.bbox
        track.validated_bbox = det.bbox
        track.tracked_bbox = det.bbox
        track.smoothed_bbox = smoothed_bbox
        track.current_bbox = smoothed_bbox
        track.is_predicted = False
        track.confidence = det.confidence
        track.detection_confidence = det.confidence
        track.missed_frames = 0

        # Physical kinematics calculated from raw detection centroid
        raw_cx = det_x + det_w / 2.0
        raw_cy = det_y + det_h / 2.0
        bottom_y = det_y + det_h
        elevation = max(0.0, min(1.0, (self.frame_height - bottom_y) / max(1, self.frame_height)))
        is_grounded = bottom_y >= self.floor_y_threshold

        prev_state = track.current_state
        if prev_state:
            # 1. Raw instantaneous finite difference
            raw_vx = (raw_cx - prev_state.centroid[0]) / dt
            raw_vy = (raw_cy - prev_state.centroid[1]) / dt

            # 2. Short rolling window displacement (over last 3-5 confirmed positions)
            # This filters out high-frequency bounding box centroid jitter
            win_vx, win_vy = raw_vx, raw_vy
            if len(track.history) >= 2:
                ref_idx = max(0, len(track.history) - 4)
                ref_state = track.history[ref_idx]
                dt_win = max(0.001, timestamp - ref_state.timestamp)
                if dt_win >= 0.03:
                    win_vx = (raw_cx - ref_state.centroid[0]) / dt_win
                    win_vy = (raw_cy - ref_state.centroid[1]) / dt_win

            # 3. Blend windowed trajectory velocity (70%) with instantaneous response (30%)
            eff_vx = 0.70 * win_vx + 0.30 * raw_vx
            eff_vy = 0.70 * win_vy + 0.30 * raw_vy

            # 4. Temporal Exponential Moving Average (EMA) smoothing with previous velocity
            if prev_state.speed > 0.0:
                vx = 0.45 * eff_vx + 0.55 * prev_state.velocity[0]
                vy = 0.45 * eff_vy + 0.55 * prev_state.velocity[1]
            else:
                vx = eff_vx
                vy = eff_vy

            raw_speed = math.sqrt(vx * vx + vy * vy)

            # 5. Minimum Movement Threshold / Jitter Deadband Filter
            # If displacement over the recent window is small (< 4.5px) and speed is low (< 35px/s),
            # treat velocity as 0.0 to prevent stationary jittering arrows.
            if len(track.history) >= 2:
                ref_state = track.history[max(0, len(track.history) - 3)]
                recent_disp = math.sqrt((raw_cx - ref_state.centroid[0]) ** 2 + (raw_cy - ref_state.centroid[1]) ** 2)
                if recent_disp < 4.5 and raw_speed < 35.0:
                    vx, vy, speed = 0.0, 0.0, 0.0
                else:
                    speed = raw_speed
            else:
                speed = raw_speed

            # Vertical acceleration
            ay = (vy - prev_state.velocity[1]) / dt
        else:
            vx, vy, speed, ay = 0.0, 0.0, 0.0, 0.0

        new_state = KinematicState(
            timestamp=timestamp,
            bbox=smoothed_bbox,
            centroid=(raw_cx, raw_cy),
            velocity=(vx, vy),
            speed=speed,
            vertical_accel=ay,
            bottom_y=bottom_y,
            elevation_ratio=elevation,
            is_grounded=is_grounded,
        )

        track.history.append(new_state)

        # Confirm track after enough observation frames
        if len(track.history) >= self.confirmation_frames:
            track.is_confirmed = True

        # Prune old history outside sliding window
        cutoff = timestamp - self.history_window_seconds
        track.history = [s for s in track.history if s.timestamp >= cutoff]

    def _compute_person_product_associations(self) -> None:
        """
        Determines spatial person-product association, handler-product relative motion,
        and assigns multi-frame ProductInteractionState (FREE, HELD, ADJACENT, TOWED, AIRBORNE, GROUND_CONTACT).
        """
        person_tracks = [t for t in self._tracks.values() if t.category == WarehouseObjectCategory.PERSON and t.is_confirmed]
        product_tracks = [t for t in self._tracks.values() if t.category == WarehouseObjectCategory.PRODUCT and t.is_confirmed]

        # Snapshot prior associations before re-evaluating
        prior_associations = {prod.track_id: prod.associated_person_id for prod in product_tracks if prod.associated_person_id is not None}

        # Clear active link lists
        for p in person_tracks:
            p.associated_product_ids.clear()
        for prod in product_tracks:
            prod.associated_person_id = None
            prod.carrying_state = "NONE"

        for prod in product_tracks:
            prior_pid = prior_associations.get(prod.track_id)
            best_person = None
            best_dist = 9999.0

            for person in person_tracks:
                centroid_dist = compute_centroid_dist(person.current_bbox, prod.current_bbox)
                edge_dist = compute_bbox_min_dist(person.current_bbox, prod.current_bbox)

                # Proximity metric: for large items (e.g. cartons/mattresses), edge distance is critical
                effective_dist = min(centroid_dist, edge_dist * 1.6)

                # Temporal stickiness bonus: if this person was already handling this product, apply 35% affinity bonus
                if prior_pid is not None and person.track_id == prior_pid:
                    effective_dist *= 0.65

                if (centroid_dist <= 260.0 or edge_dist <= 100.0) and effective_dist < best_dist:
                    best_dist = effective_dist
                    best_person = person

            # Fallback: if best_person is momentarily unassigned due to jitter, but prior handler is still active
            if best_person is None and prior_pid is not None:
                prior_track = self._tracks.get(prior_pid)
                if prior_track and prior_track.category == WarehouseObjectCategory.PERSON and prior_track.missed_frames <= 2:
                    dist_to_prior = compute_centroid_dist(prior_track.current_bbox, prod.current_bbox)
                    if dist_to_prior <= 320.0:
                        best_person = prior_track

            # Compute relative motion and classify interaction state
            candidate_state = ProductInteractionState.FREE
            if best_person is not None:
                prod.associated_person_id = best_person.track_id
                if prod.track_id not in best_person.associated_product_ids:
                    best_person.associated_product_ids.append(prod.track_id)

                p_bbox = best_person.current_bbox
                pr_bbox = prod.current_bbox
                p_y, p_h = p_bbox[1], p_bbox[3]
                prod_cy = pr_bbox[1] + pr_bbox[3] / 2.0

                # Determine interaction source (HAND_INTERACTION vs FOOT_INTERACTION)
                # Lower 35% of person silhouette and floor contact corresponds to foot region
                if prod_cy >= (p_y + 0.65 * p_h):
                    prod.interaction_source = "FOOT_INTERACTION"
                else:
                    prod.interaction_source = "HAND_INTERACTION"

                # Relative Kinematics
                p_vx, p_vy = (best_person.current_state.velocity if best_person.current_state else (0.0, 0.0))
                prod_vx, prod_vy = (prod.current_state.velocity if prod.current_state else (0.0, 0.0))
                rel_dx = prod_vx - p_vx
                rel_dy = prod_vy - p_vy
                rel_speed = math.sqrt(rel_dx * rel_dx + rel_dy * rel_dy)
                prod.relative_motion = (round(rel_dx, 1), round(rel_dy, 1), round(rel_speed, 1))

                # Geometric Carry Envelope Evaluation
                p_bottom = p_bbox[1] + p_bbox[3]
                prod_bottom = pr_bbox[1] + pr_bbox[3]
                edge_dist = compute_bbox_min_dist(p_bbox, pr_bbox)
                centroid_dist = compute_centroid_dist(p_bbox, pr_bbox)

                # Criteria for HELD:
                # 1. Close to handler body (edge_dist <= 85px or centroid_dist <= 220px)
                # 2. Elevated in carry position (prod_bottom <= p_bottom - 25 or not grounded)
                # 3. Low relative speed (moving together: rel_speed <= 110px/s or abs(rel_dy) <= 75px/s)
                # 4. Not independently accelerating downward away from handler (prod_vy <= p_vy + 90px/s)
                is_near_body = (edge_dist <= 85.0 or centroid_dist <= 220.0)
                is_elevated_in_reach = (prod_bottom <= p_bottom - 20) or (prod.current_state and not prod.current_state.is_grounded)
                is_correlated_motion = (rel_speed <= 110.0) or (abs(rel_dy) <= 75.0)
                is_not_falling_away = (prod_vy <= p_vy + 90.0)

                if is_near_body and is_elevated_in_reach and is_correlated_motion and is_not_falling_away:
                    candidate_state = ProductInteractionState.HELD
                    prod.carrying_state = "HOLDING"
                elif prod.current_state and prod.current_state.is_grounded and prod.current_state.speed > 15.0 and edge_dist <= 180.0:
                    candidate_state = ProductInteractionState.TOWED
                    prod.carrying_state = "TOWING"
                elif edge_dist <= 140.0:
                    candidate_state = ProductInteractionState.ADJACENT
                    prod.carrying_state = "ADJACENT"
                else:
                    candidate_state = ProductInteractionState.FREE
                    prod.carrying_state = "NONE"
            else:
                prod.associated_person_id = None
                prod.relative_motion = (0.0, 0.0, 0.0)
                prod.interaction_source = "UNKNOWN"
                if prod.current_state:
                    if not prod.current_state.is_grounded and (prod.current_state.elevation_ratio > 0.08 or prod.current_state.bottom_y < self.floor_y_threshold - 20) and prod.current_state.speed > 25.0:
                        candidate_state = ProductInteractionState.AIRBORNE
                    elif prod.current_state.is_grounded or prod.current_state.bottom_y >= self.floor_y_threshold - 15:
                        candidate_state = ProductInteractionState.GROUND_CONTACT
                    else:
                        candidate_state = ProductInteractionState.FREE
                else:
                    candidate_state = ProductInteractionState.FREE
                prod.carrying_state = "NONE"

            # Multi-Frame Temporal State Continuity (Hysteresis)
            prod.interaction_history.append(candidate_state)
            if len(prod.interaction_history) > 30:
                prod.interaction_history = prod.interaction_history[-30:]

            # Apply 2-frame stability filter (prevent single-frame noise flicker)
            if len(prod.interaction_history) >= 2:
                recent_2 = prod.interaction_history[-2:]
                if recent_2[0] == recent_2[1]:
                    prod.interaction_state = candidate_state
                elif candidate_state in (ProductInteractionState.HELD, ProductInteractionState.AIRBORNE, ProductInteractionState.GROUND_CONTACT):
                    # High-priority physical transitions take immediate effect
                    prod.interaction_state = candidate_state
            else:
                prod.interaction_state = candidate_state

            # Populate comprehensive carry relationship telemetry
            prod.carry_telemetry = {
                "handler_id": prod.associated_person_id,
                "product_id": prod.track_id,
                "state": prod.interaction_state.value if hasattr(prod.interaction_state, "value") else str(prod.interaction_state),
                "carrying_state": prod.carrying_state,
                "relative_distance_px": round(centroid_dist, 1) if best_person else 0.0,
                "relative_velocity_px_s": round(rel_speed, 1) if best_person else 0.0,
                "vertical_separation_px": round(abs(prod_cy - (p_y + p_h / 2.0)), 1) if best_person else 0.0,
                "torso_overlap": bool(is_near_body and is_elevated_in_reach) if best_person else False,
                "ground_contact": bool(prod.current_state and prod.current_state.is_grounded),
                "foot_contact": bool(prod.interaction_source == "FOOT_INTERACTION"),
                "stepping": False,
            }

    def propagate_tracks(self, current_time: Optional[float] = None) -> List[TrackedEntity]:
        """
        Smoothly propagates confirmed track kinematic states during intermediate frames
        when full AI detection is not run, ensuring 30+ FPS smooth tracking.
        Prunes tracks if no detection has confirmed them within max_track_age_seconds.
        """
        now = current_time if current_time is not None else time.time()
        for track in list(self._tracks.values()):
            # Expire track if underlying detection disappeared and exceeded max track age
            if track.last_detection_time > 0 and (now - track.last_detection_time > self.max_track_age_seconds):
                del self._tracks[track.track_id]
                continue

            if not track.is_confirmed or not track.current_state:
                continue
            dt = max(0.001, min(0.1, now - track.last_seen))
            vx, vy = track.current_state.velocity
            if 0.5 < track.current_state.speed < 500.0:
                x, y, w, h = track.current_bbox
                new_x = int(max(0, min(self.frame_width - w, x + vx * dt)))
                new_y = int(max(0, min(self.frame_height - h, y + vy * dt)))
                track.current_bbox = (new_x, new_y, w, h)
                track.is_predicted = True
                track.raw_detection_bbox = None
                track.last_seen = now
                cx = new_x + w / 2.0
                cy = new_y + h / 2.0
                bottom_y = new_y + h
                elevation = max(0.0, min(1.0, (self.frame_height - bottom_y) / max(1, self.frame_height)))
                is_grounded = bottom_y >= self.floor_y_threshold
                new_state = KinematicState(
                    timestamp=now,
                    bbox=(new_x, new_y, w, h),
                    centroid=(cx, cy),
                    velocity=(vx, vy),
                    speed=track.current_state.speed,
                    vertical_accel=track.current_state.vertical_accel,
                    bottom_y=bottom_y,
                    elevation_ratio=elevation,
                    is_grounded=is_grounded,
                )
                track.history.append(new_state)
                cutoff = now - self.history_window_seconds
                track.history = [s for s in track.history if s.timestamp >= cutoff]
            else:
                track.last_seen = now

        self._compute_person_product_associations()
        return [t for t in self._tracks.values() if t.is_confirmed]
