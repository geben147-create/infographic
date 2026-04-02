"""
System management API endpoints.

  GET /api/system/workers  — worker pool configuration
  GET /api/system/info     — FFmpeg, Ollama, ComfyUI versions
  GET /api/system/alerts   — recent alerts from alerts.jsonl
"""
from __future__ import annotations

import json
import pathlib
import subprocess

from fastapi import APIRouter
from pydantic import BaseModel

from src.config import settings

router = APIRouter(prefix="/api/system")


class WorkerInfo(BaseModel):
    name: str
    task_queue: str
    max_concurrent: int
    description: str


class WorkersResponse(BaseModel):
    workers: list[WorkerInfo]


class ServiceInfo(BaseModel):
    name: str
    version: str | None = None
    status: str  # "available" | "unavailable" | "unknown"
    url: str | None = None


class SystemInfoResponse(BaseModel):
    services: list[ServiceInfo]


class AlertEntry(BaseModel):
    ts: str
    level: str
    message: str
    details: str = ""


class AlertsResponse(BaseModel):
    alerts: list[AlertEntry]
    total: int


@router.get("/workers", response_model=WorkersResponse)
def get_workers() -> WorkersResponse:
    return WorkersResponse(
        workers=[
            WorkerInfo(
                name="GPU Worker",
                task_queue="gpu-queue",
                max_concurrent=1,
                description="ComfyUI, Ollama, TTS — serial GPU execution (RTX 4070 8GB)",
            ),
            WorkerInfo(
                name="CPU Worker",
                task_queue="cpu-queue",
                max_concurrent=4,
                description="FFmpeg assembly, file ops, thumbnail generation",
            ),
            WorkerInfo(
                name="API Worker",
                task_queue="api-queue",
                max_concurrent=8,
                description="fal.ai, YouTube API, Google Sheets, Gemini",
            ),
        ]
    )


def _check_ffmpeg() -> ServiceInfo:
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=5,
        )
        first_line = result.stdout.split("\n")[0] if result.stdout else ""
        version = first_line.split(" ")[2] if "ffmpeg version" in first_line else first_line
        return ServiceInfo(name="FFmpeg", version=version, status="available")
    except Exception:
        return ServiceInfo(name="FFmpeg", status="unavailable")


def _check_ollama() -> ServiceInfo:
    import httpx
    try:
        resp = httpx.get(f"{settings.ollama_url}/api/tags", timeout=3)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            model_names = [m.get("name", "") for m in models[:5]]
            return ServiceInfo(
                name="Ollama",
                version=", ".join(model_names) if model_names else "no models",
                status="available",
                url=settings.ollama_url,
            )
        return ServiceInfo(name="Ollama", status="unavailable", url=settings.ollama_url)
    except Exception:
        return ServiceInfo(name="Ollama", status="unavailable", url=settings.ollama_url)


def _check_comfyui() -> ServiceInfo:
    import httpx
    try:
        resp = httpx.get(f"{settings.comfyui_url}/system_stats", timeout=3)
        if resp.status_code == 200:
            return ServiceInfo(
                name="ComfyUI",
                version="running",
                status="available",
                url=settings.comfyui_url,
            )
        return ServiceInfo(name="ComfyUI", status="unavailable", url=settings.comfyui_url)
    except Exception:
        return ServiceInfo(name="ComfyUI", status="unavailable", url=settings.comfyui_url)


@router.get("/info", response_model=SystemInfoResponse)
def get_system_info() -> SystemInfoResponse:
    return SystemInfoResponse(
        services=[
            _check_ffmpeg(),
            _check_ollama(),
            _check_comfyui(),
        ]
    )


@router.get("/alerts", response_model=AlertsResponse)
def get_alerts(limit: int = 20) -> AlertsResponse:
    alert_path = pathlib.Path("data") / "alerts.jsonl"
    if not alert_path.exists():
        return AlertsResponse(alerts=[], total=0)

    lines = alert_path.read_text(encoding="utf-8").strip().split("\n")
    lines = [ln for ln in lines if ln.strip()]

    # Reverse for newest first
    lines.reverse()
    total = len(lines)
    lines = lines[:limit]

    alerts = []
    for line in lines:
        try:
            data = json.loads(line)
            alerts.append(AlertEntry(
                ts=data.get("ts", ""),
                level=data.get("level", "unknown"),
                message=data.get("message", ""),
                details=data.get("details", ""),
            ))
        except json.JSONDecodeError:
            continue

    return AlertsResponse(alerts=alerts, total=total)
