"""
CareGuard AI - Main Application Entry Point
-------------------------------------------
AI-Powered Video Intelligence for Safer, Damage-Free Warehouse Operations.
Godrej Enterprises Group AI Video Intelligence Hackathon.

Launches the CareGuard AI Web Application (FastAPI backend + React frontend).
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure project root is in python path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def launch_web_app(host: str = "127.0.0.1", port: int = 8000, no_browser: bool = False) -> None:
    """Launches the primary CareGuard AI Web Application."""
    if no_browser:
        os.environ["NO_BROWSER"] = "1"
    from run_app import main as web_main
    web_main()


def main() -> None:
    """CLI Argument Parser & Router."""
    parser = argparse.ArgumentParser(
        description="CareGuard AI - AI-Powered Video Intelligence for Warehouse Handling"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host address for web server (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for web server (default: 8000)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically open web browser on startup",
    )

    args = parser.parse_args()
    launch_web_app(host=args.host, port=args.port, no_browser=args.no_browser)


if __name__ == "__main__":
    main()
