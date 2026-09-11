"""
WatchGuard Vision - Global Configuration
----------------------------------------
Defines system paths, camera settings, database locations, UI parameters,
face recognition, object detection, and context security rules.
"""

import os
from pathlib import Path
from typing import Dict, Any, List

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
EVIDENCE_DIR = DATA_DIR / "evidence"
LOGS_DIR = DATA_DIR / "logs"
MODELS_DIR = DATA_DIR / "models"
FACES_DIR = DATA_DIR / "faces"
DEMO_FACES_DIR = DATA_DIR / "demo_faces"

# Ensure runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
FACES_DIR.mkdir(parents=True, exist_ok=True)
DEMO_FACES_DIR.mkdir(parents=True, exist_ok=True)

# Face Recognition Models & Thresholds (Phase 2.1)
YUNET_MODEL_PATH = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
SFACE_MODEL_PATH = MODELS_DIR / "face_recognition_sface_2021dec.onnx"
FACE_DETECTION_SCORE_THRESHOLD = 0.50            # YuNet face detector confidence threshold
FACE_COSINE_SIMILARITY_THRESHOLD = 0.55          # SFace cosine similarity required for AUTHORIZED status
FACE_AMBIGUOUS_SIMILARITY_THRESHOLD = 0.38       # SFace cosine similarity boundary for AMBIGUOUS/UNVERIFIED status
FACE_TEMPORAL_CONFIRM_FRAMES = 2                 # Consecutive frames required to confirm AUTHORIZED status
PERSON_ALERT_COOLDOWN_SECONDS = 10.0

# Presentation Attack Detection (PAD / Liveness) Configuration (Phase 3.0)
PAD_MODELS_DIR = MODELS_DIR / "pad"
PAD_MODELS_DIR.mkdir(parents=True, exist_ok=True)
PAD_MOBILENET_MODEL_PATH = PAD_MODELS_DIR / "mobilenetv3_pad.onnx"
PAD_EFFICIENTNET_MODEL_PATH = PAD_MODELS_DIR / "efficientnet_pad.onnx"
PAD_LBP_SVM_MODEL_PATH = PAD_MODELS_DIR / "lbp_svm_pad.joblib"
PAD_PROVISIONAL_LIVENESS_THRESHOLD = 0.80        # Provisional liveness score threshold; calibrated via evaluation
PAD_PROVISIONAL_SPOOF_THRESHOLD = 0.50           # Below this score is classified as presentation attack
PAD_BLINK_EAR_THRESHOLD = 0.22                  # Eye Aspect Ratio threshold for eye closure detection
PAD_VERIFICATION_TIMEOUT_SECONDS = 5.0          # Max verification window before timing out to UNVERIFIED / ACCESS DENIED
PAD_DEFAULT_MODEL = "Blink-EAR"                 # Default active PAD model ("Blink-EAR", "LBP-SVM", "MobileNetV3-Small", "EfficientNet-B0")

# YOLO26n Warehouse Object Detection Configuration (Ultralytics YOLO26)
YOLO26N_BASE_MODEL_PATH = BASE_DIR / "yolo26n.pt"
YOLO26N_WAREHOUSE_MODEL_PATH = MODELS_DIR / "yolo26n_warehouse.pt"
YOLO26N_WAREHOUSE_ONNX_PATH = MODELS_DIR / "yolo26n_warehouse.onnx"
YOLOV8N_MODEL_PATH = MODELS_DIR / "yolov8n.onnx"  # Legacy fallback
OBJECT_DETECTION_CONFIDENCE_THRESHOLD = 0.25
OBJECT_DETECTION_NMS_THRESHOLD = 0.45
OBJECT_ALERT_COOLDOWN_SECONDS = 15.0

# 4 Core Warehouse Classes (Godrej Warehouse Taxonomy)
WAREHOUSE_CLASSES = ["person", "product", "pallet", "mhe"]

