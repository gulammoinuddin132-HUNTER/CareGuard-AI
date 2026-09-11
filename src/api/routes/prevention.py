"""
src/api/routes/prevention.py
----------------------------
Proactive damage prevention insights, safety ratios, and supervisor training opportunities.
"""

from fastapi import APIRouter
from src.api.state import CareGuardBackendState

router = APIRouter(prefix="/api/prevention", tags=["Prevention"])


@router.get("")
def get_prevention_data():
    """Returns damage prevention metrics, training recommendations, and recurring risk patterns."""
    backend = CareGuardBackendState.get_instance()
    metrics = backend.db.get_warehouse_prevention_metrics()
    summary = backend.db.get_warehouse_stats_summary()

    return {
        "metrics": metrics,
        "summary": summary,
        "safe_handling_ratio": metrics["safe_handling_ratio"],
        "damage_prevented_count": metrics["potential_damage_prevented"],
        "training_opportunities": metrics["training_opportunities"],
        "recurring_risk_patterns": metrics["recurring_risk_patterns"],
    }
