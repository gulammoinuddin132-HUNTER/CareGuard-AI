# CareGuard AI 📦👁️
**AI-Powered Video Intelligence for Safer, Damage-Free Warehouse Operations**

Built for the **Godrej Enterprises Group "AI Video Intelligence for Warehouse Handling" Hackathon Challenge**.

---

## 🎯 Product Mission & Responsible AI Principles

**CareGuard AI** transforms warehouse video feeds into proactive damage-prevention intelligence. Its primary mission is **MATERIAL HANDLING DAMAGE PREVENTION & PROCESS IMPROVEMENT**, not punitive employee surveillance.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 RESPONSIBLE AI DAMAGE EXPLAINABILITY MODEL                  │
│                                                                             │
│  [1. Observed Behaviour] ──> [2. Potential Risk] ──> [3. Corrective Action]  │
│  (Kinematic & Spatial)      (Product/Package Impact) (Supervisor Guidance)  │
└─────────────────────────────────────────────────────────────────────────────┘
```

1. **Observed Behaviour**: Factual, sensor-grounded kinematic sequence (e.g., *Package #101 free-fall descent at 420 px/s with floor impact*).
2. **Potential Risk**: Objective physical vulnerability assessment (e.g., *Internal structural damage, broken components, seal rupture*).
3. **Corrective Action**: Actionable operational guidance (e.g., *Quarantine and inspect package before dispatch; review two-person team lift*).
4. **Privacy & Fair Process by Design**: No facial recognition penalty scoring, no punitive employee meters, and clear distinction between *Observed Risk* and *Confirmed Damage*.

---

## 🌟 Modern Architecture & Pipeline

CareGuard AI features a decoupled, high-performance web architecture combining a **FastAPI backend** for real-time computer vision and temporal behaviour analytics with a **React + TypeScript + Tailwind CSS** single-page web application.

```
godrej_watchguard/
├── config.py                                 # Global configuration (CareGuard branding, zones, kinematics)
├── main.py                                   # Primary application entry point (Web / CLI options)
├── run_app.py                                # Web application server launcher
├── scripts/
│   └── reset_demo_database.py                # Official SQLite database & temporary evidence reset tool
├── requirements.txt                          # Python dependencies (FastAPI, Ultralytics YOLO26, OpenCV, Pillow)
├── data/                                     # Data storage
│   ├── evidence/                             # Incident snapshots with bounding boxes and trajectory trails
│   ├── models/                               # Deep learning weights (YOLO26n Warehouse PyTorch & ONNX)
│   ├── videos/                               # Warehouse CCTV video clips (.mp4, .avi)
│   └── watchguard.db                         # SQLite database (with warehouse_behaviour_events table)
├── frontend/                                 # React + TypeScript + Tailwind Web Application
│   ├── src/
│   │   ├── components/                       # Reusable UI components (Header, Sidebar, Badge, Card, Modal)
│   │   ├── pages/                            # 7 Core Product Views:
│   │   │   ├── OverviewPage.tsx              # Command Center (<5s situational awareness & health score)
│   │   │   ├── LiveMonitoringPage.tsx        # Real-time Video Stream with Kinematics, 4 HUD Modes & 3-Tier Event Details
│   │   │   ├── IncidentsPage.tsx             # Audit log, evidence snapshots, filters & supervisor actions
│   │   │   ├── AnalyticsPage.tsx             # Behaviour breakdowns, hourly trends & bay comparisons
│   │   │   ├── PreventionPage.tsx            # Prevention metrics, coaching opportunities & damage avoided
│   │   │   ├── AssistantPage.tsx             # CareGuard Assistant (copilot querying real database telemetry)
│   │   │   └── SettingsPage.tsx              # Bay zones, kinematic thresholds & video feeds
│   │   ├── services/api.ts                   # Typed API client connecting to FastAPI backend
│   │   └── types/warehouse.ts                # TypeScript domain models and interfaces
│   ├── package.json                          # Vite, React, TypeScript, Tailwind, Lucide, Recharts
│   └── dist/                                 # Production bundle served directly by FastAPI
├── src/
│   ├── api/                                  # FastAPI Service Layer
│   │   ├── app.py                            # FastAPI application, CORS, static routes, health check
│   │   ├── state.py                          # Global CV engine background thread & state manager
│   │   └── routes/                           # REST Endpoints:
│   │       ├── video.py                      # MJPEG stream (/api/video/feed), source control, uploads
│   │       ├── overview.py                   # Executive KPIs & bay health (/api/overview)
│   │       ├── incidents.py                  # Searchable incidents & action updates (/api/incidents)
│   │       ├── analytics.py                  # Aggregated behaviour distribution & trends (/api/analytics)
│   │       ├── prevention.py                 # Prevention metrics & training insights (/api/prevention)
│   │       ├── assistant.py                  # Conversational AI supervisor assistant (/api/assistant/chat)
│   │       ├── simulator.py                  # 1-Click trigger for all warehouse behaviours (/api/simulator/trigger)
│   │       └── settings.py                   # Runtime configuration management (/api/settings)
│   ├── camera/
│   │   └── camera_manager.py                 # Ingestion from live webcams, CCTV, or local MP4/AVI files
│   ├── core/
│   │   ├── warehouse_models.py               # Domain models, enums, kinematics & 3-tier event structures
│   │   ├── warehouse_tracker.py              # Multi-frame object tracker with continuity & geometry gating
│   │   ├── warehouse_behaviour_engine.py     # 10+ Behaviour Temporal Sequence Engine
│   │   ├── warehouse_evidence_cropper.py     # Proportional participant evidence cropper
│   │   ├── warehouse_risk_policy.py          # Deterministic risk scoring & Responsible AI policy
│   │   ├── warehouse_class_mapper.py         # Standardized class taxonomy & confidence boundaries
│   │   ├── object_detection.py               # Dual-Head YOLO26n Warehouse Object Detector
│   │   └── copilot_reasoner.py               # AI supervisor reasoner with strict guardrails
│   └── database/
│       ├── db_manager.py                     # SQLite connection manager & warehouse event analytics CRUD
│       └── models.py                         # Structured dataclass records
    ├── test_action_sequencing_and_semantic_arbitration.py # Multi-action sequencing (DROP->KICK->DRAG) & semantic arbitration
    ├── test_product_validation_and_background_rejection.py # Low-confidence ceiling rejection & anti-teleportation
    ├── test_product_kicking_and_carrying.py    # Carrying state immunity & foot approach prerequisites
    ├── test_product_localization_persistence.py # Background rejection & track expiration persistence
    ├── test_product_localization_and_kick.py    # Spatial continuity, kick detection & geometry isolation
    ├── test_all_10_warehouse_behaviours.py      # Verification for all 10 core warehouse behaviours
    ├── test_event_semantic_gating_and_pause.py  # Pause persistence, tight crop & stacking semantic gating
    ├── test_priority_corrections.py             # 5 sequential uploads, stepping detection, multi-product tracking
    ├── test_api_endpoints.py                    # FastAPI TestClient endpoint verification
    ├── test_warehouse_video_pipeline.py         # Video file ingestion, looping, and pacing
    ├── test_warehouse_tracker.py                # Multi-object tracking, kinematics & spatial associations
    └── test_warehouse_db_integration.py         # Database logging and querying
