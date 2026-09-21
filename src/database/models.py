"""
Database Models & Dataclasses
-----------------------------
Structured entities representing records in the WatchGuard Vision database.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class User:
    id: Optional[int]
    username: str
    full_name: str
    role: str
    access_level: int  # 1 = Basic, 2 = Staff, 3 = Admin/Security
    created_at: str = ""


@dataclass
class FaceRegistration:
    id: Optional[int]
    user_id: int
    face_encoding: bytes  # Binary or serialized vector
    image_path: str
    registered_at: str = ""
    is_active: bool = True


@dataclass
class DetectedObjectRecord:
    id: Optional[int]
    session_id: str
    label: str
    confidence: float
    bbox_json: str
    timestamp: str = ""


@dataclass
class SecurityEventRecord:
    id: Optional[int]
    event_type: str
    risk_level: str  # GREEN, YELLOW, ORANGE, RED
    description: str
    evidence_frame_path: Optional[str] = None
    person_name: Optional[str] = None
    object_summary: Optional[str] = None
    metadata_json: Optional[str] = None
    timestamp: str = ""


@dataclass
class OCRDocumentRecord:
    id: Optional[int]
    raw_text: str
    sensitive_keywords_found: str
    document_status: str  # e.g., 'CONFIDENTIAL', 'PUBLIC', 'RESTRICTED'
    snapshot_path: Optional[str] = None
    timestamp: str = ""


@dataclass
class SystemLogRecord:
    id: Optional[int]
    level: str  # INFO, WARNING, ERROR, CRITICAL
    module: str
    message: str
    timestamp: str = ""


@dataclass
class IncidentRecord:
    incident_id: str
    risk_level: str
    state: str  # DETECTED, VERIFIED, ALERTED, ACKNOWLEDGED, RESOLVED
    policy_code: str
    reason: str
    zone: str
    created_at: str
    updated_at: str
    event_id: Optional[int] = None
    track_id: Optional[int] = None
    person_name: Optional[str] = None
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None
    operator_action: Optional[str] = None
    evidence_package_json: Optional[str] = None
    id: Optional[int] = None


@dataclass
class WarehouseBehaviourRecord:
    """Godrej Warehouse Handling & Damage Prevention Event Record."""
    event_id: str
    behaviour_type: str
    risk_level: str
    confidence: float
    start_timestamp: str
    end_timestamp: str
    duration_seconds: float
    observed_behaviour: str
    potential_risk: str
    recommended_action: str
    product_track_id: Optional[int] = None
    person_track_id: Optional[int] = None
    severity_reason: Optional[str] = None
    severity_factors_json: Optional[str] = None
    evidence_frame_path: Optional[str] = None
    video_source: Optional[str] = None
    status: str = "UNRESOLVED"
    operator_action: Optional[str] = None
    resolved_at: Optional[str] = None
    metadata_json: Optional[str] = None
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializes record to clean JSON-serializable dictionary."""
        import json
        from pathlib import Path
        d = asdict(self)
        is_sim = False
        meta_dict = {}
        if self.metadata_json:
            try:
                meta_dict = json.loads(self.metadata_json)
                is_sim = bool(meta_dict.get("is_simulated") or meta_dict.get("simulated", False))
            except Exception:
                meta_dict = {}
        if self.event_id and self.event_id.startswith("SIM-"):
            is_sim = True
        d["metadata"] = meta_dict
        d["is_simulated"] = is_sim

        factors_dict = None
        if self.severity_factors_json:
            try:
                factors_dict = json.loads(self.severity_factors_json)
            except Exception:
                factors_dict = None
        d["severity_factors"] = factors_dict

        # Assign standard loading bay from metadata or behaviour category
        bay = meta_dict.get("loading_bay") or meta_dict.get("bay")
        if not bay:
            b_upper = str(self.behaviour_type).upper()
            if "WALKWAY" in b_upper or "OUTSIDE" in b_upper:
                bay = "Transit Corridor (Bay 2)"
            elif "STACK" in b_upper or "RACK" in b_upper:
                bay = "Storage Racking (Bay 3)"
            elif "PALLET" in b_upper or "LOADING" in b_upper:
                bay = "Dispatch Dock (Bay 4)"
            else:
                bay = "Staging Bay (Bay 1)"
        d["loading_bay"] = bay

        # Normalize filesystem evidence path to web API route
        if self.evidence_frame_path:
            p = str(self.evidence_frame_path)
            if not p.startswith("/api/evidence/"):
                fname = Path(p).name
                d["evidence_frame_path"] = f"/api/evidence/{fname}"
        return d
