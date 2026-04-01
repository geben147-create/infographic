import shutil
from pathlib import Path

from pydantic import BaseModel
from temporalio import activity

DIRS_TO_DELETE = ["scripts", "images", "audio", "video", "thumbnails"]
DIRS_TO_KEEP = ["final"]


class CleanupInput(BaseModel):
    workflow_run_id: str
    base_path: str = "data/pipeline"


class CleanupOutput(BaseModel):
    deleted_dirs: list[str]
    kept_dirs: list[str]
    success: bool


@activity.defn
async def cleanup_intermediate_files(params: CleanupInput) -> CleanupOutput:
    """Delete intermediate files after pipeline completion (FILE-02).

    Keeps final/ directory. Never touches pipeline.db or cost_log.json.
    """
    base = Path(params.base_path) / params.workflow_run_id
    deleted: list[str] = []
    kept: list[str] = []

    for dirname in DIRS_TO_DELETE:
        dir_path = base / dirname
        if dir_path.exists():
            shutil.rmtree(dir_path)
            deleted.append(dirname)

    for dirname in DIRS_TO_KEEP:
        dir_path = base / dirname
        if dir_path.exists():
            kept.append(dirname)

    return CleanupOutput(
        deleted_dirs=deleted,
        kept_dirs=kept,
        success=True,
    )
