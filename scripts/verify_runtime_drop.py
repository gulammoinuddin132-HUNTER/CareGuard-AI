import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
from src.api.state import CareGuardBackendState
from src.core.warehouse_models import WarehouseBehaviourType

def test_drop_playback():
    state = CareGuardBackendState.get_instance()
    # Warm up detector
    import numpy as np
    dummy = np.zeros((480, 640, 3), dtype=np.uint8)
    state.detector.detect(dummy)

    runs = 10
    detected_count = 0

    for run_i in range(runs):
        state.reset_session(f"test_run_{run_i}")
        state.camera.start_video_file("data/videos/Rolling and dropping carton.mp4", loop=False)
        
        events_seen = []
        drop_detected = False
        start_t = time.time()
        while time.time() - start_t < 4.0:
            if state.latest_event and state.latest_event.behaviour_type not in [e.behaviour_type for e in events_seen]:
                events_seen.append(state.latest_event)
            if state.latest_verified_event and state.latest_verified_event.behaviour_type == WarehouseBehaviourType.PRODUCT_DROPPED:
                drop_detected = True
            time.sleep(0.04)
        
        state.camera.stop()
        res_str = "PASS (PRODUCT_DROPPED DETECTED)" if drop_detected else f"FAIL - Saw: {[e.behaviour_type.value for e in events_seen]}"
        if drop_detected:
            detected_count += 1
        print(f"Run {run_i+1}/{runs}: {res_str}")

    print(f"\nOVERALL RUNTIME DROP DETECTION RATE: {detected_count}/{runs} ({detected_count/runs*100:.0f}%)")

if __name__ == "__main__":
    test_drop_playback()
