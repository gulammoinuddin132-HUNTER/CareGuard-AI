"""
scripts/verify_visual_focus_and_evidence.py
---------------------------------------------
Offline verification script for CareGuard AI visual focus and evidence capture.
Processes frames from 'data/videos/Throwing Mattresses.mp4' through the detector,
tracker, behaviour engine, evidence cropper, and HUD renderer.
"""

import sys
import os
import time
from pathlib import Path
import cv2
import numpy as np

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import DATA_DIR, WAREHOUSE_FLOOR_Y_RATIO
from src.core.object_detection import ObjectDetectionEngine
from src.core.warehouse_tracker import WarehouseObjectTracker
from src.core.warehouse_behaviour_engine import TemporalWarehouseBehaviourEngine
from src.core.warehouse_evidence_cropper import save_evidence_snapshot, create_interaction_evidence_crop
from src.api.state import CareGuardBackendState

def main():
    video_path = DATA_DIR / "videos" / "Throwing Mattresses.mp4"
    if not video_path.exists():
        print(f"Error: Video file not found at {video_path}")
        return 1

    print("=" * 65)
    print("  CAREGUARD AI - VISUAL FOCUS & EVIDENCE VERIFICATION")
    print(f"  TARGET VIDEO: {video_path.name}")
    print("=" * 65)

    detector = ObjectDetectionEngine()
    detector.initialize()

    tracker = WarehouseObjectTracker(
        frame_width=1280,
        frame_height=720,
        confirmation_frames=1,
        floor_y_threshold_ratio=WAREHOUSE_FLOOR_Y_RATIO,
    )

    behaviour_engine = TemporalWarehouseBehaviourEngine(
        frame_width=1280,
        frame_height=720,
        floor_y_threshold_ratio=WAREHOUSE_FLOOR_Y_RATIO,
    )

    backend = CareGuardBackendState.get_instance()

    cap = cv2.VideoCapture(str(video_path))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    print(f"Loaded video: {frame_count} frames, {fps:.1f} FPS")

    detected_events = []
    saved_evidence_files = []
    annotated_clean_frames = []

    frame_idx = 0
    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        sim_time = start_time + (frame_idx / fps)

        # AI Detection every 2 frames for speed
        if frame_idx % 2 == 1:
            dets = detector.detect(frame)
            tracks = tracker.update(dets, current_time=sim_time)
        else:
            tracks = tracker.propagate_tracks(current_time=sim_time)

        # Behaviour Evaluation
        events = behaviour_engine.evaluate_frame(tracks, current_time=sim_time, video_source=video_path.name)
        if events:
            for evt in events:
                detected_events.append((frame_idx, evt))
                print(f"[Frame {frame_idx:04d}] DETECTED EVENT: {evt.behaviour_type.value} | Risk: {evt.risk_level} | Conf: {evt.confidence:.2f}")

                # Save smart interaction evidence crop
                p_trk = next((t for t in tracks if t.track_id == evt.product_track_id), None)
                h_trk = next((t for t in tracks if t.track_id == evt.person_track_id), None)
                if not h_trk and p_trk and p_trk.associated_person_id:
                    h_trk = next((t for t in tracks if t.track_id == p_trk.associated_person_id), None)

                snap_path = save_evidence_snapshot(
                    frame=frame,
                    output_dir=DATA_DIR / "evidence",
                    filename_prefix=f"verify_{evt.behaviour_type.value.lower()}",
                    product_track=p_trk,
                    person_track=h_trk,
                    event_type=evt.behaviour_type.display_title if hasattr(evt.behaviour_type, "display_title") else str(evt.behaviour_type),
                    risk_level=evt.risk_level,
                )
                if snap_path:
                    saved_evidence_files.append(snap_path)
                    print(f"  -> Generated smart evidence crop: {Path(snap_path).name}")

                # Render Clean View HUD with active event
                hud_clean = backend._render_warehouse_hud(
                    frame.copy(),
                    tracks=tracks,
                    events=[evt],
                    overlay_mode="clean",
                )
                annotated_clean_frames.append(hud_clean)

        # Sample first 400 frames
        if frame_idx >= 400:
            break

    cap.release()

    print("\n" + "=" * 65)
    print("  VERIFICATION SUMMARY")
    print(f"  Frames processed:       {frame_idx}")
    print(f"  Total events detected:  {len(detected_events)}")
    print(f"  Evidence crops saved:   {len(saved_evidence_files)}")
    print("=" * 65)

    assert len(detected_events) > 0, "Expected real CV events to be detected from Throwing Mattresses.mp4"
    assert len(saved_evidence_files) > 0, "Expected smart evidence crops to be generated"
    print("Verification successfully passed!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
