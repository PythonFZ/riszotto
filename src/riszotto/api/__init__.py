"""FastAPI application for riszotto web UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from riszotto.api.routes import router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns
    -------
    FastAPI
        Configured application with API routes and static file serving.
    """
    app = FastAPI(title="riszotto", docs_url="/api/docs", redoc_url=None)
    app.include_router(router, prefix="/api")

    # Serve built frontend assets if available
    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
