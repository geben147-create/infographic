"""
Temporal activity: generate_scene_image

Produces a PNG image for one scene using either:
- ComfyUIProvider (local SDXL via ComfyUI) when image_model is "local:*"
- FalImageProvider (fal.ai cloud) when image_model is "fal:*"

Output is saved to {run_dir}/images/scene_{NN}.png.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel
from temporalio import activity

from src.models.channel_config import load_channel_config
from src.models.provider import ModelSpec, ProviderType
from src.services.comfyui_client import ComfyUIProvider, ComfyUIZImageProvider
from src.services.fal_client import FalImageProvider


class ImageGenInput(BaseModel):
    """Input parameters for the generate_scene_image activity."""

    scene_index: int
    prompt: str
    channel_id: str
    run_dir: str
    negative_prompt: str = ""


class ImageGenOutput(BaseModel):
    """Output of the generate_scene_image activity."""

    file_path: str


@activity.defn
async def generate_scene_image(params: ImageGenInput) -> ImageGenOutput:
    """Generate a still image for one pipeline scene.

    Selects the appropriate provider from the channel config, generates
    the image bytes, and saves them to disk.

    Args:
        params: Scene index, prompt, channel_id, run directory, and
                optional negative prompt.

    Returns:
        ImageGenOutput with the absolute path to the saved PNG.
    """
    from src.config import settings

    config = load_channel_config(
        channel_id=params.channel_id,
        config_dir=settings.channel_configs_dir,
    )

    spec = ModelSpec.parse(config.image_model)

    if spec.provider == ProviderType.local and spec.model == "zimage-turbo":
        provider: ComfyUIProvider | ComfyUIZImageProvider | FalImageProvider = (
            ComfyUIZImageProvider(base_url=settings.comfyui_url)
        )
    elif spec.provider == ProviderType.local:
        provider = ComfyUIProvider(
            base_url=settings.comfyui_url,
            checkpoint=config.sdxl_checkpoint,
        )
    elif spec.provider == ProviderType.fal:
        provider = FalImageProvider(model=spec.model)
    else:
        raise ValueError(
            f"Unsupported image provider: {spec.provider!r} in channel {params.channel_id!r}"
        )

    image_bytes = await provider.generate(
        prompt=params.prompt,
        negative_prompt=params.negative_prompt,
    )

    output_dir = Path(params.run_dir) / "images"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"scene_{params.scene_index:02d}.png"
    output_path.write_bytes(image_bytes)

    return ImageGenOutput(file_path=str(output_path))
