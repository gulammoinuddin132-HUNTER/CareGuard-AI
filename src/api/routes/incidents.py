"""
src/api/routes/incidents.py
---------------------------
Warehouse incident management, search/filtering, and detailed evidence review.
"""

from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException, Form
from src.api.state import CareGuardBackendState

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])


@router.get("")
def list_incidents(
    risk_level: Optional[str] = Query(None),
    behaviour_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Lists warehouse handling behaviour events with optional filtering."""
    backend = CareGuardBackendState.get_instance()
    records = backend.db.get_recent_warehouse_events(
        limit=limit,
        risk_level=risk_level if risk_level != "ALL" else None,
        behaviour_type=behaviour_type if behaviour_type != "ALL" else None,
    )

    results = [r.to_dict() for r in records]

    # In-memory text search filtering if query provided
    if search:
        s_lower = search.lower()
        results = [
            r for r in results
            if (s_lower in r["event_id"].lower()
                or s_lower in r["behaviour_type"].lower()
                or s_lower in r["observed_behaviour"].lower()
                or s_lower in r["potential_risk"].lower()
                or s_lower in r["recommended_action"].lower())
        ]

    return {"count": len(results), "incidents": results}


@router.get("/{event_id}")
def get_incident_details(event_id: str):
    """Retrieves full details, evidence frame path, and kinematics for a specific incident."""
    backend = CareGuardBackendState.get_instance()
    record = backend.db.get_warehouse_event_by_id(event_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Incident {event_id} not found.")

    return record.to_dict()


@router.post("/{event_id}/action")
def log_supervisor_action(
    event_id: str,
    action_note: str = Form(...),
    supervisor_name: str = Form("Supervisor on Duty"),
):
    """Records an intervention action or corrective training note for an incident."""
    backend = CareGuardBackendState.get_instance()
    record = backend.db.get_warehouse_event_by_id(event_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Incident {event_id} not found.")

    backend.db.log_warehouse_event_action(event_id, action_note, supervisor_name)

    return {
        "status": "RESOLVED",
        "event_id": event_id,
        "action_recorded": action_note,
        "supervisor": supervisor_name,
        "message": f"Action logged successfully for incident {event_id}.",
    }
