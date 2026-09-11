"""
src/api/routes/overview.py
--------------------------
Warehouse supervisor command center overview KPIs, risk distribution,
handling quality score, and active loading bay rankings.
"""

from fastapi import APIRouter
from src.api.state import CareGuardBackendState

router = APIRouter(prefix="/api/overview", tags=["Overview"])


@router.get("")
def get_overview_data():
    """Returns high-level supervisor metrics, risk distribution, trends, and recent incidents."""
    backend = CareGuardBackendState.get_instance()
    summary = backend.db.get_warehouse_stats_summary()
    recent_events = backend.db.get_recent_warehouse_events(limit=8)
    behaviour_dist = backend.db.get_warehouse_behaviour_distribution()
    hourly_trends = backend.db.get_warehouse_hourly_trends()
    bay_stats = backend.db.get_warehouse_bay_stats()
    prevention = backend.db.get_warehouse_prevention_metrics()
    shift_stats = backend.db.get_warehouse_shift_stats()

    return {
        "summary": summary,
        "recent_incidents": [e.to_dict() for e in recent_events],
        "behaviour_distribution": behaviour_dist,
        "hourly_trends": hourly_trends,
        "bay_stats": bay_stats,
        "prevention_metrics": prevention,
        "shift_stats": shift_stats,
    }
