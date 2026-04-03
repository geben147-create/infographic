"""
Pipeline API endpoints.

Exposes the ContentPipelineWorkflow via FastAPI:
  POST   /api/pipeline/trigger             — start a new pipeline run
  GET    /api/pipeline/status/{workflow_id} — poll current step + cost
  GET    /api/pipeline/cost/{workflow_id}   — full cost breakdown
  POST   /api/pipeline/{workflow_id}/approve — quality gate: approve/reject
  GET    /api/pipeline/{workflow_id}/video  — preview assembled video
  DELETE /api/pipeline/{workflow_id}        — cancel in-flight run
"""
from __future__ import annotations

import pathlib
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from sqlmodel import Session
from temporalio.service import RPCError

from src.models.channel_config import load_channel_config
from src.models.pipeline_run import PipelineRun
from src.schemas.pipeline import (
    ApprovalSignal,
    ApproveRequest,
    CostDetailResponse,
    CostLineItem,
    PipelineStatus,
    PipelineStatusResponse,
    PipelineTriggerRequest,
    PipelineTriggerResponse,
)
from src.services.cost_tracker import CostTracker
from src.services.db_service import create_pipeline_run, engine
from src.workflows.content_pipeline import ContentPipelineWorkflow, PipelineParams

router = APIRouter(prefix="/api/pipeline")

_cost_tracker = CostTracker()


@router.post("/trigger", response_model=PipelineTriggerResponse)
async def trigger_pipeline(
    body: PipelineTriggerRequest,
    request: Request,
) -> PipelineTriggerResponse:
    """Start a new ContentPipelineWorkflow run.

    Generates a unique workflow_id, starts the Temporal workflow on gpu-queue,
    and returns the workflow_id for subsequent status polling.

    Args:
        body: PipelineTriggerRequest with topic and channel_id.
        request: FastAPI request (for temporal_client from app.state).

    Returns:
        PipelineTriggerResponse with workflow_id and status="started".
    """
    workflow_id = f"pipeline-{uuid4().hex[:8]}"
    client = request.app.state.temporal_client

    await client.start_workflow(
        ContentPipelineWorkflow.run,
        PipelineParams(
            run_id=workflow_id,
            topic=body.topic,
            channel_id=body.channel_id,
        ),
        id=workflow_id,
        task_queue="gpu-queue",
    )

    # Persist initial pipeline run record so the dashboard shows it immediately.
    with Session(engine) as session:
        create_pipeline_run(session, {
            "workflow_id": workflow_id,
            "channel_id": body.channel_id,
            "status": "running",
            "started_at": datetime.now(timezone.utc),
        })

    # Rough cost estimate from channel config (optional, non-blocking)
    estimated_cost: float | None = None
    try:
        config = load_channel_config(body.channel_id)
        if config.vgen_enabled:
            # 5 scenes × ~$0.50 average per video clip (fal.ai estimate)
            estimated_cost = 5 * 0.50
    except Exception:
        pass  # cost estimate is best-effort

    return PipelineTriggerResponse(
        workflow_id=workflow_id,
        status="started",
        channel_id=body.channel_id,
        topic=body.topic,
        estimated_cost_usd=estimated_cost,
    )


_TEMPORAL_TO_PIPELINE_STATUS: dict[str, PipelineStatus] = {
    "RUNNING": PipelineStatus.running,
    "COMPLETED": PipelineStatus.completed,
    "FAILED": PipelineStatus.failed,
    "CANCELED": PipelineStatus.failed,
    "TERMINATED": PipelineStatus.failed,
    "TIMED_OUT": PipelineStatus.failed,
    "CONTINUED_AS_NEW": PipelineStatus.running,
}