# Active Object Detector Mode
OBJECT_DETECTOR_MODE = os.getenv("OBJECT_DETECTOR_MODE", "yolo26_warehouse")  # "yolo26_warehouse" | "yolo26n_base"
WATCHGUARD_CUSTOM_MODEL_PATH = MODELS_DIR / "yolo_watchguard_assets_v3.onnx"
WATCHGUARD_CUSTOM_CONF_THRESHOLD = float(os.getenv("WATCHGUARD_CUSTOM_CONF_THRESHOLD", "0.35"))
WATCHGUARD_CUSTOM_NMS_THRESHOLD = float(os.getenv("WATCHGUARD_CUSTOM_NMS_THRESHOLD", "0.45"))
WATCHGUARD_CUSTOM_CLASSES = ["person", "laptop", "cell_phone", "mouse"]

# Phase 5.21 84-Class Unified Model Settings
WATCHGUARD_UNIFIED_MODEL_PATH = MODELS_DIR / "yolo_watchguard_unified_84.onnx"
WATCHGUARD_UNIFIED_CONF_THRESHOLD = float(os.getenv("WATCHGUARD_UNIFIED_CONF_THRESHOLD", "0.35"))
WATCHGUARD_UNIFIED_NMS_THRESHOLD = float(os.getenv("WATCHGUARD_UNIFIED_NMS_THRESHOLD", "0.45"))

# COCO 80 Class Labels for YOLOv8
COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake",
    "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop",
    "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
]

# Phase 5.21 Authoritative 84-Class Unified Taxonomy (80 COCO + 4 WatchGuard Security Assets)
WATCHGUARD_UNIFIED_CLASSES = COCO_CLASSES + [
    "pen",           # 80
    "access_badge",  # 81
    "usb_drive",     # 82
    "keys",          # 83
]

# Security Asset Role & Classification Mapping (Phase 5.19D & 5.21)
SECURITY_OBJECT_CATEGORIES: Dict[str, str] = {
    "laptop": "protected",
    "cell_phone": "security-relevant",
    "cell phone": "security-relevant",
    "mouse": "context-relevant",
    "person": "entity",
    "pen": "context-relevant",
    "access_badge": "credential",
    "usb_drive": "high-risk-asset",
    "keys": "physical-access",
}

# Context & Security Intelligence Configuration (Phase 2.3)
PROTECTED_OBJECT_CLASSES: List[str] = ["laptop", "cell phone", "cell_phone", "backpack", "book"]

# Virtual Surveillance & Warehouse Operation Zones (Normalized bounding boxes [x, y, w, h] from 0.0 to 1.0)
DEFAULT_ZONES: Dict[str, Dict[str, Any]] = {
    "NORMAL": {
        "name": "General Staging Bay",
        "rect_norm": (0.0, 0.0, 1.0, 1.0),
        "zone_type": "NORMAL",
    },
    "PEDESTRIAN_WALKWAY": {
        "name": "Pedestrian Walkway / Exit",
        "rect_norm": (0.0, 0.50, 0.40, 0.50),  # Left lower walkway
        "zone_type": "RESTRICTED",
    },
    "RACKING_STORAGE": {
        "name": "Racking & Stacking Area",
        "rect_norm": (0.45, 0.20, 0.55, 0.80),  # Right side stacking bay
        "zone_type": "PROTECTED_ASSET_AREA",
    },
}

# Operational Time Windows (24-hour format)
AUTHORIZED_HOURS_START = "09:00"
AUTHORIZED_HOURS_END = "18:00"

# Spatial Proximity Thresholds (in pixels)
PROXIMITY_PIXEL_THRESHOLD = 150
CONTEXT_ALERT_COOLDOWN_SECONDS = 15.0

