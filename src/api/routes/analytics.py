"""
src/api/routes/analytics.py
---------------------------
Behaviour analytics, recurrence frequency, shift-by-shift comparisons,
and loading bay incident density.
"""

from fastapi import APIRouter
from src.api.state import CareGuardBackendState

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("")
def get_analytics_data():
    """Returns comprehensive behaviour analytics across all 10 warehouse handling scenarios."""
    backend = CareGuardBackendState.get_instance()
    distribution = backend.db.get_warehouse_behaviour_distribution()
    hourly = backend.db.get_warehouse_hourly_trends()
    bays = backend.db.get_warehouse_bay_stats()
    summary = backend.db.get_warehouse_stats_summary()

    # Real shift comparisons computed from timestamped events
    shift_stats = backend.db.get_warehouse_shift_stats()

    return {
        "summary": summary,
        "behaviour_distribution": distribution,
        "hourly_trends": hourly,
        "shift_stats": shift_stats,
        "shift_comparison": [
            {
                "shift": s["shift"],
                "events": s["incidents"],
                "risky_events": s["critical_count"] + s["high_risk_count"],
                "quality_score": s["handling_quality_score"],
            }
            for s in shift_stats
        ],
        "bay_breakdown": bays,
        "bay_stats": bays,
    }
