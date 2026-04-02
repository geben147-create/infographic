"""
Temporal activity: generate_scene_video

Produces an MP4 video clip for one scene using either:
- FalVideoProvider (fal.ai image-to-video) when vgen_enabled=True AND fal_key is set
- Ken Burns zoompan effect (FFmpeg) as fallback — zero API cost

Cost is tracked for both paths via CostTracker.
"""
from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

import ffmpeg
from pydantic import BaseModel
from temporalio import activity

from src.config import settings
from src.models.channel_config import load_channel_config
from src.models.provider import ModelSpec
from src.services.cost_tracker import CostEntry, CostTracker
from src.services.fal_client import FalVideoProvider


class VideoGenInput(BaseModel):
    """Input parameters for the generate_scene_video activity."""

    scene_index: int
    channel_id: str
    run_dir: str
    image_path: str
    prompt: str = ""
    duration_seconds: float = 5.0


class VideoGenOutput(BaseModel):
    """Output of the generate_scene_video activity."""

    file_path: str
    cost_usd: float
    method: str  # "ai_video" or "ken_burns"


def ken_burns_clip(
    image_path: str,
    output_path: str,
    duration_seconds: float = 5.0,
) -> None:
    """Produce a Ken Burns (zoompan) MP4 from a still image.

    Uses h264_nvenc (NVENC hardware encoding) as the primary codec.
    Falls back to libx264 (software) if the NVENC encoder is not available.

    Args:
        image_path: Path to the source PNG/JPEG image.
        output_path: Destination MP4 path (created if parent exists).
        duration_seconds: Duration of the output clip in seconds.

    Raises:
        ffmpeg.Error: If both NVENC and libx264 attempts fail.
    """
    frame_rate = 25
    total_frames = int(duration_seconds * frame_rate)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    def _build_and_run(vcodec: str) -> None:
        (
            ffmpeg
            .input(image_path, loop=1, t=duration_seconds)
            .filter(
                "zoompan",
                z="min(zoom+0.0015,1.5)",
                d=total_frames,
                x="iw/2-(iw/zoom/2)",
                y="ih/2-(ih/zoom/2)",
                s="1920x1080",
            )
            .output(
                output_path,
                vcodec=vcodec,
                r=frame_rate,
                pix_fmt="yuv420p",
                t=duration_seconds,
            )
            .overwrite_output()
            .run(quiet=True)
        )

    try:
        _build_and_run("h264_nvenc")
    except ffmpeg.Error as exc:
        stderr = exc.stderr or b""
        if b"encoder" in stderr.lower() or b"nvenc" in stderr.lower():
            # NVENC not available — retry with software encoder
            _build_and_run("libx264")
        else:
            raise


def _extract_workflow_id(run_dir: str) -> str:
    """Derive a workflow_id from the run directory name."""
    return Path(run_dir).name


@activity.defn
async def generate_scene_video(params: VideoGenInput) -> VideoGenOutput:
    """Generate a video clip for one pipeline scene.

    Selects fal.ai AI video generation when enabled and a key is configured,
    otherwise falls back to Ken Burns zoompan via FFmpeg.

    Args:
        params: Scene parameters including image path, prompt, and run dir.

    Returns:
        VideoGenOutput with file path, cost, and method used.
    """
    config = load_channel_config(
        channel_id=params.channel_id,
        config_dir=settings.channel_configs_dir,
    )

    output_dir = Path(params.run_dir) / "video"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(output_dir / f"scene_{params.scene_index:02d}.mp4")

    tracker = CostTracker(log_path=settings.cost_log_path)
    workflow_id = _extract_workflow_id(params.run_dir)

    if config.vgen_enabled and settings.fal_key:
        # ── AI video path (fal.ai) ────────────────────────────────────────
        spec = ModelSpec.parse(config.video_model)
        provider = FalVideoProvider(model=spec.model)

        video_tmp_path, cost_usd = await provider.generate(
            image_path=params.image_path,
            prompt=params.prompt,
            duration_seconds=params.duration_seconds,
        )

        # Move downloaded temp file to canonical output path
        shutil.move(video_tmp_path, output_path)

        tracker.log(
            CostEntry(
                workflow_id=workflow_id,
                channel_id=params.channel_id,
                service="fal.ai",
                step=f"video_gen_scene_{params.scene_index:02d}",
                amount_usd=cost_usd,
                resolution="480p",
                timestamp=_now_iso(),
            )
        )

        return VideoGenOutput(
            file_path=output_path,
            cost_usd=cost_usd,
            method="ai_video",
        )

    else:
        # ── Ken Burns fallback (no cost) ──────────────────────────────────
        print(
            f"[video_gen] Video gen disabled (vgen_enabled={config.vgen_enabled}, "
            f"FAL_KEY={'set' if settings.fal_key else 'not set'}). "
            "Using Ken Burns fallback."
        )

        await asyncio.to_thread(
            ken_burns_clip,
            params.image_path,
            output_path,
            params.duration_seconds,
        )

        tracker.log(
            CostEntry(
                workflow_id=workflow_id,
                channel_id=params.channel_id,
                service="none",
                step=f"video_gen_scene_{params.scene_index:02d}",
                amount_usd=0.0,
                resolution=None,
                timestamp=_now_iso(),
            )
        )

        return VideoGenOutput(
            file_path=output_path,
            cost_usd=0.0,
            method="ken_burns",
        )


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
