"""
Multi-channel validation tests.

Validates that both channel configs load correctly, produce different provider
selections, and that the ChannelConfig frozen model prevents mutation.

Requirement coverage: CHAN-01 (channel_01), CHAN-02 (channel_02).
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Section 1: Config loading
# ---------------------------------------------------------------------------


class TestChannelConfigLoading:
    """Both channel YAML files must load as valid ChannelConfig instances."""

    def test_channel_01_loads_with_local_providers(self):
        """channel_01.yaml uses local providers: kokoro, zimage-turbo, qwen3:14b."""
        from src.models.channel_config import load_channel_config

        config = load_channel_config("channel_01")

        assert config.channel_id == "channel_01"
        assert config.tts_model == "local:kokoro"
        assert config.image_model == "local:zimage-turbo"
        assert config.vgen_enabled is False

    def test_channel_02_loads_with_mixed_providers(self):
        """channel_02.yaml uses mixed providers: local kokoro TTS, fal flux image, fal kling video."""
        from src.models.channel_config import load_channel_config

        config = load_channel_config("channel_02")

        assert config.channel_id == "channel_02"
        assert config.tts_model == "local:kokoro"
        assert config.image_model == "fal:flux-kontext"
        assert config.video_model == "fal:kling-2.5-turbo"
        assert config.vgen_enabled is True

    def test_channel_01_vgen_disabled(self):
        """channel_01 has vgen_enabled=False (Ken Burns fallback path)."""
        from src.models.channel_config import load_channel_config

        config = load_channel_config("channel_01")
        assert config.vgen_enabled is False

    def test_channel_02_vgen_enabled(self):
        """channel_02 has vgen_enabled=True (fal.ai AI video path)."""
        from src.models.channel_config import load_channel_config

        config = load_channel_config("channel_02")
        assert config.vgen_enabled is True

    def test_channel_configs_have_different_templates(self):
        """Each channel uses a different Jinja2 prompt template."""
        from src.models.channel_config import load_channel_config

        c1 = load_channel_config("channel_01")
        c2 = load_channel_config("channel_02")

        assert c1.prompt_template != c2.prompt_template

    def test_channel_configs_have_different_tags(self):
        """Each channel uses a different set of YouTube tags."""
        from src.models.channel_config import load_channel_config

        c1 = load_channel_config("channel_01")
        c2 = load_channel_config("channel_02")

        assert c1.tags != c2.tags

    def test_channel_01_language_is_korean(self):
        """channel_01 language is 'ko' (Korean)."""
        from src.models.channel_config import load_channel_config

        config = load_channel_config("channel_01")
        assert config.language == "ko"

    def test_channel_02_language_is_korean(self):
        """channel_02 language is 'ko' (Korean)."""
        from src.models.channel_config import load_channel_config

        config = load_channel_config("channel_02")
        assert config.language == "ko"

    def test_channel_01_has_tags(self):
        """channel_01 has a non-empty tags list."""
        from src.models.channel_config import load_channel_config

        config = load_channel_config("channel_01")
        assert len(config.tags) > 0

    def test_channel_02_has_tags(self):
        """channel_02 has a non-empty tags list including finance-related tags."""
        from src.models.channel_config import load_channel_config

        config = load_channel_config("channel_02")
        assert len(config.tags) > 0


# ---------------------------------------------------------------------------
# Section 2: Provider resolution
# ---------------------------------------------------------------------------


class TestModelSpecParsing:
    """ModelSpec.parse() correctly resolves all model specs from both channels."""

    def test_model_spec_parse_all_channel_01_models(self):
        """All model specs in channel_01 parse to ProviderType.local."""
        from src.models.channel_config import load_channel_config
        from src.models.provider import ModelSpec, ProviderType

        config = load_channel_config("channel_01")

        # LLM model
        llm_spec = ModelSpec.parse(config.llm_model)
        assert llm_spec.provider == ProviderType.local
        assert llm_spec.model == "qwen3:14b"

        # Image model
        img_spec = ModelSpec.parse(config.image_model)
        assert img_spec.provider == ProviderType.local
        assert img_spec.model == "zimage-turbo"

        # TTS model
        tts_spec = ModelSpec.parse(config.tts_model)
        assert tts_spec.provider == ProviderType.local
        assert tts_spec.model == "kokoro"

        # Video model (local:wan2gp — used as Ken Burns fallback)
        video_spec = ModelSpec.parse(config.video_model)
        assert video_spec.provider == ProviderType.local

    def test_model_spec_parse_all_channel_02_models(self):
        """channel_02 models parse to mixed provider types (local + fal + together)."""
        from src.models.channel_config import load_channel_config
        from src.models.provider import ModelSpec, ProviderType

        config = load_channel_config("channel_02")

        # TTS model (local)
        tts_spec = ModelSpec.parse(config.tts_model)
        assert tts_spec.provider == ProviderType.local
        assert tts_spec.model == "kokoro"

        # Image model (fal)
        img_spec = ModelSpec.parse(config.image_model)
        assert img_spec.provider == ProviderType.fal
        assert img_spec.model == "flux-kontext"

        # Video model (fal)
        video_spec = ModelSpec.parse(config.video_model)
        assert video_spec.provider == ProviderType.fal
        assert video_spec.model == "kling-2.5-turbo"

        # LLM model (together)
        llm_spec = ModelSpec.parse(config.llm_model)
        assert llm_spec.provider == ProviderType.together

    def test_channel_01_tts_model_is_local_kokoro(self):
        """channel_01 TTS model spec string is 'local:kokoro'."""
        from src.models.channel_config import load_channel_config

        config = load_channel_config("channel_01")
        assert config.tts_model == "local:kokoro"

    def test_channel_02_video_model_is_fal_kling(self):
        """channel_02 video model spec string is 'fal:kling-2.5-turbo'."""
        from src.models.channel_config import load_channel_config

        config = load_channel_config("channel_02")
        assert config.video_model == "fal:kling-2.5-turbo"

    def test_model_spec_parse_rejects_missing_colon(self):
        """ModelSpec.parse raises ValueError if spec has no ':' separator."""
        from src.models.provider import ModelSpec

        with pytest.raises(ValueError, match="provider:model"):
            ModelSpec.parse("no-colon-here")

    def test_model_spec_parse_handles_model_with_slash(self):
        """ModelSpec.parse handles model names containing slashes."""
        from src.models.provider import ModelSpec, ProviderType

        spec = ModelSpec.parse("fal:fal-ai/wan/image-to-video")
        assert spec.provider == ProviderType.fal
        assert "fal-ai/wan" in spec.model


# ---------------------------------------------------------------------------
# Section 3: Frozen model
# ---------------------------------------------------------------------------


class TestChannelConfigImmutable:
    """ChannelConfig is a frozen Pydantic model — mutation must raise an error."""

    def test_channel_config_immutable(self):
        """Attempting to set a field on a frozen ChannelConfig raises TypeError."""
        from src.models.channel_config import ChannelConfig

        config = ChannelConfig(
            channel_id="test_ch",
            niche="general",
        )

        with pytest.raises((TypeError, ValueError)):
            config.niche = "tech"  # type: ignore[misc]

    def test_channel_config_immutable_on_loaded_config(self):
        """load_channel_config returns a frozen instance — mutation raises TypeError."""
        from src.models.channel_config import load_channel_config

        config = load_channel_config("channel_01")

        with pytest.raises((TypeError, ValueError)):
            config.vgen_enabled = True  # type: ignore[misc]

    def test_channel_config_tags_is_not_mutable_via_assignment(self):
        """Tags field assignment on frozen config raises an error."""
        from src.models.channel_config import load_channel_config

        config = load_channel_config("channel_01")
        original_tags = list(config.tags)

        with pytest.raises((TypeError, ValueError)):
            config.tags = ["new_tag"]  # type: ignore[misc]

        # Original tags unchanged
        assert list(config.tags) == original_tags


# ---------------------------------------------------------------------------
# Section 4: Workflow compatibility
# ---------------------------------------------------------------------------


class TestWorkflowCompatibility:
    """PipelineParams must accept both channel_ids for workflow routing."""

    def test_workflow_params_accept_channel_01(self):
        """PipelineParams with channel_01 serializes correctly."""
        from src.workflows.content_pipeline import PipelineParams

        params = PipelineParams(
            run_id="run-channel01-001",
            topic="비트코인 투자 전략",
            channel_id="channel_01",
        )
        data = params.model_dump_json()
        restored = PipelineParams.model_validate_json(data)

        assert restored.channel_id == "channel_01"
        assert restored.run_id == "run-channel01-001"

    def test_workflow_params_accept_channel_02(self):
        """PipelineParams with channel_02 serializes correctly."""
        from src.workflows.content_pipeline import PipelineParams

        params = PipelineParams(
            run_id="run-channel02-001",
            topic="재테크 기초 가이드",
            channel_id="channel_02",
        )
        data = params.model_dump_json()
        restored = PipelineParams.model_validate_json(data)

        assert restored.channel_id == "channel_02"
        assert restored.run_id == "run-channel02-001"

    def test_workflow_params_accept_both_channels(self):
        """PipelineParams accepts both channel_ids without error (no enum restriction)."""
        from src.workflows.content_pipeline import PipelineParams

        for channel_id in ["channel_01", "channel_02"]:
            params = PipelineParams(
                run_id=f"run-{channel_id}-test",
                topic="테스트 토픽",
                channel_id=channel_id,
            )
            # Must not raise
            assert params.channel_id == channel_id

    def test_pipeline_result_default_values(self):
        """PipelineResult has sensible defaults for optional fields."""
        from src.workflows.content_pipeline import PipelineResult

        result = PipelineResult()
        assert result.video_id is None
        assert result.youtube_url is None
        assert result.total_cost_usd == 0.0
        assert result.scenes_count == 0
        assert result.status == "ready_to_upload"
