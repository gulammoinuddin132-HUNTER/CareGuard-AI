"""
tests/test_api_endpoints.py
----------------------------
Integration tests for the CareGuard AI FastAPI backend endpoints.
"""

import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from src.api.app import app


class TestCareGuardAPI(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_01_health_check(self):
        """GET /api/health returns 200 and healthy status."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("CareGuard AI", data["service"])

    def test_02_overview_endpoint(self):
        """GET /api/overview returns KPI summaries, risk distribution, and bay stats."""
        response = self.client.get("/api/overview")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("summary", data)
        self.assertIn("handling_quality_score", data["summary"])
        self.assertIn("risk_distribution", data["summary"])
        self.assertIn("bay_stats", data)
        self.assertIn("behaviour_distribution", data)

    def test_03_incidents_endpoint(self):
        """GET /api/incidents returns list of logged warehouse behaviour events."""
        response = self.client.get("/api/incidents?limit=10")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("incidents", data)
        self.assertIsInstance(data["incidents"], list)

    def test_04_analytics_endpoint(self):
        """GET /api/analytics returns behaviour distributions and shift comparisons."""
        response = self.client.get("/api/analytics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("behaviour_distribution", data)
        self.assertEqual(len(data["behaviour_distribution"]), 10)
        self.assertIn("shift_comparison", data)

    def test_05_prevention_endpoint(self):
        """GET /api/prevention returns damage prevention scorecard and training insights."""
        response = self.client.get("/api/prevention")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("safe_handling_ratio", data)
        self.assertIn("training_opportunities", data)

    def test_06_assistant_chat_endpoint(self):
        """POST /api/assistant/chat processes supervisor queries with data-grounded replies."""
        response = self.client.post("/api/assistant/chat", json={"message": "Show me high-risk events today"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("reply", data)
        self.assertIn("suggested_actions", data)

    def test_07_simulator_trigger(self):
        """POST /api/simulator/trigger injects a synthetic behaviour scenario demonstration."""
        response = self.client.post("/api/simulator/trigger", data={"preset_id": 1})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["behaviour_type"], "PRODUCT_DROPPED")
        self.assertEqual(data["risk_level"], "RED")
        self.assertIn("free-fall", data["observed_behaviour"].lower())

    def test_08_settings_endpoint(self):
        """GET /api/settings and POST /api/settings retrieve and update parameters."""
        response = self.client.get("/api/settings")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("zones", data)
        self.assertIn("kinematics", data)

    def test_09_video_state_endpoint(self):
        """GET /api/video/state returns active running state, source, fps, and tracks."""
        response = self.client.get("/api/video/state")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("is_running", data)
        self.assertIn("status", data)
        self.assertIn("fps", data)
        self.assertIn("active_tracks_count", data)
        self.assertIn("current_risk_level", data)

    def test_10_video_feed_stream_mjpeg(self):
        """Validates that generate_mjpeg_stream produces valid MJPEG chunks with JPEG magic bytes."""
        from src.api.routes.video import generate_mjpeg_stream
        from src.api.state import CareGuardBackendState
        backend = CareGuardBackendState.get_instance()
        gen = generate_mjpeg_stream(backend)
        first_chunk = next(gen)
        self.assertGreater(len(first_chunk), 0)
        self.assertIn(b"--frame", first_chunk)
        self.assertIn(b"Content-Type: image/jpeg", first_chunk)
        self.assertIn(b"\xff\xd8", first_chunk)

    def test_11_video_control_and_source_switch(self):
        """POST /api/video/control and POST /api/video/source toggle playback and sources."""
        # Stop
        res_stop = self.client.post("/api/video/control", data={"action": "stop"})
        self.assertEqual(res_stop.status_code, 200)
        self.assertFalse(res_stop.json()["is_running"])

        # Start
        res_start = self.client.post("/api/video/control", data={"action": "start"})
        self.assertEqual(res_start.status_code, 200)
        self.assertTrue(res_start.json()["is_running"])

        # Switch to Synthetic
        res_synth = self.client.post("/api/video/source", data={"source_type": "synthetic"})
        self.assertEqual(res_synth.status_code, 200)
        self.assertEqual(res_synth.json()["source"], "synthetic")

    def test_12_video_file_upload(self):
        """POST /api/video/upload uploads a video clip and immediately initiates ingestion."""
        sample_path = Path("data/videos/warehouse_handling_demo.mp4")
        if sample_path.exists():
            with open(sample_path, "rb") as f:
                content = f.read()
        else:
            content = b"fake_content"
        files = {"file": ("test_upload_clip.mp4", content, "video/mp4")}
        response = self.client.post("/api/video/upload", files=files)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["filename"], "test_upload_clip.mp4")


if __name__ == "__main__":
    unittest.main()
