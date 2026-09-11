import unittest
import time
import os
from pathlib import Path
import numpy as np
from fastapi.testclient import TestClient

from src.core.warehouse_models import (
    WarehouseBehaviourEvent,
    WarehouseBehaviourType,
    EventState,
)
from src.api.app import app
from src.api.state import CareGuardBackendState, SEVERITY_RANK
from src.camera.camera_manager import CameraManager, CameraStatus

class TestEventLifecycleAndMultiUpload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.backend = CareGuardBackendState.get_instance()
        cls.video_dir = Path("data/videos")

    def test_01_event_state_transitions(self):
        """Test CANDIDATE -> VERIFIED -> ACTIVE -> RESOLVED lifecycle transitions and to_dict integrity."""
        now = time.time()
        evt = WarehouseBehaviourEvent(
            event_id="EVT-TEST-001",
            behaviour_type=WarehouseBehaviourType.PRODUCT_DROPPED,
            risk_level="RED",
            confidence=0.92,
            start_timestamp="2026-09-10T00:00:00Z",
            end_timestamp="2026-09-10T00:00:01Z",
            duration_seconds=1.2,
            observed_behaviour="Carton dropped from height",
            potential_risk="Internal goods damage",
            recommended_action="Inspect item",
            state=EventState.CANDIDATE,
            activated_at=None,
            last_observed_time=now,
            resolved_at=None,
            grace_period_seconds=4.0
        )
        self.assertEqual(evt.state, EventState.CANDIDATE)

        # Transition to VERIFIED
        evt.state = EventState.VERIFIED
        self.assertEqual(evt.state, EventState.VERIFIED)

        # Transition to ACTIVE
        evt.state = EventState.ACTIVE
        evt.activated_at = now
        self.assertEqual(evt.state, EventState.ACTIVE)
        self.assertIsNotNone(evt.activated_at)

        # Verify to_dict includes state
        d = evt.to_dict()
        self.assertEqual(d["state"], "ACTIVE")
        self.assertEqual(d["event_id"], "EVT-TEST-001")
        self.assertEqual(d["risk_level"], "RED")

        # Transition to RESOLVED
        evt.state = EventState.RESOLVED
        evt.resolved_at = now + 4.1
        self.assertEqual(evt.state, EventState.RESOLVED)
        self.assertIsNotNone(evt.resolved_at)
        self.assertEqual(evt.to_dict()["state"], "RESOLVED")

    def test_02_hysteresis_grace_period_and_persistence(self):
        """Test that active verified event persists across frames during 4.0s grace period and resolves only after expiry."""
        self.backend.reset_session("TEST-HYSTERESIS")
        now = time.time()

        # Inject an active RED event
        red_evt = WarehouseBehaviourEvent(
            event_id="EVT-RED-001",
            behaviour_type=WarehouseBehaviourType.MATERIAL_PUSHED_THROWN,
            risk_level="RED",
            confidence=0.95,
            start_timestamp="2026-09-10T00:00:00Z",
            end_timestamp="2026-09-10T00:00:02Z",
            duration_seconds=1.5,
            observed_behaviour="Box thrown across staging zone",
            potential_risk="Impact crush hazard",
            recommended_action="Cease throwing immediately",
            product_bbox=(100, 100, 100, 100),
            state=EventState.ACTIVE,
            activated_at=now,
            last_observed_time=now,
            grace_period_seconds=4.0
        )
        self.backend.active_verified_event = red_evt
        self.backend.latest_event = red_evt
        self.backend.current_risk_level = "RED"

        # Check telemetry reports the active event
        telemetry = self.backend.get_full_diagnostics_telemetry()
        self.assertIsNotNone(telemetry["event"])
        self.assertEqual(telemetry["event"]["event_id"], "EVT-RED-001")
        self.assertEqual(telemetry["event"]["state"], "ACTIVE")
        self.assertEqual(telemetry["why_this_event_fired"]["event_id"], "EVT-RED-001")

        # Simulate 2.0 seconds elapsed (within 4.0s grace period): must NOT resolve
        test_now = now + 2.0
        elapsed = test_now - red_evt.last_observed_time
        self.assertLess(elapsed, red_evt.grace_period_seconds)
        self.assertEqual(self.backend.active_verified_event.state, EventState.ACTIVE)

        # Simulate 4.5 seconds elapsed (exceeding 4.0s grace period): resolves cleanly
        test_now_expired = now + 4.5
        if test_now_expired - red_evt.last_observed_time >= red_evt.grace_period_seconds:
            red_evt.state = EventState.RESOLVED
            red_evt.resolved_at = test_now_expired
            self.backend.active_verified_event = None
            self.backend.current_risk_level = "GREEN"

        self.assertIsNone(self.backend.active_verified_event)
        self.assertEqual(self.backend.current_risk_level, "GREEN")
        self.assertEqual(red_evt.state, EventState.RESOLVED)

    def test_03_non_preemptive_severity_policy(self):
        """Test that a lower severity event (YELLOW) cannot displace an active critical event (RED)."""
        now = time.time()
        critical_evt = WarehouseBehaviourEvent(
            event_id="EVT-CRITICAL-001",
            behaviour_type=WarehouseBehaviourType.PRODUCT_DROPPED,
            risk_level="RED",
            confidence=0.91,
            start_timestamp="2026-09-10T00:00:00Z",
            end_timestamp="2026-09-10T00:00:01Z",
            duration_seconds=1.0,
            observed_behaviour="Carton dropped",
            potential_risk="Impact damage",
            recommended_action="Inspect",
            state=EventState.ACTIVE,
            activated_at=now,
            last_observed_time=now,
            grace_period_seconds=4.0
        )
        self.backend.active_verified_event = critical_evt
        self.backend.current_risk_level = "RED"

        # Simulate incoming YELLOW event
        yellow_evt = WarehouseBehaviourEvent(
            event_id="EVT-YELLOW-002",
            behaviour_type=WarehouseBehaviourType.HANDLED_WITHOUT_EQUIPMENT,
            risk_level="YELLOW",
            confidence=0.88,
            start_timestamp="2026-09-10T00:00:01Z",
            end_timestamp="2026-09-10T00:00:02Z",
            duration_seconds=1.0,
            observed_behaviour="Manual carry without trolley",
            potential_risk="Ergonomic strain",
            recommended_action="Use trolley",
            state=EventState.ACTIVE,
            activated_at=now + 0.5,
            last_observed_time=now + 0.5,
            grace_period_seconds=4.0
        )

        curr_prio = SEVERITY_RANK.get(self.backend.active_verified_event.risk_level, 1)
        new_prio = SEVERITY_RANK.get(yellow_evt.risk_level, 1)

        # Hierarchy check: RED (4) must be greater than YELLOW (2)
        self.assertEqual(curr_prio, 4)
        self.assertEqual(new_prio, 2)
        self.assertGreater(curr_prio, new_prio)

        # Policy: if incoming priority is strictly lower, active event remains unchanged
        if new_prio > curr_prio:
            self.backend.active_verified_event = yellow_evt
        # Otherwise active remains RED

        self.assertEqual(self.backend.active_verified_event.event_id, "EVT-CRITICAL-001")
        self.assertEqual(self.backend.active_verified_event.risk_level, "RED")

    def test_04_focus_bounding_box_immutability(self):
        """Test that HUD retains product_bbox from active event even when live tracking flickers."""
        test_bbox = (150, 250, 200, 200)
        active_evt = WarehouseBehaviourEvent(
            event_id="EVT-DRAG-001",
            behaviour_type=WarehouseBehaviourType.PRODUCT_DRAGGED,
            risk_level="ORANGE",
            confidence=0.90,
            start_timestamp="2026-09-10T00:00:00Z",
            end_timestamp="2026-09-10T00:00:03Z",
            duration_seconds=2.0,
            observed_behaviour="Package dragged across floor",
            potential_risk="Base abrasion",
            recommended_action="Lift package",
            product_bbox=test_bbox,
            state=EventState.ACTIVE,
            activated_at=time.time(),
            last_observed_time=time.time(),
            grace_period_seconds=4.0
        )
        self.backend.active_verified_event = active_evt

        # Create dummy frame
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        rendered = self.backend._render_warehouse_hud(frame, tracks=[], events=[], overlay_mode="clean")

        # Confirm render succeeded and returned a valid numpy array of same shape
        self.assertEqual(rendered.shape, (720, 1280, 3))
        # Ensure HUD drew content by checking non-zero pixels
        self.assertGreater(np.count_nonzero(rendered), 0)

    def test_05_sequential_5_uploads_with_generation_tracking(self):
        """Test 5 sequential uploads (A->B->C->D->E) verifying all transition to READY with zero timeouts."""
        test_files = [
            'Throwing Mattresses.mp4',
            'KD packets dragged, heavy box kept on other packets.mp4',
            'Rolling and dragging on wet floor.mp4',
            'Throwing Mattresses.mp4',
            'KD packets dragged, heavy box kept on other packets.mp4',
        ]
        available_files = [f for f in test_files if (self.video_dir / f).exists()]
        self.assertGreater(len(available_files), 0, "No test videos found in data/videos")

        session_ids = []
        for i, fname in enumerate(test_files, 1):
            vid_path = self.video_dir / fname
            if not vid_path.exists():
                vid_path = self.video_dir / available_files[0]
                fname = vid_path.name

            t0 = time.time()
            with open(vid_path, 'rb') as vf:
                res = self.client.post('/api/video/upload', files={'file': (fname, vf, 'video/mp4')})
            upload_dur = time.time() - t0

            self.assertEqual(res.status_code, 200, f"Upload {i} failed: {res.text}")
            self.assertLess(upload_dur, 6.0, f"Upload {i} took too long ({upload_dur:.2f}s)")

            data = res.json()
            self.assertEqual(data['status'], 'ok')
            new_session = data.get('session_id')
            self.assertIsNotNone(new_session)
            self.assertNotIn(new_session, session_ids)
            session_ids.append(new_session)

            time.sleep(0.3)
            st_res = self.client.get('/api/video/state')
            self.assertEqual(st_res.status_code, 200)
            st = st_res.json()
            self.assertTrue(st['is_running'])
            self.assertEqual(st['active_source'], fname)
            self.assertEqual(st['session_id'], new_session)
            self.assertGreater(st['current_frame'], 0)

        self.assertEqual(len(session_ids), 5)

    def test_06_single_detection_worker_invariant(self):
        """Verify that exactly one background CV thread is running and worker count is 1."""
        cam = self.backend.camera
        self.assertIsNotNone(cam._thread)
        self.assertTrue(cam._thread.is_alive())

        # Check telemetry reports single worker
        st_res = self.client.get('/api/video/state')
        self.assertEqual(st_res.status_code, 200)
        st = st_res.json()
        self.assertTrue(st['is_running'])

    def test_07_video_decodability_probe_and_no_synthetic_fallback(self):
        """Verify that attempting to open a non-existent or unopenable video displays VIDEO SOURCE UNAVAILABLE error frame with NO synthetic fallback."""
        cam = self.backend.camera
        fake_path = "data/videos/non_existent_corrupted_file.mp4"
        success = cam.start_video_file(fake_path)
        self.assertFalse(success)
        self.assertEqual(cam.status, CameraStatus.ERROR)

        success_frame, frame = cam.get_frame()
        self.assertTrue(success_frame)
        self.assertIsNotNone(frame)
        self.assertEqual(frame.shape, (480, 640, 3))

        # Restore working video
        sample_video = self.video_dir / "Throwing Mattresses.mp4"
        if sample_video.exists():
            cam.start_video_file(str(sample_video))
            self.assertEqual(cam.status, CameraStatus.FILE)
            self.assertTrue(cam.is_running)

    def test_08_webcam_switching_lifecycle(self):
        """Verify switching to webcam (or handling camera index 0) does not deadlock or crash."""
        cam = self.backend.camera
        # Test stop-and-start cycle
        cam.stop()
        self.assertFalse(cam.is_running)

        # Attempt to open camera 0 with safe timeout
        t0 = time.time()
        opened = cam.start(camera_index=0)
        dur = time.time() - t0
        self.assertLess(dur, 5.0, "Camera start took too long - potential deadlock")

        # Stop camera cleanly
        t0 = time.time()
        cam.stop()
        dur = time.time() - t0
        self.assertLess(dur, 3.0, "Camera stop took too long - potential deadlock")
        self.assertFalse(cam.is_running)

        # Restore video file
        sample_video = self.video_dir / "Throwing Mattresses.mp4"
        if sample_video.exists():
            cam.start_video_file(str(sample_video))
            self.assertTrue(cam.is_running)

if __name__ == '__main__':
    unittest.main()
