"""
Temporal activity: generate_thumbnail

Generates a 1280x720 YouTube thumbnail from the first scene image with a
Korean text overlay (shadow + white text).

Layout:
- Source: {run_dir}/images/scene_00.png  (falls back to solid dark background)
- Text:   bottom-left area, shadow at (22, 582), main at (20, 580)
- Font:   settings.font_path (NotoSansKR-Bold) → Pillow default on FileNotFoundError
- Output: {run_dir}/thumbnails/thumbnail.jpg  quality=90, < 2MB

The Pillow operations are CPU-bound so they run via asyncio.to_thread().
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel
from temporalio import activity

from src.config import settings

logger = logging.getLogger(__name__)

_THUMB_WIDTH = 1280
_THUMB_HEIGHT = 720
_MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MB YouTube limit
_FALLBACK_BG_COLOR = (26, 26, 46)  # dark navy #1a1a2e
_FONT_SIZE = 72
_FALLBACK_FONT_SIZE = 40
_TEXT_X = 20
_TEXT_Y = 580
_SHADOW_OFFSET = 2


class ThumbnailInput(BaseModel):
    """Input parameters for the generate_thumbnail activity."""

    title: str
    channel_id: str
    run_dir: str


class ThumbnailOutput(BaseModel):
    """Output of the generate_thumbnail activity."""

    file_path: str
    file_size_bytes: int


# ---------------------------------------------------------------------------
# Synchronous worker (runs in thread)
# ---------------------------------------------------------------------------


def _load_font(font_path: str) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a TrueType font or fall back to Pillow's built-in default.

    Args:
        font_path: Filesystem path to a .ttf/.otf font file.

    Returns:
        An ImageFont object (FreeType or default).
    """
    try:
        return ImageFont.truetype(font_path, size=_FONT_SIZE)
    except (FileNotFoundError, OSError):
        logger.warning(
            "Font file not found at %r — using Pillow default font (size=%d)",
            font_path,
            _FALLBACK_FONT_SIZE,
        )
        return ImageFont.load_default(size=_FALLBACK_FONT_SIZE)


def _build_thumbnail(
    title: str,
    run_dir: str,
    font_path: str,
) -> tuple[str, int]:
    """Create the thumbnail image and return (output_path, file_size_bytes).

    This function is synchronous and designed to run inside a thread.

    Args:
        title: Korean video title for the text overlay.
        run_dir: Root pipeline run directory.
        font_path: Path to the TrueType font file.

    Returns:
        Tuple of (output_path, file_size_bytes).
    """
    run = Path(run_dir)
    scene_image = run / "images" / "scene_00.png"
    output_dir = run / "thumbnails"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(output_dir / "thumbnail.jpg")

    # ── Load / create background ─────────────────────────────────────────────
    if scene_image.exists():
        img = Image.open(scene_image).convert("RGB")
    else:
        img = Image.new("RGB", (_THUMB_WIDTH, _THUMB_HEIGHT), color=_FALLBACK_BG_COLOR)

    # ── Resize to YouTube recommended size ──────────────────────────────────
    img = img.resize((_THUMB_WIDTH, _THUMB_HEIGHT), Image.LANCZOS)

    # ── Text overlay ─────────────────────────────────────────────────────────
    font = _load_font(font_path)
    draw = ImageDraw.Draw(img)

    # Shadow (offset by SHADOW_OFFSET pixels in both axes)
    draw.text(
        (_TEXT_X + _SHADOW_OFFSET, _TEXT_Y + _SHADOW_OFFSET),
        title,
        font=font,
        fill=(0, 0, 0),
    )
    # Main text
    draw.text((_TEXT_X, _TEXT_Y), title, font=font, fill=(255, 255, 255))

    # ── Save as JPEG quality=90 ──────────────────────────────────────────────
    img.save(output_path, format="JPEG", quality=90)
    file_size = Path(output_path).stat().st_size

    # If over 2MB, reduce quality to 75 and resave
    if file_size > _MAX_FILE_BYTES:
        img.save(output_path, format="JPEG", quality=75)
        file_size = Path(output_path).stat().st_size

    return output_path, file_size


# ---------------------------------------------------------------------------
# Temporal activity
# ---------------------------------------------------------------------------


@activity.defn
async def generate_thumbnail(params: ThumbnailInput) -> ThumbnailOutput:
    """Generate a 1280x720 JPEG thumbnail with Korean text overlay.

    Loads the first scene image (scene_00.png) as the background, resizes to
    1280x720, draws a drop-shadow text overlay with the video title, and
    saves as a JPEG under the 2MB YouTube limit.

    Args:
        params: ThumbnailInput with title, channel_id, and run directory.

    Returns:
        ThumbnailOutput with output file path and file size in bytes.
    """
    output_path, file_size = await asyncio.to_thread(
        _build_thumbnail,
        params.title,
        params.run_dir,
        settings.font_path,
    )

    return ThumbnailOutput(
        file_path=output_path,
        file_size_bytes=file_size,
    )