@router.get("/status/{workflow_id}", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    workflow_id: str,
    request: Request,
) -> PipelineStatusResponse:
    """Poll the current status of a pipeline workflow.

    Maps Temporal workflow execution status to PipelineStatus enum.
    Also reads cost_so_far from CostTracker.

    Args:
        workflow_id: Temporal workflow ID returned by /trigger.
        request: FastAPI request (for temporal_client from app.state).

    Returns:
        PipelineStatusResponse with status, cost_so_far_usd, and timestamps.
    """
    client = request.app.state.temporal_client
    handle = client.get_workflow_handle(workflow_id)

    try:
        desc = await handle.describe()
        raw_status = desc.status.name if desc.status else "UNKNOWN"
        mapped_status = _TEMPORAL_TO_PIPELINE_STATUS.get(raw_status, PipelineStatus.unknown)

        started_at = (
            desc.start_time.isoformat() if desc.start_time else None
        )
        completed_at = (
            desc.close_time.isoformat()
            if desc.close_time and mapped_status == PipelineStatus.completed
            else None
        )

        cost_so_far = _cost_tracker.get_run_total(workflow_id)

        # Retrieve youtube_url from result if completed; also check for ready_to_upload
        youtube_url: str | None = None
        if mapped_status == PipelineStatus.completed:
            try:
                result = await handle.result()
                youtube_url = getattr(result, "youtube_url", None)
                result_status = getattr(result, "status", None)
                if result_status == "ready_to_upload":
                    mapped_status = PipelineStatus.ready_to_upload
            except Exception:
                pass

        return PipelineStatusResponse(
            workflow_id=workflow_id,
            status=mapped_status,
            cost_so_far_usd=cost_so_far if cost_so_far > 0 else None,
            youtube_url=youtube_url,
            started_at=started_at,
            completed_at=completed_at,
        )

    except RPCError as exc:
        return PipelineStatusResponse(
            workflow_id=workflow_id,
            status=PipelineStatus.unknown,
            error=str(exc),
        )
    except Exception as exc:
        return PipelineStatusResponse(
            workflow_id=workflow_id,
            status=PipelineStatus.unknown,
            error=str(exc),
        )


@router.get("/cost/{workflow_id}", response_model=CostDetailResponse)
async def get_pipeline_cost(
    workflow_id: str,
    request: Request,
) -> CostDetailResponse:
    """Return the full cost breakdown for a pipeline run.

    Reads all CostEntry records matching workflow_id from CostTracker.

    Args:
        workflow_id: Temporal workflow ID.
        request: FastAPI request (for temporal_client — unused but consistent).

    Returns:
        CostDetailResponse with total and per-step breakdown.
    """
    entries = _cost_tracker.get_run_breakdown(workflow_id)

    # Derive channel_id from first entry (if available)
    channel_id = entries[0].channel_id if entries else "unknown"

    total = sum(e.amount_usd for e in entries)
    breakdown = [
        CostLineItem(
            service=e.service,
            step=e.step,
            amount_usd=e.amount_usd,
            resolution=e.resolution,
        )
        for e in entries
    ]

    return CostDetailResponse(
        workflow_id=workflow_id,
        channel_id=channel_id,
        total_cost_usd=total,
        breakdown=breakdown,
    )


@router.post("/{workflow_id}/approve")
async def approve_pipeline(
    workflow_id: str,
    body: ApproveRequest,
    request: Request,
) -> dict:
    """Approve or reject an assembled video via the quality gate.

    Sends a Temporal signal to the waiting ContentPipelineWorkflow.
    When approved=True the workflow continues to YouTube upload.
    When approved=False the workflow returns status='rejected'.

    Args:
        workflow_id: Temporal workflow ID.
        body: ApproveRequest with approved bool and optional reason.
        request: FastAPI request (for temporal_client from app.state).

    Returns:
        Dict with signalled=True, workflow_id, and approved flag.
    """
    client = request.app.state.temporal_client
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(
        "approve_video",
        ApprovalSignal(approved=body.approved, reason=body.reason),
    )
    return {"signalled": True, "workflow_id": workflow_id, "approved": body.approved}


@router.get("/{workflow_id}/download")
async def download_video(workflow_id: str) -> FileResponse:
    """Download the assembled video file for manual YouTube upload.

    Video is expected at: data/pipeline/{workflow_id}/final/output.mp4

    Args:
        workflow_id: Temporal workflow ID.

    Returns:
        FileResponse with Content-Disposition attachment header.

    Raises:
        HTTPException 404: If the video file does not exist yet.
    """
    video_path = pathlib.Path("data/pipeline") / workflow_id / "final" / "output.mp4"
    if not video_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Video not found for workflow: {workflow_id}",
        )
    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename=f"{workflow_id}.mp4",
        headers={"Content-Disposition": f'attachment; filename="{workflow_id}.mp4"'},
    )


