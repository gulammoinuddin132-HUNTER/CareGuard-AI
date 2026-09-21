"""
src/api/state.py
----------------
Shared backend singleton state holding active computer-vision engines,
video ingestion manager, tracker, 10-behaviour temporal engine, and SQLite database.
"""

import logging
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
import cv2
import numpy as np

from config import (
    DATABASE_PATH,
    DATA_DIR,
    DEFAULT_CAMERA_INDEX,
    WAREHOUSE_FLOOR_Y_RATIO,
    DEFAULT_ZONES,
    WAREHOUSE_DEFAULT_VIDEO_DIR,
    WAREHOUSE_PRODUCT_CONF_THRESHOLD,
    WAREHOUSE_TRACK_MAX_MISSED_FRAMES,
    WAREHOUSE_TRACK_MAX_AGE_SECONDS,
)
from src.database.db_manager import DatabaseManager
from src.camera.camera_manager import CameraManager, CameraStatus, CameraMode
from src.core.object_detection import ObjectDetectionEngine
from src.core.warehouse_tracker import WarehouseObjectTracker, compute_iou, compute_centroid_dist, compute_bbox_min_dist
from src.core.warehouse_behaviour_engine import TemporalWarehouseBehaviourEngine
from src.core.warehouse_models import WarehouseBehaviourEvent, WarehouseBehaviourType, TrackedEntity, EventState
from src.core.warehouse_evidence_cropper import save_evidence_snapshot, create_interaction_evidence_crop, log_event_geometry

logger = logging.getLogger("CareGuard.APIState")

SEVERITY_RANK: Dict[str, int] = {
    "GREEN": 1,
    "YELLOW": 2,
    "ORANGE": 3,
    "RED": 4,
}


