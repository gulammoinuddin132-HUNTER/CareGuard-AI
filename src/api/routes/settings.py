"""
src/api/routes/settings.py
--------------------------
Configurable warehouse zones, kinematic thresholds, and data retention policies.
"""

from typing import Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter
from config import (
    DEFAULT_ZONES,
    WAREHOUSE_FLOOR_Y_RATIO,
    WAREHOUSE_DROP_VELOCITY_THRESHOLD,
    WAREHOUSE_DRAG_SPEED_THRESHOLD,
    WAREHOUSE_ROUGH_IMPACT_DECEL_THRESHOLD,
    WAREHOUSE_INCORRECT_STACK_AREA_RATIO,
    WAREHOUSE_UNSTABLE_STACK_TILT_PX,
    WAREHOUSE_WALKWAY_DWELL_SECONDS,
    WAREHOUSE_HEAVY_CARGO_AREA_PX,
    WAREHOUSE_PALLET_PROTRUSION_PX,
    WAREHOUSE_THROW_HORIZONTAL_VELOCITY,
)

router = APIRouter(prefix="/api/settings", tags=["Settings"])


class SettingsPayload(BaseModel):
    floor_y_ratio: float = WAREHOUSE_FLOOR_Y_RATIO
    drop_velocity_threshold: float = WAREHOUSE_DROP_VELOCITY_THRESHOLD
    drag_speed_threshold: float = WAREHOUSE_DRAG_SPEED_THRESHOLD
    rough_impact_decel_threshold: float = WAREHOUSE_ROUGH_IMPACT_DECEL_THRESHOLD
    incorrect_stack_area_ratio: float = WAREHOUSE_INCORRECT_STACK_AREA_RATIO
    unstable_stack_tilt_px: float = WAREHOUSE_UNSTABLE_STACK_TILT_PX
    walkway_dwell_seconds: float = WAREHOUSE_WALKWAY_DWELL_SECONDS
    heavy_cargo_area_px: int = WAREHOUSE_HEAVY_CARGO_AREA_PX
    pallet_protrusion_px: float = WAREHOUSE_PALLET_PROTRUSION_PX
    throw_velocity_threshold: float = WAREHOUSE_THROW_HORIZONTAL_VELOCITY


CURRENT_SETTINGS = SettingsPayload()


@router.get("")
def get_settings():
    """Returns current configurable warehouse zones and kinematic parameters."""
    return {
        "zones": DEFAULT_ZONES,
        "kinematics": CURRENT_SETTINGS.model_dump(),
        "privacy_policy": {
            "facial_recognition_enabled": False,
            "employee_penalties_enabled": False,
            "data_retention_days": 30,
            "purpose": "Material handling quality and damage prevention only",
        },
    }


@router.post("")
def update_settings(payload: SettingsPayload):
    """Updates active warehouse kinematic thresholds."""
    global CURRENT_SETTINGS
    CURRENT_SETTINGS = payload
    return {"status": "ok", "message": "Settings updated successfully.", "updated": CURRENT_SETTINGS.model_dump()}


@router.post("/reset-database")
def reset_database_endpoint():
    """Resets the active demo database, creates a timestamped backup, and returns fresh KPI baseline."""
    from scripts.reset_demo_database import reset_demo_database
    res = reset_demo_database(create_backup=True)
    return res

