"""
src/api/routes/simulator.py
---------------------------
1-Click warehouse scenario simulator allowing evaluators and supervisors
to inject synthetic sequence demonstrations for all 10 warehouse behaviours.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Optional
import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, Form
from src.api.state import CareGuardBackendState
from src.core.warehouse_models import WarehouseBehaviourType, WarehouseBehaviourEvent
from src.core.warehouse_risk_policy import calculate_risk_severity
from config import DATA_DIR

router = APIRouter(prefix="/api/simulator", tags=["Simulator"])

PRESETS = {
    1: (
        WarehouseBehaviourType.PRODUCT_DROPPED,
        "RED",
        "Package (Track #101) underwent sudden free-fall descent (420 px/s, ~1.1m drop) and impacted floor.",
        "Kinetic impact shock may cause internal mechanical stress or damage fragile contents.",
        "Quarantine and inspect package contents before staging or dispatch; verify team lift for heavy loads.",
    ),
    2: (
        WarehouseBehaviourType.PRODUCT_DRAGGED,
        "ORANGE",
        "Package (Track #102) dragged along floor for 115px without vertical clearance or trolley.",
        "Floor friction abrasion weakens bottom carton seams and exposes goods to surface contaminants.",
        "Use hand trolley, BOPT/pallet jack, or two-person carry; avoid pulling cartons across concrete.",
    ),
    3: (
        WarehouseBehaviourType.ROUGH_HANDLING,
        "ORANGE",
        "Package (Track #103) experienced sharp impact deceleration (480 px/s^2) during placement/handling.",
        "Abrupt impact shock risks internal component dislocation or carton wall crush.",
        "Place packages down with smooth controlled motion; use impact-absorbing staging mats.",
    ),
    4: (
        WarehouseBehaviourType.INCORRECT_STACKING,
        "ORANGE",
        "Larger/heavier package #104 (area: 8200px^2) stacked on top of smaller package #105 (area: 3600px^2).",
        "Excessive top load risks crushing lower cartons and destabilizing stack column.",
        "Restack column with heaviest and widest base items at the bottom.",
    ),
    5: (
        WarehouseBehaviourType.UNSTABLE_STACKING,
        "ORANGE",
        "Stack column tilting with 38px lateral center offset between package #106 and #107.",
        "Center-of-mass misalignment creates tipping instability, risking column toppling.",
        "Re-align and straighten stack column immediately; interlock stacked layers.",
    ),
    6: (
        WarehouseBehaviourType.PLACED_OUTSIDE_DESIGNATED_AREA,
        "ORANGE",
        "Package (Track #108) left stationary (3.2s dwell) inside pedestrian walkway corridor.",
        "Walkway obstruction creates pedestrian trip hazard and emergency egress bottlenecks.",
        "Relocate package immediately to marked staging bay or storage pallet; keep walkways clear.",
    ),
    7: (
        WarehouseBehaviourType.HANDLED_WITHOUT_EQUIPMENT,
        "YELLOW",
        "Large package (Track #109, area: 13500px^2) transported manually 85px without trolley or MHE.",
        "Extended manual carry of bulky loads increases worker fatigue and dropped cargo risk.",
        "Deploy hand trolley, platform truck, or two-person team lift for heavy/bulk items.",
    ),
    8: (
        WarehouseBehaviourType.PALLET_POSITIONED_INCORRECTLY,
        "YELLOW",
        "Pallet (Track #110) positioned misaligned, protruding 42px into transit walkway.",
        "Aisle protrusion exposes pallet runners to MHE corner collision and snagging.",
        "Re-position pallet flush within designated staging bay lines.",
    ),
    9: (
        WarehouseBehaviourType.MATERIAL_PUSHED_THROWN,
        "RED",
        "Package (Track #111) thrown/launched with high horizontal velocity (240 px/s) in free flight.",
        "Airborne projectile trajectory risks impact damage to cargo and surrounding personnel.",
        "Carry and place packages with two hands; strictly enforce zero-throwing safety policy.",
    ),
    10: (
        WarehouseBehaviourType.UNSAFE_LOADING_SEQUENCE,
        "RED",
        "Bottom package #112 pulled from stack while upper package #113 was still positioned overhead.",
        "Foundational removal leaves overhead load unsupported, risking abrupt drop onto handler.",
        "De-stack packages strictly top-to-bottom; never remove lower base units first.",
    ),
}


def _generate_simulator_evidence(preset_id: int, b_type: WarehouseBehaviourType, risk_lvl: str, event_id: str) -> str:
    """Generates an annotated synthetic evidence snapshot frame and writes it to disk."""
    evidence_dir = DATA_DIR / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    filename = f"sim_evidence_{preset_id}_{event_id}.jpg"
    filepath = evidence_dir / filename

    img = np.full((360, 640, 3), (22, 26, 32), dtype=np.uint8)

    # Grid background pattern
    for x in range(0, 640, 40):
        cv2.line(img, (x, 0), (x, 360), (28, 33, 42), 1)
    for y in range(0, 360, 40):
        cv2.line(img, (0, y), (640, y), (28, 33, 42), 1)

    # Floor plane
    cv2.line(img, (20, 290), (620, 290), (45, 55, 70), 2)
    cv2.putText(img, "WAREHOUSE FLOOR BOUNDARY", (25, 305), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (75, 85, 100), 1)

    # Risk banner color
    color_map = {
        "RED": (40, 40, 220),
        "ORANGE": (20, 130, 235),
        "YELLOW": (20, 195, 235),
        "GREEN": (50, 180, 50),
    }
    banner_color = color_map.get(risk_lvl, (20, 130, 235))

    # Top header banner
    cv2.rectangle(img, (0, 0), (640, 38), (14, 18, 24), -1)
    cv2.rectangle(img, (0, 0), (8, 38), banner_color, -1)
    cv2.putText(img, f"SIMULATED SCENARIO  |  {b_type.value}", (20, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    cv2.putText(img, f"EVENT ID: {event_id}  |  RISK: {risk_lvl}  |  PRESET #{preset_id}", (20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (160, 175, 190), 1)

    # Draw simulated scenario objects
    if preset_id in (4, 5, 10):
        # Stacking scenarios: two stacked items
        cv2.rectangle(img, (250, 180), (390, 280), (220, 140, 30), 2)
        cv2.putText(img, "PRODUCT #104 (BASE)", (255, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (220, 140, 30), 1)
        cv2.rectangle(img, (240, 80), (400, 180), (30, 70, 220), 2)
        cv2.putText(img, "PRODUCT #105 (UPPER)", (245, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (30, 70, 220), 1)
    elif preset_id == 8:
        # Pallet misalignment
        cv2.rectangle(img, (200, 200), (440, 285), (20, 180, 220), 2)
        cv2.putText(img, "PALLET #110 (MISALIGNED)", (210, 245), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (20, 180, 220), 1)
    else:
        # Handler + Product interaction
        cv2.rectangle(img, (140, 90), (240, 285), (220, 170, 40), 2)
        cv2.putText(img, "HANDLER #1", (145, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (220, 170, 40), 1)

        cv2.rectangle(img, (280, 170), (410, 285), banner_color, 2)
        cv2.putText(img, f"PRODUCT #{100 + preset_id}", (285, 195), cv2.FONT_HERSHEY_SIMPLEX, 0.40, banner_color, 1)

        # Motion arrow
        cv2.arrowedLine(img, (240, 190), (280, 210), (0, 220, 255), 2, tipLength=0.3)

    # Forensic bottom strip
    cv2.rectangle(img, (0, 325), (640, 360), (14, 18, 24), -1)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(img, f"CAREGUARD AI FORENSIC EVIDENCE  |  {ts}  |  STATUS: SIMULATED SCENARIO", (15, 347), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (130, 145, 165), 1)

    cv2.imwrite(str(filepath), img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    return str(filepath)


@router.post("/trigger")
def trigger_simulation(preset_id: int = Form(...)):
    """Triggers an instantaneous synthetic demonstration for any of the 10 target behaviours."""
    if preset_id not in PRESETS:
        raise HTTPException(status_code=400, detail=f"Invalid preset ID {preset_id}. Choose between 1 and 10.")

    b_type, risk_lvl, obs, risk_desc, rec_act = PRESETS[preset_id]
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    event_id = f"SIM-{b_type.name[:4]}-{datetime.now().strftime('%H%M%S')}"

    backend = CareGuardBackendState.get_instance()

    # Generate synthetic decodable evidence frame
    evidence_path = _generate_simulator_evidence(preset_id, b_type, risk_lvl, event_id)

    # Forensic audit traces for simulated scenario
    temp_trace = {
        "session_id": backend.active_session_id,
        "start_frame": 0,
        "trigger_frame": 1,
        "end_frame": 1,
        "timestamp_start": now_iso,
        "timestamp_trigger": now_iso,
        "timestamp_end": now_iso,
        "duration_seconds": 1.5,
        "evidence_file": Path(evidence_path).name,
    }

    kin_trace = {
        "product_vx": 120.0 if preset_id == 9 else 0.0,
        "product_vy": 420.0 if preset_id == 1 else 0.0,
        "product_speed": 420.0 if preset_id == 1 else (240.0 if preset_id == 9 else 45.0),
        "product_acceleration": 480.0 if preset_id == 3 else 0.0,
        "product_grounded": preset_id in (2, 6, 8),
        "product_elevation": 0.35 if preset_id in (1, 9) else 0.0,
        "product_displacement": 115.0 if preset_id == 2 else 0.0,
        "handler_product_distance": 45.0,
        "handler_product_relationship": "HOLDING" if preset_id in (1, 7, 10) else "TOWING",
    }

    rule_trace = {
        "trigger_conditions": {
            "preset_id": preset_id,
            "simulated_scenario": b_type.value,
            "risk_level": risk_lvl,
            "is_simulated": True,
        },
        "failed_conditions": {},
        "evaluation_result": True,
    }

    debug_trace = {
        "event_id": event_id,
        "session_id": backend.active_session_id,
        "source": "SCENARIO_SIMULATOR",
        "handler_track_id": 1,
        "product_track_id": 100 + preset_id,
        "relationship": "HOLDING" if preset_id in (1, 7, 10) else "TOWING",
        "kinematics": kin_trace,
        "trigger_conditions": rule_trace["trigger_conditions"],
        "failed_conditions": {},
        "behaviour": b_type.value,
        "risk": risk_lvl,
    }

    sev_info = calculate_risk_severity(
        b_type,
        kinematics=kin_trace,
        trigger_conditions=rule_trace["trigger_conditions"],
        confidence=0.96,
    )
    risk_lvl = sev_info["severity"]
    sev_reason = sev_info["severity_reason"]
    sev_factors = sev_info["severity_factors"]

    # Log to DB
    backend.db.log_warehouse_event(
        event_id=event_id,
        behaviour_type=b_type.value,
        risk_level=risk_lvl,
        confidence=0.96,
        start_timestamp=now_iso,
        end_timestamp=now_iso,
        duration_seconds=1.5,
        observed_behaviour=obs,
        potential_risk=risk_desc,
        recommended_action=rec_act,
        product_track_id=100 + preset_id,
        person_track_id=1,
        severity_reason=sev_reason,
        severity_factors=sev_factors,
        evidence_frame_path=evidence_path,
        video_source="SCENARIO_SIMULATOR",
        metadata={
            "preset_id": preset_id,
            "simulated": True,
            "is_simulated": True,
            "session_id": backend.active_session_id,
        },
    )

    sim_event = WarehouseBehaviourEvent(
        event_id=event_id,
        behaviour_type=b_type,
        risk_level=risk_lvl,
        confidence=0.96,
        start_timestamp=now_iso,
        end_timestamp=now_iso,
        duration_seconds=1.5,
        observed_behaviour=obs,
        potential_risk=risk_desc,
        recommended_action=rec_act,
        product_track_id=100 + preset_id,
        person_track_id=1,
        severity_reason=sev_reason,
        severity_factors=sev_factors,
        evidence_frame_path=evidence_path,
        video_source="SCENARIO_SIMULATOR",
        temporal_trace=temp_trace,
        kinematics_trace=kin_trace,
        rule_trace=rule_trace,
        debug_trace=debug_trace,
        metadata={
            "preset_id": preset_id,
            "simulated": True,
            "is_simulated": True,
            "session_id": backend.active_session_id,
        },
    )

    with backend._lock:
        backend.latest_event = sim_event
        backend.current_risk_level = risk_lvl
        backend.active_event_last_triggered_time = time.time()

    return {
        "status": "ok",
        "preset_id": preset_id,
        "event_id": event_id,
        "behaviour_type": b_type.value,
        "risk_level": risk_lvl,
        "observed_behaviour": obs,
        "potential_risk": risk_desc,
        "recommended_action": rec_act,
        "evidence_frame_path": f"/api/evidence/{Path(evidence_path).name}",
        "message": f"Successfully simulated '{b_type.value}' scenario ({risk_lvl} Risk).",
    }
