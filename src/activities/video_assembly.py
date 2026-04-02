"""
Video assembly Temporal activity — FFmpeg-based final video composition.

This file is a forward-declaration stub created by plan 02-06 to unblock
workflow import. The full implementation is provided by plan 02-05.

If this stub is still present after 02-05 completes, that plan's
implementation should have replaced it.
"""
from __future__ import annotations

from pydantic import BaseModel
from temporalio import activity


class AssemblyInput(BaseModel):
    """Input parameters for the assemble_video activity."""

    scene_count: int
    run_dir: str


class AssemblyOutput(BaseModel):
    """Output from the assemble_video activity."""

    file_path: str
    duration_seconds: float
    file_size_bytes: int


@activity.defn
async def assemble_video(params: AssemblyInput) -> AssemblyOutput:
    """Assemble scene clips into a final video using FFmpeg.

    NOTE: This is a placeholder stub. The full implementation is in plan 02-05.
    """
    raise NotImplementedError(
        "assemble_video is not yet implemented. "
        "This stub was created by plan 02-06 to unblock workflow imports. "
        "The full FFmpeg implementation belongs in plan 02-05."
    )
