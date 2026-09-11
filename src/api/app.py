"""
src/api/app.py
--------------
FastAPI backend service layer for CareGuard AI - Warehouse Video Intelligence.
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import DATA_DIR, APP_TITLE, APP_VERSION
from src.api.routes import (
    video,
    overview,
    incidents,
    analytics,
    prevention,
    assistant,
    simulator,
    settings,
)

# Ensure evidence directory exists
evidence_dir = DATA_DIR / "evidence"
evidence_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="CareGuard AI - Warehouse Video Intelligence API",
    version=APP_VERSION,
    description="Enterprise API service layer for warehouse loading/unloading damage prevention, multi-object tracking, and 10-behaviour temporal sequence analysis.",
)

# Configure CORS for local web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount evidence snapshots static directory
app.mount("/api/evidence", StaticFiles(directory=str(evidence_dir)), name="evidence")

# Include modular API routers
app.include_router(video.router)
app.include_router(overview.router)
app.include_router(incidents.router)
app.include_router(analytics.router)
app.include_router(prevention.router)
app.include_router(assistant.router)
app.include_router(simulator.router)
app.include_router(settings.router)


@app.get("/api/health")
def health_check():
    """Returns system operational status and service health."""
    return {
        "status": "healthy",
        "service": "CareGuard AI Backend",
        "version": APP_VERSION,
        "purpose": "Warehouse Video Intelligence for Material Handling Damage Prevention",
    }


# Serve built frontend assets if present
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static_frontend")
