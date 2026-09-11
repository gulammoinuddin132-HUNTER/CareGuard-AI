"""
CareGuard AI - Comprehensive Risk Severity Policy & Explicit RED Alert Test Suite
----------------------------------------------------------------------------------
Validates that:
1. MODEL CONFIDENCE != RISK SEVERITY (confidence never elevates safe handling to RED).
2. All 10 behaviours map deterministically to the correct Risk Severity Tier (RED, ORANGE, YELLOW, GREEN).
3. RED alerts only fire for critical kinetic danger (throwing, severe drops, unsafe extraction).
4. Human-readable severity_reason and structured severity_factors are generated for every event.
5. SQLite database faithfully persists and restores severity_reason and severity_factors.
6. Handling Quality Score and Command Center status calculate deterministically from risk events.
"""

import unittest
import time
import json
from datetime import datetime
from pathlib import Path

from src.core.warehouse_models import (
    WarehouseBehaviourType,
    WarehouseObjectCategory,
    KinematicState,
    TrackedEntity,
    WarehouseBehaviourEvent,
)
from src.core.warehouse_risk_policy import (
    calculate_risk_severity,
    WarehouseRiskTier,
)
from src.core.warehouse_behaviour_engine import TemporalWarehouseBehaviourEngine
from src.database.db_manager import DatabaseManager


