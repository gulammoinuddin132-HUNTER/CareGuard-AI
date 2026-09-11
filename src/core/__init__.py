"""
CareGuard AI - Core AI, Perception, Tracking & Behaviour Package
----------------------------------------------------------------
"""

from src.core.warehouse_models import (
    WarehouseObjectCategory,
    ProductInteractionState,
    WarehouseBehaviourType,
    WarehouseBehaviourEvent,
    TrackedEntity,
    KinematicState,
    EventState,
)
from src.core.warehouse_tracker import WarehouseObjectTracker
from src.core.warehouse_behaviour_engine import TemporalWarehouseBehaviourEngine
from src.core.warehouse_risk_policy import calculate_risk_severity, WarehouseRiskTier
from src.core.warehouse_class_mapper import WarehouseClassMapper
from src.core.warehouse_evidence_cropper import (
    compute_interaction_crop_box,
    save_evidence_snapshot,
    create_interaction_evidence_crop,
    log_event_geometry,
)
from src.core.object_detection import ObjectDetectionEngine

__all__ = [
    "WarehouseObjectCategory",
    "ProductInteractionState",
    "WarehouseBehaviourType",
    "WarehouseBehaviourEvent",
    "TrackedEntity",
    "KinematicState",
    "EventState",
    "WarehouseObjectTracker",
    "TemporalWarehouseBehaviourEngine",
    "calculate_risk_severity",
    "WarehouseRiskTier",
    "WarehouseClassMapper",
    "compute_interaction_crop_box",
    "save_evidence_snapshot",
    "create_interaction_evidence_crop",
    "log_event_geometry",
    "ObjectDetectionEngine",
]
