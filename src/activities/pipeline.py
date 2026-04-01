from pathlib import Path

from pydantic import BaseModel
from temporalio import activity

PIPELINE_SUBDIRS = ["scripts", "images", "audio", "video", "thumbnails", "final"]


class SetupDirsInput(BaseModel):
    workflow_run_id: str
    base_path: str = "data/pipeline"


class SetupDirsOutput(BaseModel):
    base_path: str
    created: bool
    subdirs: list[str]


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
