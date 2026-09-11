"""
src/api/routes/video.py
-----------------------
Video ingestion, playback controls, file upload, and MJPEG streaming endpoints.
"""

import asyncio
import io
import logging
import os
import time
from pathlib import Path
from typing import Optional
import cv2
import numpy as np

logger = logging.getLogger("CareGuard.VideoRoute")
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse

from config import DATA_DIR, WAREHOUSE_DEFAULT_VIDEO_DIR
from src.api.state import CareGuardBackendState
from src.camera.camera_manager import CameraMode, CameraStatus
from src.core.warehouse_models import EventState

router = APIRouter(prefix="/api/video", tags=["Video"])


_active_mjpeg_clients: int = 0
_mjpeg_stream_generation: int = 0
_mjpeg_clients_lock = asyncio.Lock()
_upload_lock = asyncio.Lock()
_source_switch_state: str = "READY"


async def generate_mjpeg_stream(request: Request, backend: CareGuardBackendState, client_stream_gen: int):
    """High-throughput async generator yielding pre-encoded MJPEG multipart frame chunks with disconnect and generation detection."""
    global _active_mjpeg_clients
    async with _mjpeg_clients_lock:
        _active_mjpeg_clients += 1
        active_count = _active_mjpeg_clients
    logger.info(f"[MJPEG] Client connected. ACTIVE_CLIENTS={active_count}, STREAM_GEN={client_stream_gen}")

    try:
        while not await request.is_disconnected():
            if client_stream_gen != _mjpeg_stream_generation:
                logger.info(f"[MJPEG] Stream generation superseded ({client_stream_gen} != {_mjpeg_stream_generation}). Terminating stream.")
                break

            with backend._lock:
                frame_bytes = backend.latest_jpeg_bytes
                frame = backend.latest_processed_frame

            if frame_bytes is None:
                if frame is None or frame.size == 0:
                    success, raw_frame = backend.camera.get_frame()
                    if success and raw_frame is not None and raw_frame.size > 0:
                        frame = raw_frame
                    else:
                        placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
                        cv2.putText(placeholder, "CAREGUARD AI // SYSTEM READY", (130, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (220, 220, 220), 2)
                        cv2.putText(placeholder, "Status: Standby  |  Click START STREAM or Select Video Source", (95, 265), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (140, 160, 180), 1)
                        frame = placeholder

                ret, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                if not ret:
                    await asyncio.sleep(0.03)
                    continue
                frame_bytes = jpeg.tobytes()

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(frame_bytes)).encode() + b"\r\n\r\n"
                + frame_bytes + b"\r\n"
            )
            await asyncio.sleep(0.03)  # ~30 FPS streaming cadence
    except (asyncio.CancelledError, GeneratorExit):
        pass
    finally:
        async with _mjpeg_clients_lock:
            _active_mjpeg_clients = max(0, _active_mjpeg_clients - 1)
            remaining = _active_mjpeg_clients
        logger.info(f"[MJPEG] Client disconnected. REMAINING_ACTIVE_CLIENTS={remaining}")


@router.get("/feed")
async def video_feed(request: Request, overlay: Optional[str] = "clean"):
    """Live MJPEG video stream with computer vision bounding boxes and HUD overlays."""
    backend = CareGuardBackendState.get_instance()
    if overlay and overlay.lower() in ("clean", "detection", "tracking", "diagnostics"):
        backend.overlay_mode = overlay.lower()
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Connection": "close",
    }
    return StreamingResponse(
        generate_mjpeg_stream(request, backend, _mjpeg_stream_generation),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers=headers,
    )


@router.post("/overlay")
def set_overlay_mode(mode: str = Form(...)):
    """Sets active visual overlay mode ('clean', 'detection', 'tracking', 'diagnostics')."""
    clean_mode = mode.lower().strip()
    if clean_mode not in ("clean", "detection", "tracking", "diagnostics"):
        raise HTTPException(status_code=400, detail=f"Invalid overlay mode: {mode}")
    backend = CareGuardBackendState.get_instance()
    backend.overlay_mode = clean_mode
    return {"status": "ok", "overlay_mode": clean_mode}