@router.get("/{workflow_id}/thumbnail")
async def download_thumbnail(workflow_id: str) -> FileResponse:
    """Download the thumbnail image for manual YouTube upload.

    Thumbnail is expected at: data/pipeline/{workflow_id}/thumbnails/thumbnail.jpg

    Args:
        workflow_id: Temporal workflow ID.

    Returns:
        FileResponse with Content-Disposition attachment header.

    Raises:
        HTTPException 404: If the thumbnail file does not exist yet.
    """
    thumb_path = pathlib.Path("data/pipeline") / workflow_id / "thumbnails" / "thumbnail.jpg"
    if not thumb_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Thumbnail not found for workflow: {workflow_id}",
        )
    return FileResponse(
        path=str(thumb_path),
        media_type="image/jpeg",
        filename=f"{workflow_id}_thumbnail.jpg",
        headers={"Content-Disposition": f'attachment; filename="{workflow_id}_thumbnail.jpg"'},
    )


@router.get("/{workflow_id}/video")
async def get_pipeline_video(workflow_id: str) -> FileResponse:
    """Serve the assembled video file for operator preview.

    Video is expected at: data/pipeline/{workflow_id}/final/output.mp4

    Args:
        workflow_id: Temporal workflow ID.

    Returns:
        FileResponse streaming the assembled MP4.

    Raises:
        HTTPException 404: If the video file does not exist yet.
    """
    video_path = pathlib.Path("data/pipeline") / workflow_id / "final" / "output.mp4"
    if not video_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Video not found for workflow: {workflow_id}",
        )
    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename=f"{workflow_id}.mp4",
    )


@router.get("/{workflow_id}/artifacts")
async def get_pipeline_artifacts(workflow_id: str) -> dict:
    """Return available pipeline artifacts (script, scene images, audio files).

    Scans the pipeline directory for generated files and returns their paths.
    """
    import json

    base = pathlib.Path("data/pipeline") / workflow_id
    if not base.exists():
        raise HTTPException(status_code=404, detail=f"Pipeline directory not found: {workflow_id}")

    artifacts: dict = {"workflow_id": workflow_id, "script": None, "scenes": [], "audio": [], "video_clips": []}

    # Script
    script_path = base / "script.json"
    if script_path.exists():
        try:
            artifacts["script"] = json.loads(script_path.read_text(encoding="utf-8"))
        except Exception:
            artifacts["script"] = None

    # Scene images
    images_dir = base / "images"
    if images_dir.exists():
        artifacts["scenes"] = sorted([
            {"filename": f.name, "url": f"/api/pipeline/{workflow_id}/scene/{f.name}"}
            for f in images_dir.iterdir() if f.suffix in (".jpg", ".png", ".webp")
        ], key=lambda x: x["filename"])

    # TTS audio
    audio_dir = base / "audio"
    if audio_dir.exists():
        artifacts["audio"] = sorted([
            {"filename": f.name, "url": f"/api/pipeline/{workflow_id}/audio/{f.name}"}
            for f in audio_dir.iterdir() if f.suffix in (".wav", ".mp3")
        ], key=lambda x: x["filename"])

    # Video clips
    clips_dir = base / "videos"
    if clips_dir.exists():
        artifacts["video_clips"] = sorted([
            {"filename": f.name, "url": f"/api/pipeline/{workflow_id}/clip/{f.name}"}
            for f in clips_dir.iterdir() if f.suffix in (".mp4", ".webm")
        ], key=lambda x: x["filename"])

    return artifacts


@router.get("/{workflow_id}/scene/{filename}")
async def get_scene_image(workflow_id: str, filename: str) -> FileResponse:
    """Serve a scene image file."""
    img_path = pathlib.Path("data/pipeline") / workflow_id / "images" / filename
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Scene image not found")
    media_type = "image/jpeg" if img_path.suffix == ".jpg" else "image/png"
    return FileResponse(path=str(img_path), media_type=media_type)


@router.delete("/{workflow_id}")
async def cancel_pipeline(
    workflow_id: str,
    request: Request,
) -> dict:
    """Cancel an in-flight pipeline workflow.

    Sends a cancellation request to Temporal. The workflow will receive
    a CancelledException on its next activity boundary.

    Args:
        workflow_id: Temporal workflow ID to cancel.
        request: FastAPI request (for temporal_client from app.state).

    Returns:
        Dict with cancelled=True and workflow_id.
    """
    client = request.app.state.temporal_client
    handle = client.get_workflow_handle(workflow_id)
    await handle.cancel()
    return {"cancelled": True, "workflow_id": workflow_id}
