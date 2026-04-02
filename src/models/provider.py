"""
Provider abstraction layer for Phase 2.

Defines the ABC interfaces for LLM, image, TTS, and video generation providers,
plus the ModelSpec parser for "provider:model" string syntax.
"""
from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel


class ProviderType(str, Enum):
    local = "local"
    fal = "fal"
    replicate = "replicate"
    together = "together"
    fireworks = "fireworks"
    krea = "krea"
    wavespeed = "wavespeed"


class ModelSpec(BaseModel):
    provider: ProviderType
    model: str

    @classmethod
    def parse(cls, spec: str) -> "ModelSpec":
        """Parse a 'provider:model' string into a ModelSpec.

        The first ':' separates provider from model — everything after belongs
        to the model name (e.g. 'fal:fal-ai/wan/image-to-video' is valid).

        Raises:
            ValueError: if spec contains no ':' separator.
        """
        if ":" not in spec:
            raise ValueError(
                f"Invalid model spec {spec!r}: must be 'provider:model' format"
            )
        provider_str, model_name = spec.split(":", 1)
        return cls(provider=ProviderType(provider_str), model=model_name)


# ─────────────────────────────────────────────
# Provider ABCs
# ─────────────────────────────────────────────


class ModelProvider(ABC):
    """Base class for all provider implementations."""


class LLMProvider(ModelProvider, ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: str,
        format_schema: dict | None = None,
    ) -> str:
        """Generate text from prompt.

        Args:
            prompt: User prompt.
            system: System instruction.
            format_schema: Optional JSON schema for structured output.

        Returns:
            Generated text string.
        """


class ImageProvider(ModelProvider, ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
    ) -> bytes:
        """Generate an image from a text prompt.

        Returns:
            Raw image bytes (PNG/JPEG).
        """


class TTSProvider(ModelProvider, ABC):
    @abstractmethod
    async def synthesize(self, text: str, voice_ref: str = "") -> bytes:
        """Synthesize speech from text.

        Args:
            text: Text to convert to speech.
            voice_ref: Path to voice reference audio file for zero-shot cloning.

        Returns:
            Raw audio bytes (WAV/MP3).
        """


class VideoProvider(ModelProvider, ABC):
    @abstractmethod
    async def generate(
        self,
        image_path: str,
        prompt: str,
        duration_seconds: float = 5.0,
    ) -> tuple[str, float]:
        """Generate a video clip from an image and motion prompt.

        Args:
            image_path: Path to the source image.
            prompt: Motion/style prompt.
            duration_seconds: Desired clip duration.

        Returns:
            Tuple of (video_path, cost_usd).
        """
