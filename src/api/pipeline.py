"""
Pipeline API endpoints.

Exposes the ContentPipelineWorkflow via FastAPI:
  POST   /api/pipeline/trigger             — start a new pipeline run
  GET    /api/pipeline/status/{workflow_id} — poll current step + cost
  GET    /api/pipeline/cost/{workflow_id}   — full cost breakdown
  DELETE /api/pipeline/{workflow_id}        — cancel in-flight run
"""
from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Request
from temporalio.service import RPCError

from src.models.channel_config import load_channel_config
from src.schemas.pipeline import (
    CostDetailResponse,
    CostLineItem,
    PipelineStatus,
    PipelineStatusResponse,
    PipelineTriggerRequest,
    PipelineTriggerResponse,
)
from src.services.cost_tracker import CostTracker
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

        # Retrieve youtube_url from result if completed
        youtube_url: str | None = None
        if mapped_status == PipelineStatus.completed:
            try:
                result = await handle.result()
                youtube_url = getattr(result, "youtube_url", None)
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