class TestRiskSeverityPolicy(unittest.TestCase):

    def setUp(self):
        self.engine = TemporalWarehouseBehaviourEngine(frame_width=640, frame_height=480)

    # -------------------------------------------------------------------------
    # TEST 1: Model Confidence Independence (Confidence != Severity)
    # -------------------------------------------------------------------------
    def test_high_confidence_safe_handling_is_green(self):
        """Even with 0.99 model confidence, safe/normal handling MUST be GREEN."""
        result = calculate_risk_severity(
            behaviour_type="SAFE_HANDLING",
            kinematics={"speed": 10.0, "product_grounded": True},
            confidence=0.99,
        )
        self.assertEqual(result["severity"], WarehouseRiskTier.GREEN.value)
        self.assertEqual(result["severity_factors"]["confidence"], 0.99)
        self.assertIn("safe operational boundaries", result["severity_reason"])

    # -------------------------------------------------------------------------
    # TEST 2: Low Confidence Violations Still Reflect True Physical Severity
    # -------------------------------------------------------------------------
    def test_low_confidence_throwing_still_evaluates_red(self):
        """A verified ballistic throw at 320 px/s is RED even with low (0.65) confidence."""
        result = calculate_risk_severity(
            behaviour_type=WarehouseBehaviourType.MATERIAL_PUSHED_THROWN,
            kinematics={"horizontal_velocity": 320.0, "product_grounded": False},
            confidence=0.65,
        )
        self.assertEqual(result["severity"], WarehouseRiskTier.RED.value)
        self.assertGreaterEqual(result["severity_factors"]["measured_value"], 160.0)
        self.assertIn("320.0 px/s", result["severity_reason"])

    # -------------------------------------------------------------------------
    # TEST 3: Material Pushed / Thrown -> Critical RED
    # -------------------------------------------------------------------------
    def test_material_pushed_thrown_produces_red(self):
        """High horizontal ballistic velocity while airborne MUST produce RED alert."""
        result = calculate_risk_severity(
            behaviour_type=WarehouseBehaviourType.MATERIAL_PUSHED_THROWN,
            kinematics={"horizontal_velocity": 240.0, "speed": 245.0, "product_grounded": False},
            confidence=0.88,
        )
        self.assertEqual(result["severity"], "RED")
        self.assertTrue(result["severity_factors"]["is_airborne"])
        self.assertEqual(result["severity_factors"]["threshold"], 160.0)
        self.assertIn("ballistic flight", result["severity_reason"])

    # -------------------------------------------------------------------------
    # TEST 4: Product Dropped -> Severe Free Fall produces RED
    # -------------------------------------------------------------------------
    def test_product_dropped_severe_produces_red(self):
        """Product dropping with downward velocity > 250 px/s and > 0.8m drop MUST produce RED."""
        result = calculate_risk_severity(
            WarehouseBehaviourType.PRODUCT_DROPPED,
            kinematics={"max_downward_vy": 380.0, "displacement": 220.0},
            metadata={"drop_height_m": 0.95},
            confidence=0.92,
        )
        self.assertEqual(result["severity"], "RED")
        self.assertEqual(result["severity_factors"]["measured_value"], 380.0)
        self.assertIn("high-elevation free fall", result["severity_reason"])

    # -------------------------------------------------------------------------
    # TEST 5: Product Dropped -> Minor Drop produces ORANGE
    # -------------------------------------------------------------------------
    def test_product_dropped_minor_produces_orange(self):
        """Product dropping from low height (< 0.8m, vy < 250 px/s) produces ORANGE."""
        result = calculate_risk_severity(
            WarehouseBehaviourType.PRODUCT_DROPPED,
            kinematics={"max_downward_vy": 180.0, "displacement": 80.0},
            metadata={"drop_height_m": 0.35},
            confidence=0.85,
        )
        self.assertEqual(result["severity"], "ORANGE")
        self.assertIn("moderate height", result["severity_reason"])

    # -------------------------------------------------------------------------
    # TEST 6: Unsafe Loading Sequence -> Critical RED
    # -------------------------------------------------------------------------
    def test_unsafe_loading_sequence_produces_red(self):
        """Pulling bottom unit out while upper cargo remains overhead MUST produce RED."""
        result = calculate_risk_severity(
            WarehouseBehaviourType.UNSAFE_LOADING_SEQUENCE,
            kinematics={"bot_speed": 45.0, "top_speed": 0.0},
            confidence=0.90,
        )
        self.assertEqual(result["severity"], "RED")
        self.assertTrue(result["severity_factors"]["overhead_suspended_load"])
        self.assertIn("imminent column collapse", result["severity_reason"])

    # -------------------------------------------------------------------------
    # TEST 7: Product Dragged -> Severe Sustained produces ORANGE
    # -------------------------------------------------------------------------
    def test_product_dragged_severe_produces_orange(self):
        """Dragging for >= 2.0s or > 100px produces ORANGE."""
        result = calculate_risk_severity(
            WarehouseBehaviourType.PRODUCT_DRAGGED,
            kinematics={"duration": 2.4, "displacement": 140.0, "speed": 55.0},
            confidence=0.89,
        )
        self.assertEqual(result["severity"], "ORANGE")
        self.assertIn("Sustained severe floor dragging", result["severity_reason"])

    # -------------------------------------------------------------------------
    # TEST 8: Product Dragged -> Standard Drag produces YELLOW
    # -------------------------------------------------------------------------
    def test_product_dragged_standard_produces_yellow(self):
        """Short dragging (< 2.0s and < 100px) produces YELLOW."""
        result = calculate_risk_severity(
            WarehouseBehaviourType.PRODUCT_DRAGGED,
            kinematics={"duration": 0.8, "displacement": 45.0, "speed": 40.0},
            confidence=0.82,
        )
        self.assertEqual(result["severity"], "YELLOW")
        self.assertIn("without mechanical trolley clearance", result["severity_reason"])

    # -------------------------------------------------------------------------
    # TEST 9: Rough Handling / High Deceleration -> ORANGE
    # -------------------------------------------------------------------------
    def test_rough_handling_produces_orange(self):
        """Sudden high impact deceleration produces ORANGE."""
        result = calculate_risk_severity(
            WarehouseBehaviourType.ROUGH_HANDLING,
            kinematics={"deceleration": 460.0, "peak_speed": 85.0},
            confidence=0.87,
        )
        self.assertEqual(result["severity"], "ORANGE")
        self.assertEqual(result["severity_factors"]["threshold"], 350.0)
        self.assertIn("Sharp impact deceleration", result["severity_reason"])

    # -------------------------------------------------------------------------
    # TEST 10: Stacking Violations -> ORANGE
    # -------------------------------------------------------------------------
    def test_incorrect_and_unstable_stacking_produce_orange(self):
        """Incorrect stacking (heavy top) and leaning column produce ORANGE."""
        res_inc = calculate_risk_severity(
            WarehouseBehaviourType.INCORRECT_STACKING,
            kinematics={"top_area": 35000.0, "bot_area": 20000.0, "overhang_px": 30.0},
            confidence=0.91,
        )
        self.assertEqual(res_inc["severity"], "ORANGE")
        self.assertIn("crushing risk", res_inc["severity_reason"])

        res_unst = calculate_risk_severity(
            WarehouseBehaviourType.UNSTABLE_STACKING,
            kinematics={"tilt_offset_px": 48.0},
            confidence=0.91,
        )
        self.assertEqual(res_unst["severity"], "ORANGE")
        self.assertIn("toppling collapse", res_unst["severity_reason"])

    # -------------------------------------------------------------------------
    # TEST 11: Walkway Dwell -> ORANGE
    # -------------------------------------------------------------------------
    def test_placed_outside_designated_area_produces_orange(self):
        """Leaving items in walkway corridor for >= 3.0s produces ORANGE."""
        result = calculate_risk_severity(
            WarehouseBehaviourType.PLACED_OUTSIDE_DESIGNATED_AREA,
            kinematics={"dwell_time": 4.5},
            confidence=0.85,
        )
        self.assertEqual(result["severity"], "ORANGE")
        self.assertEqual(result["severity_factors"]["zone"], "PEDESTRIAN_WALKWAY")

    # -------------------------------------------------------------------------
    # TEST 12: Manual Carry & Pallet Misalignment -> YELLOW
    # -------------------------------------------------------------------------
    def test_manual_carry_and_pallet_protrusion_produce_yellow(self):
        """Manual carry and pallet protrusion produce YELLOW."""
        res_carry = calculate_risk_severity(
            WarehouseBehaviourType.HANDLED_WITHOUT_EQUIPMENT,
            kinematics={"displacement": 85.0, "cargo_area": 18000.0},
            confidence=0.86,
        )
        self.assertEqual(res_carry["severity"], "YELLOW")

        res_pallet = calculate_risk_severity(
            WarehouseBehaviourType.PALLET_POSITIONED_INCORRECTLY,
            kinematics={"protrusion_px": 35.0},
            confidence=0.90,
        )
        self.assertEqual(res_pallet["severity"], "YELLOW")

    # -------------------------------------------------------------------------
    # TEST 13: End-to-End Behaviour Engine Event Evaluation
    # -------------------------------------------------------------------------
    def test_engine_throwing_event_attaches_severity_policy(self):
        """Temporal behaviour engine evaluation creates events with exact severity metadata."""
        t0 = 100.0
        prod = TrackedEntity(
            track_id=10,
            class_id=1,
            label="product",
            category=WarehouseObjectCategory.PRODUCT,
            confidence=0.88,
            current_bbox=(200, 150, 120, 90),
            first_seen=t0,
            last_seen=t0 + 0.3,
            is_confirmed=True,
            history=[
                KinematicState(timestamp=t0, bbox=(200, 150, 120, 90), centroid=(260.0, 195.0), velocity=(0.0, 0.0), speed=0.0, elevation_ratio=0.4, is_grounded=False),
                KinematicState(timestamp=t0 + 0.15, bbox=(240, 150, 120, 90), centroid=(300.0, 195.0), velocity=(260.0, 0.0), speed=260.0, elevation_ratio=0.4, is_grounded=False),
                KinematicState(timestamp=t0 + 0.30, bbox=(280, 150, 120, 90), centroid=(340.0, 195.0), velocity=(266.7, 0.0), speed=266.7, elevation_ratio=0.4, is_grounded=False),
            ],
        )

        events = self.engine.evaluate_frame([prod], current_time=t0 + 0.30, video_source="TEST_FEED")
        self.assertEqual(len(events), 1)
        evt = events[0]
        self.assertEqual(evt.behaviour_type, WarehouseBehaviourType.MATERIAL_PUSHED_THROWN)
        self.assertEqual(evt.risk_level, "RED")
        self.assertIsNotNone(evt.severity_reason)
        self.assertIsNotNone(evt.severity_factors)
        self.assertEqual(evt.severity_factors["behaviour"], "MATERIAL_PUSHED_THROWN")
        self.assertGreaterEqual(evt.severity_factors["measured_value"], 160.0)

    # -------------------------------------------------------------------------
    # TEST 14: SQLite Database Persistence & Immutability of Severity Fields
    # -------------------------------------------------------------------------
    def test_database_persists_severity_reason_and_factors(self):
        """Database manager stores and retrieves severity_reason and structured severity_factors."""
        db_path = Path("data/test_severity_db.sqlite")
        if db_path.exists():
            db_path.unlink()

        db = DatabaseManager(db_path=db_path)
        test_factors = {
            "behaviour": "MATERIAL_PUSHED_THROWN",
            "primary_metric": "horizontal_velocity",
            "measured_value": 266.7,
            "threshold": 160.0,
            "unit": "px/s",
            "is_airborne": True,
        }

        rec_id = db.log_warehouse_event(
            event_id="TEST-SEV-001",
            behaviour_type="MATERIAL_PUSHED_THROWN",
            risk_level="RED",
            confidence=0.88,
            start_timestamp="2026-09-10 10:00:00",
            end_timestamp="2026-09-10 10:00:01",
            duration_seconds=1.0,
            observed_behaviour="Product thrown horizontally at 266.7 px/s.",
            potential_risk="High damage hazard.",
            recommended_action="Zero throwing standard.",
            severity_reason="Product entered unsupported ballistic flight with horizontal velocity of 266.7 px/s.",
            severity_factors=test_factors,
            video_source="TEST_FEED",
        )

        record = db.get_warehouse_event_by_id("TEST-SEV-001")
        self.assertIsNotNone(record)
        self.assertEqual(record.risk_level, "RED")
        self.assertIn("266.7 px/s", record.severity_reason)

        # Verify to_dict serializes structured severity_factors
        rec_dict = record.to_dict()
        self.assertEqual(rec_dict["severity_factors"]["measured_value"], 266.7)
        self.assertEqual(rec_dict["severity_factors"]["threshold"], 160.0)

        # Cleanup
        if db_path.exists():
            db_path.unlink()

    # -------------------------------------------------------------------------
    # TEST 15: Handling Quality Score & Summary KPI Calculation
    # -------------------------------------------------------------------------
    def test_handling_quality_score_penalties(self):
        """Deductions: RED (-10), ORANGE (-5), YELLOW (-2), GREEN (0). Baseline 100."""
        db_path = Path("data/test_kpi_db.sqlite")
        if db_path.exists():
            db_path.unlink()

        db = DatabaseManager(db_path=db_path)
        # 1 RED (-10), 2 ORANGE (-10), 3 YELLOW (-6) -> Total penalty: 26 -> Score: 74
        db.log_warehouse_event(event_id="E1", behaviour_type="MATERIAL_PUSHED_THROWN", risk_level="RED", confidence=0.9, start_timestamp="2026-09-10 10:00:00", end_timestamp="2026-09-10 10:00:01", duration_seconds=1.0, observed_behaviour="", potential_risk="", recommended_action="")
        db.log_warehouse_event(event_id="E2", behaviour_type="ROUGH_HANDLING", risk_level="ORANGE", confidence=0.9, start_timestamp="2026-09-10 10:00:02", end_timestamp="2026-09-10 10:00:03", duration_seconds=1.0, observed_behaviour="", potential_risk="", recommended_action="")
        db.log_warehouse_event(event_id="E3", behaviour_type="INCORRECT_STACKING", risk_level="ORANGE", confidence=0.9, start_timestamp="2026-09-10 10:00:04", end_timestamp="2026-09-10 10:00:05", duration_seconds=1.0, observed_behaviour="", potential_risk="", recommended_action="")
        db.log_warehouse_event(event_id="E4", behaviour_type="PRODUCT_DRAGGED", risk_level="YELLOW", confidence=0.9, start_timestamp="2026-09-10 10:00:06", end_timestamp="2026-09-10 10:00:07", duration_seconds=1.0, observed_behaviour="", potential_risk="", recommended_action="")
        db.log_warehouse_event(event_id="E5", behaviour_type="HANDLED_WITHOUT_EQUIPMENT", risk_level="YELLOW", confidence=0.9, start_timestamp="2026-09-10 10:00:08", end_timestamp="2026-09-10 10:00:09", duration_seconds=1.0, observed_behaviour="", potential_risk="", recommended_action="")
        db.log_warehouse_event(event_id="E6", behaviour_type="PALLET_POSITIONED_INCORRECTLY", risk_level="YELLOW", confidence=0.9, start_timestamp="2026-09-10 10:00:10", end_timestamp="2026-09-10 10:00:11", duration_seconds=1.0, observed_behaviour="", potential_risk="", recommended_action="")

        summary = db.get_warehouse_stats_summary()
        self.assertEqual(summary["total_events"], 6)
        self.assertEqual(summary["critical_events"], 1)
        self.assertEqual(summary["high_risk_events"], 2)
        self.assertEqual(summary["attention_events"], 3)
        self.assertEqual(summary["handling_quality_score"], 74)
        self.assertEqual(summary["overall_status"], "RED")

        # Cleanup
        if db_path.exists():
            db_path.unlink()


if __name__ == "__main__":
    unittest.main()
