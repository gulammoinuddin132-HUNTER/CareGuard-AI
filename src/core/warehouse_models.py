"""
Godrej AI Video Intelligence for Warehouse Handling - Data Models
------------------------------------------------------------------
Structured entities and enums for warehouse object tracking, temporal kinematics,
and damage-prevention behaviour events following the Responsible AI paradigm:
  Observed Behaviour -> Potential Risk -> Corrective Action
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import time
from typing import Dict, Any, List, Optional, Tuple


class WarehouseObjectCategory(str, Enum):
    """Semantic category for warehouse visual entities."""
    PRODUCT = "PRODUCT"        # Cartons, boxes, packaged goods, parcels
    PALLET = "PALLET"          # Wooden or plastic pallets
    MHE = "MHE"                # Material Handling Equipment (trolleys, pallet jacks, forklifts)
    PERSON = "PERSON"          # Warehouse operators, handlers
    INFRASTRUCTURE = "INFRASTRUCTURE"  # Racks, bays, floor markings
    OTHER = "OTHER"


class ProductInteractionState(str, Enum):
    """Spatial and physical interaction state of a tracked warehouse product."""
    FREE = "FREE"                      # Unheld, resting or moving independently on ground/surface
    HELD = "HELD"                      # Held/carried by handler; motion strongly correlated with handler
    ADJACENT = "ADJACENT"              # Near a handler, but not actively carried or towed
    TOWED = "TOWED"                    # Grounded on floor while being pulled/dragged by handler
    AIRBORNE = "AIRBORNE"              # Unsupported by handler, not grounded, in ballistic/free-fall flight
    GROUND_CONTACT = "GROUND_CONTACT"  # Touching floor plane, landing, or grounded settlement
    ROLLING = "ROLLING"                # Grounded, pivoting / rotating across ground plane
    STEPPED_ON = "STEPPED_ON"          # Under operator foot / bodily weight load


class WarehouseBehaviourType(str, Enum):
    """10+ Target warehouse handling and damage-risk behaviours."""
    PRODUCT_DROPPED = "PRODUCT_DROPPED"
    PRODUCT_DRAGGED = "PRODUCT_DRAGGED"
    ROUGH_HANDLING = "ROUGH_HANDLING"
    INCORRECT_STACKING = "INCORRECT_STACKING"
    UNSTABLE_STACKING = "UNSTABLE_STACKING"
    PLACED_OUTSIDE_DESIGNATED_AREA = "PLACED_OUTSIDE_DESIGNATED_AREA"
    HANDLED_WITHOUT_EQUIPMENT = "HANDLED_WITHOUT_EQUIPMENT"
    PALLET_POSITIONED_INCORRECTLY = "PALLET_POSITIONED_INCORRECTLY"
    MATERIAL_PUSHED_THROWN = "MATERIAL_PUSHED_THROWN"
    UNSAFE_LOADING_SEQUENCE = "UNSAFE_LOADING_SEQUENCE"
    STEPPING_ON_PRODUCT = "STEPPING_ON_PRODUCT"
    PRODUCT_KICKED = "PRODUCT_KICKED"

    @property
    def display_title(self) -> str:
        titles = {
            WarehouseBehaviourType.PRODUCT_DROPPED: "Product Dropped / Free-Fall Impact",
            WarehouseBehaviourType.PRODUCT_DRAGGED: "Product Dragged Along Floor",
            WarehouseBehaviourType.ROUGH_HANDLING: "Rough Handling / Excessive Impact",
            WarehouseBehaviourType.INCORRECT_STACKING: "Incorrect Stacking / Overhang Load",
            WarehouseBehaviourType.UNSTABLE_STACKING: "Unstable / Leaning Stack",
            WarehouseBehaviourType.PLACED_OUTSIDE_DESIGNATED_AREA: "Material Left in Walkway / Exit",
            WarehouseBehaviourType.HANDLED_WITHOUT_EQUIPMENT: "Manual Carry of Heavy Cargo (No Trolley)",
            WarehouseBehaviourType.PALLET_POSITIONED_INCORRECTLY: "Misaligned / Blocking Pallet Placement",
            WarehouseBehaviourType.MATERIAL_PUSHED_THROWN: "Material Pushed / Thrown",
            WarehouseBehaviourType.UNSAFE_LOADING_SEQUENCE: "Unsafe Loading / Unloading Order",
            WarehouseBehaviourType.STEPPING_ON_PRODUCT: "Stepping on Product / Walking on Cartons",
            WarehouseBehaviourType.PRODUCT_KICKED: "Product Kicked / Foot Impact",
        }
        return titles.get(self, self.value)


@dataclass
class KinematicState:
    """Snapshot of spatial and motion state of an object at a specific instant."""
    timestamp: float
    bbox: Tuple[int, int, int, int]          # (x, y, w, h)
    centroid: Tuple[float, float]            # (cx, cy)
    velocity: Tuple[float, float] = (0.0, 0.0) # (vx, vy) in pixels/sec
    speed: float = 0.0                       # Euclidean speed in pixels/sec
    vertical_accel: float = 0.0              # dv_y / dt in pixels/sec^2
    bottom_y: int = 0                        # y + h (ground contact point)
    elevation_ratio: float = 0.0             # 0.0 (ground level) to 1.0 (top of frame)
    is_grounded: bool = False

    def __post_init__(self):
        if self.bottom_y == 0 and len(self.bbox) == 4:
            self.bottom_y = self.bbox[1] + self.bbox[3]


@dataclass
class TrackedEntity:
    """Persistent tracked entity across video frames with kinematic history."""
    track_id: int
    class_id: int
    label: str
    category: WarehouseObjectCategory
    confidence: float
    current_bbox: Tuple[int, int, int, int]
    first_seen: float
    last_seen: float
    last_detection_time: float = 0.0
    history: List[KinematicState] = field(default_factory=list)
    missed_frames: int = 0
    is_confirmed: bool = False
    associated_person_id: Optional[int] = None
    associated_product_ids: List[int] = field(default_factory=list)
    carrying_state: str = "NONE"             # Backward compatible string: "NONE", "HOLDING", "TOWING", "ADJACENT"
    interaction_state: ProductInteractionState = ProductInteractionState.FREE
    interaction_history: List[ProductInteractionState] = field(default_factory=list)
    interaction_source: Optional[str] = None # "HAND_INTERACTION", "FOOT_INTERACTION", "UNKNOWN"
    raw_detection_bbox: Optional[Tuple[int, int, int, int]] = None
    raw_bbox: Optional[Tuple[int, int, int, int]] = None
    validated_bbox: Optional[Tuple[int, int, int, int]] = None
    tracked_bbox: Optional[Tuple[int, int, int, int]] = None
    smoothed_bbox: Optional[Tuple[int, int, int, int]] = None
    is_predicted: bool = False               # True when bbox updated via motion prediction instead of detection
    relative_motion: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # (rel_dx, rel_dy, rel_speed)
    detection_confidence: float = 0.0
    behaviour_confidence: float = 0.0
    localization_quality: float = 1.0        # 0.0 to 1.0 geometric stability score
    carry_confidence: float = 0.0            # 0.0 to 1.0 confidence in HELD/carried state
    validation_status: str = "PASS"          # "PASS" | "REJECT"
    validation_reason: str = "VALID_GEOMETRY"# Diagnostic explanation
    carry_telemetry: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.detection_confidence == 0.0:
            self.detection_confidence = self.confidence
        if self.raw_bbox is None and self.raw_detection_bbox is not None:
            self.raw_bbox = self.raw_detection_bbox
        elif self.raw_bbox is None and self.current_bbox is not None:
            self.raw_bbox = self.current_bbox
        if self.validated_bbox is None:
            self.validated_bbox = self.current_bbox
        if self.tracked_bbox is None:
            self.tracked_bbox = self.current_bbox
        if self.smoothed_bbox is None:
            self.smoothed_bbox = self.current_bbox

    @property
    def current_state(self) -> Optional[KinematicState]:
        return self.history[-1] if self.history else None

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.last_seen - self.first_seen)

    def get_recent_history(self, window_seconds: float = 2.0) -> List[KinematicState]:
        """Returns kinematic states within the specified sliding time window."""
        if not self.history:
            return []
        cutoff = self.last_seen - window_seconds
        return [s for s in self.history if s.timestamp >= cutoff]

    def get_recent_interaction_history(self, count: int = 5) -> List[ProductInteractionState]:
        """Returns the most recent interaction states."""
        return self.interaction_history[-count:] if self.interaction_history else []


class EventState(str, Enum):
    """Lifecycle state machine for warehouse behaviour events."""
    CANDIDATE = "CANDIDATE"
    VERIFIED = "VERIFIED"
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"


@dataclass
class WarehouseBehaviourEvent:
    """
    Structured warehouse damage-risk or handling quality event.
    Enforces the 3-tier Responsible AI explainability format:
      1. Observed Behaviour
      2. Potential Risk
      3. Recommended Corrective Action
    """
    event_id: str
    behaviour_type: WarehouseBehaviourType
    risk_level: str                          # "GREEN", "YELLOW", "ORANGE", "RED"
    confidence: float
    start_timestamp: str
    end_timestamp: str
    duration_seconds: float
    observed_behaviour: str
    potential_risk: str
    recommended_action: str
    product_track_id: Optional[int] = None
    person_track_id: Optional[int] = None
    product_bbox: Optional[Tuple[int, int, int, int]] = None
    person_bbox: Optional[Tuple[int, int, int, int]] = None
    focus_bbox: Optional[Tuple[int, int, int, int]] = None
    product_bbox_at_event: Optional[Tuple[int, int, int, int]] = None
    handler_bbox_at_event: Optional[Tuple[int, int, int, int]] = None
    focus_bbox_at_event: Optional[Tuple[int, int, int, int]] = None
    handler_relationship: Optional[str] = "ISOLATED"
    interaction_source: Optional[str] = None # "HAND_INTERACTION", "FOOT_INTERACTION", "UNKNOWN"
    severity_reason: Optional[str] = None
    severity_factors: Optional[Dict[str, Any]] = None
    evidence_frame_path: Optional[str] = None
    video_source: Optional[str] = None
    detection_confidence: float = 0.0
    behaviour_confidence: float = 0.0
    interaction_state_sequence: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    temporal_trace: Optional[Dict[str, Any]] = None
    kinematics_trace: Optional[Dict[str, Any]] = None
    rule_trace: Optional[Dict[str, Any]] = None
    debug_trace: Optional[Dict[str, Any]] = None
    state: EventState = EventState.ACTIVE
    activated_at: Optional[float] = None
    last_observed_time: Optional[float] = None
    resolved_at: Optional[float] = None
    grace_period_seconds: float = 4.0
    id: Optional[int] = None

    def __post_init__(self):
        if self.detection_confidence == 0.0:
            self.detection_confidence = self.confidence
        if self.behaviour_confidence == 0.0:
            self.behaviour_confidence = self.confidence
        if self.product_bbox_at_event is None and self.product_bbox is not None:
            self.product_bbox_at_event = self.product_bbox
        if self.handler_bbox_at_event is None and self.person_bbox is not None:
            self.handler_bbox_at_event = self.person_bbox
        if self.focus_bbox_at_event is None and self.focus_bbox is not None:
            self.focus_bbox_at_event = self.focus_bbox

    @property
    def severity(self) -> str:
        return self.risk_level

    def to_dict(self) -> Dict[str, Any]:
        from pathlib import Path
        d = asdict(self)
        d["behaviour_type"] = self.behaviour_type.value if isinstance(self.behaviour_type, WarehouseBehaviourType) else str(self.behaviour_type)
        d["state"] = self.state.value if isinstance(self.state, EventState) else str(self.state)
        is_sim = False
        if self.event_id and self.event_id.startswith("SIM-"):
            is_sim = True
        elif isinstance(self.metadata, dict):
            is_sim = bool(self.metadata.get("is_simulated") or self.metadata.get("simulated", False))
        d["is_simulated"] = is_sim

        # Normalize filesystem evidence path to web API route
        if self.evidence_frame_path:
            p = str(self.evidence_frame_path)
            if not p.startswith("/api/evidence/"):
                fname = Path(p).name
                d["evidence_frame_path"] = f"/api/evidence/{fname}"
        return d

