import uuid

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/sync")


class SyncTriggerResponse(BaseModel):
    workflow_id: str
    status: str


class SyncStatusResponse(BaseModel):
    workflow_id: str
    status: str
    result: str | None = None


@router.post("/sheets", response_model=SyncTriggerResponse)
async def trigger_sync(request: Request) -> SyncTriggerResponse:
    """Trigger Sheets -> SQLite sync via Temporal workflow (per D-09).

    Starts a Temporal workflow on gpu-queue (PipelineValidationWorkflow
    hosts the workflow definition on gpu-queue per RESEARCH.md Open Question 3).
    Returns workflow_id for polling status.

    Note: In Phase 2, this will be replaced with a dedicated SheetsSyncWorkflow.
    The purpose here is to prove the FastAPI -> Temporal -> Worker flow works.
    """
    from src.workflows.pipeline_validation import (
        PipelineValidationWorkflow,
        ValidationParams,
    )

    client = request.app.state.temporal_client
    workflow_id = f"sheets-sync-{uuid.uuid4().hex[:8]}"

    await client.start_workflow(
        PipelineValidationWorkflow.run,
        ValidationParams(workflow_run_id=workflow_id),
        id=workflow_id,
        task_queue="gpu-queue",
    )

    return SyncTriggerResponse(workflow_id=workflow_id, status="started")


@router.get("/status/{workflow_id}", response_model=SyncStatusResponse)
async def get_sync_status(
    workflow_id: str, request: Request
) -> SyncStatusResponse:
    """Poll sync workflow status (per D-09)."""
    client = request.app.state.temporal_client
    handle = client.get_workflow_handle(workflow_id)
    try:
        desc = await handle.describe()
        status = str(desc.status)
        result = None
        if desc.status and desc.status.name == "COMPLETED":
            result = str(await handle.result())
        return SyncStatusResponse(
            workflow_id=workflow_id, status=status, result=result
        )
    except Exception as e:
        return SyncStatusResponse(
            workflow_id=workflow_id, status="unknown", result=str(e)
        )
