"""
CareGuard AI - Deterministic Warehouse Risk Severity Policy and Explicit RED Alert Engine
------------------------------------------------------------------------------------------
Governs risk severity classification (GREEN, YELLOW, ORANGE, RED) based strictly on:
  DETECTED BEHAVIOUR + MEASURED KINEMATICS + TEMPORAL CONTEXT + SAFETY POLICY

CORE PRINCIPLE:
  MODEL CONFIDENCE != RISK SEVERITY
  High detection confidence alone must NEVER produce RED. Severity is governed
  exclusively by verified physical kinematics and warehouse damage vulnerability.

SEVERITY TIERS:
  - GREEN:  Safe / normal handling within operational boundaries.
  - YELLOW: Low-to-moderate operational handling concern (e.g. manual carry, pallet protrusion, standard dragging).
  - ORANGE: Significant handling/damage risk requiring supervisor attention (e.g. rough impact, unstable stack, walkway block).
  - RED:    Critical/immediate damage or safety risk requiring urgent intervention (e.g. high-speed throwing, severe drop impact, unsafe unloading order).
"""

from enum import Enum
from typing import Dict, Any, Optional, Union
from src.core.warehouse_models import WarehouseBehaviourType


class WarehouseRiskTier(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"


def calculate_risk_severity(
    behaviour_type: Union[WarehouseBehaviourType, str],
    kinematics: Optional[Dict[str, Any]] = None,
    trigger_conditions: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    confidence: float = 0.85,
) -> Dict[str, Any]:
    """
    Calculates deterministic risk severity, human-readable severity reason,
    and structured physical factors for an observed warehouse event.

    Args:
        behaviour_type: WarehouseBehaviourType enum or string representation.
        kinematics: Measured physical kinematics (velocities, displacements, accelerations).
        trigger_conditions: Verified rule evaluation conditions.
        metadata: Additional context (e.g. dimensions, zone info).
        confidence: Object/action detection confidence (used ONLY as supporting context).

    Returns:
        Dict containing:
          - "severity": "GREEN" | "YELLOW" | "ORANGE" | "RED"
          - "severity_reason": Human-readable physical justification
          - "severity_factors": Structured dictionary of measured values vs policy thresholds
    """
    if kinematics is None:
        kinematics = {}
    if trigger_conditions is None:
        trigger_conditions = {}
    if metadata is None:
        metadata = {}

    b_str = behaviour_type.value if isinstance(behaviour_type, WarehouseBehaviourType) else str(behaviour_type)

    # -------------------------------------------------------------------------
    # 1. MATERIAL_PUSHED_THROWN -> Critical Immediate Danger (RED)
    # -------------------------------------------------------------------------
    if b_str == WarehouseBehaviourType.MATERIAL_PUSHED_THROWN.value or b_str == "MATERIAL_PUSHED_THROWN":
        vx = float(kinematics.get("horizontal_velocity", kinematics.get("product_vx", 0.0)))
        speed = float(kinematics.get("speed", kinematics.get("product_speed", abs(vx))))
        thresh = 160.0
        is_airborne = not bool(kinematics.get("product_grounded", False))

        severity = WarehouseRiskTier.RED.value
        severity_reason = (
            f"Product entered unsupported ballistic flight with horizontal velocity of {abs(vx):.1f} px/s "
            f"(exceeding critical threshold of {thresh:.1f} px/s), posing severe damage and personnel hazard."
        )
        severity_factors = {
            "behaviour": "MATERIAL_PUSHED_THROWN",
            "primary_metric": "horizontal_velocity",
            "measured_value": round(abs(vx), 1),
            "threshold": thresh,
            "unit": "px/s",
            "is_airborne": is_airborne,
            "flight_speed_px_s": round(speed, 1),
            "confidence": round(confidence, 3),
        }
        return {
            "severity": severity,
            "severity_reason": severity_reason,
            "severity_factors": severity_factors,
        }

    # -------------------------------------------------------------------------
    # 2. PRODUCT_DROPPED -> Severe Drop (RED) vs Minor Drop (ORANGE)
    # -------------------------------------------------------------------------
    if b_str == WarehouseBehaviourType.PRODUCT_DROPPED.value or b_str == "PRODUCT_DROPPED":
        vy = float(kinematics.get("max_downward_vy", kinematics.get("product_vy", 0.0)))
        descent_px = float(kinematics.get("displacement", kinematics.get("product_displacement", 0.0)))
        drop_height_m = float(metadata.get("drop_height_m", (descent_px / 480.0) * 2.0 if descent_px > 0 else 0.5))

        is_critical_drop = (drop_height_m >= 0.8) or (vy >= 250.0) or (descent_px >= 180.0)
        severity = WarehouseRiskTier.RED.value if is_critical_drop else WarehouseRiskTier.ORANGE.value

        if is_critical_drop:
            severity_reason = (
                f"Product underwent high-elevation free fall (descent: {descent_px:.0f}px / ~{drop_height_m:.2f}m, "
                f"velocity: {vy:.1f} px/s) ending in high-energy ground impact exceeding the 0.80m / 250 px/s safety threshold."
            )
        else:
            severity_reason = (
                f"Product dropped from moderate height (descent: {descent_px:.0f}px / ~{drop_height_m:.2f}m, "
                f"velocity: {vy:.1f} px/s) onto warehouse floor."
            )

        severity_factors = {
            "behaviour": "PRODUCT_DROPPED",
            "primary_metric": "downward_velocity",
            "measured_value": round(vy, 1),
            "threshold": 250.0,
            "unit": "px/s",
            "drop_height_px": round(descent_px, 1),
            "drop_height_m": round(drop_height_m, 2),
            "impact_detected": True,
            "confidence": round(confidence, 3),
        }
        return {
            "severity": severity,
            "severity_reason": severity_reason,
            "severity_factors": severity_factors,
        }

    # -------------------------------------------------------------------------
    # 3. UNSAFE_LOADING_SEQUENCE -> Critical Collapse Risk (RED)
    # -------------------------------------------------------------------------
    if b_str == WarehouseBehaviourType.UNSAFE_LOADING_SEQUENCE.value or b_str == "UNSAFE_LOADING_SEQUENCE":
        bot_speed = float(kinematics.get("bot_speed", 30.0))
        top_speed = float(kinematics.get("top_speed", 0.0))
        thresh = 30.0

        severity = WarehouseRiskTier.RED.value
        severity_reason = (
            f"Base supporting container extracted at {bot_speed:.1f} px/s while upper cargo remained suspended overhead, "
            f"creating imminent column collapse hazard."
        )
        severity_factors = {
            "behaviour": "UNSAFE_LOADING_SEQUENCE",
            "primary_metric": "base_extraction_speed",
            "measured_value": round(bot_speed, 1),
            "threshold": thresh,
            "unit": "px/s",
            "overhead_suspended_load": True,
            "top_unit_speed": round(top_speed, 1),
            "confidence": round(confidence, 3),
        }
        return {
            "severity": severity,
            "severity_reason": severity_reason,
            "severity_factors": severity_factors,
        }

    # -------------------------------------------------------------------------
    # 4. PRODUCT_DRAGGED -> Severe Sustained (ORANGE) vs Standard (YELLOW)
    # -------------------------------------------------------------------------
    if b_str == WarehouseBehaviourType.PRODUCT_DRAGGED.value or b_str == "PRODUCT_DRAGGED":
        duration = float(kinematics.get("duration", kinematics.get("drag_duration_seconds", 0.0)))
        displacement = float(kinematics.get("displacement", kinematics.get("product_displacement", 0.0)))
        speed = float(kinematics.get("speed", kinematics.get("product_speed", 0.0)))

        is_severe = (duration >= 2.0) or (displacement >= 100.0)
        severity = WarehouseRiskTier.ORANGE.value if is_severe else WarehouseRiskTier.YELLOW.value

        if is_severe:
            severity_reason = (
                f"Sustained severe floor dragging ({displacement:.0f}px displacement over {duration:.2f}s) "
                f"causing continuous abrasive friction damage to container bottom seams."
            )
        else:
            severity_reason = (
                f"Product dragged along floor ({displacement:.0f}px over {duration:.2f}s) without mechanical trolley clearance."
            )

        severity_factors = {
            "behaviour": "PRODUCT_DRAGGED",
            "primary_metric": "drag_duration",
            "measured_value": round(duration, 2),
            "threshold": 2.0 if is_severe else 0.4,
            "unit": "s",
            "displacement_px": round(displacement, 1),
            "speed_px_s": round(speed, 1),
            "grounded": True,
            "confidence": round(confidence, 3),
        }
        return {
            "severity": severity,
            "severity_reason": severity_reason,
            "severity_factors": severity_factors,
        }

    # -------------------------------------------------------------------------
    # 5. ROUGH_HANDLING -> High Shock Impact (ORANGE)
    # -------------------------------------------------------------------------
    if b_str == WarehouseBehaviourType.ROUGH_HANDLING.value or b_str == "ROUGH_HANDLING":
        decel = float(kinematics.get("deceleration", kinematics.get("impact_deceleration_px_s2", 0.0)))
        prior_speed = float(kinematics.get("peak_speed", kinematics.get("prior_speed_px_s", 0.0)))
        thresh = 350.0

        severity = WarehouseRiskTier.ORANGE.value
        severity_reason = (
            f"Sharp impact deceleration of {decel:.0f} px/s^2 upon placement (prior speed: {prior_speed:.0f} px/s, "
            f"threshold: {thresh:.0f} px/s^2), transmitting mechanical shock into cargo."
        )
        severity_factors = {
            "behaviour": "ROUGH_HANDLING",
            "primary_metric": "impact_deceleration",
            "measured_value": round(decel, 1),
            "threshold": thresh,
            "unit": "px/s^2",
            "prior_speed_px_s": round(prior_speed, 1),
            "confidence": round(confidence, 3),
        }
        return {
            "severity": severity,
            "severity_reason": severity_reason,
            "severity_factors": severity_factors,
        }

    # -------------------------------------------------------------------------
    # 6. INCORRECT_STACKING -> Top-Heavy / Overhang Load (ORANGE)
    # -------------------------------------------------------------------------
    if b_str == WarehouseBehaviourType.INCORRECT_STACKING.value or b_str == "INCORRECT_STACKING":
        top_area = float(kinematics.get("top_area", 0.0))
        bot_area = float(kinematics.get("bot_area", 1.0))
        area_ratio = round(top_area / max(1.0, bot_area), 2)
        overhang_px = float(kinematics.get("overhang_px", 0.0))

        severity = WarehouseRiskTier.ORANGE.value
        severity_reason = (
            f"Disproportionate load stacking: Upper package area ({top_area:.0f}px^2) exceeds base ({bot_area:.0f}px^2) "
            f"by {area_ratio:.2f}x (or {overhang_px:.0f}px overhang), creating container wall crushing risk."
        )
        severity_factors = {
            "behaviour": "INCORRECT_STACKING",
            "primary_metric": "stack_area_ratio",
            "measured_value": area_ratio,
            "threshold": 1.30,
            "unit": "ratio",
            "top_area_px": round(top_area, 1),
            "base_area_px": round(bot_area, 1),
            "overhang_px": round(overhang_px, 1),
            "confidence": round(confidence, 3),
        }
        return {
            "severity": severity,
            "severity_reason": severity_reason,
            "severity_factors": severity_factors,
        }

    # -------------------------------------------------------------------------
    # 7. UNSTABLE_STACKING -> Leaning Stack Column (ORANGE)
    # -------------------------------------------------------------------------
    if b_str == WarehouseBehaviourType.UNSTABLE_STACKING.value or b_str == "UNSTABLE_STACKING":
        tilt_offset = float(kinematics.get("tilt_offset_px", 0.0))
        thresh = 35.0

        severity = WarehouseRiskTier.ORANGE.value
        severity_reason = (
            f"Stack column leaning with {tilt_offset:.1f}px lateral center-of-gravity displacement "
            f"(threshold: {thresh:.1f} px), risking toppling collapse."
        )
        severity_factors = {
            "behaviour": "UNSTABLE_STACKING",
            "primary_metric": "tilt_offset",
            "measured_value": round(tilt_offset, 1),
            "threshold": thresh,
            "unit": "px",
            "confidence": round(confidence, 3),
        }
        return {
            "severity": severity,
            "severity_reason": severity_reason,
            "severity_factors": severity_factors,
        }

    # -------------------------------------------------------------------------
    # 8. PLACED_OUTSIDE_DESIGNATED_AREA -> Walkway Obstruction (ORANGE)
    # -------------------------------------------------------------------------
    if b_str == WarehouseBehaviourType.PLACED_OUTSIDE_DESIGNATED_AREA.value or b_str == "PLACED_OUTSIDE_DESIGNATED_AREA":
        dwell = float(kinematics.get("dwell_time", kinematics.get("dwell_seconds", 3.0)))
        thresh = 3.0

        severity = WarehouseRiskTier.ORANGE.value
        severity_reason = (
            f"Material left stationary ({dwell:.1f}s dwell, threshold: {thresh:.1f}s) inside active pedestrian walkway, "
            f"obstructing safe transit."
        )
        severity_factors = {
            "behaviour": "PLACED_OUTSIDE_DESIGNATED_AREA",
            "primary_metric": "walkway_dwell_time",
            "measured_value": round(dwell, 1),
            "threshold": thresh,
            "unit": "s",
            "zone": "PEDESTRIAN_WALKWAY",
            "confidence": round(confidence, 3),
        }
        return {
            "severity": severity,
            "severity_reason": severity_reason,
            "severity_factors": severity_factors,
        }

    # -------------------------------------------------------------------------
    # 9. HANDLED_WITHOUT_EQUIPMENT -> Bulky Manual Carry (YELLOW)
    # -------------------------------------------------------------------------
    if b_str == WarehouseBehaviourType.HANDLED_WITHOUT_EQUIPMENT.value or b_str == "HANDLED_WITHOUT_EQUIPMENT":
        dist = float(kinematics.get("displacement", kinematics.get("carry_distance_px", 60.0)))
        area = float(kinematics.get("cargo_area", kinematics.get("package_area_px", 16000.0)))
        thresh = 60.0

        severity = WarehouseRiskTier.YELLOW.value
        severity_reason = (
            f"Bulky package ({area:.0f}px^2) transported manually for {dist:.0f}px without mechanical equipment (trolley/jack)."
        )
        severity_factors = {
            "behaviour": "HANDLED_WITHOUT_EQUIPMENT",
            "primary_metric": "carry_distance",
            "measured_value": round(dist, 1),
            "threshold": thresh,
            "unit": "px",
            "cargo_area_px": round(area, 1),
            "mhe_present": False,
            "confidence": round(confidence, 3),
        }
        return {
            "severity": severity,
            "severity_reason": severity_reason,
            "severity_factors": severity_factors,
        }

    # -------------------------------------------------------------------------
    # 10. PALLET_POSITIONED_INCORRECTLY -> Traffic Aisle Protrusion (YELLOW)
    # -------------------------------------------------------------------------
    if b_str == WarehouseBehaviourType.PALLET_POSITIONED_INCORRECTLY.value or b_str == "PALLET_POSITIONED_INCORRECTLY":
        protrusion = float(kinematics.get("protrusion_px", 25.0))
        thresh = 25.0

        severity = WarehouseRiskTier.YELLOW.value
        severity_reason = (
            f"Pallet misaligned, protruding {protrusion:.0f}px into active transit corridor beyond bay demarcations."
        )
        severity_factors = {
            "behaviour": "PALLET_POSITIONED_INCORRECTLY",
            "primary_metric": "corridor_protrusion",
            "measured_value": round(protrusion, 1),
            "threshold": thresh,
            "unit": "px",
            "confidence": round(confidence, 3),
        }
        return {
            "severity": severity,
            "severity_reason": severity_reason,
            "severity_factors": severity_factors,
        }

    # -------------------------------------------------------------------------
    # 11. STEPPING_ON_PRODUCT -> Handler Standing/Stepping on Carton (ORANGE)
    # -------------------------------------------------------------------------
    if b_str == WarehouseBehaviourType.STEPPING_ON_PRODUCT.value or b_str == "STEPPING_ON_PRODUCT":
        foot_overlap = float(kinematics.get("foot_overlap_px", kinematics.get("overlap_px", 35.0)))
        duration = float(kinematics.get("duration_s", 0.5))
        thresh = 20.0

        severity = WarehouseRiskTier.ORANGE.value
        severity_reason = (
            f"Handler foot/lower-body positioned directly on top surface of carton (overlap: {foot_overlap:.0f}px, "
            f"duration: {duration:.1f}s), causing crushing stress and structural deformation of packaging."
        )
        severity_factors = {
            "behaviour": "STEPPING_ON_PRODUCT",
            "primary_metric": "foot_surface_overlap",
            "measured_value": round(foot_overlap, 1),
            "threshold": thresh,
            "unit": "px",
            "duration_s": round(duration, 2),
            "confidence": round(confidence, 3),
        }
        return {
            "severity": severity,
            "severity_reason": severity_reason,
            "severity_factors": severity_factors,
        }

    # -------------------------------------------------------------------------
    # 12. PRODUCT_KICKED -> Kinetic Foot Impact / Foot Strike (ORANGE)
    # -------------------------------------------------------------------------
    if b_str == WarehouseBehaviourType.PRODUCT_KICKED.value or b_str == "PRODUCT_KICKED":
        vx = float(kinematics.get("horizontal_velocity", kinematics.get("product_vx", 0.0)))
        speed = float(kinematics.get("speed", kinematics.get("product_speed", abs(vx))))
        thresh = 45.0

        severity = WarehouseRiskTier.ORANGE.value
        severity_reason = (
            f"Product subjected to kinetic foot impact / kick (horizontal speed: {speed:.1f} px/s), "
            f"transmitting shock force into packaging and risking internal merchandise damage."
        )
        severity_factors = {
            "behaviour": "PRODUCT_KICKED",
            "primary_metric": "kick_speed",
            "measured_value": round(speed, 1),
            "threshold": thresh,
            "unit": "px/s",
            "interaction_source": "FOOT_INTERACTION",
            "confidence": round(confidence, 3),
        }
        return {
            "severity": severity,
            "severity_reason": severity_reason,
            "severity_factors": severity_factors,
        }

    # -------------------------------------------------------------------------
    # DEFAULT / SAFE HANDLING -> GREEN
    # -------------------------------------------------------------------------
    return {
        "severity": WarehouseRiskTier.GREEN.value,
        "severity_reason": "All handling kinematics and staging clearances remain within safe operational boundaries.",
        "severity_factors": {
            "behaviour": "SAFE_HANDLING",
            "primary_metric": "none",
            "measured_value": 0.0,
            "threshold": 0.0,
            "unit": "none",
            "confidence": round(confidence, 3),
        },
    }


# -----------------------------------------------------------------------------
# Score Penalties & Warehouse Compliance Index Calculations
# -----------------------------------------------------------------------------
SEVERITY_PENALTIES = {
    WarehouseRiskTier.RED.value: 10,
    WarehouseRiskTier.ORANGE.value: 5,
    WarehouseRiskTier.YELLOW.value: 2,
    WarehouseRiskTier.GREEN.value: 0,
}


def get_severity_penalty(severity: Union[WarehouseRiskTier, str]) -> int:
    """Returns the point deduction penalty for a given severity level."""
    s_val = severity.value if isinstance(severity, WarehouseRiskTier) else str(severity).upper()
    return SEVERITY_PENALTIES.get(s_val, 0)


def calculate_overall_compliance_score(events: list, baseline_score: float = 100.0) -> Dict[str, Any]:
    """
    Computes overall warehouse safety score and aggregate status based on logged events.

    Scoring Rule:
      Baseline: 100
      RED event: -10 pts
      ORANGE event: -5 pts
      YELLOW event: -2 pts
      GREEN event: 0 pts
      Score floor: 0

    Status Priority:
      Any RED -> RED
      Any ORANGE (no RED) -> ORANGE
      Any YELLOW (no RED/ORANGE) -> YELLOW
      Otherwise -> GREEN
    """
    red_count = 0
    orange_count = 0
    yellow_count = 0
    green_count = 0
    total_penalty = 0

    for e in events:
        sev = getattr(e, "severity", None)
        if sev is None and isinstance(e, dict):
            sev = e.get("severity", "GREEN")
        sev_str = str(sev).upper()

        if sev_str == "RED":
            red_count += 1
            total_penalty += SEVERITY_PENALTIES["RED"]
        elif sev_str == "ORANGE":
            orange_count += 1
            total_penalty += SEVERITY_PENALTIES["ORANGE"]
        elif sev_str == "YELLOW":
            yellow_count += 1
            total_penalty += SEVERITY_PENALTIES["YELLOW"]
        else:
            green_count += 1

    final_score = max(0.0, min(100.0, baseline_score - total_penalty))

    if red_count > 0:
        overall_status = "RED"
    elif orange_count > 0:
        overall_status = "ORANGE"
    elif yellow_count > 0:
        overall_status = "YELLOW"
    else:
        overall_status = "GREEN"

    return {
        "safety_score": round(final_score, 1),
        "overall_status": overall_status,
        "counts": {
            "RED": red_count,
            "ORANGE": orange_count,
            "YELLOW": yellow_count,
            "GREEN": green_count,
            "total": len(events),
        },
    }

