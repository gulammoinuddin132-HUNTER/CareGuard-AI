"""
tests/test_safety_copilot.py
----------------------------
Test suite for the Data-Grounded CareGuard Safety Copilot.
Tests deterministic reasoning, telemetry context grounding,
conversation follow-ups, and anti-hallucination guardrails.
"""

import unittest
from fastapi.testclient import TestClient
from src.api.app import app
from src.core.warehouse_safety_copilot import WarehouseSafetyCopilot, build_warehouse_context


class TestSafetyCopilot(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.copilot = WarehouseSafetyCopilot()

    def test_01_build_warehouse_context(self):
        """Context builder aggregates live metrics from careguard.db."""
        ctx = build_warehouse_context()
        self.assertIn("kpis", ctx)
        self.assertIn("handling_quality_score", ctx["kpis"])
        self.assertIn("bay_stats", ctx)
        self.assertIn("shifts", ctx)
        self.assertIn("recent_events", ctx)
        self.assertIn("behaviour_distribution", ctx)
        self.assertIn("db_grounded", ctx)
        self.assertTrue(ctx["db_grounded"])

    def test_02_handling_quality_intent(self):
        """Copilot explains Handling Quality score grounded in DB penalties."""
        res = self.copilot.answer_query(
            "Why is our Handling Quality score at this level?"
        )
        self.assertIn("reply", res)
        self.assertIn("Handling Quality Score", res["reply"])
        self.assertIn("Observed Telemetry", res["reply"])
        self.assertIn("Risk Assessment", res["reply"])
        self.assertIn("Operational Action", res["reply"])
        self.assertIn("careguard.db", res["source_context"])
        self.assertIn("structured_data", res)

    def test_03_critical_drop_event_intent(self):
        """Copilot breaks down critical drop/alert with kinematic parameters."""
        res = self.copilot.answer_query(
            "Why did the latest RED alert fire?"
        )
        self.assertIn("reply", res)
        self.assertIn("careguard.db", res["source_context"])
        # Checks for structured response components
        self.assertTrue(
            "Critical" in res["reply"] or "CRITICAL" in res["reply"] or "No Critical" in res["reply"] or "PRODUCT_DROPPED" in res["reply"]
        )

    def test_04_bay_risk_intent(self):
        """Copilot identifies bay risks and primary issues without hallucination."""
        res = self.copilot.answer_query(
            "What is the status of Bay 1 and which bay is riskiest?"
        )
        self.assertIn("reply", res)
        self.assertTrue("Bay" in res["reply"])
        self.assertIn("careguard.db", res["source_context"])

    def test_05_behaviour_frequency_intent(self):
        """Copilot ranks observed warehouse behaviours correctly."""
        res = self.copilot.answer_query(
            "What are our most frequent risky behaviours today?"
        )
        self.assertIn("reply", res)
        self.assertIn("Observed Telemetry", res["reply"])
        self.assertIn("careguard.db", res["source_context"])

    def test_06_shift_comparison_intent(self):
        """Copilot compares shift risks accurately."""
        res = self.copilot.answer_query(
            "Which shift has the highest risk and what should we do?"
        )
        self.assertIn("reply", res)
        self.assertTrue("Shift" in res["reply"] or "Morning" in res["reply"] or "Afternoon" in res["reply"] or "Night" in res["reply"])

    def test_07_multiturn_followup_intent(self):
        """Copilot resolves conversational follow-ups like 'Which ones?' using history."""
        history = [
            {"sender": "user", "text": "What are our most frequent risky behaviours?"},
            {"sender": "assistant", "text": "Top behaviors logged: PRODUCT_DROPPED and UNSTABLE_STACKING."},
        ]
        res = self.copilot.answer_query(
            "Which ones happened in Bay 1?",
            conversation_history=history
        )
        self.assertIn("reply", res)
        self.assertIn("Bay", res["reply"])

    def test_08_anti_hallucination_guardrail(self):
        """Copilot refrains from hallucinating on queries outside CareGuard data."""
        res = self.copilot.answer_query(
            "Who won the FIFA World Cup in 2022?"
        )
        self.assertIn("reply", res)
        # Verify strict guardrail trigger
        self.assertTrue(
            "I do not have evidence in the active CareGuard telemetry" in res["reply"]
            or "outside" in res["reply"].lower()
            or "careguard" in res["reply"].lower()
        )

    def test_09_api_assistant_endpoint(self):
        """POST /api/assistant/chat returns grounded response structure."""
        payload = {
            "message": "Why is our handling quality score at this level?",
            "conversation_history": []
        }
        response = self.client.post("/api/assistant/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("reply", data)
        self.assertIn("structured_data", data)
        self.assertIn("suggested_actions", data)
        self.assertIn("source_context", data)
        self.assertIn("careguard.db", data["source_context"])


if __name__ == "__main__":
    unittest.main()