@router.get("/state")
def get_video_state():
    """Returns real-time perception state, FPS, active tracks, and diagnostic telemetry."""
    backend = CareGuardBackendState.get_instance()
    diag_telemetry = backend.get_full_diagnostics_telemetry()
    with backend._lock:
        latest = backend.active_verified_event if (backend.active_verified_event and getattr(backend.active_verified_event, "state", None) == EventState.ACTIVE) else (backend.latest_verified_event or backend.latest_event)
        latest_dict = latest.to_dict() if latest else None
        video_path = backend.camera.video_file_path
        mode_val = backend.camera.mode.value if hasattr(backend.camera.mode, "value") else str(backend.camera.mode)
        status_val = backend.camera.status.value if hasattr(backend.camera.status, "value") else str(backend.camera.status)
        cur_f = backend.camera.video_progress[0] if backend.camera.is_file_mode else backend.total_frames_processed
        tot_f = backend.camera.video_progress[1] if backend.camera.is_file_mode else 0
        is_active = backend.camera.is_running and not backend.is_paused
        status_val = "PAUSED" if backend.is_paused else (backend.camera.status.value if hasattr(backend.camera.status, "value") else str(backend.camera.status))
        return {
            "session_id": backend.active_session_id,
            "is_running": is_active,
            "is_paused": backend.is_paused,
            "status": "READY" if (not backend.camera.is_running and not backend.is_paused) else status_val,
            "source_type": mode_val.lower() if (backend.camera.is_running or backend.is_paused) else "standby",
            "video_file": Path(video_path).name if video_path else None,
            "active_source": backend.active_source,
            "current_frame": cur_f,
            "total_frames": tot_f,
            "camera_index": backend.camera.camera_index,
            "fps": 0.0 if backend.is_paused else backend.fps,
            "detection_fps": 0.0 if backend.is_paused else backend.detection_fps,
            "inference_latency_ms": backend.inference_latency_ms,
            "tracking_latency_ms": backend.tracking_latency_ms,
            "capture_fps": 0.0 if backend.is_paused else round(backend.camera.fps, 1),
            "active_tracks_count": backend.active_tracks_count,
            "total_frames_processed": backend.total_frames_processed,
            "last_frame_timestamp": backend.last_frame_timestamp,
            "detection_status": "PAUSED" if backend.is_paused else backend.detection_status,
            "tracking_status": "PAUSED" if backend.is_paused else backend.tracking_status,
            "current_risk_level": backend.current_risk_level,
            "current_event": latest_dict,
            "telemetry": diag_telemetry,
        }


@router.post("/control")
async def video_control(action: str = Form(...)):
    """Controls video stream playback (start, stop, pause, resume)."""
    backend = CareGuardBackendState.get_instance()
    action_clean = action.lower().strip()
    if action_clean in ("start", "resume"):
        if backend.is_paused:
            backend.resume()
        elif not backend.camera.is_running:
            if backend.camera.video_file_path:
                backend.reset_session(Path(backend.camera.video_file_path).name)
                await asyncio.to_thread(backend.camera.start_video_file, backend.camera.video_file_path, True)
            else:
                default_videos = list(WAREHOUSE_DEFAULT_VIDEO_DIR.glob("*.mp4")) + list(WAREHOUSE_DEFAULT_VIDEO_DIR.glob("*.avi"))
                if default_videos:
                    backend.reset_session(default_videos[0].name)
                    await asyncio.to_thread(backend.camera.start_video_file, str(default_videos[0]), True)
                else:
                    backend.reset_session("WEBCAM_0")
                    await asyncio.to_thread(backend.camera.start, None, CameraMode.PHYSICAL, True)
    elif action_clean in ("stop", "pause"):
        backend.pause()
    return {
        "status": "ok",
        "is_running": (backend.camera.is_running and not backend.is_paused),
        "is_paused": backend.is_paused,
    }


@router.post("/source")
async def set_video_source(
    source_type: str = Form(...),  # 'file' or 'camera' or 'synthetic'
    video_path: Optional[str] = Form(None),
    camera_index: int = Form(0),
):
    """Switches active ingestion source to a video file, physical camera, or synthetic stream."""
    backend = CareGuardBackendState.get_instance()
    await asyncio.to_thread(backend.camera.stop)

    if source_type == "file":
        if not video_path:
            # Check default video directory for available clips
            files = list(WAREHOUSE_DEFAULT_VIDEO_DIR.glob("*.mp4")) + list(WAREHOUSE_DEFAULT_VIDEO_DIR.glob("*.avi"))
            if files:
                video_path = str(files[0])
            else:
                raise HTTPException(status_code=400, detail="No video file specified or found.")

        fname = Path(video_path).name
        backend.reset_session(fname)
        ok = await asyncio.to_thread(backend.camera.start_video_file, video_path, True)
        if not ok:
            raise HTTPException(status_code=500, detail=f"Failed to open video file: {video_path}")
        return {"status": "ok", "source": "file", "file": fname, "session_id": backend.active_session_id}

    elif source_type == "camera":
        backend.reset_session(f"WEBCAM_{camera_index}")
        ok = await asyncio.to_thread(backend.camera.start, camera_index, CameraMode.PHYSICAL, False)
        return {"status": "ok", "source": "camera", "index": camera_index, "live": ok, "session_id": backend.active_session_id}

    elif source_type == "synthetic":
        backend.reset_session("SYNTHETIC_SIMULATOR")
        ok = await asyncio.to_thread(backend.camera.start, None, CameraMode.SYNTHETIC)
        return {"status": "ok", "source": "synthetic", "session_id": backend.active_session_id}

    raise HTTPException(status_code=400, detail=f"Unknown source type: {source_type}")