# Phase 5.20 Novelty Feature Research Configuration
# 1. Tailgating & Multi-Person Access Anomaly
TAILGATING_TIME_WINDOW_SECONDS = float(os.getenv("TAILGATING_TIME_WINDOW_SECONDS", "3.0"))
TAILGATING_SPATIAL_THRESHOLD_PIXELS = float(os.getenv("TAILGATING_SPATIAL_THRESHOLD_PIXELS", "160.0"))
TAILGATING_CONFIRMATION_FRAMES = int(os.getenv("TAILGATING_CONFIRMATION_FRAMES", "2"))
TAILGATING_ALERT_COOLDOWN_SECONDS = float(os.getenv("TAILGATING_ALERT_COOLDOWN_SECONDS", "10.0"))

# 2. Behavioral & Temporal Anomaly Engine
BEHAVIOR_DWELL_THRESHOLD_SECONDS = float(os.getenv("BEHAVIOR_DWELL_THRESHOLD_SECONDS", "15.0"))
BEHAVIOR_APPROACH_REPETITION_THRESHOLD = int(os.getenv("BEHAVIOR_APPROACH_REPETITION_THRESHOLD", "3"))
BEHAVIOR_RESTRICTED_RETRY_THRESHOLD = int(os.getenv("BEHAVIOR_RESTRICTED_RETRY_THRESHOLD", "2"))

# 3. Uncertainty-Aware Decision Layer
CONFIDENCE_HIGH_THRESHOLD = float(os.getenv("CONFIDENCE_HIGH_THRESHOLD", "0.75"))
CONFIDENCE_LOW_THRESHOLD = float(os.getenv("CONFIDENCE_LOW_THRESHOLD", "0.45"))

# =============================================================================
# CAREGUARD AI - 10 WAREHOUSE HANDLING & DAMAGE PREVENTION THRESHOLDS
# =============================================================================
WAREHOUSE_MODE = os.getenv("WAREHOUSE_MODE", "true").lower() in ("true", "1", "yes")
WAREHOUSE_DEFAULT_VIDEO_DIR = DATA_DIR / "videos"
WAREHOUSE_DEFAULT_VIDEO_DIR.mkdir(parents=True, exist_ok=True)

# Floor & General Kinematics Thresholds
WAREHOUSE_FLOOR_Y_RATIO = float(os.getenv("WAREHOUSE_FLOOR_Y_RATIO", "0.68")) # Calibrated for standard dock/warehouse cameras (lower 32% floor plane)
WAREHOUSE_BEHAVIOUR_COOLDOWN_SECONDS = float(os.getenv("WAREHOUSE_BEHAVIOUR_COOLDOWN_SECONDS", "12.0")) # Episode debouncing window

# Behaviour 1: Product Dropped
WAREHOUSE_DROP_VELOCITY_THRESHOLD = float(os.getenv("WAREHOUSE_DROP_VELOCITY_THRESHOLD", "120.0")) # px/s downward velocity
WAREHOUSE_DROP_MIN_DISPLACEMENT_PX = float(os.getenv("WAREHOUSE_DROP_MIN_DISPLACEMENT_PX", "40.0"))

# Behaviour 2: Product Dragged
WAREHOUSE_DRAG_SPEED_THRESHOLD = float(os.getenv("WAREHOUSE_DRAG_SPEED_THRESHOLD", "20.0")) # px/s horizontal speed
WAREHOUSE_DRAG_MIN_DURATION_SECONDS = float(os.getenv("WAREHOUSE_DRAG_MIN_DURATION_SECONDS", "0.8")) # min seconds sustained drag

# Behaviour 3: Rough Handling / Excessive Impact
WAREHOUSE_ROUGH_IMPACT_DECEL_THRESHOLD = float(os.getenv("WAREHOUSE_ROUGH_IMPACT_DECEL_THRESHOLD", "300.0")) # px/s^2 deceleration spike
WAREHOUSE_ROUGH_IMPACT_MIN_SPEED_PX = float(os.getenv("WAREHOUSE_ROUGH_IMPACT_MIN_SPEED_PX", "50.0"))

