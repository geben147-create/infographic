"""
Phase 2 model and schema tests.
TDD RED phase — all tests must fail before implementation.
"""
import pytest
from pydantic import ValidationError


# ─────────────────────────────────────────────
# ModelSpec.parse tests
# ─────────────────────────────────────────────
class TestModelSpecParse:
    def test_parse_fal_provider(self):
        from src.models.provider import ModelSpec

        result = ModelSpec.parse("fal:kling-2.5-turbo")
        assert result.provider == "fal"
        assert result.model == "kling-2.5-turbo"

    def test_parse_local_provider(self):
        from src.models.provider import ModelSpec

        result = ModelSpec.parse("local:sdxl-juggernaut")
        assert result.provider == "local"
        assert result.model == "sdxl-juggernaut"

    def test_parse_together_provider(self):
        from src.models.provider import ModelSpec

        result = ModelSpec.parse("together:qwen3-8b")
        assert result.provider == "together"
        assert result.model == "qwen3-8b"

    def test_parse_invalid_raises_value_error(self):
        from src.models.provider import ModelSpec

        with pytest.raises(ValueError):
            ModelSpec.parse("invalid")

    def test_parse_model_with_colons_keeps_rest(self):
        """Model name may contain a second colon (e.g. 'provider:org/model:version')."""
        from src.models.provider import ModelSpec

        result = ModelSpec.parse("fal:fal-ai/wan/image-to-video")
        assert result.provider == "fal"
        assert result.model == "fal-ai/wan/image-to-video"


# ─────────────────────────────────────────────
# ProviderType enum tests
# ─────────────────────────────────────────────
class TestProviderType:
    def test_all_values_present(self):
        from src.models.provider import ProviderType

        values = {p.value for p in ProviderType}
        assert "local" in values
        assert "fal" in values
        assert "replicate" in values
        assert "together" in values
        assert "fireworks" in values
        assert "krea" in values
        assert "wavespeed" in values


# ─────────────────────────────────────────────
# ChannelConfig tests
# ─────────────────────────────────────────────
class TestChannelConfig:
    def test_frozen_raises_on_assignment(self):
        from src.models.channel_config import ChannelConfig

        config = ChannelConfig(channel_id="test_01", niche="finance")
        with pytest.raises((TypeError, ValidationError)):
            config.channel_id = "modified"  # type: ignore[misc]

    def test_model_validate_populates_fields(self):
        from src.models.channel_config import ChannelConfig

        data = {
            "channel_id": "chan_01",
            "niche": "tech",
            "language": "en",
            "vgen_enabled": True,
            "tags": ["tech", "ai"],
        }
        config = ChannelConfig.model_validate(data)
        assert config.channel_id == "chan_01"
        assert config.niche == "tech"
        assert config.language == "en"
        assert config.vgen_enabled is True
        assert config.tags == ["tech", "ai"]

    def test_defaults_language_ko(self):
        from src.models.channel_config import ChannelConfig

        config = ChannelConfig(channel_id="chan_02", niche="travel")
        assert config.language == "ko"

    def test_defaults_vgen_enabled_false(self):
        from src.models.channel_config import ChannelConfig

        config = ChannelConfig(channel_id="chan_02", niche="travel")
        assert config.vgen_enabled is False

    def test_defaults_video_model(self):
        from src.models.channel_config import ChannelConfig

        config = ChannelConfig(channel_id="chan_02", niche="travel")
        assert config.video_model == "local:wan2gp"

    def test_defaults_tts_model(self):
        from src.models.channel_config import ChannelConfig

        config = ChannelConfig(channel_id="chan_02", niche="travel")
        assert config.tts_model == "local:cosyvoice2"

    def test_defaults_llm_model(self):
        from src.models.channel_config import ChannelConfig

        config = ChannelConfig(channel_id="chan_02", niche="travel")
        assert config.llm_model == "local:qwen3.5-9b"


