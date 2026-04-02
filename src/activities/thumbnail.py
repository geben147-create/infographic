"""
Thumbnail generation Temporal activity — SDXL + Pillow text overlay.

This file is a forward-declaration stub created by plan 02-06 to unblock
workflow import. The full implementation is provided by plan 02-05.

If this stub is still present after 02-05 completes, that plan's
implementation should have replaced it.
"""
from __future__ import annotations

from pydantic import BaseModel
from temporalio import activity


class ThumbnailInput(BaseModel):
    """Input parameters for the generate_thumbnail activity."""

    title: str
    channel_id: str
    run_dir: str


class ThumbnailOutput(BaseModel):
    """Output from the generate_thumbnail activity."""

    file_path: str
    file_size_bytes: int


@activity.defn
async def generate_thumbnail(params: ThumbnailInput) -> ThumbnailOutput:
    """Generate a YouTube thumbnail using SDXL + Pillow text overlay.

    NOTE: This is a placeholder stub. The full implementation is in plan 02-05.
    """
    raise NotImplementedError(
        "generate_thumbnail is not yet implemented. "
        "This stub was created by plan 02-06 to unblock workflow imports. "
        "The full ComfyUI/Pillow implementation belongs in plan 02-05."
    )