# Behaviour 4: Incorrect Stacking (Heavy on light / severe overhang)
WAREHOUSE_INCORRECT_STACK_AREA_RATIO = float(os.getenv("WAREHOUSE_INCORRECT_STACK_AREA_RATIO", "1.25")) # Top area > 1.25x bottom area
WAREHOUSE_INCORRECT_STACK_OVERHANG_RATIO = float(os.getenv("WAREHOUSE_INCORRECT_STACK_OVERHANG_RATIO", "0.22")) # Top width extends > 22% beyond bottom

# Behaviour 5: Unstable Stacking (Leaning column / lateral drift)
WAREHOUSE_UNSTABLE_STACK_TILT_PX = float(os.getenv("WAREHOUSE_UNSTABLE_STACK_TILT_PX", "18.0")) # Horizontal center offset between stacked levels

# Behaviour 6: Placed Outside Designated Area (Left in Walkway / Fire Exit)
WAREHOUSE_WALKWAY_DWELL_SECONDS = float(os.getenv("WAREHOUSE_WALKWAY_DWELL_SECONDS", "2.5")) # Stationary in walkway > 2.5s

# Behaviour 7: Handled Without Equipment (Heavy cargo manual carry across distance)
WAREHOUSE_HEAVY_CARGO_AREA_PX = int(os.getenv("WAREHOUSE_HEAVY_CARGO_AREA_PX", "12000")) # Large package area
WAREHOUSE_MANUAL_CARRY_DISTANCE_PX = float(os.getenv("WAREHOUSE_MANUAL_CARRY_DISTANCE_PX", "70.0"))

# Behaviour 8: Pallet Positioned Incorrectly (Misaligned or blocking lane)
WAREHOUSE_PALLET_PROTRUSION_PX = float(os.getenv("WAREHOUSE_PALLET_PROTRUSION_PX", "25.0"))

# Behaviour 9: Material Pushed / Thrown (High horizontal velocity ballistic toss)
WAREHOUSE_THROW_HORIZONTAL_VELOCITY = float(os.getenv("WAREHOUSE_THROW_HORIZONTAL_VELOCITY", "160.0")) # px/s horizontal speed during release

# Behaviour 10: Unsafe Loading / Unloading Sequence (Removing bottom package before top)
WAREHOUSE_UNSAFE_UNLOAD_GAP_PX = float(os.getenv("WAREHOUSE_UNSAFE_UNLOAD_GAP_PX", "20.0"))

# Warehouse Object Category Taxonomies & Strict Classification
WAREHOUSE_PRODUCT_CLASSES = ["carton", "box", "package", "parcel", "product", "cargo", "crate", "cardboard_box"]
WAREHOUSE_PALLET_CLASSES = ["pallet", "wooden_pallet", "plastic_pallet"]
WAREHOUSE_MHE_CLASSES = ["trolley", "mhe", "forklift", "pallet_jack", "hand_truck", "reach_truck", "stacker", "cart", "bopt", "tow_tractor", "truck"]
WAREHOUSE_PERSON_CLASSES = ["person", "human", "worker", "operator", "handler", "employee"]

# Warehouse Object Confidence Thresholds
WAREHOUSE_PERSON_CONF_THRESHOLD = float(os.getenv("WAREHOUSE_PERSON_CONF_THRESHOLD", "0.25"))
WAREHOUSE_PRODUCT_CONF_THRESHOLD = float(os.getenv("WAREHOUSE_PRODUCT_CONF_THRESHOLD", "0.15"))
WAREHOUSE_PALLET_CONF_THRESHOLD = float(os.getenv("WAREHOUSE_PALLET_CONF_THRESHOLD", "0.25"))
WAREHOUSE_MHE_CONF_THRESHOLD = float(os.getenv("WAREHOUSE_MHE_CONF_THRESHOLD", "0.25"))
WAREHOUSE_OTHER_CONF_THRESHOLD = float(os.getenv("WAREHOUSE_OTHER_CONF_THRESHOLD", "0.35"))