@router.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    """
    Uploads a warehouse CCTV video file (.mp4, .avi) with strict 20-stage lifecycle management,
    capture generation safety, and thread-safe connection closing.
    """
    global _mjpeg_stream_generation, _source_switch_state
    import threading

    start_time = time.time()
    thread_id = threading.get_ident()
    upload_id = f"UP-{int(start_time * 1000)}"

    # 1. UPLOAD_START
    logger.info(f"[STAGE 1/20: UPLOAD_START] upload_id={upload_id}, thread_id={thread_id}")

    # 2. REQUEST_RECEIVED
    if not file.filename:
        logger.error(f"[STAGE 2/20: REQUEST_RECEIVED] UPLOAD_FAILURE: upload_id={upload_id}, stage=REQUEST_RECEIVED, exception=No file selected")
        raise HTTPException(status_code=400, detail="No file selected")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".mp4", ".avi", ".mkv", ".mov"):
        logger.error(f"[STAGE 2/20: REQUEST_RECEIVED] UPLOAD_FAILURE: upload_id={upload_id}, stage=REQUEST_RECEIVED, exception=Unsupported format {suffix}")
        raise HTTPException(status_code=400, detail="Unsupported video format. Please upload MP4 or AVI.")

    logger.info(
        f"[STAGE 2/20: REQUEST_RECEIVED] upload_id={upload_id}, filename={file.filename}, "
        f"content_type={file.content_type}, thread_id={thread_id}"
    )

    if _upload_lock.locked():
        logger.warning(f"[UPLOAD] Concurrent upload rejected: upload_id={upload_id} already locked.")
        raise HTTPException(status_code=409, detail="A video upload is currently in progress. Please wait.")

    async with _upload_lock:
        backend = CareGuardBackendState.get_instance()
        _source_switch_state = "STOPPING"
        target_path = WAREHOUSE_DEFAULT_VIDEO_DIR / file.filename

        try:
            # 3. MJPEG_STREAM_PRE_INVALIDATE (Immediately break old browser streams before file operations)
            _mjpeg_stream_generation += 1
            logger.info(
                f"[STAGE 3/20: MJPEG_STREAM_PRE_INVALIDATE] upload_id={upload_id}, "
                f"mjpeg_generation={_mjpeg_stream_generation}"
            )
            await asyncio.sleep(0.04)  # Allow running MJPEG generators to observe generation bump and exit cleanly

            # 4. SOURCE_STOP_START (Release video capture handles BEFORE writing to file to prevent Windows [WinError 32])
            logger.info(
                f"[STAGE 4/20: SOURCE_STOP_START] upload_id={upload_id}, "
                f"capture_generation={backend.camera.capture_generation}, thread_id={thread_id}"
            )
            await asyncio.to_thread(backend.camera.stop)
            logger.info(f"[STAGE 5/20: SOURCE_STOP_END] upload_id={upload_id}")

            # 6. CAPTURE_RELEASE_CONFIRMED
            cap_thread_alive = backend.camera._thread is not None and backend.camera._thread.is_alive()
            cap_released = backend.camera._cap is None
            logger.info(
                f"[STAGE 6/20: CAPTURE_RELEASE_CONFIRMED] upload_id={upload_id}, "
                f"thread_alive={cap_thread_alive}, capture_is_none={cap_released}"
            )

            # 7. DETECTION_WORKER_STATE_RESET
            with backend._det_lock:
                backend._latest_raw_frame_for_det = None
                backend._latest_detections = []
            det_worker_count = 1 if (backend._det_worker_thread and backend._det_worker_thread.is_alive()) else 0
            logger.info(
                f"[STAGE 7/20: DETECTION_WORKER_STATE_RESET] upload_id={upload_id}, "
                f"detection_worker_count={det_worker_count}"
            )

            # 8. TRACKER_RESET & BEHAVIOUR_ENGINE_RESET
            backend.tracker.reset()
            backend.behaviour_engine.reset()
            logger.info(f"[STAGE 8/20: PIPELINES_RESET] upload_id={upload_id}, active_tracks=0, active_events=0")

            # 9. FILE_SAVE_START
            _source_switch_state = "WRITING"
            logger.info(f"[STAGE 9/20: FILE_SAVE_START] upload_id={upload_id}, target={target_path.name}")
            content = await file.read()

            def write_file():
                with open(target_path, "wb") as f:
                    f.write(content)

            await asyncio.to_thread(write_file)

            # 10. FILE_SAVE_END
            file_size = target_path.stat().st_size if target_path.exists() else 0
            if file_size == 0:
                raise ValueError("Uploaded file wrote 0 bytes to disk.")
            logger.info(f"[STAGE 10/20: FILE_SAVE_END] upload_id={upload_id}, size_bytes={file_size}")

            # 11. MJPEG_CLIENTS_CONFIRMED_CLEARED
            _source_switch_state = "RESETTING"
            logger.info(
                f"[STAGE 11/20: MJPEG_CLIENTS_CONFIRMED_CLEARED] upload_id={upload_id}, "
                f"active_mjpeg_clients={_active_mjpeg_clients}"
            )

            # 12. NEW_SESSION_CREATED
            new_session_id = backend.reset_session(file.filename)
            logger.info(
                f"[STAGE 12/20: NEW_SESSION_CREATED] upload_id={upload_id}, "
                f"session_id={new_session_id}"
            )

            # Probe decodability before starting background playback thread
            def probe_video():
                cap = cv2.VideoCapture(str(target_path))
                if not cap.isOpened():
                    return False, 0, 0, 0
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                ret, frame = cap.read()
                cap.release()
                return (ret and frame is not None and frame.size > 0), w, h, count

            # 13. PROBE_VIDEO_DECODABILITY
            is_decodable, vid_w, vid_h, vid_count = await asyncio.to_thread(probe_video)
            if not is_decodable:
                raise ValueError(f"Uploaded file {target_path.name} cannot be decoded by OpenCV backend.")

            # 14. NEW_CAPTURE_OPEN
            _source_switch_state = "STARTING"
            success = await asyncio.to_thread(backend.camera.start_video_file, str(target_path), True)
            if not success:
                raise RuntimeError(f"Failed to start video playback for {target_path.name}")
            logger.info(
                f"[STAGE 14/20: NEW_CAPTURE_OPEN] upload_id={upload_id}, "
                f"capture_generation={backend.camera.capture_generation}, resolution={vid_w}x{vid_h}, frames={vid_count}"
            )

            # 15. FIRST_FRAME_READ
            first_frame_ok = False
            for attempt in range(40):  # Wait up to 2.0s (40 * 50ms)
                succ, f = backend.camera.get_frame()
                if succ and f is not None and f.size > 0:
                    first_frame_ok = True
                    break
                await asyncio.sleep(0.05)
            logger.info(
                f"[STAGE 15/20: FIRST_FRAME_READ] upload_id={upload_id}, "
                f"first_frame_ok={first_frame_ok}"
            )
            if not first_frame_ok:
                raise TimeoutError("Capture loop timed out waiting for first frame.")

            # 16. FIRST_FRAME_VALID
            _source_switch_state = "FIRST_FRAME"
            logger.info(f"[STAGE 17/20: FIRST_FRAME_VALID] upload_id={upload_id}, frame_shape={f.shape}")

            # 18. CV_PIPELINE_READY
            logger.info(
                f"[STAGE 18/20: CV_PIPELINE_READY] upload_id={upload_id}, "
                f"detector_ready={backend.detector.is_ready}, tracker_ready=True"
            )

            # 19. STREAM_READY
            _source_switch_state = "READY"
            logger.info(
                f"[STAGE 19/20: STREAM_READY] upload_id={upload_id}, "
                f"stream_ready=True, active_threads={threading.active_count()}"
            )

            # 20. UPLOAD_COMPLETE
            duration = round(time.time() - start_time, 2)
            logger.info(
                f"[STAGE 20/20: UPLOAD_COMPLETE] upload_id={upload_id}, "
                f"session_id={new_session_id}, duration_sec={duration}, "
                f"detection_worker_count={det_worker_count}, active_mjpeg_clients={_active_mjpeg_clients}"
            )

            return {
                "status": "ok",
                "upload_id": upload_id,
                "filename": file.filename,
                "saved_path": str(target_path),
                "session_id": new_session_id,
                "resolution": f"{vid_w}x{vid_h}",
                "frames": vid_count,
                "duration_sec": duration,
                "capture_generation": backend.camera.capture_generation,
                "detection_worker_count": det_worker_count,
                "active_mjpeg_clients": _active_mjpeg_clients,
                "message": f"Successfully uploaded and initialized playback for {file.filename}",
            }

        except Exception as e:
            _source_switch_state = "READY"
            logger.error(
                f"[UPLOAD_FAILURE] upload_id={upload_id}, stage={_source_switch_state}, exception={e}",
                exc_info=True
            )
            raise HTTPException(status_code=500, detail=f"Upload processing failed at stage {_source_switch_state}: {e}")


@router.get("/files")
def list_available_videos():
    """Lists available warehouse test video clips."""
    files = list(WAREHOUSE_DEFAULT_VIDEO_DIR.glob("*.mp4")) + list(WAREHOUSE_DEFAULT_VIDEO_DIR.glob("*.avi"))
    return [
        {
            "filename": f.name,
            "path": str(f),
            "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
        }
        for f in files
    ]
