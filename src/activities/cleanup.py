"""Cleanup activity for intermediate pipeline files (FILE-02, per D-14).

Deletes intermediate artifacts after pipeline completion.
Keeps final/ directory. Never touches pipeline.db or cost_log.json.
Full implementation provided by Plan 01-02.
"""
import shutil
from pathlib import Path

from pydantic import BaseModel
from temporalio import activity


class CleanupInput(BaseModel):
    workflow_run_id: str
    base_path: str = "data/pipeline"


class CleanupOutput(BaseModel):
    deleted_dirs: list[str]
    kept_dirs: list[str]
    success: bool


DIRS_TO_DELETE = ["scripts", "images", "audio", "video", "thumbnails"]
DIRS_TO_KEEP = ["final"]


@activity.defn
async def cleanup_intermediate_files(params: CleanupInput) -> CleanupOutput:
    """Delete intermediate files after pipeline completion (FILE-02).

    Keeps final/ directory. Never touches pipeline.db or cost_log.json.
    """
    base = Path(params.base_path) / params.workflow_run_id
    deleted = []
    kept = []

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
