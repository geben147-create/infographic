"""
Health check endpoint with Temporal, SQLite, and disk space monitoring.

GET /health — returns system status JSON.
Critical failures are logged to data/alerts.jsonl.
"""
from __future__ import annotations

import pathlib
import shutil

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlmodel import Session, text

from src.services.alert_log import log_alert
from src.services.db_service import engine

router = APIRouter()


class HealthResponse(BaseModel):
    status: str  # "ok" | "degraded" | "error"
    temporal: bool
    sqlite: bool
    disk_free_gb: float


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    temporal_ok = False
    sqlite_ok = False
    disk_free_gb = 0.0

    # Check Temporal connectivity
    try:
        client = getattr(request.app.state, "temporal_client", None)
        if client is not None:
            # Light-weight check: if this doesn't raise, Temporal is reachable
            await client.service_client.check_health()
            temporal_ok = True
    except Exception as exc:
        log_alert(
            level="critical",
            message="Temporal health check failed",
            details=str(exc),
        )

    # Check SQLite connectivity
    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
        sqlite_ok = True
    except Exception as exc:
        log_alert(
            level="critical",
            message="SQLite health check failed",
            details=str(exc),
        )

    # Check disk space
    try:
        data_dir = pathlib.Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(str(data_dir))
        disk_free_gb = round(usage.free / (1024**3), 2)
        if disk_free_gb < 5.0:
            log_alert(
                level="warning",
                message=f"Low disk space: {disk_free_gb} GB free",
                details=f"Total: {round(usage.total / (1024**3), 2)} GB, Used: {round(usage.used / (1024**3), 2)} GB",
            )
    except Exception as exc:
        log_alert(
            level="warning",
            message="Disk space check failed",
            details=str(exc),
        )

    overall = "ok"
    if not temporal_ok or not sqlite_ok:
        overall = "degraded"
    if not temporal_ok and not sqlite_ok:
        overall = "error"

    return HealthResponse(
        status=overall,
        temporal=temporal_ok,
        sqlite=sqlite_ok,
        disk_free_gb=disk_free_gb,
    )
