"""
Provider registry — resolves 'provider:model' spec strings to provider instances.

Usage:
    from src.services.provider_registry import registry

    # Register a provider implementation
    registry.register("llm", "local", my_ollama_provider)

    # Resolve a model spec to its provider
    llm = registry.get_llm("local:qwen3-14b")
    result = await llm.generate(prompt, system)

FastAPI Depends() integration:
    def my_endpoint(reg: ProviderRegistry = Depends(get_provider_registry)):
        ...
"""
from __future__ import annotations

from src.models.provider import (
    ImageProvider,
    LLMProvider,
    ModelProvider,
    ModelSpec,
    TTSProvider,
    VideoProvider,
)


class ProviderRegistry:
    """Registry that maps (capability, provider_name) -> ModelProvider instance.

    Capabilities: "llm", "image", "tts", "video"
    """

    def __init__(self) -> None:
        # {capability: {provider_name: provider_instance}}
        self._providers: dict[str, dict[str, ModelProvider]] = {
            "llm": {},
            "image": {},
            "tts": {},
            "video": {},
        }

    def register(
        self,
        capability: str,
        provider_name: str,
        provider: ModelProvider,
    ) -> None:
        """Register a provider implementation.

        Args:
            capability: One of "llm", "image", "tts", "video".
            provider_name: Provider identifier (e.g. "local", "fal").
            provider: Provider instance implementing the relevant ABC.

        Raises:
            ValueError: If capability is not recognized.
        """
        if capability not in self._providers:
            raise ValueError(
                f"Unknown capability {capability!r}. "
                f"Must be one of: {list(self._providers)}"
            )
        self._providers[capability][provider_name] = provider

    def get_provider(self, capability: str, model_spec: str) -> ModelProvider:
        """Resolve a model spec string to a registered provider instance.

        Args:
            capability: One of "llm", "image", "tts", "video".
            model_spec: 'provider:model' string, e.g. "fal:kling-2.5-turbo".

        Returns:
            The registered ModelProvider instance for that capability + provider.

        Raises:
            ValueError: If the spec is malformed.
            KeyError: If no provider is registered for this capability+provider combo.
        """
        spec = ModelSpec.parse(model_spec)
        bucket = self._providers.get(capability, {})
        if spec.provider.value not in bucket:
            raise KeyError(
                f"No {capability!r} provider registered for {spec.provider.value!r}. "
                f"Registered: {list(bucket)}"
            )
        return bucket[spec.provider.value]

    def get_llm(self, model_spec: str) -> LLMProvider:
        """Convenience accessor for LLM providers."""
        provider = self.get_provider("llm", model_spec)
        assert isinstance(provider, LLMProvider)
        return provider

    def get_image(self, model_spec: str) -> ImageProvider:
        """Convenience accessor for image generation providers."""
        provider = self.get_provider("image", model_spec)
        assert isinstance(provider, ImageProvider)
        return provider

    def get_tts(self, model_spec: str) -> TTSProvider:
        """Convenience accessor for TTS providers."""
        provider = self.get_provider("tts", model_spec)
        assert isinstance(provider, TTSProvider)
        return provider

    def get_video(self, model_spec: str) -> VideoProvider:
        """Convenience accessor for video generation providers."""
        provider = self.get_provider("video", model_spec)
        assert isinstance(provider, VideoProvider)
        return provider


# Module-level singleton — used by all pipeline activities
registry = ProviderRegistry()


def get_provider_registry() -> ProviderRegistry:
    """FastAPI Depends() factory for the provider registry singleton."""
    return registry
