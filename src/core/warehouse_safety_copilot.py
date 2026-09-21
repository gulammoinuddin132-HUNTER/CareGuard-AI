"""
src/core/warehouse_safety_copilot.py
------------------------------------
CareGuard AI - Data-Grounded Warehouse Safety Intelligence Copilot
==================================================================
Transforms warehouse inquiries into evidence-backed operational intelligence
grounded strictly in live database records (careguard.db), kinematic vectors,
10-behaviour frequency distributions, multi-bay status, and safety policy.

Execution Pipeline:
  User Query + Conversation History
  -> Warehouse Context Aggregation (Current KPIs, 20-Event Window, Analytics, Prevention)
  -> Intent & Entity Understanding (Handling Quality, Alerts, Bays, Shifts, Trends, Follow-ups)
  -> Dual-Mode Reasoning (LLM if API Key configured, or Deterministic Grounded Reasoner)
  -> Evidence-Backed Response Format (Answer, Evidence, Why, Recommended Action)
  -> Anti-Hallucination Guardrail (Strictly denies ungrounded claims)
"""

import os
import re
import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from src.core.warehouse_models import WarehouseBehaviourType

logger = logging.getLogger("CareGuard.SafetyCopilot")


def build_warehouse_context(state_or_db: Optional[Any] = None) -> Dict[str, Any]:
    """
    Compiles complete structured operational telemetry from the database
    and active runtime state for assistant reasoning.
    """
    if state_or_db is None:
        from src.api.state import CareGuardBackendState
        state_or_db = CareGuardBackendState.get_instance()

    db = getattr(state_or_db, "db", state_or_db)
    state = state_or_db if hasattr(state_or_db, "camera") else None

    # 1. Summary KPIs
    summary = db.get_warehouse_stats_summary() if hasattr(db, "get_warehouse_stats_summary") else {}
    
    # 2. Recent 20 Events Window
    recent_events = []
    if hasattr(db, "get_recent_warehouse_events"):
        raw_events = db.get_recent_warehouse_events(limit=20)
        for ev in raw_events:
            recent_events.append({
                "event_id": ev.event_id,
                "behaviour_type": ev.behaviour_type,
                "risk_level": ev.risk_level,
                "confidence": round(ev.confidence, 2),
                "start_timestamp": ev.start_timestamp,
                "observed_behaviour": ev.observed_behaviour,
                "potential_risk": ev.potential_risk,
                "recommended_action": ev.recommended_action,
                "product_track_id": ev.product_track_id,
                "person_track_id": ev.person_track_id,
                "loading_bay": getattr(ev, "loading_bay", "Bay 01"),
                "severity_reason": getattr(ev, "severity_reason", None),
            })

    # 3. 10-Behaviour Taxonomy Distribution
    dist = db.get_warehouse_behaviour_distribution() if hasattr(db, "get_warehouse_behaviour_distribution") else []

    # 4. Multi-Bay Status
    bay_stats = db.get_warehouse_bay_stats() if hasattr(db, "get_warehouse_bay_stats") else []

    # 5. Shift Analysis
    shift_stats = db.get_warehouse_shift_stats() if hasattr(db, "get_warehouse_shift_stats") else []

    # 6. Hourly Trends
    hourly_trends = db.get_warehouse_hourly_trends() if hasattr(db, "get_warehouse_hourly_trends") else []

    # 7. Prevention Metrics
    prevention = db.get_warehouse_prevention_metrics() if hasattr(db, "get_warehouse_prevention_metrics") else {}

    # 8. Live System Viewport State (if available)
    live_system = {
        "is_running": bool(state.camera.is_running) if state and hasattr(state, "camera") else False,
        "source_type": getattr(state, "active_source", "STANDBY") if state else "STANDBY",
        "video_file": getattr(state, "video_file", None) if state else None,
        "active_bay": "Bay 01 (General Staging & Conveyor Dock)",
        "current_risk_level": getattr(state, "current_risk_level", "GREEN") if state else "GREEN",
        "active_tracks_count": len(getattr(state, "active_tracks", [])) if state and hasattr(state, "active_tracks") else 0,
        "current_event": {
            "event_id": state.latest_event.event_id,
            "behaviour_type": state.latest_event.behaviour_type.value if hasattr(state.latest_event.behaviour_type, "value") else str(state.latest_event.behaviour_type),
            "risk_level": state.latest_event.risk_level,
            "observed_behaviour": state.latest_event.observed_behaviour,
        } if state and getattr(state, "latest_event", None) else None,
    }

    return {
        "summary": summary,
        "kpis": summary,
        "recent_events": recent_events,
        "behaviour_distribution": dist,
        "bay_stats": bay_stats,
        "shift_stats": shift_stats,
        "shifts": shift_stats,
        "hourly_trends": hourly_trends,
        "prevention": prevention,
        "live_system": live_system,
        "db_grounded": True,
        "grounded_source": "careguard.db",
    }


