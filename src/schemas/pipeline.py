"""
API request/response schemas for the pipeline endpoints.

Field names must match the UI-SPEC.md contract exactly — they are the JSON
surface that operators interact with.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel


class PipelineStatus(str, Enum):
    """Pipeline execution status values.

    Use these exact lowercase strings — not 'RUNNING', not 'in_progress'.
    """

    running = "running"
    completed = "completed"
    failed = "failed"
    unknown = "unknown"
    waiting_approval = "waiting_approval"
    ready_to_upload = "ready_to_upload"


class PipelineTriggerRequest(BaseModel):
    """POST /api/pipeline/trigger — request body."""

    topic: str
    channel_id: str


class PipelineTriggerResponse(BaseModel):
    """POST /api/pipeline/trigger — success response."""

    workflow_id: str
    status: Literal["started"]
    channel_id: str
    topic: str
    estimated_cost_usd: float | None = None


class PipelineStatusResponse(BaseModel):
    """GET /api/pipeline/status/{workflow_id} — status poll response."""

    workflow_id: str
    status: PipelineStatus
    current_step: str | None = None
    scenes_total: int | None = None
    scenes_done: int | None = None
    cost_so_far_usd: float | None = None
    youtube_url: str | None = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class ApprovalSignal(BaseModel):
    """Temporal signal payload for the quality gate approval."""

    approved: bool
    reason: str = ""


class ApproveRequest(BaseModel):
    """POST /api/pipeline/{id}/approve — request body from operator."""

    approved: bool
    reason: str = ""


class VideoPreviewResponse(BaseModel):
    """GET /api/pipeline/{id}/video — metadata before streaming."""

    workflow_id: str
    video_path: str
    file_size_bytes: int


class CostLineItem(BaseModel):
    """A single cost line in the cost breakdown."""

    service: str  # "fal.ai" | "none"
    step: str  # e.g. "video_gen_scene_01"
    amount_usd: float
    resolution: str | None = None  # "480p" | "720p" | null


class CostDetailResponse(BaseModel):
    """GET /api/pipeline/cost/{workflow_id} — cost breakdown response."""

    workflow_id: str
    channel_id: str
    total_cost_usd: float
    breakdown: list[CostLineItem]