class CareGuardBackendState:
    """Singleton state manager coordinating CV inference, video streaming, and DB logging."""

    _instance: Optional["CareGuardBackendState"] = None

    def __init__(self):
        self.db = DatabaseManager(db_path=DATABASE_PATH)
        self.camera = CameraManager()
        self.detector = ObjectDetectionEngine(db_manager=self.db, conf_threshold=WAREHOUSE_PRODUCT_CONF_THRESHOLD)
        try:
            self.detector.initialize()
            print("=" * 65)
            print("  CAREGUARD AI // DETECTION ENGINE DIAGNOSTIC")
            print(f"  MODEL LOADED:   {getattr(self.detector._detector, 'mode_name', 'YOLO26n Warehouse Perception')}")
            print(f"  WEIGHTS PATH:   {getattr(self.detector._detector, 'model_path', 'N/A')}")
            print(f"  BACKEND:        {'PyTorch' if getattr(self.detector._detector, '_yolo_model', None) is not None else ('OpenCV DNN ONNX' if getattr(self.detector._detector, '_net', None) is not None else 'UNINITIALIZED')}")
            print(f"  CLASSES:        {self.detector.class_names}")
            print(f"  CONF THRESHOLD: {getattr(self.detector._detector, 'conf_threshold', 'N/A')}")
            print(f"  NMS THRESHOLD:  {getattr(self.detector._detector, 'nms_threshold', 'N/A')}")
            print(f"  STATUS:         {'READY' if self.detector.is_ready else 'FAILED'}")
            print("=" * 65)
        except Exception as e:
            logger.warning(f"Could not initialize detector: {e}")

        self.frame_width: int = 640
        self.frame_height: int = 480

        self.tracker = WarehouseObjectTracker(
            frame_width=640,
            frame_height=480,
            confirmation_frames=2,
            max_missed_frames=WAREHOUSE_TRACK_MAX_MISSED_FRAMES,
            max_track_age_seconds=WAREHOUSE_TRACK_MAX_AGE_SECONDS,
            floor_y_threshold_ratio=WAREHOUSE_FLOOR_Y_RATIO,
        )

        self.behaviour_engine = TemporalWarehouseBehaviourEngine(
            floor_y_threshold_ratio=WAREHOUSE_FLOOR_Y_RATIO,
            frame_width=640,
            frame_height=480,
            evidence_capture_callback=self._capture_evidence_snapshot,
        )

        self.latest_event: Optional[WarehouseBehaviourEvent] = None
        self.active_verified_event: Optional[WarehouseBehaviourEvent] = None
        self.event_resolution_grace_seconds: float = 4.0
        self.latest_processed_frame: Optional[np.ndarray] = None
        self.latest_jpeg_bytes: Optional[bytes] = None
        
        # Active Playback Session & Synchronization
        self.session_counter: int = 1
        ts_init = time.strftime("%Y%m%d_%H%M%S")
        self.active_session_id: str = f"SES-{ts_init}-001"
        self.active_source: str = "STANDBY"
        self.current_frame_index: int = 0
        self.active_event_last_triggered_time: float = 0.0
        self.latest_verified_event: Optional[WarehouseBehaviourEvent] = None

        # Real-time Telemetry & Diagnostics
        self.fps: float = 0.0
        self.detection_fps: float = 0.0
        self.inference_latency_ms: float = 0.0
        self.tracking_latency_ms: float = 0.0
        self.active_tracks_count: int = 0
        self.total_frames_processed: int = 0
        self.last_frame_timestamp: Optional[str] = None
        self.detection_status: str = "ACTIVE"
        self.tracking_status: str = "STANDBY"
        self.current_risk_level: str = "GREEN"
        self.is_paused: bool = False
        self.overlay_mode: str = "clean"  # 'clean' (default), 'detection', 'tracking', 'diagnostics'

        # Threading and synchronization
        self._lock = threading.Lock()
        self._det_lock = threading.Lock()
        self._latest_raw_frame_for_det: Optional[np.ndarray] = None
        self._latest_detections: List[Any] = []
        self._current_det_seq: int = 0
        self._last_used_det_seq: int = -1
        self._frame_times: List[float] = []
        self._det_times: List[float] = []
        self._stop_event = threading.Event()

        # No auto-start on backend initialization: stream remains idle until operator explicitly starts it
        logger.info("[BACKEND] Initialized in STANDBY mode. Awaiting operator stream start.")

        # Start decoupled detection worker thread & main rendering loop
        self._det_worker_thread = threading.Thread(target=self._detection_worker_loop, daemon=True)
        self._det_worker_thread.start()

        self._worker_thread = threading.Thread(target=self._cv_processing_loop, daemon=True)
        self._worker_thread.start()

    def reset_session(self, source_name: str) -> str:
        """
        Cleanly terminates previous event state and initializes a new isolated playback session.
        Called on video upload or source change to prevent cross-video event leakage.
        """
        with self._lock:
            self.session_counter += 1
            ts = time.strftime("%Y%m%d_%H%M%S")
            self.active_session_id = f"SES-{ts}-{self.session_counter:03d}"
            self.active_source = source_name
            self.current_frame_index = 0
            self.total_frames_processed = 0
            self.latest_event = None
            self.active_verified_event = None
            self.latest_verified_event = None
            self.current_risk_level = "GREEN"
            self.active_event_last_triggered_time = 0.0
            self.latest_processed_frame = None
            self.latest_jpeg_bytes = None
            self.is_paused = False
            with self._det_lock:
                self._latest_raw_frame_for_det = None
                self._latest_detections = []
            self.tracker.reset()
            self.behaviour_engine.reset()
            logger.info(f"[SESSION] Initialized new playback session: {self.active_session_id} for source: {source_name}")
            return self.active_session_id

    def pause(self) -> None:
        """Freezes playback, active event state, and MJPEG frame without resetting session."""
        with self._lock:
            self.is_paused = True
            self.tracking_status = "PAUSED"
            self.detection_status = "PAUSED"
            self.camera.pause()
            active_info = self.latest_event.get("event_id") if isinstance(self.latest_event, dict) else getattr(self.latest_event, "event_id", "None")
            logger.info(f"[SESSION] Paused session {self.active_session_id} on frame {self.current_frame_index}. Preserving active event: {active_info}")

    def resume(self) -> None:
        """Resumes existing playback session and unfreezes capture loop."""
        with self._lock:
            self.is_paused = False
            self.camera.resume()
            # Update last observed time so paused duration does not immediately expire grace period
            now = time.time()
            if self.active_verified_event and getattr(self.active_verified_event, "state", None) == EventState.ACTIVE:
                self.active_verified_event.last_observed_time = now
                self.active_event_last_triggered_time = now
            logger.info(f"[SESSION] Resumed session {self.active_session_id} on frame {self.current_frame_index}.")


    @classmethod
    def get_instance(cls) -> "CareGuardBackendState":
        if cls._instance is None:
            cls._instance = CareGuardBackendState()
        return cls._instance

    def get_full_diagnostics_telemetry(self) -> Dict[str, Any]:
        """
        Gathers comprehensive, real-time, truthful engineering telemetry
        directly from active detector, tracker, behaviour engine, and camera states.
        """
        with self._lock:
            # 1. Model Telemetry
            det_engine = self.detector
            active_detector = getattr(det_engine, "_detector", None)
            model_path_str = str(getattr(active_detector, "model_path", "N/A"))
            is_pytorch = getattr(active_detector, "_yolo_model", None) is not None
            is_onnx = getattr(active_detector, "_net", None) is not None
            backend_type = "PyTorch" if is_pytorch else ("OpenCV DNN ONNX" if is_onnx else "STANDBY")

            model_telemetry = {
                "name": getattr(active_detector, "mode_name", "YOLO26n Warehouse Perception (4 Classes)"),
                "backend": backend_type,
                "model_path": model_path_str,
                "input_resolution": "640x640",
                "conf_threshold": getattr(active_detector, "conf_threshold", 0.25),
                "nms_threshold": getattr(active_detector, "nms_threshold", 0.45),
                "status": "READY" if det_engine.is_ready else "STANDBY",
                "classes": getattr(det_engine, "class_names", ["person", "product", "pallet", "mhe"]),
            }

            # 2. Video Telemetry
            total_frames = self.camera.video_progress[1] if self.camera.is_file_mode else 0
            cur_frame = self.camera.video_progress[0] if self.camera.is_file_mode else self.total_frames_processed
            src_fps = self.camera.fps or 30.0
            video_secs = (cur_frame / max(1.0, src_fps)) if src_fps > 0 else 0.0
            mins = int(video_secs // 60)
            secs = video_secs % 60
            video_time_str = f"{mins:02d}:{secs:04.1f}"

            video_telemetry = {
                "source": self.active_source,
                "session_id": self.active_session_id,
                "current_frame": cur_frame,
                "total_frames": total_frames,
                "video_time": video_time_str,
                "source_fps": round(src_fps, 1),
                "render_fps": round(self.fps, 1),
                "detection_fps": round(self.detection_fps, 1),
                "inference_latency_ms": self.inference_latency_ms,
                "tracking_latency_ms": self.tracking_latency_ms,
            }

            # 3. Detection Telemetry (from current confirmed active tracks & recent detections)
            all_confirmed_tracks = [t for t in self.tracker.all_tracks if t.is_confirmed and t.missed_frames == 0]
            cat_counts = {"PERSON": 0, "PRODUCT": 0, "PALLET": 0, "MHE": 0}
            active_dets_list = []
            for t in all_confirmed_tracks:
                cat_val = t.category.value
                if cat_val in cat_counts:
                    cat_counts[cat_val] += 1
                disp_lbl = f"HANDLER {int(t.confidence*100)}%" if cat_val == "PERSON" else f"{cat_val} {int(t.confidence*100)}%"
                active_dets_list.append({
                    "track_id": t.track_id,
                    "category": cat_val,
                    "label": t.label,
                    "display_label": disp_lbl,
                    "confidence": round(t.confidence, 3),
                    "bbox": list(t.current_bbox),
                })

            detection_telemetry = {
                "counts": cat_counts,
                "total_active": len(active_dets_list),
                "detections": active_dets_list,
            }

            # 4. Tracking Telemetry
            tracks_list = []
            now_t = time.time()
            for t in all_confirmed_tracks:
                age_s = round(now_t - t.first_seen, 2) if t.first_seen else 0.0
                tracks_list.append({
                    "track_id": t.track_id,
                    "category": t.category.value,
                    "label": t.label,
                    "confidence": round(t.confidence, 3),
                    "bbox": list(t.current_bbox),
                    "age_seconds": age_s,
                    "detection_count": len(t.history),
                    "missed_frames": t.missed_frames,
                    "is_grounded": t.current_state.is_grounded if t.current_state else True,
                })

            tracking_telemetry = {
                "active_tracks_count": len(tracks_list),
                "tracks": tracks_list,
            }

            # 5. Active Product / Handler Relationship & Kinematics (Multi-Product Aware)
            prod_tracks = [t for t in all_confirmed_tracks if t.category.value == "PRODUCT"]
            prod_track = prod_tracks[0] if prod_tracks else None
            products_summary = []
            for pt in prod_tracks:
                pt_state = pt.current_state
                products_summary.append({
                    "product_track_id": pt.track_id,
                    "interaction_state": pt.interaction_state.value if hasattr(pt.interaction_state, "value") else str(pt.interaction_state),
                    "carrying_state": pt.carrying_state or "NONE",
                    "speed": round(pt_state.speed, 1) if pt_state else 0.0,
                    "is_grounded": pt_state.is_grounded if pt_state else True,
                    "bbox": list(pt.current_bbox),
                    "raw_bbox": list(pt.raw_bbox) if pt.raw_bbox else list(pt.current_bbox),
                    "validated_bbox": list(pt.validated_bbox) if pt.validated_bbox else list(pt.current_bbox),
                    "smoothed_bbox": list(pt.smoothed_bbox) if pt.smoothed_bbox else list(pt.current_bbox),
                    "detection_confidence": round(pt.detection_confidence or pt.confidence, 3),
                    "track_confidence": round(pt.confidence, 3),
                    "localization_quality": round(getattr(pt, "localization_quality", 1.0), 2),
                    "validation_status": getattr(pt, "validation_status", "PASS"),
                    "validation_reason": getattr(pt, "validation_reason", "VALID_GEOMETRY"),
                    "handler_id": pt.associated_person_id,
                    "carry_telemetry": getattr(pt, "carry_telemetry", {}),
                })

            handler_track = None
            rel_info = {
                "product_track_id": None,
                "handler_track_id": None,
                "relationship": "NONE",
                "interaction_state": "FREE",
                "relative_motion": [0.0, 0.0, 0.0],
                "edge_distance_px": None,
                "centroid_distance_px": None,
                "products_summary": products_summary,
                "total_products_tracked": len(prod_tracks),
            }
            kin_info = {
                "vx": 0.0,
                "vy": 0.0,
                "speed": 0.0,
                "accel_y": 0.0,
                "elevation_ratio": 0.0,
                "bottom_y": 0,
                "ground_state": "N/A",
            }

            if prod_track:
                rel_info["product_track_id"] = prod_track.track_id
                rel_info["relationship"] = prod_track.carrying_state or "NONE"
                rel_info["interaction_state"] = prod_track.interaction_state.value if hasattr(prod_track.interaction_state, "value") else str(prod_track.interaction_state)
                rel_info["relative_motion"] = list(prod_track.relative_motion)
                if prod_track.associated_person_id:
                    handler_track = next((t for t in all_confirmed_tracks if t.track_id == prod_track.associated_person_id), None)
                    rel_info["handler_track_id"] = prod_track.associated_person_id
                    if handler_track:
                        rel_info["centroid_distance_px"] = round(compute_centroid_dist(handler_track.current_bbox, prod_track.current_bbox), 1)
                        rel_info["edge_distance_px"] = round(compute_bbox_min_dist(handler_track.current_bbox, prod_track.current_bbox), 1)

                if prod_track.current_state:
                    s = prod_track.current_state
                    kin_info = {
                        "vx": round(s.velocity[0], 1),
                        "vy": round(s.velocity[1], 1),
                        "speed": round(s.speed, 1),
                        "accel_y": round(s.vertical_accel, 1),
                        "elevation_ratio": round(s.elevation_ratio, 2),
                        "bottom_y": s.bottom_y,
                        "ground_state": "GROUNDED" if s.is_grounded else "AIRBORNE",
                    }

            # 6. Behaviour Engine Candidate State
            cand_name = "NONE"
            trigger_status = "IDLE"
            rules_dict = {}
            active_evt = self.active_verified_event if (self.active_verified_event and self.active_verified_event.state == EventState.ACTIVE) else self.latest_event
            if active_evt and (active_evt.state == EventState.ACTIVE or (now_t - self.active_event_last_triggered_time) <= 5.0):
                cand_name = active_evt.behaviour_type.value if hasattr(active_evt.behaviour_type, "value") else str(active_evt.behaviour_type)
                trigger_status = "PASS"
                rules_dict = {
                    "event_id": active_evt.event_id,
                    "state": active_evt.state.value if hasattr(active_evt.state, "value") else str(active_evt.state),
                    "confidence": f"{int(active_evt.confidence * 100)}%",
                    "detection_confidence": f"{int(active_evt.detection_confidence * 100)}%" if active_evt.detection_confidence else "N/A",
                    "behaviour_confidence": f"{int(active_evt.behaviour_confidence * 100)}%" if active_evt.behaviour_confidence else "N/A",
                    "duration": f"{active_evt.duration_seconds:.1f}s",
                    "observed": active_evt.observed_behaviour,
                }
            elif prod_track and prod_track.current_state:
                if prod_track.current_state.speed > 35.0:
                    cand_name = "MATERIAL_PUSHED_THROWN" if not prod_track.current_state.is_grounded else "PRODUCT_DRAGGED"
                    trigger_status = "MONITORING"
                    rules_dict = {
                        "current_speed": f"{prod_track.current_state.speed:.1f} px/s",
                        "elevation": f"{prod_track.current_state.elevation_ratio:.2f}",
                        "grounded": "TRUE" if prod_track.current_state.is_grounded else "FALSE",
                        "interaction": prod_track.interaction_state.value if hasattr(prod_track.interaction_state, "value") else str(prod_track.interaction_state),
                    }

            behaviour_telemetry = {
                "candidate": cand_name,
                "trigger_status": trigger_status,
                "rules": rules_dict,
            }

            # 7. Event & Evidence Telemetry
            evt_dict = active_evt.to_dict() if active_evt else None
            evidence_telemetry = {
                "status": "AVAILABLE" if (evt_dict and evt_dict.get("evidence_frame_path")) else "NONE",
                "evidence_path": evt_dict.get("evidence_frame_path") if evt_dict else None,
                "product_track_id": active_evt.product_track_id if active_evt else None,
                "handler_track_id": active_evt.person_track_id if active_evt else None,
                "timestamp": active_evt.start_timestamp if active_evt else None,
            }

            # 8. Why This Event Fired (Physical Grounding & Rules)
            why_fired = None
            if active_evt:
                rule_tr = active_evt.rule_trace or {}
                kin_tr = active_evt.kinematics_trace or {}
                temp_tr = active_evt.temporal_trace or {}
                dbg_tr = active_evt.debug_trace or {}
                why_fired = {
                    "event_id": active_evt.event_id,
                    "behaviour": active_evt.behaviour_type.value if hasattr(active_evt.behaviour_type, "value") else str(active_evt.behaviour_type),
                    "risk_level": active_evt.risk_level,
                    "confidence": round(active_evt.confidence, 3),
                    "detection_confidence": round(active_evt.detection_confidence, 3) if active_evt.detection_confidence else None,
                    "behaviour_confidence": round(active_evt.behaviour_confidence, 3) if active_evt.behaviour_confidence else None,
                    "interaction_sequence": active_evt.interaction_state_sequence,
                    "state": active_evt.state.value if hasattr(active_evt.state, "value") else str(active_evt.state),
                    "trigger_conditions": rule_tr.get("trigger_conditions", {}),
                    "failed_conditions": rule_tr.get("failed_conditions", {}),
                    "kinematics": kin_tr,
                    "temporal": temp_tr,
                    "debug": dbg_tr,
                    "grounded": kin_tr.get("product_grounded", True),
                    "horizontal_speed": kin_tr.get("product_vx", 0.0),
                    "vertical_speed": kin_tr.get("product_vy", 0.0),
                    "displacement": kin_tr.get("product_displacement", 0.0),
                    "duration_seconds": active_evt.duration_seconds,
                }

            return {
                "model": model_telemetry,
                "video": video_telemetry,
                "detection": detection_telemetry,
                "tracking": tracking_telemetry,
                "relationship": rel_info,
                "kinematics": kin_info,
                "behaviour": behaviour_telemetry,
                "event": evt_dict,
                "evidence": evidence_telemetry,
                "why_this_event_fired": why_fired,
            }

    def _capture_evidence_snapshot(
        self,
        prefix: str,
        product_track: Optional[TrackedEntity] = None,
        person_track: Optional[TrackedEntity] = None,
        event_title: Optional[str] = None,
        risk_level: Optional[str] = None,
    ) -> Optional[str]:
        """Saves current processed video frame to evidence directory using smart interaction cropping."""
        if self.camera.is_running:
            success, raw_frame = self.camera.get_frame()
            if success and raw_frame is not None and raw_frame.size > 0:
                snap_path = save_evidence_snapshot(
                    frame=raw_frame,
                    output_dir=DATA_DIR / "evidence",
                    filename_prefix=prefix,
                    product_track=product_track,
                    person_track=person_track,
                    event_type=event_title or "WAREHOUSE SAFETY INCIDENT",
                    risk_level=risk_level or "YELLOW",
                )
                if snap_path:
                    return snap_path
            return self.camera.capture_snapshot(filename_prefix=prefix)
        return None

    def _detection_worker_loop(self):
        """Dedicated background AI inference worker thread (runs continuously at max CPU rate ~12-15 Hz)."""
        while not self._stop_event.is_set():
            try:
                frame_to_detect = None
                with self._det_lock:
                    if self._latest_raw_frame_for_det is not None:
                        frame_to_detect = self._latest_raw_frame_for_det
                        self._latest_raw_frame_for_det = None

                if frame_to_detect is None:
                    time.sleep(0.005)
                    continue

                t0 = time.perf_counter()
                dets = self.detector.detect(frame_to_detect)
                dt_ms = (time.perf_counter() - t0) * 1000.0

                now_perf = time.perf_counter()
                with self._lock:
                    self._latest_detections = dets
                    self._current_det_seq += 1
                    self.inference_latency_ms = round(dt_ms, 1)

                    # Rolling detection rate
                    self._det_times.append(now_perf)
                    cutoff = now_perf - 2.0
                    self._det_times = [t for t in self._det_times if t >= cutoff]
                    if len(self._det_times) > 1:
                        span = self._det_times[-1] - self._det_times[0]
                        self.detection_fps = round((len(self._det_times) - 1) / max(0.001, span), 1)

            except Exception as e:
                logger.error(f"Error in detection worker loop: {e}", exc_info=True)
                time.sleep(0.02)

    def _cv_processing_loop(self):
        """
        High-speed real-time frame processing loop (runs at full camera/video 25-30+ FPS).
        Integrates detections asynchronously and propagates kinematics smoothly.
        """
        while not self._stop_event.is_set():
            try:
                if self.is_paused:
                    time.sleep(0.04)
                    continue

                if not self.camera.is_running:
                    with self._lock:
                        self.tracking_status = "STANDBY"
                    time.sleep(0.04)
                    continue

                success, frame = self.camera.get_frame()
                if not success or frame is None or frame.size == 0:
                    time.sleep(0.01)
                    continue

                fh, fw = frame.shape[:2]
                if fw != self.frame_width or fh != self.frame_height:
                    self.frame_width = fw
                    self.frame_height = fh
                    self.tracker.set_frame_dimensions(fw, fh)
                    self.behaviour_engine.set_frame_dimensions(fw, fh)

                now = time.time()
                now_perf = time.perf_counter()

                # Dispatch latest frame to detection worker (latest-frame strategy, zero queuing)
                with self._det_lock:
                    self._latest_raw_frame_for_det = frame

                # Check if new AI detection sequence has arrived
                t_trk_0 = time.perf_counter()
                with self._lock:
                    has_new_dets = (self._current_det_seq != self._last_used_det_seq)
                    cur_dets = list(self._latest_detections)
                    if has_new_dets:
                        self._last_used_det_seq = self._current_det_seq

                if has_new_dets:
                    tracks = self.tracker.update(cur_dets, current_time=now)
                else:
                    tracks = self.tracker.propagate_tracks(current_time=now)

                trk_latency = (time.perf_counter() - t_trk_0) * 1000.0

                tracking_state = f"TRACKING ({len(tracks)} active)" if tracks else "SEARCHING"
                detection_state = "ACTIVE" if getattr(self.detector, "is_ready", True) else "STANDBY"

                # Identify active source name
                if self.camera.is_file_mode and self.camera.video_file_path:
                    curr_source = Path(self.camera.video_file_path).name
                elif self.camera.is_physical:
                    curr_source = f"WEBCAM_{self.camera.camera_index}"
                elif self.camera.is_fallback_mode:
                    curr_source = "SYNTHETIC_STREAM"
                else:
                    curr_source = "WAREHOUSE_STREAM"

                with self._lock:
                    if self.active_source != curr_source:
                        self.active_source = curr_source
                    self.current_frame_index = self.camera.video_progress[0] if self.camera.is_file_mode else self.total_frames_processed

                # 3. 10-Behaviour sequence analysis
                new_events = self.behaviour_engine.evaluate_frame(
                    tracks,
                    current_time=now,
                    video_source=curr_source,
                )

                # Process event lifecycle state machine with temporal hysteresis
                with self._lock:
                    SEVERITY_RANK = {"RED": 4, "ORANGE": 3, "YELLOW": 2, "GREEN": 1}

                    if new_events:
                        for evt in new_events:
                            evt.video_source = curr_source
                            evt.state = EventState.VERIFIED
                            if isinstance(evt.metadata, dict):
                                evt.metadata["session_id"] = self.active_session_id
                                evt.metadata["frame_index"] = self.current_frame_index

                            # Populate session and frame identifiers into forensic audit traces
                            if evt.temporal_trace:
                                evt.temporal_trace["session_id"] = self.active_session_id
                                evt.temporal_trace["trigger_frame"] = self.current_frame_index
                            if evt.debug_trace:
                                evt.debug_trace["session_id"] = self.active_session_id
                                evt.debug_trace["trigger_frame"] = self.current_frame_index

                            # Create smart interaction evidence crop focused on handler + product
                            p_trk = next((t for t in tracks if t.track_id == evt.product_track_id), None)
                            h_trk = next((t for t in tracks if t.track_id == evt.person_track_id), None)
                            if not h_trk and p_trk and p_trk.associated_person_id:
                                h_trk = next((t for t in tracks if t.track_id == p_trk.associated_person_id), None)
                            b_type = evt.behaviour_type.value if hasattr(evt.behaviour_type, "value") else str(evt.behaviour_type)

                            # Always ensure a valid decodable evidence frame exists on disk
                            needs_snap = not evt.evidence_frame_path or not Path(evt.evidence_frame_path).exists()
                            if needs_snap:
                                snap_path = save_evidence_snapshot(
                                    frame=frame,
                                    output_dir=DATA_DIR / "evidence",
                                    filename_prefix=f"evidence_{b_type.lower()}",
                                    product_track=p_trk,
                                    person_track=h_trk,
                                    product_bbox=evt.product_bbox,
                                    person_bbox=evt.person_bbox,
                                    event_type=evt.behaviour_type.display_title if hasattr(evt.behaviour_type, "display_title") else str(evt.behaviour_type),
                                    risk_level=evt.risk_level,
                                )
                                if snap_path:
                                    evt.evidence_frame_path = snap_path
                                    if evt.temporal_trace:
                                        evt.temporal_trace["evidence_file"] = Path(snap_path).name

                            # Log geometry telemetry
                            geom_telemetry = log_event_geometry(
                                event_id=evt.event_id,
                                frame_shape=frame.shape[:2],
                                product_track_id=evt.product_track_id,
                                product_bbox=evt.product_bbox,
                                handler_track_id=evt.person_track_id,
                                handler_bbox=evt.person_bbox,
                                focus_box=evt.focus_bbox or (0, 0, frame.shape[1], frame.shape[0]),
                            )
                            if isinstance(evt.metadata, dict):
                                evt.metadata["geometry_telemetry"] = geom_telemetry

                            self.db.log_warehouse_event(
                                event_id=evt.event_id,
                                behaviour_type=evt.behaviour_type.value if hasattr(evt.behaviour_type, "value") else str(evt.behaviour_type),
                                risk_level=evt.risk_level,
                                confidence=evt.confidence,
                                start_timestamp=evt.start_timestamp,
                                end_timestamp=evt.end_timestamp,
                                duration_seconds=evt.duration_seconds,
                                observed_behaviour=evt.observed_behaviour,
                                potential_risk=evt.potential_risk,
                                recommended_action=evt.recommended_action,
                                product_track_id=evt.product_track_id,
                                person_track_id=evt.person_track_id,
                                severity_reason=evt.severity_reason,
                                severity_factors=evt.severity_factors,
                                evidence_frame_path=evt.evidence_frame_path,
                                video_source=evt.video_source,
                                metadata=evt.metadata,
                            )

                        # Authoritative active event assignment with sequential action support & severity protection
                        sorted_events = sorted(
                            new_events,
                            key=lambda e: SEVERITY_RANK.get(getattr(e, "risk_level", "GREEN"), 1),
                            reverse=True,
                        )
                        candidate_evt = sorted_events[0]
                        candidate_evt.state = EventState.ACTIVE
                        candidate_evt.activated_at = now
                        candidate_evt.last_observed_time = now
                        self.latest_verified_event = candidate_evt

                        candidate_sev = SEVERITY_RANK.get(getattr(candidate_evt, "risk_level", "GREEN"), 1)
                        active_sev = SEVERITY_RANK.get(getattr(self.active_verified_event, "risk_level", "GREEN"), 1) if self.active_verified_event else 0
                        time_since_active = now - self.active_event_last_triggered_time

                        # Protect high-severity events (e.g. RED / PRODUCT_DROPPED) from being squashed by lower severity events within 3.5s
                        should_override = (
                            self.active_verified_event is None
                            or candidate_sev >= active_sev
                            or time_since_active >= 3.5
                        )

                        if should_override:
                            if self.active_verified_event and self.active_verified_event.state == EventState.ACTIVE:
                                if (candidate_evt.behaviour_type != self.active_verified_event.behaviour_type or
                                    candidate_evt.product_track_id != self.active_verified_event.product_track_id):
                                    self.active_verified_event.state = EventState.RESOLVED
                                    self.active_verified_event.resolved_at = now
                            
                            self.active_verified_event = candidate_evt
                            self.latest_event = candidate_evt
                            self.current_risk_level = candidate_evt.risk_level
                            self.active_event_last_triggered_time = now
                        else:
                            self.latest_event = self.active_verified_event
                            self.current_risk_level = self.active_verified_event.risk_level
                    else:
                        # Normal frame without new violation: Apply temporal hysteresis grace period
                        if self.active_verified_event and self.active_verified_event.state == EventState.ACTIVE:
                            grace = getattr(self.active_verified_event, "grace_period_seconds", self.event_resolution_grace_seconds)
                            elapsed = now - (self.active_verified_event.last_observed_time or self.active_event_last_triggered_time)
                            if elapsed > grace:
                                # Grace period elapsed without re-triggering -> RESOLVED
                                self.active_verified_event.state = EventState.RESOLVED
                                self.active_verified_event.resolved_at = now
                                self.latest_verified_event = self.active_verified_event
                                self.active_verified_event = None
                                self.latest_event = self.latest_verified_event
                                self.current_risk_level = "GREEN"
                            else:
                                # Still within grace period: REMAINS ACTIVE
                                self.latest_event = self.active_verified_event
                                self.current_risk_level = self.active_verified_event.risk_level

                # 4. Draw HUD overlays onto frame using updated active event state
                annotated = self._render_warehouse_hud(frame.copy(), tracks, new_events)

                # 5. Pre-encode directly to JPEG for instant 0ms streaming delivery
                ret, jpeg = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                jpeg_bytes = jpeg.tobytes() if ret else None

                # 6. Update frame buffers & telemetry
                with self._lock:
                    self.latest_processed_frame = annotated
                    self.latest_jpeg_bytes = jpeg_bytes
                    self.active_tracks_count = len(tracks)
                    self.total_frames_processed += 1
                    self.last_frame_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
                    self.detection_status = detection_state
                    self.tracking_status = tracking_state
                    self.tracking_latency_ms = round(trk_latency, 2)

                    # Rolling processed FPS calculation over last 1.5 seconds
                    self._frame_times.append(now_perf)
                    cutoff = now_perf - 1.5
                    self._frame_times = [t for t in self._frame_times if t >= cutoff]
                    if len(self._frame_times) > 1:
                        time_span = self._frame_times[-1] - self._frame_times[0]
                        self.fps = round((len(self._frame_times) - 1) / max(0.001, time_span), 1)
                    else:
                        self.fps = 25.0
                
                # Small yield to maintain smooth 30 FPS pacing without CPU pinning
                time.sleep(0.015)

            except Exception as e:
                logger.error(f"Error in CV processing loop: {e}", exc_info=True)
                time.sleep(0.03)

    def _render_warehouse_hud(self, frame: np.ndarray, tracks: list, events: list, overlay_mode: Optional[str] = None) -> np.ndarray:
        """
        Draws presentation-grade video overlays with 4 distinct visualization tiers:
          - 'clean' (default): True executive presentation mode. Zero bounding boxes by default, zero clutter.
                               When an active event occurs, draws a subtle highlight on the handler + product together.
          - 'detection': Relevant object bounding boxes + category labels + confidence % (strictly current frame).
          - 'tracking': Bounding boxes + confirmed track IDs + motion breadcrumbs + smoothed velocity vectors + carrying state.
          - 'diagnostics': Full engineering telemetry (vectors, speeds, dimensions, floor line, geofences, FPS, live HUD).
        """
        if frame is None or frame.size == 0:
            return np.zeros((480, 640, 3), dtype=np.uint8)

        mode = (overlay_mode or self.overlay_mode or "clean").lower()
        h, w = frame.shape[:2]
        floor_y = int(h * WAREHOUSE_FLOOR_Y_RATIO)

        # -------------------------------------------------------------
        # TIER 1: CLEAN VIEW (Executive Presentation Mode)
        # -------------------------------------------------------------
        if mode == "clean":
            active_risk_event = None
            if self.active_verified_event and getattr(self.active_verified_event, "state", None) == EventState.ACTIVE and self.active_verified_event.risk_level != "GREEN":
                active_risk_event = self.active_verified_event
            elif self.latest_event and self.current_risk_level != "GREEN":
                active_risk_event = self.latest_event
            elif events and events[-1].risk_level != "GREEN":
                active_risk_event = events[-1]

            # If an active risk event is detected: Draw sleek top alert banner and focus on HANDLER + PRODUCT
            if active_risk_event and active_risk_event.risk_level != "GREEN":
                evt_title = active_risk_event.behaviour_type.display_title if hasattr(active_risk_event.behaviour_type, "display_title") else str(active_risk_event.behaviour_type)
                alert_txt = f"! RISK DETECTED: {evt_title}"
                (aw, ah), _ = cv2.getTextSize(alert_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.40, 1)
                ax = max(10, (w - aw) // 2)

                # Semi-transparent top alert banner
                banner_sub = frame[8:34, max(0, ax - 16):min(w, ax + aw + 16)]
                if banner_sub.size > 0:
                    red_rect = np.zeros(banner_sub.shape, dtype=np.uint8)
                    red_rect[:] = (15, 15, 130) if active_risk_event.risk_level == "RED" else (15, 70, 145)
                    frame[8:34, max(0, ax - 16):min(w, ax + aw + 16)] = cv2.addWeighted(banner_sub, 0.20, red_rect, 0.80, 0)

                border_col = (0, 70, 240) if active_risk_event.risk_level == "RED" else (0, 160, 240)
                cv2.rectangle(frame, (max(0, ax - 16), 8), (min(w, ax + aw + 16), 34), border_col, 1)
                cv2.putText(frame, alert_txt, (ax, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 255, 255), 1, cv2.LINE_AA)

                # Identify involved product & handler tracks
                inv_prod_id = getattr(active_risk_event, "product_track_id", None)
                inv_person_id = getattr(active_risk_event, "person_track_id", None)

                prod_track = next((t for t in tracks if inv_prod_id and t.track_id == inv_prod_id), None)
                if not inv_person_id and prod_track and prod_track.associated_person_id:
                    inv_person_id = prod_track.associated_person_id
                person_track = next((t for t in tracks if inv_person_id and t.track_id == inv_person_id), None)

                if not prod_track:
                    if person_track and getattr(person_track, "associated_product_id", None):
                        prod_track = next((t for t in tracks if t.track_id == person_track.associated_product_id), None)
                    if not prod_track:
                        prod_candidates = [t for t in tracks if t.category.value == "PRODUCT" and t.is_confirmed and t.missed_frames == 0]
                        if len(prod_candidates) == 1:
                            prod_track = prod_candidates[0]

                if not person_track:
                    person_candidates = [t for t in tracks if t.category.value == "PERSON" and t.is_confirmed and t.missed_frames == 0]
                    if len(person_candidates) == 1:
                        person_track = person_candidates[0]

                # Authoritative single-geometry: strictly use current_bbox (smoothed_bbox) when track is active
                p_box = (prod_track.current_bbox if (prod_track and prod_track.missed_frames == 0) else None) or getattr(active_risk_event, "product_bbox", None)
                h_box = (person_track.current_bbox if (person_track and person_track.missed_frames == 0) else None) or getattr(active_risk_event, "person_bbox", None)

                # Highlight involved product
                if p_box:
                    px, py, pbw, pbh = p_box
                    cv2.rectangle(frame, (px, py), (px + pbw, py + pbh), border_col, 2, cv2.LINE_AA)
                    ptag = f"PRODUCT #{prod_track.track_id if prod_track else (inv_prod_id or '1')}"
                    (tw, th), _ = cv2.getTextSize(ptag, cv2.FONT_HERSHEY_SIMPLEX, 0.34, 1)
                    cv2.rectangle(frame, (px, max(0, py - th - 6)), (px + tw + 6, py), border_col, -1)
                    cv2.putText(frame, ptag, (px + 3, max(12, py - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (255, 255, 255), 1, cv2.LINE_AA)

                # Highlight associated handler
                if h_box:
                    hx, hy, hbw, hbh = h_box
                    h_color = (0, 210, 255)
                    cv2.rectangle(frame, (hx, hy), (hx + hbw, hy + hbh), h_color, 1, cv2.LINE_AA)
                    htag = f"HANDLER #{person_track.track_id if person_track else (inv_person_id or '1')}"
                    (hw_t, hh_t), _ = cv2.getTextSize(htag, cv2.FONT_HERSHEY_SIMPLEX, 0.34, 1)
                    cv2.rectangle(frame, (hx, max(0, hy - hh_t - 6)), (hx + hw_t + 6, hy), (20, 25, 30), -1)
                    cv2.rectangle(frame, (hx, max(0, hy - hh_t - 6)), (hx + hw_t + 6, hy), h_color, 1)
                    cv2.putText(frame, htag, (hx + 3, max(12, hy - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.34, h_color, 1, cv2.LINE_AA)

                # Interaction connection link between handler and product
                if p_box and h_box:
                    pcx = int(p_box[0] + p_box[2] / 2.0)
                    pcy = int(p_box[1] + p_box[3] / 2.0)
                    hcx = int(h_box[0] + h_box[2] / 2.0)
                    hcy = int(h_box[1] + h_box[3] / 2.0)
                    cv2.line(frame, (hcx, hcy), (pcx, pcy), border_col, 1, cv2.LINE_AA)

            # Return pure, presentation-quality video frame
            return frame

        # Filter strictly active visible tracks (missed_frames == 0) for current frame rendering
        active_visible_tracks = [
            t for t in tracks
            if t.is_confirmed and t.missed_frames == 0 and t.category.value != "OTHER"
        ]

        # -------------------------------------------------------------
        # TIER 2: DETECTION VIEW (Confidence & Trained Categories)
        # -------------------------------------------------------------
        if mode == "detection":
            if not active_visible_tracks:
                # Sleek subtle empty state indicator
                empty_txt = "NO ACTIVE WAREHOUSE DETECTIONS"
                (ew, eh), _ = cv2.getTextSize(empty_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.36, 1)
                ex = max(10, (w - ew) // 2)
                cv2.rectangle(frame, (ex - 8, 8), (ex + ew + 8, 28), (18, 22, 28), -1)
                cv2.rectangle(frame, (ex - 8, 8), (ex + ew + 8, 28), (60, 70, 85), 1)
                cv2.putText(frame, empty_txt, (ex, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (140, 155, 175), 1, cv2.LINE_AA)
            else:
                seen_person_boxes = []
                for t in active_visible_tracks:
                    x, y, bw, bh = t.current_bbox
                    if t.category.value == "PERSON":
                        skip = False
                        for p_box in seen_person_boxes:
                            if compute_iou((x, y, bw, bh), p_box) > 0.30:
                                skip = True
                                break
                        if skip:
                            continue
                        seen_person_boxes.append((x, y, bw, bh))

                    label, color = self.tracker.class_mapper.get_display_label(
                        category=t.category,
                        raw_label=t.label,
                        track_id=t.track_id,
                        mode="detection",
                        confidence=t.confidence,
                    )

                    # Crisp bounding box & high-tech corner brackets
                    cv2.rectangle(frame, (x, y), (x + bw, y + bh), color, 2, cv2.LINE_AA)
                    c_len = min(12, bw // 4, bh // 4)
                    if c_len > 3:
                        cv2.line(frame, (x, y), (x + c_len, y), color, 2)
                        cv2.line(frame, (x, y), (x, y + c_len), color, 2)
                        cv2.line(frame, (x + bw, y), (x + bw - c_len, y), color, 2)
                        cv2.line(frame, (x + bw, y), (x + bw, y + c_len), color, 2)
                        cv2.line(frame, (x, y + bh), (x + c_len, y + bh), color, 2)
                        cv2.line(frame, (x, y + bh), (x, y + bh - c_len), color, 2)
                        cv2.line(frame, (x + bw, y + bh), (x + bw - c_len, y + bh), color, 2)
                        cv2.line(frame, (x + bw, y + bh), (x + bw, y + bh - c_len), color, 2)

                    # Pill label
                    label_y = max(16, y - 4)
                    (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
                    cv2.rectangle(frame, (x, label_y - lh - 4), (x + lw + 6, label_y + 2), (18, 22, 28), -1)
                    cv2.rectangle(frame, (x, label_y - lh - 4), (x + lw + 6, label_y + 2), color, 1)
                    cv2.putText(frame, label, (x + 3, label_y - 1), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1, cv2.LINE_AA)

            return frame

        # -------------------------------------------------------------
        # TIER 4 (DIAGNOSTICS ONLY): Floor Line & Geofences
        # -------------------------------------------------------------
        if mode == "diagnostics":
            # 1. Floor reference line
            cv2.line(frame, (0, floor_y), (w, floor_y), (140, 180, 80), 1, cv2.LINE_AA)
            cv2.putText(frame, f"FLOOR LEVEL (y={floor_y})", (12, floor_y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (140, 180, 80), 1, cv2.LINE_AA)

            # 2. Walkway corridor geofence
            walkway_norm = DEFAULT_ZONES.get("PEDESTRIAN_WALKWAY", {}).get("rect_norm", (0.0, 0.50, 0.40, 0.50))
            wx1, wy1 = int(walkway_norm[0] * w), int(walkway_norm[1] * h)
            wx2, wy2 = int((walkway_norm[0] + walkway_norm[2]) * w), int((walkway_norm[1] + walkway_norm[3]) * h)
            sub_img = frame[wy1:wy2, wx1:wx2]
            if sub_img.size > 0:
                white_rect = np.ones(sub_img.shape, dtype=np.uint8) * 30
                frame[wy1:wy2, wx1:wx2] = cv2.addWeighted(sub_img, 0.90, white_rect, 0.10, 0)
            cv2.rectangle(frame, (wx1, wy1), (wx2, wy2), (180, 140, 50), 1)
            cv2.putText(frame, "PEDESTRIAN TRANSIT ZONE", (wx1 + 8, wy1 + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (180, 140, 50), 1, cv2.LINE_AA)

        # -------------------------------------------------------------
        # TIERS 3 & 4: Tracking Overlays & Full Diagnostics
        # -------------------------------------------------------------
        seen_person_boxes = []
        for t in active_visible_tracks:
            x, y, bw, bh = t.current_bbox
            is_person = (t.category.value == "PERSON")

            if is_person:
                # Deduplicate overlapping person boxes
                skip = False
                for p_box in seen_person_boxes:
                    if compute_iou((x, y, bw, bh), p_box) > 0.30:
                        skip = True
                        break
                if skip:
                    continue
                seen_person_boxes.append((x, y, bw, bh))

            # Strictly resolve category-driven display label and color
            label, color = self.tracker.class_mapper.get_display_label(
                category=t.category,
                raw_label=t.label,
                track_id=t.track_id,
                mode=mode,
                confidence=t.confidence,
            )

            # Append interaction state badge in tracking mode if product is being held/towed
            if t.category.value == "PRODUCT":
                if getattr(t, "carrying_state", "NONE") in ("HOLDING", "TOWING"):
                    label = f"{label} [{t.carrying_state}]"

            # Main bounding box (crisp 1px)
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), color, 1, cv2.LINE_AA)

            # High-tech corner bracket accents
            c_len = min(12, bw // 4, bh // 4)
            if c_len > 3:
                cv2.line(frame, (x, y), (x + c_len, y), color, 2)
                cv2.line(frame, (x, y), (x, y + c_len), color, 2)
                cv2.line(frame, (x + bw, y), (x + bw - c_len, y), color, 2)
                cv2.line(frame, (x + bw, y), (x + bw, y + c_len), color, 2)
                cv2.line(frame, (x, y + bh), (x + c_len, y + bh), color, 2)
                cv2.line(frame, (x, y + bh), (x, y + bh - c_len), color, 2)
                cv2.line(frame, (x + bw, y + bh), (x + bw - c_len, y + bh), color, 2)
                cv2.line(frame, (x + bw, y + bh), (x + bw, y + bh - c_len), color, 2)

            # Minimal pill label above box
            label_y = max(16, y - 4)
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
            cv2.rectangle(frame, (x, label_y - lh - 3), (x + lw + 6, label_y + 2), (18, 22, 28), -1)
            cv2.rectangle(frame, (x, label_y - lh - 3), (x + lw + 6, label_y + 2), color, 1)
            cv2.putText(frame, label, (x + 3, label_y - 1), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1, cv2.LINE_AA)

            curr_s = t.current_state

            # Draw breadcrumbs in Tracking / Diagnostics
            if len(t.history) >= 2:
                recent_pts = [s.centroid for s in t.history[-8:]]
                for i in range(len(recent_pts) - 1):
                    pt1 = (int(recent_pts[i][0]), int(recent_pts[i][1]))
                    pt2 = (int(recent_pts[i+1][0]), int(recent_pts[i+1][1]))
                    cv2.line(frame, pt1, pt2, color, 1, cv2.LINE_AA)

            # Velocity vector arrow: ONLY for confirmed moving tracks
            if curr_s and len(t.history) >= 3 and t.confidence >= 0.30 and curr_s.speed >= 35.0:
                cx, cy = int(curr_s.centroid[0]), int(curr_s.centroid[1])
                raw_len = curr_s.speed * 0.15
                arrow_len = min(38.0, max(12.0, raw_len))

                dir_x = curr_s.velocity[0] / curr_s.speed
                dir_y = curr_s.velocity[1] / curr_s.speed

                end_x = int(cx + dir_x * arrow_len)
                end_y = int(cy + dir_y * arrow_len)

                if curr_s.velocity[1] > 90.0:
                    arrow_color = (0, 80, 255)
                elif abs(curr_s.velocity[0]) > 90.0:
                    arrow_color = (0, 180, 255)
                else:
                    arrow_color = (0, 230, 255)

                cv2.arrowedLine(frame, (cx, cy), (end_x, end_y), arrow_color, 2, tipLength=0.30)

                if mode == "diagnostics":
                    diag_txt = f"{curr_s.speed:.0f}px/s"
                    (dw, dh), _ = cv2.getTextSize(diag_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.32, 1)
                    cv2.rectangle(frame, (end_x + 2, end_y - dh - 2), (end_x + dw + 6, end_y + 2), (10, 10, 10), -1)
                    cv2.putText(frame, diag_txt, (end_x + 4, end_y - 1), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (0, 240, 255), 1, cv2.LINE_AA)

            # In Full Diagnostics mode, show bounding box kinematics, elevation, and product telemetry
            if mode == "diagnostics" and curr_s:
                if t.category.value == "PRODUCT":
                    raw_b = getattr(t, "raw_detection_bbox", None)
                    raw_str = f"RAW:({raw_b[0]},{raw_b[1]},{raw_b[2]},{raw_b[3]})" if raw_b else "RAW:PREDICTED"
                    trk_str = f"TRK:({x},{y},{bw},{bh})"
                    pred_flag = "[PRED]" if getattr(t, "is_predicted", False) else "[DET]"
                    line1 = f"{pred_flag} {raw_str} | {trk_str}"

                    d_conf = getattr(t, "detection_confidence", t.confidence)
                    b_conf = getattr(t, "behaviour_confidence", t.confidence)
                    i_state = t.interaction_state.value if hasattr(t.interaction_state, "value") else str(t.interaction_state)
                    src = getattr(t, "interaction_source", "UNKNOWN") or "UNKNOWN"
                    line2 = f"CONF: det:{d_conf:.2f} beh:{b_conf:.2f} | {i_state} | SRC:{src}"

                    h_id = t.associated_person_id
                    h_str = f"HND: #{h_id}" if h_id else "HND: NONE"
                    line3 = f"{h_str} | {bw}x{bh} el:{curr_s.elevation_ratio:.2f} {'GND' if curr_s.is_grounded else 'AIR'}"

                    val_stat = getattr(t, "validation_status", "PASS")
                    val_rsn = getattr(t, "validation_reason", "VALID_GEOMETRY")
                    line4 = f"VAL: {val_stat} ({val_rsn})"

                    cv2.putText(frame, line1, (x, y + bh + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (0, 230, 255), 1, cv2.LINE_AA)
                    cv2.putText(frame, line2, (x, y + bh + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (180, 220, 255), 1, cv2.LINE_AA)
                    cv2.putText(frame, line3, (x, y + bh + 36), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (180, 180, 180), 1, cv2.LINE_AA)
                    cv2.putText(frame, line4, (x, y + bh + 48), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (120, 255, 160) if val_stat == "PASS" else (100, 100, 255), 1, cv2.LINE_AA)
                else:
                    dim_txt = f"{bw}x{bh} el:{curr_s.elevation_ratio:.2f} {'GND' if curr_s.is_grounded else 'AIR'}"
                    cv2.putText(frame, dim_txt, (x, y + bh + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.30, (180, 180, 180), 1, cv2.LINE_AA)

        # -------------------------------------------------------------
        # TOP TELEMETRY BAR (Diagnostics Mode Only)
        # -------------------------------------------------------------
        if mode == "diagnostics":
            cv2.rectangle(frame, (0, 0), (w, 24), (14, 18, 24), -1)
            cv2.line(frame, (0, 24), (w, 24), (35, 42, 54), 1)
            cv2.putText(frame, "CAREGUARD AI", (10, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(frame, f"• DIAG | MODEL: {self.detector.active_mode} | FPS: {self.fps:.1f} | DET: {self.detection_fps:.1f}Hz", (105, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (140, 155, 175), 1, cv2.LINE_AA)

            risk_lvl = self.current_risk_level
            risk_color = (70, 200, 100) if risk_lvl == "GREEN" else ((0, 165, 255) if risk_lvl in ("YELLOW", "ORANGE") else (40, 40, 240))
            cv2.putText(frame, f"STATUS: {risk_lvl}", (w - 110, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.38, risk_color, 1, cv2.LINE_AA)

            # Bottom Live Diagnostics Telemetry Overlay Bar
            sub_bot = frame[h - 22:h, 0:w]
            if sub_bot.size > 0:
                dark_bot = np.zeros(sub_bot.shape, dtype=np.uint8)
                dark_bot[:] = (12, 16, 22)
                frame[h - 22:h, 0:w] = cv2.addWeighted(sub_bot, 0.20, dark_bot, 0.80, 0)
            cv2.line(frame, (0, h - 22), (w, h - 22), (35, 42, 54), 1)

            # Tally active counts
            p_cnt = sum(1 for t in active_visible_tracks if t.category.value == "PERSON")
            prod_cnt = sum(1 for t in active_visible_tracks if t.category.value == "PRODUCT")
            pl_cnt = sum(1 for t in active_visible_tracks if t.category.value == "PALLET")
            m_cnt = sum(1 for t in active_visible_tracks if t.category.value == "MHE")

            # Active product relationship
            prod_t = next((t for t in active_visible_tracks if t.category.value == "PRODUCT"), None)
            rel_str = "REL: NONE"
            if prod_t and prod_t.associated_person_id:
                rel_str = f"REL: #{prod_t.track_id} ↔ #{prod_t.associated_person_id} [{prod_t.carrying_state}]"

            bot_summary = f"ACTIVE: {len(active_visible_tracks)} (P:{p_cnt} PR:{prod_cnt} PL:{pl_cnt} M:{m_cnt}) | {rel_str} | SESSION: {self.active_session_id}"
            cv2.putText(frame, bot_summary, (10, h - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (180, 200, 220), 1, cv2.LINE_AA)

        return frame
