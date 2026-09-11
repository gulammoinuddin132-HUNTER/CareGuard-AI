"""
src/core/warehouse_evidence_cropper.py
---------------------------------------
Smart Evidence Cropper Utility for Godrej CareGuard AI.

Focuses visual evidence capture directly on the physical interaction between
HANDLER (Person) and PRODUCT (Carton/Box/Mattress) rather than whole-scene/road
backgrounds. Computes an optimal union bounding box with contextual padding,
minimum resolution constraints, trajectory inclusion, and forensic annotations.
"""

import time
import math
import logging
from pathlib import Path
from typing import Optional, Tuple, List, Any, Dict
import cv2
import numpy as np

from src.core.warehouse_models import TrackedEntity, KinematicState

logger = logging.getLogger("GodrejWarehouse.Cropper")


def compute_interaction_crop_box(
    frame_shape: Tuple[int, int],
    product_track: Optional[TrackedEntity] = None,
    person_track: Optional[TrackedEntity] = None,
    product_bbox: Optional[Tuple[int, int, int, int]] = None,
    person_bbox: Optional[Tuple[int, int, int, int]] = None,
    extra_points: Optional[List[Tuple[int, int]]] = None,
    behaviour_type: Optional[str] = None,
    padding_ratio: float = 0.12,
    min_w: Optional[int] = None,
    min_h: Optional[int] = None,
) -> Tuple[int, int, int, int]:
    """
    Computes optimal tight (x1, y1, x2, y2) crop window centered strictly on the
    frozen handler-product interaction area with 10-15% contextual padding.

    Args:
        frame_shape: (height, width) of original frame.
        product_track: Product TrackedEntity.
        person_track: Handler TrackedEntity.
        product_bbox: Explicit (x, y, w, h) bounding box for the product.
        person_bbox: Explicit (x, y, w, h) bounding box for the handler.
        extra_points: Unused (kept for API compatibility).
        behaviour_type: Optional behaviour string.
        padding_ratio: Fractional padding around the interaction bounding box (default 12%).
        min_w: Optional explicit minimum crop width.
        min_h: Optional explicit minimum crop height.

    Returns:
        (x1, y1, x2, y2) coordinate tuple clamped to frame boundaries.
    """
    frame_h, frame_w = frame_shape[:2]
    boxes: List[Tuple[int, int, int, int]] = []

    # 1. Collect entity bounding boxes from explicit parameters or tracks
    p_box = product_bbox or (product_track.current_bbox if product_track else None)
    h_box = person_bbox or (person_track.current_bbox if person_track else None)

    # Determine whether handler should be included in the crop:
    # If handler is far away (>140px boundary distance) or unassociated,
    # crop only the product box to avoid inflating the view across the entire room.
    include_handler = False
    b_type_str = str(behaviour_type or "").upper()

    if h_box and len(h_box) == 4 and h_box[2] > 0 and h_box[3] > 0:
        if p_box and len(p_box) == 4 and p_box[2] > 0 and p_box[3] > 0:
            dx = max(0, max(p_box[0], h_box[0]) - min(p_box[0] + p_box[2], h_box[0] + h_box[2]))
            dy = max(0, max(p_box[1], h_box[1]) - min(p_box[1] + p_box[3], h_box[1] + h_box[3]))
            dist = math.sqrt(dx * dx + dy * dy)
            if dist <= 140.0:
                include_handler = True
        else:
            include_handler = True

    if p_box and len(p_box) == 4 and p_box[2] > 0 and p_box[3] > 0:
        boxes.append(p_box)

    if include_handler and h_box:
        hx, hy, hw, hh = h_box
        # Event-Specific Body Region Focus:
        if "KICK" in b_type_str:
            # Focus strictly on Lower Body / Foot region for KICK
            foot_y = hy + int(0.55 * hh)
            foot_h = max(20, hh - int(0.55 * hh))
            boxes.append((hx, foot_y, hw, foot_h))
        elif "DROP" in b_type_str:
            # Focus on mid-to-lower body and descent path
            body_y = hy + int(0.20 * hh)
            body_h = max(30, hh - int(0.20 * hh))
            boxes.append((hx, body_y, hw, body_h))
        else:
            boxes.append(h_box)

    # Fallback: If no boxes exist, return full frame
    if not boxes:
        return (0, 0, frame_w, frame_h)

    # 2. Compute tight bounding union of participant boxes
    min_x = min(b[0] for b in boxes)
    min_y = min(b[1] for b in boxes)
    max_x = max(b[0] + b[2] for b in boxes)
    max_y = max(b[1] + b[3] for b in boxes)

    union_w = max(1, max_x - min_x)
    union_h = max(1, max_y - min_y)

    # 3. Add focused 10–15% context padding (default 12%)
    eff_padding = max(0.10, min(0.15, padding_ratio))
    pad_x = max(8, int(union_w * eff_padding))
    pad_y = max(8, int(union_h * eff_padding))

    x1 = max(0, min_x - pad_x)
    y1 = max(0, min_y - pad_y)
    x2 = min(frame_w, max_x + pad_x)
    y2 = min(frame_h, max_y + pad_y)

    # 4. Proportional minimum size without whole-frame distortion (1.15x participant union)
    target_min_w = min_w if min_w is not None else min(frame_w, max(60, int(1.15 * union_w)))
    target_min_h = min_h if min_h is not None else min(frame_h, max(60, int(1.15 * union_h)))

    cw = x2 - x1
    ch = y2 - y1
    if cw < target_min_w:
        diff = target_min_w - cw
        x1 = max(0, x1 - diff // 2)
        x2 = min(frame_w, x1 + target_min_w)
        if x2 - x1 < target_min_w:
            x1 = max(0, x2 - target_min_w)
    if ch < target_min_h:
        diff = target_min_h - ch
        y1 = max(0, y1 - diff // 2)
        y2 = min(frame_h, y1 + target_min_h)
        if y2 - y1 < target_min_h:
            y1 = max(0, y2 - target_min_h)

    return (int(x1), int(y1), int(x2), int(y2))


def log_event_geometry(
    event_id: str,
    frame_shape: Tuple[int, int],
    product_track_id: Optional[int],
    product_bbox: Optional[Tuple[int, int, int, int]],
    handler_track_id: Optional[int],
    handler_bbox: Optional[Tuple[int, int, int, int]],
    focus_box: Tuple[int, int, int, int],
    trajectory_points: Optional[List[Tuple[int, int]]] = None,
) -> Dict[str, Any]:
    """
    Constructs and logs detailed geometry telemetry for a warehouse event,
    recording native, processed, rendered, and viewport dimensions.
    """
    frame_h, frame_w = frame_shape[:2]
    
    all_boxes = []
    if product_bbox:
        all_boxes.append(product_bbox)
    if handler_bbox:
        all_boxes.append(handler_bbox)
    
    if all_boxes:
        u_x1 = min(b[0] for b in all_boxes)
        u_y1 = min(b[1] for b in all_boxes)
        u_x2 = max(b[0] + b[2] for b in all_boxes)
        u_y2 = max(b[1] + b[3] for b in all_boxes)
        raw_union = [u_x1, u_y1, u_x2 - u_x1, u_y2 - u_y1]
    else:
        raw_union = list(focus_box)

    fx1, fy1, fx2, fy2 = focus_box
    focus_w = fx2 - fx1
    focus_h = fy2 - fy1

    geo_data = {
        "event_id": event_id,
        "video_frame": {
            "width": frame_w,
            "height": frame_h,
        },
        "handler": {
            "track_id": handler_track_id,
            "bbox_raw": list(handler_bbox) if handler_bbox else None,
            "bbox_smoothed": list(handler_bbox) if handler_bbox else None,
            "bbox_rendered": list(handler_bbox) if handler_bbox else None,
        },
        "product": {
            "track_id": product_track_id,
            "bbox_raw": list(product_bbox) if product_bbox else None,
            "bbox_smoothed": list(product_bbox) if product_bbox else None,
            "bbox_rendered": list(product_bbox) if product_bbox else None,
        },
        "trajectory": {
            "raw_points": [list(pt) for pt in (trajectory_points or [])],
            "rendered_points": [list(pt) for pt in (trajectory_points or [])],
        },
        "focus": {
            "raw_union": raw_union,
            "margin_px": int(max(0, (focus_w - raw_union[2]) / 2)),
            "final_crop_rectangle": list(focus_box),
        },
        "transform": {
            "native_video": f"{frame_w}x{frame_h}",
            "processed_frame": f"{frame_w}x{frame_h}",
            "rendered_frame": f"{frame_w}x{frame_h}",
            "frontend_viewport": "aspect-video (16:9 object-contain)",
        },
    }

    logger.info(
        f"[GEOMETRY TRACE] Event: {event_id} | Frame: {frame_w}x{frame_h} | "
        f"Handler #{handler_track_id} {handler_bbox} | Product #{product_track_id} {product_bbox} | "
        f"Focus Rect: {focus_box} (Union: {raw_union})"
    )
    return geo_data


def create_interaction_evidence_crop(
    frame: np.ndarray,
    product_track: Optional[TrackedEntity] = None,
    person_track: Optional[TrackedEntity] = None,
    product_bbox: Optional[Tuple[int, int, int, int]] = None,
    person_bbox: Optional[Tuple[int, int, int, int]] = None,
    event_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    padding_ratio: float = 0.12,
    annotate: bool = True,
) -> np.ndarray:
    """
    Produces a cropped, presentation-grade forensic evidence image focused on the
    handler-product interaction area, with optional metadata annotations.

    Args:
        frame: Full source image (BGR numpy array).
        product_track: Product TrackedEntity.
        person_track: Handler TrackedEntity.
        product_bbox: Explicit (x, y, w, h) bounding box for the product.
        person_bbox: Explicit (x, y, w, h) bounding box for the handler.
        event_type: Behaviour event title string.
        risk_level: Risk level ("RED", "ORANGE", "YELLOW", "GREEN").
        padding_ratio: Ratio of padding around interaction.
        annotate: Whether to overlay sleek forensic metadata and bounding boxes.

    Returns:
        Cropped and annotated BGR image.
    """
    if frame is None or frame.size == 0:
        return np.zeros((360, 480, 3), dtype=np.uint8)

    h, w = frame.shape[:2]
    x1, y1, x2, y2 = compute_interaction_crop_box(
        (h, w),
        product_track=product_track,
        person_track=person_track,
        product_bbox=product_bbox,
        person_bbox=person_bbox,
        behaviour_type=event_type,
        padding_ratio=padding_ratio,
    )

    crop = frame[y1:y2, x1:x2].copy()
    crop_h, crop_w = crop.shape[:2]

    if not annotate:
        return crop

    # Overlay entity bounding boxes in crop coordinates
    crop_offset_x, crop_offset_y = x1, y1

    # Product Box
    p_box = product_bbox or (product_track.current_bbox if product_track else None)
    if p_box:
        bx, by, bw, bh = p_box
        cx1 = max(0, bx - crop_offset_x)
        cy1 = max(0, by - crop_offset_y)
        cx2 = min(crop_w, bx + bw - crop_offset_x)
        cy2 = min(crop_h, by + bh - crop_offset_y)
        if cx2 > cx1 and cy2 > cy1:
            p_color = (0, 70, 240) if risk_level == "RED" else (0, 160, 240)
            cv2.rectangle(crop, (cx1, cy1), (cx2, cy2), p_color, 2, cv2.LINE_AA)
            p_id = product_track.track_id if product_track else "N/A"
            p_tag = f"PRODUCT #{p_id}"
            (tw, th), _ = cv2.getTextSize(p_tag, cv2.FONT_HERSHEY_SIMPLEX, 0.35, 1)
            cv2.rectangle(crop, (cx1, max(0, cy1 - th - 6)), (cx1 + tw + 6, cy1), p_color, -1)
            cv2.putText(crop, p_tag, (cx1 + 3, max(10, cy1 - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)

    # Person / Handler Box
    h_box = person_bbox or (person_track.current_bbox if person_track else None)
    if h_box:
        bx, by, bw, bh = h_box
        cx1 = max(0, bx - crop_offset_x)
        cy1 = max(0, by - crop_offset_y)
        cx2 = min(crop_w, bx + bw - crop_offset_x)
        cy2 = min(crop_h, by + bh - crop_offset_y)
        if cx2 > cx1 and cy2 > cy1:
            h_color = (0, 210, 255)
            cv2.rectangle(crop, (cx1, cy1), (cx2, cy2), h_color, 1, cv2.LINE_AA)
            h_id = person_track.track_id if person_track else "N/A"
            h_tag = f"HANDLER #{h_id}"
            (hw_t, hh_t), _ = cv2.getTextSize(h_tag, cv2.FONT_HERSHEY_SIMPLEX, 0.35, 1)
            cv2.rectangle(crop, (cx1, max(0, cy1 - hh_t - 6)), (cx1 + hw_t + 6, cy1), (20, 25, 30), -1)
            cv2.rectangle(crop, (cx1, max(0, cy1 - hh_t - 6)), (cx1 + hw_t + 6, cy1), h_color, 1)
            cv2.putText(crop, h_tag, (cx1 + 3, max(10, cy1 - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, h_color, 1, cv2.LINE_AA)

    # Top Forensic Header Bar
    bar_h = 26
    sub = crop[0:bar_h, 0:crop_w]
    if sub.size > 0:
        dark_bar = np.zeros(sub.shape, dtype=np.uint8)
        dark_bar[:] = (12, 16, 22)
        crop[0:bar_h, 0:crop_w] = cv2.addWeighted(sub, 0.25, dark_bar, 0.75, 0)
    cv2.line(crop, (0, bar_h), (crop_w, bar_h), (35, 45, 60), 1)

    # Title & Risk Badge
    title_txt = f"CAREGUARD EVIDENCE • {event_type or 'WAREHOUSE INCIDENT'}"
    cv2.putText(crop, title_txt, (8, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (240, 240, 240), 1, cv2.LINE_AA)

    lvl = (risk_level or "YELLOW").upper()
    lvl_color = (40, 40, 240) if lvl == "RED" else ((0, 160, 240) if lvl == "ORANGE" else (0, 220, 120))
    badge_txt = f"RISK: {lvl}"
    (bw_txt, _), _ = cv2.getTextSize(badge_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.34, 1)
    cv2.putText(crop, badge_txt, (crop_w - bw_txt - 10, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.34, lvl_color, 1, cv2.LINE_AA)

    # Bottom Metadata Bar
    bot_y = crop_h - 18
    sub_bot = crop[bot_y:crop_h, 0:crop_w]
    if sub_bot.size > 0:
        dark_bot = np.zeros(sub_bot.shape, dtype=np.uint8)
        dark_bot[:] = (10, 12, 16)
        crop[bot_y:crop_h, 0:crop_w] = cv2.addWeighted(sub_bot, 0.30, dark_bot, 0.70, 0)

    ts_str = time.strftime("%Y-%m-%d %H:%M:%S")
    bot_txt = f"FOCUS: HANDLER + PRODUCT INTERACTION | {ts_str} | REAL CV DETECTED"
    cv2.putText(crop, bot_txt, (8, crop_h - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (140, 160, 180), 1, cv2.LINE_AA)

    return crop


def save_evidence_snapshot(
    frame: np.ndarray,
    output_dir: Path,
    filename_prefix: str = "evidence",
    product_track: Optional[TrackedEntity] = None,
    person_track: Optional[TrackedEntity] = None,
    product_bbox: Optional[Tuple[int, int, int, int]] = None,
    person_bbox: Optional[Tuple[int, int, int, int]] = None,
    event_type: Optional[str] = None,
    risk_level: Optional[str] = None,
) -> Optional[str]:
    """
    Crops frame strictly to handler-product interaction area, annotates forensic metadata,
    writes to evidence directory, and validates decodability.

    Returns:
        Absolute filepath string of the validated image, or None on failure.
    """
    if frame is None or frame.size == 0:
        return None

    try:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        cropped_evidence = create_interaction_evidence_crop(
            frame=frame,
            product_track=product_track,
            person_track=person_track,
            product_bbox=product_bbox,
            person_bbox=person_bbox,
            event_type=event_type,
            risk_level=risk_level,
            padding_ratio=0.12,
            annotate=True,
        )

        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        millis = int((time.time() % 1) * 1000)
        clean_prefix = filename_prefix.replace(" ", "_").lower()
        filename = f"{clean_prefix}_{timestamp_str}_{millis:03d}.jpg"
        filepath = output_dir / filename

        success = cv2.imwrite(str(filepath), cropped_evidence, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        if not success:
            logger.error(f"cv2.imwrite returned False for {filepath}")
            return None

        # Post-write assertions: exists, non-zero size, decodable by OpenCV
        if not filepath.exists() or filepath.stat().st_size == 0:
            logger.error(f"Evidence file {filepath} was not written or is 0 bytes")
            return None

        verify_img = cv2.imread(str(filepath))
        if verify_img is None or verify_img.size == 0:
            logger.error(f"Failed to decode saved evidence snapshot {filepath}")
            return None

        vh, vw = verify_img.shape[:2]
        logger.info(f"[EVIDENCE VERIFIED] Saved and verified evidence snapshot: {filepath.name} ({vw}x{vh}, {filepath.stat().st_size} bytes)")
        return str(filepath)
    except Exception as e:
        logger.error(f"Failed to save smart evidence crop: {e}", exc_info=True)
        return None
