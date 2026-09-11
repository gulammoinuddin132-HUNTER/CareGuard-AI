"""
src/research/train_real_yolo26_warehouse.py
-------------------------------------------
Trains YOLO26n on warehouse_real_v2 dataset (100% photographic real data)
using gentle transfer learning from yolo26n.pt.
Evaluates on both validation and held-out test splits.
Exports to ONNX for production CPU inference.
"""
import sys
import time
import shutil
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ultralytics import YOLO

from config import (
    BASE_DIR,
    DATA_DIR,
    MODELS_DIR,
    YOLO26N_BASE_MODEL_PATH,
    YOLO26N_WAREHOUSE_MODEL_PATH,
    YOLO26N_WAREHOUSE_ONNX_PATH,
)


def train_real_yolo26_warehouse():
    data_yaml_path = DATA_DIR / "datasets" / "warehouse_real_v2" / "data.yaml"
    if not data_yaml_path.exists():
        raise FileNotFoundError(f"data.yaml not found at: {data_yaml_path}")

    base_weights = str(YOLO26N_BASE_MODEL_PATH.resolve()) if YOLO26N_BASE_MODEL_PATH.exists() else "yolo26n.pt"
    print("==================================================")
    print("  YOLO26n REAL WAREHOUSE TRAINING INITIATION")
    print(f"  BASE WEIGHTS: {base_weights}")
    print(f"  DATA YAML: {data_yaml_path}")
    print(f"  OUTPUT PT: {YOLO26N_WAREHOUSE_MODEL_PATH}")
    print(f"  OUTPUT ONNX: {YOLO26N_WAREHOUSE_ONNX_PATH}")
    print("==================================================")

    # Load base YOLO26n model
    model = YOLO(base_weights)

    # Fine-tune on custom real dataset with gentle learning rate
    t0 = time.time()
    results = model.train(
        data=str(data_yaml_path.resolve()),
        epochs=18,
        imgsz=640,
        batch=16,
        workers=0,  # Windows safe
        device="cpu",
        lr0=0.001,  # Gentle transfer learning
        lrf=0.01,
        project=str(DATA_DIR / "research" / "yolo26_real_runs"),
        name="real_warehouse_finetune",
        exist_ok=True,
        verbose=True,
    )
    train_duration = time.time() - t0
    print(f"\n[TRAINING COMPLETE] Time taken: {train_duration:.1f}s")

    # Save best weights to models directory
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    best_weights_path = Path(model.trainer.best) if hasattr(model, "trainer") and hasattr(model.trainer, "best") else None
    if best_weights_path and best_weights_path.exists():
        shutil.copy(str(best_weights_path), str(YOLO26N_WAREHOUSE_MODEL_PATH))
        print(f"[MODEL SAVED] Best PyTorch weights saved to: {YOLO26N_WAREHOUSE_MODEL_PATH}")
    else:
        model.save(str(YOLO26N_WAREHOUSE_MODEL_PATH))
        print(f"[MODEL SAVED] Weights saved to: {YOLO26N_WAREHOUSE_MODEL_PATH}")

    # Reload best model for evaluation
    best_model = YOLO(str(YOLO26N_WAREHOUSE_MODEL_PATH))

    # Evaluate validation metrics
    print("\n[VALIDATION METRICS - SEQUENCE 2 DRAGGING + BOXES]")
    val_metrics = best_model.val(data=str(data_yaml_path.resolve()), split="val")
    v_mp = val_metrics.box.mp
    v_mr = val_metrics.box.mr
    v_map50 = val_metrics.box.map50
    v_map95 = val_metrics.box.map
    print(f"  Val Precision: {v_mp:.4f}")
    print(f"  Val Recall:    {v_mr:.4f}")
    print(f"  Val mAP50:     {v_map50:.4f}")
    print(f"  Val mAP50-95:  {v_map95:.4f}")

    # Evaluate held-out test metrics (Zero-leakage test sequence 3: throwing)
    print("\n[HELD-OUT TEST METRICS - SEQUENCE 3 THROWING + TEST BOXES]")
    test_metrics = best_model.val(data=str(data_yaml_path.resolve()), split="test")
    t_mp = test_metrics.box.mp
    t_mr = test_metrics.box.mr
    t_map50 = test_metrics.box.map50
    t_map95 = test_metrics.box.map
    print(f"  Test Precision: {t_mp:.4f}")
    print(f"  Test Recall:    {t_mr:.4f}")
    print(f"  Test mAP50:     {t_map50:.4f}")
    print(f"  Test mAP50-95:  {t_map95:.4f}")

    # Export to ONNX for fast OpenCV DNN CPU deployment
    print("\n[ONNX EXPORT] Exporting to ONNX format...")
    try:
        exported_path = best_model.export(format="onnx", imgsz=640, dynamic=False, simplify=True)
        if Path(exported_path).exists():
            shutil.copy(str(exported_path), str(YOLO26N_WAREHOUSE_ONNX_PATH))
            print(f"[ONNX EXPORT SUCCESS] Model saved at: {YOLO26N_WAREHOUSE_ONNX_PATH}")
    except Exception as e:
        print(f"[ONNX EXPORT WARNING] Could not auto-export ONNX: {e}")

    return {
        "val_precision": float(v_mp),
        "val_recall": float(v_mr),
        "val_map50": float(v_map50),
        "val_map50_95": float(v_map95),
        "test_precision": float(t_mp),
        "test_recall": float(t_mr),
        "test_map50": float(t_map50),
        "test_map50_95": float(t_map95),
        "training_seconds": round(train_duration, 1),
    }


if __name__ == "__main__":
    metrics = train_real_yolo26_warehouse()
    print("\n--- FINAL TRAINING RESULT ---")
    print(metrics)
