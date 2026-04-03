"""
Temporal activity: save_pipeline_run_result

Writes the final PipelineResult back to the pipeline_runs SQLite table.
Called as the last step in ContentPipelineWorkflow so that the dashboard
and Pipelines page always reflect completed runs.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel
from temporalio import activity

from sqlmodel import Session

from src.services.db_service import engine, update_pipeline_run


class SaveRunResultInput(BaseModel):
    """Input for save_pipeline_run_result activity."""

    workflow_id: str
    status: str
    video_path: str
    thumbnail_path: str
    total_cost_usd: float
    scenes_count: int
    error_message: str = ""


@activity.defn
async def save_pipeline_run_result(params: SaveRunResultInput) -> None:
    """Update the pipeline_runs row for the given workflow_id.

    Called at the end of ContentPipelineWorkflow (success) and in the
    workflow's exception handler (failure).  Uses update_pipeline_run()
    so the row must already exist — it is created by the trigger endpoint.
    """
    updates: dict = {
        "status": params.status,
        "completed_at": datetime.now(timezone.utc),
        "video_path": params.video_path or None,
        "thumbnail_path": params.thumbnail_path or None,
        "total_cost_usd": params.total_cost_usd,
        "error_message": params.error_message or None,
    }

    with Session(engine) as session:
        update_pipeline_run(session, params.workflow_id, updates)
