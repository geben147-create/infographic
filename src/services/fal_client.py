"""
fal.ai image and video generation providers.

FalImageProvider: Generates still images via fal-client run_async.
FalVideoProvider: Generates video clips via fal-client submit_async with
                  image upload and progress event streaming.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import fal_client
import httpx

from src.models.provider import ImageProvider, VideoProvider

# Cost per second (USD) for known video models
_VIDEO_COST_PER_SECOND: dict[str, float] = {
    "kling-2.5-turbo": 0.07,
    "kling-2.5": 0.07,
    "wan/image-to-video": 0.07,
    "fal-ai/wan/image-to-video": 0.07,
}

_DEFAULT_VIDEO_COST_PER_SECOND = 0.07


class FalImageProvider(ImageProvider):
    """Generate images via fal.ai API."""

    def __init__(self, model: str) -> None:
        """
        Args:
            model: fal.ai model slug (e.g. "flux-kontext").
                   Will be prefixed with "fal-ai/" if not already.
        """
        self._model = model if model.startswith("fal-ai/") else f"fal-ai/{model}"

    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
    ) -> bytes:
        """Generate an image via fal.ai and return raw image bytes."""
        arguments: dict = {
            "prompt": prompt,
            "image_size": {"width": width, "height": height},
        }
        if negative_prompt:
            arguments["negative_prompt"] = negative_prompt

        result = await fal_client.run_async(self._model, arguments=arguments)

        # Extract first image URL from result
        images = result.get("images") or []
        if not images:
            raise RuntimeError(f"fal.ai returned no images for model={self._model}")

        image_url: str = images[0]["url"]

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(image_url)
            resp.raise_for_status()
            return resp.content


class FalVideoProvider(VideoProvider):
    """Generate video clips via fal.ai API (image-to-video)."""

    def __init__(self, model: str) -> None:
        """
        Args:
            model: fal.ai model slug (e.g. "kling-2.5-turbo").
                   Will be prefixed with "fal-ai/" if not already.
        """
        self._model = model if model.startswith("fal-ai/") else f"fal-ai/{model}"
        self._cost_per_second = _VIDEO_COST_PER_SECOND.get(
            model, _DEFAULT_VIDEO_COST_PER_SECOND
        )

    async def generate(
        self,
        image_path: str,
        prompt: str,
        duration_seconds: float = 5.0,
    ) -> tuple[str, float]:
        """Generate a video clip from an image.

        Uploads the local image to fal.ai CDN, submits the generation
        job, streams progress events, then downloads the result.

        Returns:
            Tuple of (local_video_path, cost_usd).
        """
        # Upload source image to fal.ai CDN
        image_url = await fal_client.upload_file_async(image_path)

        arguments = {
            "image_url": image_url,
            "prompt": prompt,
            "duration": str(int(duration_seconds)),
        }

        handle = await fal_client.submit_async(self._model, arguments=arguments)

        # Stream progress events
        async for event in handle:
            if isinstance(event, dict):
                progress = event.get("completed", 0)
                total = event.get("total", 1)
                print(f"[fal.ai] video gen progress: {progress}/{total}")

        result = await handle.get()

        video_info = result.get("video") or {}
        video_url: str = video_info.get("url", "")
        if not video_url:
            raise RuntimeError(f"fal.ai returned no video URL for model={self._model}")

        # Download video to a local temp file
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.get(video_url)
            resp.raise_for_status()
            video_bytes = resp.content

        # Write to a temp file — caller is responsible for moving it
        suffix = Path(video_url).suffix or ".mp4"
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        try:
            with os.fdopen(tmp_fd, "wb") as f:
                f.write(video_bytes)
        except Exception:
            os.close(tmp_fd)
            raise

        cost_usd = self._cost_per_second * duration_seconds
        return tmp_path, cost_usd