```

---

## 🧠 Perception & Computer Vision Safeguards

CareGuard AI incorporates enterprise-grade perception safeguards engineered specifically for noisy warehouse CCTV environments:

1. **Multi-Action Temporal Sequencing (`DROP` $\to$ `KICK` $\to$ `DRAG`)**:
   - Distinct physical actions performed on the same tracked product generate separate event instances with unique `event_id`, timestamps, frozen participant bboxes, and independent evidence snapshots.
   - Cooldown deduplication strictly suppresses duplicate frames of the *same* continuous physical action without masking distinct subsequent handling actions.
2. **Semantic Action Arbitration (Foot Contact vs Ballistic Flight vs Floor Drag)**:
   - Evaluates physical actions in strict semantic priority: `EXPLICIT FOOT CONTACT` > `EXPLICIT RELEASE + AIRBORNE` > `EXPLICIT FLOOR DRAG` > `IMPACT / DECELERATION` > `GENERIC MOTION`.
   - `PRODUCT_KICKED` requires grounded pre-impact state + foot approach + foot contact prior to acceleration + floor plane motion ($\Delta v \ge 40\text{px/s}$, $v_x \ge 45\text{px/s}$ dominating $|v_y|$).
   - `MATERIAL_PUSHED_THROWN` requires unsupported in-flight trajectory + hand/arm release context + explicit absence of foot contact.
3. **Event-Specific Body Region Focus Cropping**:
   - `PRODUCT_KICKED` visual evidence focuses on the `PRODUCT` + `HANDLER FOOT/LOWER BODY` ($y \ge y_h + 0.55 h_h$).
   - `PRODUCT_DROPPED` focuses on `PRODUCT` + `HANDLER BODY` and descent path.
   - Proportional $1.15\times$ participant union minimums eliminate whole-scene inflation and unwanted background capture.
4. **Dual-Head YOLO26n Perception (`data/models/yolo26n_warehouse.pt` + `yolo26n.pt`)**:
   - High-accuracy handler (`person`) localization combined with custom-trained warehouse entity detection (`carton`, `box`, `pallet`, `mhe`).
5. **Product Geometric & Background Structure Filtering**:
   - **Ceiling & Top-of-Frame Rejection**: Rejects false product detections in the upper $28\%$ of the frame unless actively held by an elevated reaching handler ($y_{\text{handler\_top}} \le y_{\text{product\_top}} + 15\text{px}$).
   - **Area & Dimension Gating**: Rejects false product candidates exceeding $18\%$ of frame area or $60\%$ frame width to suppress dock doors, truck beds, and walls.
   - **Aspect Ratio Bounds**: Rejects extreme non-carton aspect ratios outside $0.22 \le \text{aspect} \le 4.5$.
   - **Contextual Confidence Floor**: Isolated candidate detections require confidence $\ge 0.35$; detections in immediate proximity ($<120\text{px}$) to handlers or in multi-product clusters are validated down to $0.20$.
6. **Torso Carry Candidate Locking & Hard Semantic Immunity**:
   - When a carton is carried at chest/torso height ($y_{\text{product}} < y_h + 0.65 h_h$), the tracker locks candidate associations to the upper body, rejecting phantom floor/leg artifacts created by swinging legs or floor shadows ($c_y \ge y_h + 0.50 h_h$).
   - Confirmed `HELD` carrying state grants hard semantic immunity against false stepping, false kicking, and false rough handling alerts during normal walking.
7. **Single Authoritative Geometry Source & Cross-View Parity**:
   - All visualization modes (`Detection View`, `Clean View`, `Tracking View`, `Diagnostics View`) and evidence croppers derive coordinates from the identical smoothed tracked geometry (`smoothed_bbox`).
   - Dynamic track resolution guarantees that Clean View participant focus boxes never freeze at historical timestamps while an entity remains active and moving.
8. **Anti-Teleportation & Occlusion Protection**:
   - Multi-frame confirmation (`confirmation_frames = 2`) with average confidence checks prevents single-frame noise from spawning active tracks.
   - Kinematic displacement and aspect/area ratio continuity guards prevent bounding boxes from jumping between handler torso, legs, and floor (rejecting jumps $>80\text{px}$ from predicted trajectory).
   - Ballistic trajectory continuity in `MATERIAL_PUSHED_THROWN` requires smooth multi-frame displacement, rejecting single-frame coordinate teleportation spikes ($>180\text{px}$).
   - Short-term linear motion prediction (`is_predicted = True`) bridges momentary occlusions.
9. **Decoupled Incident Lifecycle & State Retention**:
   - Explicit state transitions: `CANDIDATE` $\to$ `VERIFIED` $\to$ `ACTIVE` $\to$ `RESOLVED`.
   - Incident records (`WarehouseBehaviourEvent`) are decoupled from transient track lifetimes (`TrackedEntity`), ensuring verified events and Responsible AI explanations remain preserved in the UI Right Panel and audit log even after a product moves out of view.
10. **Tight Proportional Evidence Cropping**:
   - Computes tight $12\%$ proportional margins centered on the verified participants (`PRODUCT_BBOX` vs `EVENT_FOCUS_BBOX`) without full-frame aspect distortion.
11. **Diagnostics HUD & Telemetry**:
   - Real-time diagnostics overlay displaying track validation status (`VAL: PASS/REJECT`) and exact rejection reason (`CEILING_NOISE`, `LOW_CONF_ISOLATED`, `OVERSIZED_BBOX`).
12. **Robust Resource Lifecycle & Stream Management**:
   - Generation-isolated OpenCV `VideoCapture` handles prevent thread leaks and file locks on sequential video uploads.
   - Decoupled detection workers and async MJPEG connection pool management guarantee responsive 30 FPS streaming with zero browser socket starvation.

---

## 🖥️ 7 Dedicated Product Views

1. **Command Center (Overview)**: Immediate situational awareness in $<5	ext{s}$. Displays Warehouse Handling Quality Score (0–100), active risk level breakdown, active loading bay risk cards, and top 5 risk indicators.
2. **Live Monitoring**: Real-time video stream with 4 selectable visual overlay modes (`Clean View`, `Detection View`, `Tracking View`, `Diagnostics View`), fullscreen toggle, and a dedicated **Current Event Panel** with 3-tier Responsible AI explanations.
3. **Incidents & Evidence**: Searchable, filterable audit log with severity filters, loading bay filters, interactive inspection modal with evidence snapshots, kinematics, and supervisor corrective action logger.
4. **Behaviour Analytics**: Comprehensive charts powered by Recharts comparing all handling behaviours, 24-hour incident trends, and risk distribution across loading bays.
5. **Prevention Insights**: Proactive operational intelligence tracking estimated damage events prevented, safe-to-risky handling ratio, and targeted coaching/training recommendations.
6. **CareGuard Assistant**: Natural-language conversational supervisor copilot grounded in actual SQLite warehouse incident telemetry and SOP guidelines.
7. **Settings & Configuration**: Warehouse bay zone management, velocity/impact kinematic threshold tuning, video source selector, and system diagnostic status.

---

## 📦 Complete Warehouse Handling Behaviours

CareGuard AI implements sequence-based temporal detection across all core warehouse handling scenarios:

| # | Behaviour Name | Temporal Action Sequence Logic | Risk Level | 3-Tier Responsible AI Breakdown |
| :-: | :--- | :--- | :-: | :--- |
| **1** | **Product Dropped** | Elevated ($y < y_{	ext{floor}} - 45	ext{px}$) $	o$ Free-fall velocity spike ($v_y \ge 180	ext{px/s}$) $	o$ Floor impact $	o$ Stationary | **`RED` / `ORANGE`** | **Observed**: Free-fall descent & floor impact.<br>**Risk**: Internal product structural fracture, broken components.<br>**Action**: Quarantine and inspect package contents before dispatch. |
| **2** | **Product Dragged** | Grounded on floor $	o$ Sustained horizontal motion ($v_x \ge 20	ext{px/s}$) along floor ($t \ge 0.8	ext{s}$) without vertical clearance | **`ORANGE` / `YELLOW`** | **Observed**: Package dragged across floor without clearance.<br>**Risk**: Bottom carton abrasion, seam tearing, moisture/dust ingress.<br>**Action**: Use hand trolley, pallet jack, or two-person team carry. |
| **3** | **Rough Handling / Excessive Impact** | Moving package undergoes sharp deceleration impact ($	ext{decel} \ge 750	ext{px/s}^2$) upon placement/slamming | **`ORANGE`** | **Observed**: Sharp deceleration impact during placement.<br>**Risk**: Mechanical shock, fragile component stress, packaging crush.<br>**Action**: Place down with smooth controlled motion; use rubber staging mats. |
| **4** | **Incorrect Stacking** | Top package area $\ge 1.25	imes$ bottom package area or overhang $\ge 22\%$ of bottom width (sustained over resting column) | **`ORANGE`** | **Observed**: Larger/heavier package placed on top of smaller base.<br>**Risk**: Base carton crushing, structural deformation, stack collapse.<br>**Action**: Restack column with heaviest and widest base items at bottom. |
| **5** | **Unstable / Leaning Stack** | Multi-carton resting stack column with center-of-mass lateral displacement ($	ext{tilt} \ge 18	ext{px}$) | **`ORANGE`** | **Observed**: Stack column tilting with severe lateral offset.<br>**Risk**: Imminent column topple, crushing surrounding personnel/cargo.<br>**Action**: Re-align column immediately; interlock stacked layers. |
| **6** | **Placed Outside Designated Area** | Package placed stationary ($	ext{dwell} \ge 2.5	ext{s}$, $	ext{speed} < 12	ext{px/s}$) inside pedestrian walkway/exit zone | **`ORANGE`** | **Observed**: Package left stationary inside transit corridor.<br>**Risk**: Pedestrian trip hazard, blocked emergency egress, MHE collision.<br>**Action**: Relocate package immediately to marked staging bay. |
| **7** | **Handled Without Equipment** | Bulky/heavy cargo ($	ext{area} \ge 12000	ext{px}^2$) carried manually over distance ($\ge 70	ext{px}$) without trolley | **`YELLOW`** | **Observed**: Large heavy package transported manually without MHE.<br>**Risk**: Worker fatigue, musculoskeletal strain, dropped load hazard.<br>**Action**: Deploy hand trolley, platform truck, or two-person team lift. |
| **8** | **Pallet Positioned Incorrectly** | Pallet protruding ($> 25	ext{px}$) into transit walkway or blocking aisle | **`YELLOW`** | **Observed**: Pallet misaligned and protruding into transit lane.<br>**Risk**: Forklift corner impact, pallet runner cracking, transit blockage.<br>**Action**: Re-position pallet flush within designated staging bay markings. |
| **9** | **Material Pushed / Thrown** | Package propelled in free ballistic flight with high horizontal velocity ($v_x \ge 160	ext{px/s}$) separated from hand interaction | **`RED`** | **Observed**: Package thrown/launched with high horizontal velocity.<br>**Risk**: Severe kinetic impact destruction, airborne projectile hazard.<br>**Action**: Carry and place packages with two hands; enforce zero-throwing rule. |
| **10** | **Unsafe Loading / Unloading Order** | Worker pulls bottom package horizontally ($\ge 30	ext{px/s}$) while upper package rests overhead | **`RED`** | **Observed**: Bottom package pulled while upper package rests overhead.<br>**Risk**: Sudden unsupported drop and collapse of upper cargo onto handler.<br>**Action**: De-stack packages strictly top-to-bottom; never remove base first. |
| **11** | **Stepping on Product** | Operator standing/walking directly on top surface of carton ($y_{	ext{feet}} pprox y_{	ext{box\_top}}$ for $\ge 0.35	ext{s}$) | **`ORANGE`** | **Observed**: Operator foot surface contact on top of carton.<br>**Risk**: Structural deformation, top flap puncture, internal contents crush.<br>**Action**: Do not use cartons as footrests or steps; use safety ladders. |
| **12** | **Product Kicked** | Operator foot/lower-leg contact imparting sharp horizontal acceleration along floor | **`ORANGE`** | **Observed**: Package kicked or shoved with foot along floor.<br>**Risk**: Corner impact deformation, seam split, uncontrolled collision.<br>**Action**: Guide packages by hand or MHE; enforce zero-kicking policy. |

---

## 🚦 Damage-Risk Classification Scale

| Risk Level | Status | Color | Description |
| :--- | :--- | :--- | :--- |
| **`GREEN`** | **NORMAL** | Emerald Green | Safe material handling, pallets staged properly within bay lines, no drop/drag risks. |
| **`YELLOW`** | **ATTENTION** | Amber | Minor procedural risks: manual heavy carry without trolley, slight pallet protrusion. |
| **`ORANGE`** | **HIGH RISK** | Orange | High damage risks: rough slamming, dragging on concrete, incorrect/unstable stacking, kicking, stepping on cartons. |
| **`RED`** | **CRITICAL DAMAGE RISK** | Crimson Red | Critical events: free-fall drop, thrown material, or pulling bottom box from stack. Immediate inspection required. |

---

## 🛠️ How to Run, Test & Demonstrate

### 1. Launch the CareGuard AI Web Application (Recommended)
```bash
# Start the web app (FastAPI backend + built React frontend on http://127.0.0.1:8000)
.venv\Scripts\python.exe main.py
```
*The web browser will automatically open to `http://127.0.0.1:8000`.*

