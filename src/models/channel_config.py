"""
ChannelConfig — immutable per-channel pipeline configuration.

Each YouTube channel has its own YAML config file that specifies which
AI models to use, TTS settings, and upload credentials.
"""
from __future__ import annotations

from pydantic import BaseModel


class ChannelConfig(BaseModel, frozen=True):
    """Frozen (immutable) per-channel configuration.

    Model spec fields use 'provider:model' syntax parsed by ModelSpec.
    Example: "fal:kling-2.5-turbo", "local:sdxl-juggernaut"
    """

    channel_id: str
    niche: str

    # Locale
    language: str = "ko"

    # Model selection (provider:model format)
    video_model: str = "local:wan2gp"
    image_model: str = "local:sdxl-juggernaut"
    tts_model: str = "local:cosyvoice2"
    llm_model: str = "local:qwen3.5-9b"

    # Generation settings
    sdxl_checkpoint: str = "juggernautXL_v9.safetensors"
    tts_voice_reference: str = "voices/default_ko.wav"

    # Templates
    prompt_template: str = "script_default.j2"
    thumbnail_style: str = "default"

    # Metadata
    tags: list[str] = []

    # Feature flags
    vgen_enabled: bool = False

    # YouTube upload
    youtube_credentials_path: str = ""
    publish_status: str = "private"
    category_id: str = "22"


def load_channel_config(
    channel_id: str,
    config_dir: str = "src/channel_configs",
) -> ChannelConfig:
    """Load a ChannelConfig from a YAML file.

    Looks for `{config_dir}/{channel_id}.yaml`.

    Args:
        channel_id: Channel identifier (used as filename stem).
        config_dir: Directory containing channel YAML files.

    Returns:
        Frozen ChannelConfig instance.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If the YAML is missing required fields.
    """
    import pathlib

    import yaml  # pyyaml — installed as part of Phase 2 dependencies

    config_path = pathlib.Path(config_dir) / f"{channel_id}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(
            f"Channel config not found: {config_path}"
        )

    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    # Ensure channel_id from filename matches (or inject it)
    if "channel_id" not in data:
        data["channel_id"] = channel_id

    return ChannelConfig.model_validate(data)