# ─────────────────────────────────────────────
# Script / ScriptScene tests
# ─────────────────────────────────────────────
class TestScriptModels:
    def test_script_scene_fields(self):
        from src.models.script import ScriptScene

        scene = ScriptScene(
            narration="Hello world",
            image_prompt="A beautiful landscape",
            duration_seconds=5.0,
        )
        assert scene.narration == "Hello world"
        assert scene.image_prompt == "A beautiful landscape"
        assert scene.duration_seconds == 5.0

    def test_script_fields(self):
        from src.models.script import Script, ScriptScene

        scene = ScriptScene(
            narration="Intro narration",
            image_prompt="Opening shot",
            duration_seconds=4.0,
        )
        script = Script(
            title="Test Video",
            description="A test video about nothing",
            tags=["test", "video"],
            scenes=[scene],
        )
        assert script.title == "Test Video"
        assert script.description == "A test video about nothing"
        assert script.tags == ["test", "video"]
        assert len(script.scenes) == 1
        assert script.scenes[0].narration == "Intro narration"


# ─────────────────────────────────────────────
# PipelineStatus enum tests
# ─────────────────────────────────────────────
class TestPipelineStatus:
    def test_all_four_values(self):
        from src.schemas.pipeline import PipelineStatus

        values = {s.value for s in PipelineStatus}
        assert "running" in values
        assert "completed" in values
        assert "failed" in values
        assert "unknown" in values

    def test_exactly_four_values(self):
        from src.schemas.pipeline import PipelineStatus

        assert len(list(PipelineStatus)) == 4


# ─────────────────────────────────────────────
# PipelineTriggerResponse tests
# ─────────────────────────────────────────────
class TestPipelineTriggerResponse:
    def test_required_fields(self):
        from src.schemas.pipeline import PipelineTriggerResponse

        resp = PipelineTriggerResponse(
            workflow_id="pipeline-abc12345",
            status="started",
            channel_id="channel_01",
            topic="한국 부동산",
        )
        assert resp.workflow_id == "pipeline-abc12345"
        assert resp.status == "started"
        assert resp.channel_id == "channel_01"
        assert resp.topic == "한국 부동산"
        assert resp.estimated_cost_usd is None

    def test_with_estimated_cost(self):
        from src.schemas.pipeline import PipelineTriggerResponse

        resp = PipelineTriggerResponse(
            workflow_id="pipeline-xyz",
            status="started",
            channel_id="channel_02",
            topic="AI trends",
            estimated_cost_usd=1.50,
        )
        assert resp.estimated_cost_usd == 1.50


# ─────────────────────────────────────────────
# PipelineStatusResponse tests
# ─────────────────────────────────────────────
class TestPipelineStatusResponse:
    def test_all_fields_present(self):
        from src.schemas.pipeline import PipelineStatus, PipelineStatusResponse

        resp = PipelineStatusResponse(
            workflow_id="pipeline-abc12345",
            status=PipelineStatus.running,
            current_step="generate_script",
            scenes_total=10,
            scenes_done=3,
            cost_so_far_usd=0.60,
            youtube_url=None,
            error=None,
            started_at="2026-04-02T10:00:00Z",
            completed_at=None,
        )
        assert resp.workflow_id == "pipeline-abc12345"
        assert resp.status == PipelineStatus.running
        assert resp.current_step == "generate_script"
        assert resp.scenes_total == 10
        assert resp.scenes_done == 3
        assert resp.cost_so_far_usd == 0.60
        assert resp.youtube_url is None
        assert resp.error is None

    def test_optional_fields_default_none(self):
        from src.schemas.pipeline import PipelineStatus, PipelineStatusResponse

        resp = PipelineStatusResponse(
            workflow_id="pipeline-min",
            status=PipelineStatus.unknown,
        )
        assert resp.current_step is None
        assert resp.scenes_total is None
        assert resp.scenes_done is None
        assert resp.cost_so_far_usd is None
        assert resp.youtube_url is None
        assert resp.error is None
        assert resp.started_at is None
        assert resp.completed_at is None
