"""
TTS audio generation Temporal activity.

Generates speech audio for a single video scene using the configured
TTS provider (CosyVoice2 or Kokoro). Saves the result as a WAV file
in the pipeline run directory.
"""
from __future__ import annotations

import wave
from pathlib import Path

from pydantic import BaseModel
from temporalio import activity

from src.models.channel_config import load_channel_config
from src.services.tts_client import get_tts_provider


class TTSInput(BaseModel):
    """Input parameters for the generate_tts_audio activity."""

    scene_index: int
    text: str
    channel_id: str
    run_dir: str


class TTSOutput(BaseModel):
    """Output from the generate_tts_audio activity."""

    file_path: str
    duration_seconds: float


def _wav_duration(wav_bytes: bytes) -> float:
    """Calculate audio duration from WAV bytes using the wave module.

    Args:
        wav_bytes: Raw WAV file bytes.

    Returns:
        Duration in seconds.
    """
    import io

    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / float(rate)


@activity.defn
async def generate_tts_audio(params: TTSInput) -> TTSOutput:
    """Generate TTS audio for a single scene and save to disk.

    Steps:
    1. Load channel config to determine which TTS provider to use.
    2. Select provider via get_tts_provider().
    3. Call provider.synthesize() with scene narration text.
    4. Save WAV bytes to {run_dir}/audio/scene_{NN:02d}.wav.
    5. Calculate audio duration from WAV header.
    6. Return TTSOutput with file_path and duration_seconds.

    Args:
        params: TTSInput with scene_index, text, channel_id, run_dir.

    Returns:
        TTSOutput with file_path and duration_seconds.

    Raises:
        ApplicationError: If the TTS provider is not installed or fails.
    """
    config = load_channel_config(params.channel_id)
    provider = get_tts_provider(config.tts_model)

    wav_bytes = await provider.synthesize(
        text=params.text,
        voice_ref=config.tts_voice_reference,
    )

    # Save WAV file
    audio_path = (
        Path(params.run_dir)
        / "audio"
        / f"scene_{params.scene_index:02d}.wav"
    )
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(wav_bytes)

    duration = _wav_duration(wav_bytes)

    return TTSOutput(
        file_path=str(audio_path),
        duration_seconds=duration,
    )