# Warehouse Tracking Expiration Settings
WAREHOUSE_TRACK_MAX_MISSED_FRAMES = int(os.getenv("WAREHOUSE_TRACK_MAX_MISSED_FRAMES", "8"))
WAREHOUSE_TRACK_MAX_AGE_SECONDS = float(os.getenv("WAREHOUSE_TRACK_MAX_AGE_SECONDS", "0.8"))

# Database Configuration
DATABASE_PATH = DATA_DIR / "watchguard.db"

# Real-Time Video & CV Pipeline Settings (Near-Real-Time Optimization)
DETECTION_CADENCE_INTERVAL = int(os.getenv("DETECTION_CADENCE_INTERVAL", "3"))  # Run full detector every N frames (async worker)
DETECTION_INFERENCE_SIZE = int(os.getenv("DETECTION_INFERENCE_SIZE", "640"))    # Model input resolution
STREAM_JPEG_QUALITY = int(os.getenv("STREAM_JPEG_QUALITY", "75"))                # Fast JPEG compression quality
STREAM_TARGET_FPS = int(os.getenv("STREAM_TARGET_FPS", "30"))                    # Max MJPEG streaming rate
MAX_FRAME_BUFFER_SIZE = int(os.getenv("MAX_FRAME_BUFFER_SIZE", "1"))            # Latest-frame queue depth (prevents lag)

# Camera Settings
DEFAULT_CAMERA_INDEX = 0
CAMERA_FRAME_WIDTH = 640
CAMERA_FRAME_HEIGHT = 480
TARGET_FPS = 30
CAMERA_WARMUP_FRAMES = 5

# Event & Logging
LOG_FILE_PATH = LOGS_DIR / "watchguard.log"
CONSOLE_LOG_LEVEL = os.getenv("CONSOLE_LOG_LEVEL", "INFO")
FILE_LOG_LEVEL = os.getenv("FILE_LOG_LEVEL", "INFO")
MAX_RECENT_EVENTS_DISPLAY = 100
MAX_DATABASE_NORMAL_EVENTS = int(os.getenv("MAX_DATABASE_NORMAL_EVENTS", "500"))
EVENT_RETENTION_CHECK_INTERVAL = int(os.getenv("EVENT_RETENTION_CHECK_INTERVAL", "25"))
LOG_ROTATION_MAX_BYTES = int(os.getenv("LOG_ROTATION_MAX_BYTES", str(5 * 1024 * 1024)))
LOG_ROTATION_BACKUP_COUNT = int(os.getenv("LOG_ROTATION_BACKUP_COUNT", "3"))

# Risk Thresholds
RISK_LEVELS = {
    "GREEN": "Normal / Safe Handling",
    "YELLOW": "Attention / Minor Risk",
    "ORANGE": "High Damage Risk",
    "RED": "Critical Impact / Breach"
}

# CareGuard AI Identity & Styling
APP_TITLE = "CareGuard AI - Warehouse Video Intelligence"
APP_VERSION = "1.0.0-godrej"
AI_ASSISTANT_NAME = "CareGuard Assistant"
TAGLINE = "AI-Powered Video Intelligence for Safer, Damage-Free Warehouse Operations"
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 880
VIDEO_DISPLAY_WIDTH = 640
VIDEO_DISPLAY_HEIGHT = 480

# Phase 5.5 / 5.7 AI Security Copilot Configuration
COPILOT_ENABLED = os.getenv("COPILOT_ENABLED", "true").lower() in ("true", "1", "yes")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
COPILOT_MODEL_NAME = os.getenv("COPILOT_MODEL_NAME", "gemini-2.5-flash")
COPILOT_TIMEOUT_SECONDS = float(os.getenv("COPILOT_TIMEOUT_SECONDS", "3.0"))
COPILOT_LOCAL_ENDPOINT = os.getenv("COPILOT_LOCAL_ENDPOINT", "http://localhost:11434/api/generate")
COPILOT_LOCAL_MODEL = os.getenv("COPILOT_LOCAL_MODEL", "llama3.2:3b")
