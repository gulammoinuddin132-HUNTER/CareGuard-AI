"""
run_app.py
----------
Primary application launcher for CareGuard AI - Warehouse Video Intelligence.
Starts the FastAPI backend server and serves the modern React web frontend.
"""

import os
import sys
import webbrowser
from pathlib import Path
import uvicorn

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def main():
    print("==================================================================")
    print("  CAREGUARD AI - WAREHOUSE VIDEO INTELLIGENCE")
    print("  Godrej Enterprises Group AI Video Intelligence Hackathon")
    print("  See Risk. Prevent Damage.")
    print("==================================================================")
    print("\n[1/2] Initializing CareGuard AI Backend & CV Ingestion Engine...")
    print("      • Database: SQLite (warehouse_behaviour_events)")
    print("      • Perception: Multi-Object Tracker & 10 Temporal Behaviour Engines")
    print("      • Responsible AI: Observed -> Potential Risk -> Corrective Action")

    print("\n[2/2] Starting Web Server on http://127.0.0.1:8000 ...")
    print("      • Dashboard UI: http://127.0.0.1:8000")
    print("      • API Docs: http://127.0.0.1:8000/docs")
    print("      • Live Video Feed: http://127.0.0.1:8000/api/video/feed\n")

    # Optionally auto-open browser in non-headless environments
    try:
        if os.getenv("NO_BROWSER", "0") != "1":
            webbrowser.open("http://127.0.0.1:8000")
    except Exception:
        pass

    uvicorn.run(
        "src.api.app:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    main()