class WarehouseSafetyCopilot:
    """
    CareGuard Safety Copilot Reasoning Engine.
    Executes intent identification, multi-turn history resolution,
    and produces structured, evidence-backed supervisor answers.
    """

    def __init__(self, backend_state: Optional[Any] = None):
        self.backend_state = backend_state
        self.gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

    def ask(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Processes a supervisor inquiry and returns a data-grounded response.
        """
        raw_query = message.strip()
        query = raw_query.lower()
        history = conversation_history or []

        # 1. Build authoritative warehouse context
        from src.api.state import CareGuardBackendState
        state = self.backend_state or CareGuardBackendState.get_instance()
        context = build_warehouse_context(state)

        # 2. Try LLM if configured, otherwise execute Deterministic Grounded Reasoner
        if self.gemini_api_key or self.openai_api_key:
            try:
                llm_response = self._query_llm(raw_query, context, history)
                if llm_response:
                    return llm_response
            except Exception as e:
                logger.warning(f"[COPILOT] LLM execution failed, falling back to deterministic reasoner: {e}")

        # 3. Deterministic Grounded Reasoning
        return self._reason_grounded_response(raw_query, query, context, history)

    def answer_query(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Alias for ask() for test and external callers."""
        return self.ask(message, conversation_history)

    def _query_llm(
        self,
        query: str,
        context: Dict[str, Any],
        history: List[Dict[str, str]],
    ) -> Optional[Dict[str, Any]]:
        """Invokes external LLM (Gemini / OpenAI) with strict data grounding."""
        system_prompt = (
            "You are CareGuard Safety Copilot, an enterprise warehouse safety intelligence assistant. "
            "You assist warehouse operations supervisors in analyzing handling safety, incident root causes, "
            "handling quality KPIs, bay risks, and damage prevention.\n\n"
            "CRITICAL OPERATIONAL RULES:\n"
            "1. Answer strictly using the provided CareGuard warehouse context JSON. Do NOT invent or hallucinate facts, events, track IDs, damage, or numbers.\n"
            "2. If the data does not contain the answer, say: 'I don't have enough evidence in the current CareGuard data to determine that.'\n"
            "3. Structure operational explanations with:\n"
            "   - Direct Answer\n"
            "   - Evidence (citing exact metrics, event IDs, timestamps, or bays)\n"
            "   - Why (kinematic or policy rationale)\n"
            "   - Recommended Action (practical supervisor guidance)\n"
            "4. Keep your tone professional, concise, and focused on warehouse safety operations without robotic AI disclaimers."
        )

        if self.gemini_api_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_api_key}"
            contents = []
            
            # Add recent history (last 4 turns)
            for turn in history[-4:]:
                role = "user" if turn.get("sender") == "user" else "model"
                contents.append({"role": role, "parts": [{"text": turn.get("text", "")}]})
            
            prompt_payload = f"WAREHOUSE TELEMETRY CONTEXT:\n{json.dumps(context, indent=2)}\n\nUSER QUESTION: {query}"
            contents.append({"role": "user", "parts": [{"text": prompt_payload}]})

            req_data = {
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": contents,
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600},
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(req_data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                text = res_json["candidates"][0]["content"]["parts"][0]["text"]
                return {
                    "reply": text,
                    "structured_data": self._extract_contextual_cards(context),
                    "suggested_actions": self._generate_suggested_actions(query, context),
                    "source_context": "careguard.db (Grounded via Gemini & Telemetry Engine)",
                }
        return None

    def _reason_grounded_response(
        self,
        raw_query: str,
        query: str,
        context: Dict[str, Any],
        history: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """
        Deterministic, fully data-grounded reasoning engine across all CareGuard metrics.
        """
        summary = context.get("summary", {})
        recent = context.get("recent_events", [])
        dist = context.get("behaviour_distribution", [])
        bay_stats = context.get("bay_stats", [])
        shift_stats = context.get("shift_stats", [])
        prevention = context.get("prevention", {})
        live = context.get("live_system", {})

        total_events = summary.get("total_events", 0)
        quality_score = summary.get("handling_quality_score", 100)
        critical_events = summary.get("critical_events", 0)
        high_risk_events = summary.get("high_risk_events", 0)
        safe_ratio = summary.get("risk_free_observation_ratio", 100.0)

        # ---------------------------------------------------------------------
        # Intent 0: Anti-Hallucination & Off-Topic Guardrail
        # ---------------------------------------------------------------------
        off_topic_patterns = [
            "fifa", "world cup", "weather", "president", "poem", "recipe", "joke", 
            "stock market", "capital of", "movie", "song", "actor", "sports",
            "temperature", "humidity", "driver name", "battery", "gps", "salary",
        ]
        if any(w in query for w in off_topic_patterns):
            return {
                "reply": (
                    "I do not have evidence in the active CareGuard telemetry database to answer that question.\n\n"
                    "CareGuard Safety Copilot is strictly grounded in warehouse handling operations, "
                    "kinematic tracking vectors, bay risk metrics, and safety policy violations recorded in `careguard.db`."
                ),
                "structured_data": {"domain": "warehouse_safety_only"},
                "suggested_actions": [
                    "Why is our Handling Quality score at this level?",
                    "Explain the latest critical safety event",
                    "Which bay has the most drops or improper handling?",
                    "What should the supervisor do next?",
                ],
                "source_context": "CareGuard Grounding Guardrail (careguard.db)",
            }

        # ---------------------------------------------------------------------
        # Intent 1: Handling Quality Score Inquiry
        # ---------------------------------------------------------------------
        if any(k in query for k in ["handling quality", "quality score", "score", "why is handling", "why is score", "handling index", "explain the score"]):
            if total_events == 0:
                reply = (
                    f"**Handling Quality Score**: **{quality_score} / 100 (Optimal Baseline)**\n\n"
                    f"### Observed Telemetry\n"
                    f"- **Active Safety Events**: Zero safety violations have been logged in the active session.\n"
                    f"- **Monitored Scope**: All active warehouse zones are operating within safe kinematic thresholds.\n\n"
                    f"### Risk Assessment\n"
                    f"- Current operations reflect optimal risk-free material movement.\n"
                    f"- Rate-based rolling calculation applies zero penalty deductions.\n\n"
                    f"### Operational Action\n"
                    f"- Continue standard supervision and maintain MHE availability at active staging docks."
                )
            else:
                red_rec = sum(1 for e in recent if e["risk_level"] == "RED")
                orange_rec = sum(1 for e in recent if e["risk_level"] == "ORANGE")
                yellow_rec = sum(1 for e in recent if e["risk_level"] == "YELLOW")
                tier_desc = "Optimal" if quality_score >= 90 else ("Watch Tier" if quality_score >= 75 else "Needs Supervisor Attention")

                reply = (
                    f"**Handling Quality Score**: **{quality_score} / 100** ({tier_desc})\n\n"
                    f"### Observed Telemetry\n"
                    f"- **20-Event Window**: {red_rec} Critical (RED), {orange_rec} High-Risk (ORANGE), {yellow_rec} Attention (YELLOW).\n"
                    f"- **Risk-Free Ratio**: **{safe_ratio}%** across observed material handling cycles.\n\n"
                    f"### Risk Assessment\n"
                    f"- The score reflects a rolling rate-based index penalized proportionally by kinematic impact severity.\n"
                    f"- Each RED event imparts an authoritative penalty (-0.85 per rate unit) due to potential structural goods compromise.\n\n"
                    f"### Operational Action\n"
                    f"- {'Initiate floor coaching on proper product support and mechanical lift usage.' if quality_score < 85 else 'Maintain standard shift monitoring. Operations remain within safe handling limits.'}"
                )

            return {
                "reply": reply,
                "structured_data": {
                    "handling_quality_score": quality_score,
                    "critical_events": critical_events,
                    "high_risk_events": high_risk_events,
                    "total_events": total_events,
                },
                "suggested_actions": [
                    "Explain the latest critical safety event",
                    "Which bay has the highest risk today?",
                    "What should the supervisor do next?",
                ],
                "source_context": "careguard.db (safety_events, handling_quality_kpis)",
            }

        # ---------------------------------------------------------------------
        # Intent 2: Critical Alerts / Drops / Red Alerts
        # ---------------------------------------------------------------------
        if any(k in query for k in ["red", "critical", "alert", "drop", "dropped", "product_dropped", "last incident", "latest event", "why did"]):
            high_sev_events = [e for e in recent if e["risk_level"] in ("RED", "ORANGE") or "drop" in e["behaviour_type"].lower()]
            if high_sev_events:
                e = high_sev_events[0]
                p_text = f"Product Track #{e['product_track_id']}" if e.get('product_track_id') else "Monitored Product"
                h_text = f"Handler Track #{e['person_track_id']}" if e.get('person_track_id') else "Floor Handler"

                reply = (
                    f"**Critical Safety Alert Breakdown** (Event `{e['event_id']}`):\n\n"
                    f"### Observed Telemetry\n"
                    f"- **Behaviour**: **{e['behaviour_type']}** [{e['risk_level']} Severity]\n"
                    f"- **Timestamp & Bay**: {e['start_timestamp']} • {e['loading_bay']}\n"
                    f"- **Entities**: {p_text} interacted with {h_text} (Detection Confidence: {int(e['confidence'] * 100)}%)\n\n"
                    f"### Risk Assessment\n"
                    f"- **Observed Dynamics**: {e['observed_behaviour']}\n"
                    f"- **Potential Risk**: {e['potential_risk']}\n\n"
                    f"### Operational Action\n"
                    f"- **Recommended Response**: {e['recommended_action']}"
                )
                return {
                    "reply": reply,
                    "structured_data": {
                        "event_id": e["event_id"],
                        "behavior_type": e["behaviour_type"],
                        "risk_level": e["risk_level"],
                        "bay_id": e["loading_bay"],
                    },
                    "suggested_actions": [
                        "What should the supervisor do next?",
                        "What is the status of Bay 1?",
                        "What are our top 3 most frequent risky behaviours?",
                    ],
                    "source_context": "careguard.db (safety_events, kinematic_evidence)",
                }
            else:
                return {
                    "reply": (
                        f"**No Critical (RED) or Drop Incidents Logged**\n\n"
                        f"### Observed Telemetry\n"
                        f"- Total logged safety incidents in current session: **{total_events}**.\n"
                        f"- Active stream status: **{live.get('source_type', 'STANDBY')}**.\n\n"
                        f"### Risk Assessment\n"
                        f"- No product drops or severe kinetic impacts have been recorded.\n\n"
                        f"### Operational Action\n"
                        f"- Continue normal operations and routine dock inspections."
                    ),
                    "structured_data": {"critical_events": 0, "total_events": total_events},
                    "suggested_actions": [
                        "Why is our Handling Quality score at this level?",
                        "Which bay has the most drops or improper handling?",
                    ],
                    "source_context": "careguard.db (safety_events)",
                }

        # ---------------------------------------------------------------------
        # Intent 3: Bay Risk & Analytics ("What is the status of Bay 1?", "Which bay is riskiest?")
        # ---------------------------------------------------------------------
        if "bay" in query or "dock" in query or "zone" in query:
            target_bay = None
            if "bay 1" in query or "bay 01" in query or "staging" in query:
                target_bay = next((b for b in bay_stats if "1" in b.get("bay_id", "") or "1" in b.get("name", "")), None)
            elif "bay 2" in query or "bay 02" in query:
                target_bay = next((b for b in bay_stats if "2" in b.get("bay_id", "") or "2" in b.get("name", "")), None)

            if target_bay:
                reply = (
                    f"**Operational Intelligence for {target_bay.get('name', 'Bay 01')}**:\n\n"
                    f"### Observed Telemetry\n"
                    f"- **Zone Status**: **{target_bay.get('status', 'OPTIMAL')}** (Zone Health: {target_bay.get('health_score', 100)}%)\n"
                    f"- **Recorded Incidents**: {target_bay.get('incident_count', 0)} logged events.\n"
                    f"- **Primary Issue Identified**: {target_bay.get('primary_issue', 'Normal Operations')}\n\n"
                    f"### Risk Assessment\n"
                    f"- Bay risk score is **{target_bay.get('risk_score', 0)}/100** based on historical event density.\n\n"
                    f"### Operational Action\n"
                    f"- Stage auxiliary material handling equipment (pallet jacks/hand trucks) near dock entry to streamline loading."
                )
                return {
                    "reply": reply,
                    "structured_data": {"bay_id": target_bay.get("bay_id", "Bay 01"), "risk_score": target_bay.get("risk_score", 0)},
                    "suggested_actions": [
                        "What should the supervisor do next?",
                        "Explain the latest critical safety event",
                    ],
                    "source_context": "careguard.db (bay_metrics, zone_health)",
                }
            else:
                bay_lines = "\n".join([
                    f"- **{b.get('name', b.get('bay_id'))}**: {b.get('incident_count', 0)} incidents | Status: {b.get('status', 'NORMAL')} | Risk Score: {b.get('risk_score', 0)}"
                    for b in bay_stats
                ]) if bay_stats else "- All bays operating normally."
                reply = (
                    f"**Multi-Bay Safety & Risk Comparison**:\n\n"
                    f"### Observed Telemetry\n"
                    f"{bay_lines}\n\n"
                    f"### Risk Assessment\n"
                    f"- **Highest Risk Bay**: **{summary.get('highest_risk_bay', 'Bay 01')}**\n\n"
                    f"### Operational Action\n"
                    f"- Focus supervisory walk-throughs in the highest-risk dock areas."
                )
                return {
                    "reply": reply,
                    "structured_data": {"bay_stats": bay_stats, "highest_risk_bay": summary.get("highest_risk_bay", "Bay 01")},
                    "suggested_actions": [
                        "What is the status of Bay 1?",
                        "What should the supervisor do next?",
                    ],
                    "source_context": "careguard.db (bay_metrics)",
                }

        # ---------------------------------------------------------------------
        # Intent 4: Shift Comparison & Shifts Analysis
        # ---------------------------------------------------------------------
        if any(k in query for k in ["shift", "shifts", "morning shift", "night shift", "afternoon shift"]):
            if shift_stats:
                shift_lines = "\n".join([
                    f"- **{s.get('shift', s.get('shift_id'))}**: {s.get('incidents', 0)} incidents ({s.get('critical_count', 0)} RED) | Quality Score: {s.get('handling_quality_score', 100)}/100 | Status: {s.get('status', 'NORMAL')}"
                    for s in shift_stats
                ])
                highest_risk_shift = max(shift_stats, key=lambda s: s.get("incidents", 0) + s.get("critical_count", 0) * 2)
                reply = (
                    f"**Shift Risk Analysis & Comparison**:\n\n"
                    f"### Observed Telemetry\n"
                    f"{shift_lines}\n\n"
                    f"### Risk Assessment\n"
                    f"- **Highest Risk Shift**: **{highest_risk_shift.get('shift', 'Morning Shift')}** with {highest_risk_shift.get('incidents', 0)} logged incident(s).\n\n"
                    f"### Operational Action\n"
                    f"- Conduct pre-shift ergonomics briefing for {highest_risk_shift.get('shift', 'active shift')} handlers."
                )
            else:
                reply = (
                    f"**Shift Risk Status**:\n\n"
                    f"### Observed Telemetry\n"
                    f"- Current shift records zero critical incidents.\n\n"
                    f"### Risk Assessment\n"
                    f"- Operations across Morning, Afternoon, and Night shifts remain balanced.\n\n"
                    f"### Operational Action\n"
                    f"- Continue standard shift handovers."
                )
            return {
                "reply": reply,
                "structured_data": {"shifts": shift_stats},
                "suggested_actions": [
                    "What are our top 3 most frequent risky behaviours?",
                    "What should the supervisor do next?",
                ],
                "source_context": "careguard.db (shift_telemetry)",
            }

        # ---------------------------------------------------------------------
        # Intent 5: Behaviour Frequency & Taxonomy
        # ---------------------------------------------------------------------
        if any(k in query for k in ["most common", "most often", "frequent", "behaviour", "behavior", "taxonomy", "distribution", "risks"]):
            active_dist = [d for d in dist if d.get("count", 0) > 0]
            if active_dist:
                sorted_d = sorted(active_dist, key=lambda x: x.get("count", 0), reverse=True)
                top_d = sorted_d[0]
                lines = "\n".join([f"- **{d['title']}**: {d['count']} occurrence(s) [{d['risk_level']} Tier]" for d in sorted_d[:5]])
                reply = (
                    f"**Warehouse Handling Behaviour Frequency**:\n\n"
                    f"### Observed Telemetry\n"
                    f"{lines}\n\n"
                    f"### Risk Assessment\n"
                    f"- **Primary Risk Driver**: **{top_d['title']}** ({top_d['count']} logged event(s)).\n\n"
                    f"### Operational Action\n"
                    f"- **Countermeasure**: {top_d.get('recommended_response', 'Enforce standard ergonomic protocols.')}"
                )
            else:
                reply = (
                    f"**10-Behaviour Taxonomy Benchmark**:\n\n"
                    f"### Observed Telemetry\n"
                    f"- All 10 monitored warehouse behaviours currently record **0 incidents** in the active session.\n"
                    f"- Monitored Categories: `PRODUCT_DROPPED`, `HEAVY_LIFT_SOLO`, `UNSTABLE_STACKING`, `PRODUCT_DRAGGED`, `ROUGH_HANDLING`, `WALKWAY_DWELL`, `MANUAL_CARRYING`, `PALLET_PROTRUSION`, `PUSHED_THROWN`, `UNSAFE_LOADING`.\n\n"
                    f"### Risk Assessment\n"
                    f"- Zero active safety policy violations detected.\n\n"
                    f"### Operational Action\n"
                    f"- Maintain continuous vision stream monitoring."
                )
            return {
                "reply": reply,
                "structured_data": {"distribution": dist},
                "suggested_actions": [
                    "Why is our Handling Quality score at this level?",
                    "What should the supervisor do next?",
                ],
                "source_context": "careguard.db (behaviour_distribution)",
            }

        # ---------------------------------------------------------------------
        # Intent 6: Supervisor Action Plan
        # ---------------------------------------------------------------------
        if any(k in query for k in ["supervisor do", "what should", "action", "recommend", "next", "improve first"]):
            recs = prevention.get("structured_recommendations", [])
            if recs:
                rec_lines = "\n".join([
                    f"{idx+1}. **{r.get('what_to_change')}** [{r.get('priority', 'HIGH')} Priority]\n   - *Issue*: {r.get('what_happened')} in {r.get('where', 'Bay 01')}\n   - *Operational Effect*: {r.get('expected_operational_effect')}"
                    for idx, r in enumerate(recs[:3])
                ])
                reply = (
                    f"**Supervisor Action Plan** (Derived from careguard.db):\n\n"
                    f"### Operational Action\n"
                    f"{rec_lines}\n\n"
                    f"Log corrective resolutions directly in the Safety Events workspace."
                )
            else:
                reply = (
                    f"**Supervisor Action Plan**:\n\n"
                    f"### Operational Action\n"
                    f"1. **Continuous Dock Surveillance**: Maintain active vision pipeline monitoring across Bay 01 and Bay 02.\n"
                    f"2. **Equipment Accessibility**: Ensure hand trucks and pallet jacks are visibly staged for heavy package movements."
                )
            return {
                "reply": reply,
                "structured_data": {"recommendations": recs},
                "suggested_actions": [
                    "What is the status of Bay 1?",
                    "Why is our Handling Quality score at this level?",
                ],
                "source_context": "careguard.db (prevention_actions)",
            }

        # ---------------------------------------------------------------------
        # Intent 7: Conversational Follow-Up Resolution ("Which ones?", "Why?")
        # ---------------------------------------------------------------------
        if any(q in query for q in ["which ones", "which one", "which", "show them", "what are they"]):
            high_events = [e for e in recent if e["risk_level"] in ("RED", "ORANGE")]
            if high_events:
                items = "\n".join([
                    f"- **[{e['risk_level']}] {e['behaviour_type']}** (`{e['event_id']}` in {e['loading_bay']}): {e['observed_behaviour']}"
                    for e in high_events[:4]
                ])
                reply = f"**Recent High-Risk Events Referenced**:\n\n### Observed Telemetry\n{items}"
            else:
                reply = (
                    f"**Follow-Up Reference**:\n\n"
                    f"### Observed Telemetry\n"
                    f"- Zero high-risk incidents are currently logged in the active activity window.\n"
                    f"- Total recorded events: {total_events}."
                )
            return {
                "reply": reply,
                "structured_data": {"events": high_events[:4] if high_events else []},
                "suggested_actions": [
                    "What should the supervisor do next?",
                    "Why is our Handling Quality score at this level?",
                ],
                "source_context": "careguard.db (safety_events)",
            }

        # ---------------------------------------------------------------------
        # Default Grounded Telemetry Overview
        # ---------------------------------------------------------------------
        reply = (
            f"**CareGuard Safety Copilot — Operational Overview**:\n\n"
            f"### Observed Telemetry\n"
            f"- **Handling Quality Score**: **{quality_score} / 100**\n"
            f"- **Recorded Incidents**: {total_events} total ({critical_events} Critical RED, {high_risk_events} High-Risk ORANGE)\n"
            f"- **Risk-Free Handling Ratio**: **{safe_ratio}%**\n"
            f"- **Primary Monitored Bay**: {summary.get('highest_risk_bay', 'Bay 01 • Staging & Conveyor Dock')}\n\n"
            f"### Operational Action\n"
            f"- Select any quick query prompt or inquire about specific bays, handling scores, or incident kinematics."
        )
        return {
            "reply": reply,
            "structured_data": self._extract_contextual_cards(context),
            "suggested_actions": [
                "Why is our Handling Quality score at this level?",
                "Explain the latest critical safety event",
                "Which bay has the most drops or improper handling?",
                "What should the supervisor do next?",
            ],
            "source_context": "careguard.db (safety_events, handling_quality_kpis)",
        }

    def _extract_contextual_cards(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts key KPI metrics for frontend contextual display."""
        summary = context.get("summary", {})
        recent = context.get("recent_events", [])
        last_crit = next((e for e in recent if e.get("risk_level") == "RED"), None)
        return {
            "handling_quality_score": summary.get("handling_quality_score", 100),
            "high_risk_events": summary.get("critical_events", 0) + summary.get("high_risk_events", 0),
            "total_events": summary.get("total_events", 0),
            "critical_events": summary.get("critical_events", 0),
            "event_id": last_crit["event_id"] if last_crit else None,
            "bay_id": last_crit.get("loading_bay", "Bay 01") if last_crit else "Bay 01",
        }

    def _generate_suggested_actions(self, query: str, context: Dict[str, Any]) -> List[str]:
        """Generates dynamic follow-up prompt suggestions."""
        return [
            "Why is our Handling Quality score at this level?",
            "Explain the latest critical safety event",
            "Which bay has the most drops or improper handling?",
            "What should the supervisor do next?",
        ]
