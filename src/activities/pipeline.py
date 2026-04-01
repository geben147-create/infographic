"""Pipeline directory management activities (FILE-01, per D-13).

Creates and manages the artifact directory tree for each pipeline run.
Full implementation provided by Plan 01-02.
"""
from pathlib import Path

from pydantic import BaseModel
from temporalio import activity


class SetupDirsInput(BaseModel):
    workflow_run_id: str
    base_path: str = "data/pipeline"


class SetupDirsOutput(BaseModel):
    base_path: str
    created: bool
    subdirs: list[str]


PIPELINE_SUBDIRS = ["scripts", "images", "audio", "video", "thumbnails", "final"]


@activity.defn
async def setup_pipeline_dirs(params: SetupDirsInput) -> SetupDirsOutput:
    """Create artifact directory tree for a pipeline run (FILE-01)."""
    base = Path(params.base_path) / params.workflow_run_id
    for subdir in PIPELINE_SUBDIRS:
        (base / subdir).mkdir(parents=True, exist_ok=True)
    return SetupDirsOutput(
        base_path=str(base),
        created=True,
        subdirs=PIPELINE_SUBDIRS,
    )
