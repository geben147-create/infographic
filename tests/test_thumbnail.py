"""
Tests for src/activities/thumbnail.py

TDD: tests written BEFORE implementation (RED phase).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image
from temporalio.testing import ActivityEnvironment

from src.activities.thumbnail import (
    ThumbnailInput,
    ThumbnailOutput,
    generate_thumbnail,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def run_dir(tmp_path: Path) -> Path:
    """Create a minimal run directory with a scene image."""
    images_dir = tmp_path / "images"
    images_dir.mkdir(parents=True)

    # Create a small 100x100 solid color PNG (green)
    img = Image.new("RGB", (100, 100), color=(0, 200, 100))
    img.save(images_dir / "scene_00.png")

    (tmp_path / "thumbnails").mkdir()
    return tmp_path


@pytest.fixture()
def run_dir_no_image(tmp_path: Path) -> Path:
    """Run directory without any scene image (tests fallback background)."""
    (tmp_path / "images").mkdir(parents=True)
    (tmp_path / "thumbnails").mkdir()
    return tmp_path


# ---------------------------------------------------------------------------
# ThumbnailInput / ThumbnailOutput models
# ---------------------------------------------------------------------------


def test_thumbnail_input_fields() -> None:
    """ThumbnailInput requires title, channel_id, run_dir."""
    params = ThumbnailInput(
        title="한국어 제목입니다",
        channel_id="test_channel",
        run_dir="/tmp/run",
    )
    assert params.title == "한국어 제목입니다"
    assert params.channel_id == "test_channel"


def test_thumbnail_output_fields() -> None:
    """ThumbnailOutput carries file_path and file_size_bytes."""
    out = ThumbnailOutput(file_path="/out/thumb.jpg", file_size_bytes=512)
    assert out.file_path.endswith(".jpg")
    assert out.file_size_bytes == 512


# ---------------------------------------------------------------------------
# Resize to 1280x720
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thumbnail_resize_to_1280x720(run_dir: Path) -> None:
    """Activity produces a 1280x720 image regardless of source size."""
    env = ActivityEnvironment()
    params = ThumbnailInput(
        title="테스트 제목",
        channel_id="ch01",
        run_dir=str(run_dir),
    )

    with patch("src.activities.thumbnail.settings") as mock_settings:
        mock_settings.font_path = "/nonexistent/font.ttf"  # triggers fallback
        result = await env.run(generate_thumbnail, params)

    out_img = Image.open(result.file_path)
    assert out_img.size == (1280, 720)


# ---------------------------------------------------------------------------
# Output path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thumbnail_output_path(run_dir: Path) -> None:
    """Thumbnail is saved as JPEG under run_dir/thumbnails/thumbnail.jpg."""
    env = ActivityEnvironment()
    params = ThumbnailInput(
        title="경로 확인",
        channel_id="ch01",
        run_dir=str(run_dir),
    )

    with patch("src.activities.thumbnail.settings") as mock_settings:
        mock_settings.font_path = "/nonexistent/font.ttf"
        result = await env.run(generate_thumbnail, params)

    expected = str(run_dir / "thumbnails" / "thumbnail.jpg")
    assert result.file_path == expected
    assert Path(result.file_path).exists()


# ---------------------------------------------------------------------------
# File size under 2MB
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thumbnail_under_2mb(run_dir: Path) -> None:
    """Output JPEG must be under 2MB (YouTube limit)."""
    env = ActivityEnvironment()
    params = ThumbnailInput(
        title="사이즈 테스트",
        channel_id="ch01",
        run_dir=str(run_dir),
    )

    with patch("src.activities.thumbnail.settings") as mock_settings:
        mock_settings.font_path = "/nonexistent/font.ttf"
        result = await env.run(generate_thumbnail, params)

    assert result.file_size_bytes < 2 * 1024 * 1024


# ---------------------------------------------------------------------------
# Fallback to solid background when scene_00.png missing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thumbnail_fallback_background(run_dir_no_image: Path) -> None:
    """When scene_00.png is absent, a solid color background is used."""
    env = ActivityEnvironment()
    params = ThumbnailInput(
        title="폴백 배경",
        channel_id="ch01",
        run_dir=str(run_dir_no_image),
    )

    with patch("src.activities.thumbnail.settings") as mock_settings:
        mock_settings.font_path = "/nonexistent/font.ttf"
        result = await env.run(generate_thumbnail, params)

    assert Path(result.file_path).exists()
    out_img = Image.open(result.file_path)
    assert out_img.size == (1280, 720)


# ---------------------------------------------------------------------------
# Korean text overlay (shadow + main text — verify image changed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thumbnail_text_overlay_changes_image(run_dir: Path) -> None:
    """Text overlay produces a result different from a plain resize."""
    # Plain resized image
    src_img = Image.open(run_dir / "images" / "scene_00.png")
    plain = src_img.resize((1280, 720))
    plain_bytes = plain.tobytes()

    env = ActivityEnvironment()
    params = ThumbnailInput(
        title="오버레이 테스트 한국어",
        channel_id="ch01",
        run_dir=str(run_dir),
    )

    with patch("src.activities.thumbnail.settings") as mock_settings:
        mock_settings.font_path = "/nonexistent/font.ttf"
        result = await env.run(generate_thumbnail, params)

    out_img = Image.open(result.file_path).convert("RGB")
    # Open original and resize to compare
    out_bytes = out_img.tobytes()
    # They must differ (text was drawn on top)
    assert out_bytes != plain_bytes


# ---------------------------------------------------------------------------
# Font fallback when custom font missing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thumbnail_default_font_fallback(run_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
    """When font_path does not exist, default font is used and a warning is logged."""
    import logging

    env = ActivityEnvironment()
    params = ThumbnailInput(
        title="폰트 폴백 테스트",
        channel_id="ch01",
        run_dir=str(run_dir),
    )

    with patch("src.activities.thumbnail.settings") as mock_settings:
        mock_settings.font_path = "/absolutely/nonexistent/font.ttf"
        with caplog.at_level(logging.WARNING, logger="src.activities.thumbnail"):
            result = await env.run(generate_thumbnail, params)

    assert Path(result.file_path).exists()
    assert any("font" in rec.message.lower() for rec in caplog.records)
