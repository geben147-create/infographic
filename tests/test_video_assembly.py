"""
Tests for src/activities/video_assembly.py

TDD: tests written BEFORE implementation (RED phase).
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from temporalio.testing import ActivityEnvironment

from src.activities.video_assembly import (
    AssemblyInput,
    AssemblyOutput,
    assemble_video,
    build_concat_file,
    merge_audio_video,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def run_dir(tmp_path: Path) -> Path:
    """Create a minimal run directory with scene video + audio stubs."""
    video_dir = tmp_path / "video"
    audio_dir = tmp_path / "audio"
    final_dir = tmp_path / "final"

    for d in (video_dir, audio_dir, final_dir):
        d.mkdir(parents=True)

    for i in range(3):
        (video_dir / f"scene_{i:02d}.mp4").write_bytes(b"stub")
        (audio_dir / f"scene_{i:02d}.wav").write_bytes(b"stub")

    return tmp_path


# ---------------------------------------------------------------------------
# build_concat_file
# ---------------------------------------------------------------------------


def test_build_concat_file_creates_file(tmp_path: Path) -> None:
    """build_concat_file writes a valid concat demuxer text file."""
    concat_path = build_concat_file(str(tmp_path), scene_count=3)

    assert Path(concat_path).exists()
    content = Path(concat_path).read_text()
    assert "file" in content


def test_build_concat_file_correct_format(tmp_path: Path) -> None:
    """Each line follows the FFmpeg concat demuxer format: file 'path'."""
    concat_path = build_concat_file(str(tmp_path), scene_count=3)
    lines = [l.strip() for l in Path(concat_path).read_text().splitlines() if l.strip()]

    # Expect 3 entries
    file_lines = [l for l in lines if l.startswith("file")]
    assert len(file_lines) == 3

    for i, line in enumerate(file_lines):
        expected_fragment = f"scene_{i:02d}_merged.mp4"
        assert expected_fragment in line, f"Line {line!r} missing {expected_fragment}"


def test_build_concat_file_zero_scenes(tmp_path: Path) -> None:
    """Zero scene count produces an empty concat file without error."""
    concat_path = build_concat_file(str(tmp_path), scene_count=0)
    content = Path(concat_path).read_text()
    file_lines = [l for l in content.splitlines() if l.strip().startswith("file")]
    assert file_lines == []


# ---------------------------------------------------------------------------
# merge_audio_video
# ---------------------------------------------------------------------------


def test_merge_audio_video_calls_ffmpeg(tmp_path: Path) -> None:
    """merge_audio_video constructs an ffmpeg command and calls run()."""
    out = str(tmp_path / "merged.mp4")

    mock_run = MagicMock()
    mock_output = MagicMock()
    mock_output.overwrite_output.return_value.run = mock_run
    mock_output.overwrite_output.return_value = MagicMock(run=mock_run)

    with patch("src.activities.video_assembly.ffmpeg") as mock_ffmpeg:
        # Chain: ffmpeg.output(video, audio, ...).overwrite_output().run()
        mock_ffmpeg.input.return_value = MagicMock()
        mock_ffmpeg.output.return_value = mock_output

        merge_audio_video("video.mp4", "audio.wav", out)

    mock_ffmpeg.output.assert_called_once()
    # The call should include output path
    call_args = mock_ffmpeg.output.call_args
    assert out in call_args.args or out in call_args.kwargs.values()


# ---------------------------------------------------------------------------
# assemble_video — missing scene files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assemble_video_raises_on_missing_files(tmp_path: Path) -> None:
    """ApplicationError raised when scene files are missing."""
    from temporalio.exceptions import ApplicationError

    env = ActivityEnvironment()
    params = AssemblyInput(
        scene_count=3,
        run_dir=str(tmp_path),  # no scene files created
        transition_duration_seconds=0.5,
    )
    with pytest.raises(ApplicationError, match="Missing scene files"):
        await env.run(assemble_video, params)


# ---------------------------------------------------------------------------
# assemble_video — NVENC → libx264 fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assemble_video_nvenc_fallback(run_dir: Path) -> None:
    """When NVENC fails with encoder-related stderr, libx264 is used as fallback."""
    import ffmpeg as ffmpeg_lib

    call_log: list[str] = []

    def fake_run(quiet: bool = False) -> None:
        vcodec = fake_run._vcodec  # type: ignore[attr-defined]
        if vcodec == "h264_nvenc":
            raise ffmpeg_lib.Error(
                "ffmpeg",
                stdout=b"",
                stderr=b"encoder nvenc not available",
            )
        call_log.append(vcodec)

    def make_stream(vcodec: str) -> MagicMock:
        s = MagicMock()
        fake_run._vcodec = vcodec  # type: ignore[attr-defined]
        s.run = fake_run
        return s

    output_mock = MagicMock()
    output_mock.overwrite_output.return_value = MagicMock(run=MagicMock())

    with (
        patch("src.activities.video_assembly.merge_audio_video"),
        patch("src.activities.video_assembly.build_concat_file") as mock_concat,
        patch("src.activities.video_assembly.ffmpeg") as mock_ffmpeg,
        patch("src.activities.video_assembly._get_duration", return_value=15.0),
    ):
        mock_concat.return_value = str(run_dir / "concat_list.txt")
        (run_dir / "concat_list.txt").touch()

        # Simulate NVENC failure then libx264 success
        nvenc_stream = MagicMock()
        libx264_stream = MagicMock()

        call_log_codecs: list[str] = []

        def fake_output(*args: object, **kwargs: object) -> MagicMock:
            vcodec = kwargs.get("vcodec", "")
            call_log_codecs.append(str(vcodec))
            if vcodec == "h264_nvenc":
                fail_stream = MagicMock()
                fail_stream.overwrite_output.return_value.run.side_effect = (
                    ffmpeg_lib.Error("ffmpeg", b"", b"encoder nvenc not available")
                )
                return fail_stream
            else:
                ok_stream = MagicMock()
                ok_stream.overwrite_output.return_value.run = MagicMock()
                return ok_stream

        mock_ffmpeg.input.return_value = MagicMock()
        mock_ffmpeg.input.return_value.output = fake_output

        # Create the merged files so the activity doesn't fail validation
        for i in range(3):
            merged = run_dir / "video" / f"scene_{i:02d}_merged.mp4"
            merged.write_bytes(b"stub")

        # Create final dir
        (run_dir / "final").mkdir(exist_ok=True)
        # Create a fake output file
        final_path = run_dir / "final" / "final_video.mp4"
        final_path.write_bytes(b"stub" * 100)

        env = ActivityEnvironment()
        params = AssemblyInput(
            scene_count=3,
            run_dir=str(run_dir),
            transition_duration_seconds=0.5,
        )
        result = await env.run(assemble_video, params)

    assert "libx264" in call_log_codecs
    assert "h264_nvenc" in call_log_codecs


# ---------------------------------------------------------------------------
# assemble_video — output path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assemble_video_output_path(run_dir: Path) -> None:
    """assemble_video returns AssemblyOutput with correct file_path."""
    import ffmpeg as ffmpeg_lib

    final_path = run_dir / "final" / "final_video.mp4"
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_bytes(b"stub" * 500)

    for i in range(3):
        merged = run_dir / "video" / f"scene_{i:02d}_merged.mp4"
        merged.write_bytes(b"stub")

    with (
        patch("src.activities.video_assembly.merge_audio_video"),
        patch("src.activities.video_assembly.build_concat_file") as mock_concat,
        patch("src.activities.video_assembly.ffmpeg") as mock_ffmpeg,
        patch("src.activities.video_assembly._get_duration", return_value=15.0),
    ):
        mock_concat.return_value = str(run_dir / "concat_list.txt")
        (run_dir / "concat_list.txt").touch()

        ok_stream = MagicMock()
        ok_stream.overwrite_output.return_value.run = MagicMock()
        mock_ffmpeg.input.return_value = MagicMock()
        mock_ffmpeg.input.return_value.output = MagicMock(return_value=ok_stream)

        env = ActivityEnvironment()
        params = AssemblyInput(
            scene_count=3,
            run_dir=str(run_dir),
            transition_duration_seconds=0.5,
        )
        result = await env.run(assemble_video, params)

    assert result.file_path.endswith("final/final_video.mp4") or result.file_path.endswith(
        "final\\final_video.mp4"
    )
    assert result.file_size_bytes > 0


# ---------------------------------------------------------------------------
# AssemblyInput model
# ---------------------------------------------------------------------------


def test_assembly_input_defaults() -> None:
    """AssemblyInput accepts required fields and has sensible defaults."""
    params = AssemblyInput(scene_count=5, run_dir="/tmp/run")
    assert params.transition_duration_seconds == 0.5


def test_assembly_output_fields() -> None:
    """AssemblyOutput carries file_path, duration_seconds, file_size_bytes."""
    out = AssemblyOutput(file_path="/out/final.mp4", duration_seconds=30.5, file_size_bytes=1024)
    assert out.file_path == "/out/final.mp4"
    assert out.duration_seconds == 30.5
    assert out.file_size_bytes == 1024
