"""
Temporal activity: assemble_video

Concatenates per-scene video clips (already merged with their audio tracks)
into a single final MP4 using the FFmpeg concat demuxer.

Encoding strategy:
- Primary:  h264_nvenc  (NVENC hardware on RTX 4070)
- Fallback: libx264     (software, triggered when stderr contains encoder/nvenc)

Output: {run_dir}/final/final_video.mp4
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import ffmpeg
from ffmpeg._run import Error as FfmpegError
from pydantic import BaseModel
from temporalio import activity
from temporalio.exceptions import ApplicationError


class AssemblyInput(BaseModel):
    """Input parameters for the assemble_video activity."""

    scene_count: int
    run_dir: str
    transition_duration_seconds: float = 0.5


class AssemblyOutput(BaseModel):
    """Output of the assemble_video activity."""

    file_path: str
    duration_seconds: float
    file_size_bytes: int


# ---------------------------------------------------------------------------
# Helpers (module-level so tests can patch them directly)
# ---------------------------------------------------------------------------


def build_concat_file(run_dir: str, scene_count: int) -> str:
    """Write an FFmpeg concat demuxer text file listing all merged scene clips.

    Each line follows the format::

        file 'video/scene_NN_merged.mp4'

    Args:
        run_dir: Root directory of this pipeline run.
        scene_count: Number of scenes (0-indexed from 0 to scene_count-1).

    Returns:
        Absolute path to the written concat_list.txt file.
    """
    concat_path = Path(run_dir) / "concat_list.txt"
    lines: list[str] = []
    for i in range(scene_count):
        clip_rel = f"video/scene_{i:02d}_merged.mp4"
        lines.append(f"file '{clip_rel}'")

    concat_path.write_text("\n".join(lines), encoding="utf-8")
    return str(concat_path)


def merge_audio_video(video_path: str, audio_path: str, output_path: str) -> None:
    """Merge a silent video clip with its corresponding audio track.

    Uses ``vcodec=copy`` to avoid re-encoding the video stream.

    Args:
        video_path: Path to the scene video MP4 (no audio).
        audio_path: Path to the scene WAV audio file.
        output_path: Destination MP4 path.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    video_in = ffmpeg.input(video_path)
    audio_in = ffmpeg.input(audio_path)
    (
        ffmpeg.output(video_in, audio_in, output_path, vcodec="copy", acodec="aac")
        .overwrite_output()
        .run(quiet=True)
    )


def _get_duration(file_path: str) -> float:
    """Return the duration of a media file in seconds using ffprobe.

    Falls back to 0.0 if the probe fails (e.g., stub file in tests).
    """
    try:
        probe = ffmpeg.probe(file_path)
        return float(probe["format"]["duration"])
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Temporal activity
# ---------------------------------------------------------------------------


@activity.defn
async def assemble_video(params: AssemblyInput) -> AssemblyOutput:
    """Concatenate scene clips + audio into a final MP4.

    Steps:
    1. Verify all per-scene video and audio files are present.
    2. Merge each scene's video and audio into a ``*_merged.mp4``.
    3. Write a concat demuxer file listing all merged clips.
    4. Run FFmpeg concat → output MP4 with h264_nvenc (libx264 fallback).
    5. Return output path, duration, and file size.

    Args:
        params: AssemblyInput specifying scene_count and run directory.

    Returns:
        AssemblyOutput with file_path, duration_seconds, file_size_bytes.

    Raises:
        ApplicationError: If any expected scene file is missing.
    """
    run = Path(params.run_dir)
    video_dir = run / "video"
    audio_dir = run / "audio"
    final_dir = run / "final"
    final_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Verify scene files ────────────────────────────────────────────────
    missing: list[str] = []
    for i in range(params.scene_count):
        vp = video_dir / f"scene_{i:02d}.mp4"
        ap = audio_dir / f"scene_{i:02d}.wav"
        if not vp.exists():
            missing.append(str(vp))
        if not ap.exists():
            missing.append(str(ap))

    if missing:
        raise ApplicationError(
            f"Missing scene files for assembly: {missing}",
            non_retryable=True,
        )

    # ── 2. Merge video + audio per scene (blocking I/O → thread) ────────────
    def _merge_all() -> None:
        for i in range(params.scene_count):
            video_path = str(video_dir / f"scene_{i:02d}.mp4")
            audio_path = str(audio_dir / f"scene_{i:02d}.wav")
            merged_path = str(video_dir / f"scene_{i:02d}_merged.mp4")
            merge_audio_video(video_path, audio_path, merged_path)

    await asyncio.to_thread(_merge_all)

    # ── 3. Build concat demuxer file ─────────────────────────────────────────
    concat_file = build_concat_file(params.run_dir, params.scene_count)

    # ── 4. Concatenate all merged clips → final MP4 ──────────────────────────
    output_path = str(final_dir / "final_video.mp4")

    def _concat(vcodec: str) -> None:
        (
            ffmpeg.input(concat_file, format="concat", safe=0)
            .output(output_path, vcodec=vcodec, acodec="copy", pix_fmt="yuv420p")
            .overwrite_output()
            .run(quiet=True)
        )

    def _run_concat() -> None:
        try:
            _concat("h264_nvenc")
        except FfmpegError as exc:
            stderr = (exc.stderr or b"").lower()
            if b"encoder" in stderr or b"nvenc" in stderr:
                _concat("libx264")
            else:
                raise

    await asyncio.to_thread(_run_concat)

    # ── 5. Collect output metadata ───────────────────────────────────────────
    output_file = Path(output_path)
    file_size = output_file.stat().st_size if output_file.exists() else 0
    duration = await asyncio.to_thread(_get_duration, output_path)

    return AssemblyOutput(
        file_path=output_path,
        duration_seconds=duration,
        file_size_bytes=file_size,
    )