#### Additional CLI Flags:
```bash
# Launch without auto-opening browser
.venv\Scripts\python.exe main.py --no-browser

# Custom port or host
.venv\Scripts\python.exe main.py --port 8080 --host 0.0.0.0
```

---

### 2. Run the Complete Automated Test Suite (87 Tests Across 8 Modules)
```bash
# Run all 87 tests via the verified warehouse test suite runner
.venv\Scripts\python.exe scripts/run_all_warehouse_tests.py
```

Or run targeted verification suites individually:
```bash
# 1. Action sequencing (DROP->KICK->DRAG), semantic arbitration & carrying immunity
.venv\Scripts\python.exe -m unittest tests.test_action_sequencing_and_semantic_arbitration

# 2. Product validation, ceiling noise rejection & ballistic trajectory gating
.venv\Scripts\python.exe -m unittest tests.test_product_validation_and_background_rejection

# 3. Product kicking semantic gating & carrying state immunity
.venv\Scripts\python.exe -m unittest tests.test_product_kicking_and_carrying

# 4. Perception filtering & track expiration persistence
.venv\Scripts\python.exe -m unittest tests.test_product_localization_persistence

# 5. Product localization & kick vs throw discrimination
.venv\Scripts\python.exe -m unittest tests.test_product_localization_and_kick

# 6. All 10 core warehouse behaviours
.venv\Scripts\python.exe -m unittest tests.test_all_10_warehouse_behaviours

# 7. Pause persistence & stacking semantic gating
.venv\Scripts\python.exe -m unittest tests.test_event_semantic_gating_and_pause

# 8. Multi-upload lifecycle & stepping detection
.venv\Scripts\python.exe -m unittest tests.test_priority_corrections
```

---

### 3. Reset Demo Database & Clean Baseline
To reset the system to a clean baseline state before demonstrations:
```bash
.venv\Scripts\python.exe scripts/reset_demo_database.py
```
*(Creates an automatic pre-reset SQLite backup in `data/backups/`, clears ephemeral test events and temporary evidence files, and verifies database integrity).*
