"""
Unit & Integration Tests for Warehouse Video Ingestion Pipeline (Phase 1)
--------------------------------------------------------------------------
Verifies video file opening, frame iteration, FPS regulation, looping, and resource cleanup.
"""

import os
import tempfile
import time
import unittest
from pathlib import Path

import cv2
import numpy as np

from src.camera.camera_manager import CameraManager, CameraStatus, CameraMode


def create_synthetic_test_video(filepath: str, num_frames: int = 30, fps: int = 30, width: int = 640, height: int = 480) -> str:
    """Creates a temporary MP4 video file for testing."""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(filepath, fourcc, float(fps), (width, height))
    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        # Draw moving circle
        cx = int(50 + (i * 15) % (width - 100))
        cy = int(200 + 50 * np.sin(i / 5.0))
        cv2.circle(frame, (cx, cy), 30, (0, 165, 255), -1)
        cv2.putText(frame, f"Frame {i+1}/{num_frames}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        writer.write(frame)
    writer.release()
    return filepath


class TestWarehouseVideoPipeline(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.video_path = os.path.join(self.temp_dir.name, "test_warehouse_clip.mp4")
        create_synthetic_test_video(self.video_path, num_frames=20, fps=25, width=640, height=480)
        self.cam = CameraManager()

    def tearDown(self):
        if self.cam.is_running:
            self.cam.stop()
        self.temp_dir.cleanup()

    def test_video_file_ingestion_success(self):
        """Verifies opening a video file, starting playback loop, and retrieving valid frames."""
        started = self.cam.start_video_file(self.video_path, loop=True)
        self.assertTrue(started)
        self.assertEqual(self.cam.status, CameraStatus.FILE)
        self.assertTrue(self.cam.is_file_mode)
        self.assertTrue(self.cam.is_running)
        self.assertEqual(self.cam.video_file_path, str(Path(self.video_path).resolve()))

        # Allow worker thread to read frames
        time.sleep(0.3)
        success, frame = self.cam.get_frame()
        self.assertTrue(success)
        self.assertIsNotNone(frame)
        self.assertEqual(frame.shape[0], 480)
        self.assertEqual(frame.shape[1], 640)
        self.assertIn("FILE", self.cam.status_label)

    def test_video_file_not_found(self):
        """Verifies graceful handling when video path does not exist."""
        non_existent = os.path.join(self.temp_dir.name, "missing.mp4")
        started = self.cam.start_video_file(non_existent)
        self.assertFalse(started)
        self.assertEqual(self.cam.status, CameraStatus.ERROR)
        self.assertIn("not found", self.cam.error_message.lower())

    def test_video_file_looping(self):
        """Verifies that playback continues seamlessly when loop=True."""
        started = self.cam.start_video_file(self.video_path, loop=True)
        self.assertTrue(started)

        # Wait longer than clip length (20 frames @ 25fps = 0.8s)
        time.sleep(1.2)
        self.assertTrue(self.cam.is_running)
        success, frame = self.cam.get_frame()
        self.assertTrue(success)
        self.assertIsNotNone(frame)

    def test_video_stop_and_restart(self):
        """Verifies stopping and restarting video playback cleanly."""
        self.cam.start_video_file(self.video_path, loop=True)
        self.assertTrue(self.cam.is_running)

        self.cam.stop()
        self.assertFalse(self.cam.is_running)
        self.assertEqual(self.cam.status, CameraStatus.OFFLINE)

        # Restart
        restarted = self.cam.restart()
        self.assertTrue(restarted)
        self.assertTrue(self.cam.is_running)
        self.assertEqual(self.cam.status, CameraStatus.FILE)


if __name__ == "__main__":
    unittest.main()
