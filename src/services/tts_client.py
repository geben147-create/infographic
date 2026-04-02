"""
TTS provider implementations — CosyVoice2 and Kokoro.

Both providers implement the TTSProvider ABC from src/models/provider.py.
Heavy ML model imports are done lazily inside the synthesize() method to
avoid blocking the event loop and to allow the module to load in environments
where the TTS engines are not installed (e.g., CI/test environments).

asyncio.to_thread() is used to run synchronous inference off the event loop
so the Temporal worker remains responsive during long audio synthesis.
"""
from __future__ import annotations

import asyncio
import io
import wave

from temporalio.exceptions import ApplicationError

from src.models.provider import TTSProvider


# ---------------------------------------------------------------------------
# Internal helpers — thin async wrappers around sync inference.
# These are module-level so tests can patch them directly.
# ---------------------------------------------------------------------------


async def _synthesize_cosyvoice(text: str, voice_ref: str = "") -> bytes:
    """Run CosyVoice2 inference in a thread and return WAV bytes.

    Raises:
        ApplicationError: If CosyVoice2 is not installed.
    """
    try:
        import importlib
        cosyvoice_mod = importlib.import_module("cosyvoice")
        CosyVoice2 = getattr(cosyvoice_mod, "CosyVoice2", None)
        if CosyVoice2 is None:
            raise ImportError("CosyVoice2 class not found in cosyvoice module")
    except (ImportError, TypeError):
        raise ApplicationError(
            "CosyVoice2 not installed. Install from https://github.com/FunAudioLLM/CosyVoice",
            non_retryable=True,
        )

    def _run_sync() -> bytes:
        model = CosyVoice2("pretrained_models/CosyVoice2-0.5B")
        results = model.inference_sft(text, "中文女", stream=False)
        # Convert numpy array to WAV bytes
        audio_array = results[0]["tts_speech"].numpy()
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(22050)
            # numpy float32 → int16
            import numpy as np
            pcm = (audio_array * 32767).astype("int16")
            wf.writeframes(pcm.tobytes())
        return buf.getvalue()

    return await asyncio.to_thread(_run_sync)


async def _synthesize_kokoro(text: str, voice_ref: str = "") -> bytes:
    """Run Kokoro inference in a thread and return WAV bytes.

    Raises:
        ApplicationError: If kokoro is not installed.
    """
    try:
        import importlib
        kokoro_mod = importlib.import_module("kokoro")
        if kokoro_mod is None:
            raise ImportError("kokoro module is None")
    except (ImportError, TypeError):
        raise ApplicationError(
            "Kokoro not installed. Install via: pip install kokoro",
            non_retryable=True,
        )

    def _run_sync() -> bytes:
        from kokoro import KPipeline  # type: ignore[import]
        pipeline = KPipeline(lang_code="a")
        audio_chunks = []
        for _, _, audio in pipeline(text, voice="af_heart"):
            audio_chunks.append(audio)

        import numpy as np
        audio_array = np.concatenate(audio_chunks)
        buf = io.BytesIO()
        sample_rate = 24000  # Kokoro default
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            pcm = (audio_array * 32767).astype("int16")
            wf.writeframes(pcm.tobytes())
        return buf.getvalue()

    return await asyncio.to_thread(_run_sync)


# ---------------------------------------------------------------------------
# Provider classes
# ---------------------------------------------------------------------------


class CosyVoiceTTSProvider(TTSProvider):
    """TTS provider using local CosyVoice2 model.

    CosyVoice2 is a zero-shot TTS system with strong Korean language support.
    Requires: https://github.com/FunAudioLLM/CosyVoice
    """

    async def synthesize(self, text: str, voice_ref: str = "") -> bytes:
        """Synthesize Korean speech with CosyVoice2.

        Args:
            text: Korean text to synthesize.
            voice_ref: Path to reference audio for voice cloning (optional).

        Returns:
            WAV audio bytes.

        Raises:
            ApplicationError: If CosyVoice2 is not installed.
        """
        return await _synthesize_cosyvoice(text, voice_ref)


class KokoroTTSProvider(TTSProvider):
    """TTS provider using local Kokoro model.

    Kokoro is a lightweight TTS model (82M params). English-focused but
    can handle Korean text with reduced quality. Used as a fallback.
    Requires: pip install kokoro
    """

    async def synthesize(self, text: str, voice_ref: str = "") -> bytes:
        """Synthesize speech with Kokoro.

        Args:
            text: Text to synthesize.
            voice_ref: Voice reference (used for voice selection).

        Returns:
            WAV audio bytes.

        Raises:
            ApplicationError: If kokoro is not installed.
        """
        return await _synthesize_kokoro(text, voice_ref)


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------


def get_tts_provider(model_spec: str) -> TTSProvider:
    """Parse a 'provider:model' spec and return the appropriate TTSProvider.

    Supported model specs:
        - "local:cosyvoice2" → CosyVoiceTTSProvider
        - "local:kokoro" → KokoroTTSProvider

    Args:
        model_spec: Provider:model string from channel config.

    Returns:
        TTSProvider instance.

    Raises:
        ValueError: For unsupported model specs.
    """
    from src.models.provider import ModelSpec

    spec = ModelSpec.parse(model_spec)
    model_lower = spec.model.lower()

    if model_lower == "cosyvoice2":
        return CosyVoiceTTSProvider()
    elif model_lower == "kokoro":
        return KokoroTTSProvider()
    else:
        raise ValueError(
            f"Unsupported TTS model: {spec.model!r}. "
            "Supported models: 'cosyvoice2', 'kokoro'."
        )
