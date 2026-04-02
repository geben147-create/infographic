"""
Integration tests for the full content pipeline.

Tests cover:
- Section 1: Activity I/O serialization (round-trip JSON)
- Section 2: Activity chain tests (individual activities with mocked external deps)
- Section 3: Cost tracking integration
- Section 4: API response shape tests (FastAPI TestClient)
"""
from __future__ import annotations

import io
import json
import struct
import wave
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_channel_config(channel_id: str = "channel_01", vgen_enabled: bool = False):
    """Return a minimal ChannelConfig for testing."""
    from src.models.channel_config import ChannelConfig

    return ChannelConfig(
        channel_id=channel_id,
        niche="general",
        language="ko",
        llm_model="local:qwen3.5-9b",
        image_model="local:sdxl-juggernaut",
        tts_model="local:cosyvoice2",
        video_model="local:wan2gp",
        prompt_template="script_default.j2",
        tags=["태그1"],
        vgen_enabled=vgen_enabled,
    )


def _make_script_json() -> str:
    """Return a valid serialized Script JSON string."""
    return json.dumps(
        {
            "title": "테스트 영상 제목",
            "description": "테스트 영상 설명입니다.",
            "tags": ["태그1", "태그2"],
            "scenes": [
                {
                    "narration": "첫 번째 장면 내레이션.",
                    "image_prompt": "A scenic mountain landscape",
                    "duration_seconds": 5.0,
                }
            ],
        }
    )


def _make_wav_bytes(duration_seconds: float = 3.0, sample_rate: int = 22050) -> bytes:
    """Generate minimal valid WAV bytes for testing."""
    num_frames = int(duration_seconds * sample_rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{num_frames}h", *([0] * num_frames)))
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Section 1: Activity I/O serialization tests
# ---------------------------------------------------------------------------


class TestActivityIOSerialization:
    """Each activity input/output model must survive a JSON round-trip."""

    def test_script_gen_input_round_trip(self):
        from src.activities.script_gen import ScriptGenInput

        original = ScriptGenInput(
            topic="비트코인 투자 전략",
            channel_id="channel_01",
            run_dir="/data/pipeline/run001",
        )
        data = original.model_dump_json()
        restored = ScriptGenInput.model_validate_json(data)
        assert restored == original

    def test_script_gen_output_round_trip(self):
        from src.activities.script_gen import ScriptGenOutput
        from src.models.script import Script, ScriptScene

        script = Script(
            title="제목",
            description="설명",
            tags=["태그"],
            scenes=[ScriptScene(narration="나레이션", image_prompt="prompt", duration_seconds=5.0)],
        )
        original = ScriptGenOutput(script=script, file_path="/tmp/script.json")
        data = original.model_dump_json()
        restored = ScriptGenOutput.model_validate_json(data)
        assert restored == original

    def test_image_gen_input_round_trip(self):
        from src.activities.image_gen import ImageGenInput

        original = ImageGenInput(
            scene_index=0,
            prompt="A mountain sunrise",
            channel_id="channel_01",
            run_dir="/data/pipeline/run001",
        )
        data = original.model_dump_json()
        restored = ImageGenInput.model_validate_json(data)
        assert restored == original

    def test_image_gen_output_round_trip(self):
        from src.activities.image_gen import ImageGenOutput

        original = ImageGenOutput(file_path="/data/pipeline/run001/images/scene_00.png")
        data = original.model_dump_json()
        restored = ImageGenOutput.model_validate_json(data)
        assert restored == original

    def test_tts_input_round_trip(self):
        from src.activities.tts import TTSInput

        original = TTSInput(
            scene_index=0,
            text="첫 번째 장면 나레이션 텍스트입니다.",
            channel_id="channel_01",
            run_dir="/data/pipeline/run001",
        )
        data = original.model_dump_json()
        restored = TTSInput.model_validate_json(data)
        assert restored == original

    def test_tts_output_round_trip(self):
        from src.activities.tts import TTSOutput

        original = TTSOutput(
            file_path="/data/pipeline/run001/audio/scene_00.wav",
            duration_seconds=5.25,
        )
        data = original.model_dump_json()
        restored = TTSOutput.model_validate_json(data)
        assert restored.duration_seconds == pytest.approx(5.25)

    def test_video_gen_input_round_trip(self):
        from src.activities.video_gen import VideoGenInput

        original = VideoGenInput(
            scene_index=0,
            channel_id="channel_01",
            run_dir="/data/pipeline/run001",
            image_path="/data/pipeline/run001/images/scene_00.png",
            prompt="A mountain sunrise pan",
            duration_seconds=5.0,
        )
        data = original.model_dump_json()
        restored = VideoGenInput.model_validate_json(data)
        assert restored == original

    def test_video_gen_output_round_trip(self):
        from src.activities.video_gen import VideoGenOutput

        original = VideoGenOutput(
            file_path="/data/pipeline/run001/video/scene_00.mp4",
            cost_usd=0.0,
            method="ken_burns",
        )
        data = original.model_dump_json()
        restored = VideoGenOutput.model_validate_json(data)
        assert restored == original

    def test_assembly_input_round_trip(self):
        from src.activities.video_assembly import AssemblyInput

        original = AssemblyInput(scene_count=3, run_dir="/data/pipeline/run001")
        data = original.model_dump_json()
        restored = AssemblyInput.model_validate_json(data)
        assert restored == original

    def test_assembly_output_round_trip(self):
        from src.activities.video_assembly import AssemblyOutput

        original = AssemblyOutput(
            file_path="/data/pipeline/run001/final/final_video.mp4",
            duration_seconds=30.5,
            file_size_bytes=50_000_000,
        )
        data = original.model_dump_json()
        restored = AssemblyOutput.model_validate_json(data)
        assert restored == original

    def test_thumbnail_input_round_trip(self):
        from src.activities.thumbnail import ThumbnailInput

        original = ThumbnailInput(
            title="테스트 썸네일 제목",
            channel_id="channel_01",
            run_dir="/data/pipeline/run001",
        )
        data = original.model_dump_json()
        restored = ThumbnailInput.model_validate_json(data)
        assert restored == original

    def test_thumbnail_output_round_trip(self):
        from src.activities.thumbnail import ThumbnailOutput

        original = ThumbnailOutput(
            file_path="/data/pipeline/run001/thumbnails/thumbnail.jpg",
            file_size_bytes=102400,
        )
        data = original.model_dump_json()
        restored = ThumbnailOutput.model_validate_json(data)
        assert restored == original

    def test_upload_input_round_trip(self):
        from src.activities.youtube_upload import UploadInput

        original = UploadInput(
            video_path="/data/pipeline/run001/final/final_video.mp4",
            thumbnail_path="/data/pipeline/run001/thumbnails/thumbnail.jpg",
            title="유튜브 영상 제목",
            description="영상 설명입니다.",
            tags=["태그1", "태그2"],
            channel_id="channel_01",
        )
        data = original.model_dump_json()
        restored = UploadInput.model_validate_json(data)
        assert restored == original

    def test_upload_output_round_trip(self):
        from src.activities.youtube_upload import UploadOutput

        original = UploadOutput(
            video_id="dQw4w9WgXcQ",
            youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )
        data = original.model_dump_json()
        restored = UploadOutput.model_validate_json(data)
        assert restored == original


# ---------------------------------------------------------------------------
# Section 2: Activity chain tests (mocked external deps)
# ---------------------------------------------------------------------------


class TestScriptGenActivity:
    """generate_script activity with mocked Ollama."""

    @pytest.mark.asyncio
    async def test_script_gen_produces_valid_script(self, tmp_path):
        """generate_script writes script.json with correct fields when Ollama returns valid JSON."""
        from src.activities.script_gen import ScriptGenInput, generate_script

        script_json = _make_script_json()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"response": script_json}

        with (
            patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp)),
            patch(
                "src.activities.script_gen.load_channel_config",
                return_value=_make_channel_config(),
            ),
            patch("src.config.settings.prompt_templates_dir", "src/prompt_templates"),
        ):
            out = await generate_script(
                ScriptGenInput(
                    topic="비트코인 최신 동향",
                    channel_id="channel_01",
                    run_dir=str(tmp_path),
                )
            )

        script_path = Path(tmp_path) / "scripts" / "script.json"
        assert script_path.exists(), "script.json not written"
        saved = json.loads(script_path.read_text(encoding="utf-8"))
        assert saved["title"] == "테스트 영상 제목"
        assert len(saved["scenes"]) == 1
        assert out.script.title == "테스트 영상 제목"


class TestImageGenActivity:
    """generate_scene_image activity with mocked ComfyUI."""

    @pytest.mark.asyncio
    async def test_image_gen_saves_png(self, tmp_path):
        """generate_scene_image saves scene_00.png when ComfyUI returns image bytes."""
        from src.activities.image_gen import ImageGenInput, generate_scene_image

        fake_png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # minimal PNG header

        mock_provider = MagicMock()
        mock_provider.generate = AsyncMock(return_value=fake_png_bytes)

        with (
            patch(
                "src.activities.image_gen.load_channel_config",
                return_value=_make_channel_config(),
            ),
            patch(
                "src.activities.image_gen.ComfyUIProvider",
                return_value=mock_provider,
            ),
            patch("src.config.settings.channel_configs_dir", "src/channel_configs"),
        ):
            out = await generate_scene_image(
                ImageGenInput(
                    scene_index=0,
                    prompt="A scenic mountain landscape",
                    channel_id="channel_01",
                    run_dir=str(tmp_path),
                )
            )

        png_path = Path(tmp_path) / "images" / "scene_00.png"
        assert png_path.exists(), "scene_00.png was not created"
        assert out.file_path == str(png_path)


class TestTTSActivity:
    """generate_tts_audio activity with mocked TTS provider."""

    @pytest.mark.asyncio
    async def test_tts_saves_wav(self, tmp_path):
        """generate_tts_audio saves scene_00.wav with valid WAV bytes."""
        from src.activities.tts import TTSInput, generate_tts_audio

        wav_bytes = _make_wav_bytes(duration_seconds=3.0)

        mock_provider = MagicMock()
        mock_provider.synthesize = AsyncMock(return_value=wav_bytes)

        with (
            patch(
                "src.activities.tts.load_channel_config",
                return_value=_make_channel_config(),
            ),
            patch("src.activities.tts.get_tts_provider", return_value=mock_provider),
        ):
            out = await generate_tts_audio(
                TTSInput(
                    scene_index=0,
                    text="첫 번째 장면 나레이션 텍스트입니다.",
                    channel_id="channel_01",
                    run_dir=str(tmp_path),
                )
            )

        wav_path = Path(tmp_path) / "audio" / "scene_00.wav"
        assert wav_path.exists(), "scene_00.wav was not created"
        assert out.file_path == str(wav_path)
        assert out.duration_seconds == pytest.approx(3.0, abs=0.1)


class TestVideoGenActivity:
    """generate_scene_video activity — Ken Burns and fal.ai paths."""

    @pytest.mark.asyncio
    async def test_video_gen_ken_burns(self, tmp_path):
        """Ken Burns is used when vgen_enabled=False; cost=0.0 and method='ken_burns'."""
        from src.activities.video_gen import VideoGenInput, generate_scene_video

        # Create a fake source image
        img_path = tmp_path / "images" / "scene_00.png"
        img_path.parent.mkdir(parents=True)
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        config_no_vgen = _make_channel_config(vgen_enabled=False)

        with (
            patch(
                "src.activities.video_gen.load_channel_config",
                return_value=config_no_vgen,
            ),
            patch("src.activities.video_gen.settings.channel_configs_dir", "src/channel_configs"),
            patch("src.activities.video_gen.settings.fal_key", ""),
            patch("src.activities.video_gen.settings.cost_log_path", str(tmp_path / "cost_log.json")),
            patch("src.activities.video_gen.ken_burns_clip") as mock_ken_burns,
        ):
            mock_ken_burns.return_value = None
            # Create a fake output file (ken_burns_clip is mocked so we must create it)
            out_path = tmp_path / "video" / "scene_00.mp4"
            out_path.parent.mkdir(parents=True)
            out_path.write_bytes(b"fake_mp4")

            out = await generate_scene_video(
                VideoGenInput(
                    scene_index=0,
                    channel_id="channel_01",
                    run_dir=str(tmp_path),
                    image_path=str(img_path),
                    prompt="zoom in slowly",
                    duration_seconds=5.0,
                )
            )

        assert out.method == "ken_burns"
        assert out.cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_video_gen_fal_ai(self, tmp_path):
        """fal.ai path is used when vgen_enabled=True and FAL_KEY is set."""
        from src.activities.video_gen import VideoGenInput, generate_scene_video

        img_path = tmp_path / "images" / "scene_00.png"
        img_path.parent.mkdir(parents=True)
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        # Pre-create the output file (shutil.move needs a source to exist)
        tmp_video = tmp_path / "tmp_video.mp4"
        tmp_video.write_bytes(b"fake_mp4_data")

        config_vgen = _make_channel_config(vgen_enabled=True)

        mock_fal_provider = MagicMock()
        mock_fal_provider.generate = AsyncMock(return_value=(str(tmp_video), 0.25))

        with (
            patch(
                "src.activities.video_gen.load_channel_config",
                return_value=config_vgen,
            ),
            patch("src.activities.video_gen.settings.channel_configs_dir", "src/channel_configs"),
            patch("src.activities.video_gen.settings.fal_key", "fake-fal-key"),
            patch("src.activities.video_gen.settings.cost_log_path", str(tmp_path / "cost_log.json")),
            patch(
                "src.activities.video_gen.FalVideoProvider",
                return_value=mock_fal_provider,
            ),
        ):
            out = await generate_scene_video(
                VideoGenInput(
                    scene_index=0,
                    channel_id="channel_01",
                    run_dir=str(tmp_path),
                    image_path=str(img_path),
                    prompt="flying camera over mountains",
                    duration_seconds=5.0,
                )
            )

        assert out.method == "ai_video"
        assert out.cost_usd == pytest.approx(0.25)


class TestThumbnailActivity:
    """generate_thumbnail activity with real Pillow (no external deps)."""

    @pytest.mark.asyncio
    async def test_thumbnail_creates_jpeg(self, tmp_path):
        """generate_thumbnail creates thumbnail.jpg < 2MB from a test PNG."""
        from PIL import Image

        from src.activities.thumbnail import ThumbnailInput, generate_thumbnail

        # Create a test scene_00.png
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        img = Image.new("RGB", (1280, 720), color=(100, 149, 237))
        img.save(str(images_dir / "scene_00.png"), format="PNG")

        with patch("src.activities.thumbnail.settings.font_path", "nonexistent_font.ttf"):
            out = await generate_thumbnail(
                ThumbnailInput(
                    title="테스트 썸네일",
                    channel_id="channel_01",
                    run_dir=str(tmp_path),
                )
            )

        thumb_path = Path(out.file_path)
        assert thumb_path.exists(), "thumbnail.jpg was not created"
        assert thumb_path.suffix == ".jpg"
        assert out.file_size_bytes < 2 * 1024 * 1024, "thumbnail exceeds 2MB limit"


class TestYouTubeUploadActivity:
    """upload_to_youtube activity with mocked Google API."""

    @pytest.mark.asyncio
    async def test_youtube_upload_returns_video_id_and_url(self, tmp_path):
        """upload_to_youtube calls YouTube API and returns video_id and URL."""
        from src.activities.youtube_upload import UploadInput, upload_to_youtube

        # Create a fake video file
        video_path = tmp_path / "final_video.mp4"
        video_path.write_bytes(b"fake_video_data")
        thumbnail_path = tmp_path / "thumbnail.jpg"
        thumbnail_path.write_bytes(b"fake_thumb_data")

        # Create fake credentials file
        creds_file = tmp_path / "yt_creds.json"
        creds_file.write_text(
            json.dumps(
                {
                    "token": "fake_token",
                    "refresh_token": "fake_refresh",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "client_id": "fake_client_id",
                    "client_secret": "fake_secret",
                    "scopes": ["https://www.googleapis.com/auth/youtube.upload"],
                }
            ),
            encoding="utf-8",
        )

        config_with_creds = _make_channel_config()

        # Mock credential loading and YouTube service
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds.refresh_token = "fake_refresh"

        mock_thumbnails_set = MagicMock()
        mock_thumbnails_set.execute = MagicMock(return_value={})

        mock_youtube = MagicMock()
        mock_youtube.videos.return_value.insert.return_value.next_chunk.return_value = (
            None,
            {"id": "testVideoId123"},
        )
        mock_youtube.thumbnails.return_value.set.return_value = mock_thumbnails_set

        with (
            patch(
                "src.activities.youtube_upload.load_channel_config",
                return_value=config_with_creds,
            ),
            patch(
                "src.activities.youtube_upload._load_and_refresh_credentials",
                return_value=mock_creds,
            ),
            patch("src.activities.youtube_upload.build", return_value=mock_youtube),
        ):
            out = await upload_to_youtube(
                UploadInput(
                    video_path=str(video_path),
                    thumbnail_path=str(thumbnail_path),
                    title="테스트 영상 제목",
                    description="테스트 설명",
                    tags=["태그1"],
                    channel_id="channel_01",
                )
            )

        assert out.video_id == "testVideoId123"
        assert "testVideoId123" in out.youtube_url


# ---------------------------------------------------------------------------
# Section 3: Cost tracking integration
# ---------------------------------------------------------------------------


class TestCostTrackerIntegration:
    """CostTracker log-and-retrieval integration tests."""

    def test_cost_tracker_full_run(self, tmp_path):
        """Log 5 entries, get_run_total sums correctly, get_run_breakdown returns 5 items."""
        from src.services.cost_tracker import CostEntry, CostTracker

        log_path = tmp_path / "cost_log.json"
        tracker = CostTracker(log_path=str(log_path))

        workflow_id = "test-workflow-abc123"
        amounts = [0.10, 0.20, 0.15, 0.05, 0.50]

        for i, amount in enumerate(amounts):
            tracker.log(
                CostEntry(
                    workflow_id=workflow_id,
                    channel_id="channel_01",
                    service="fal.ai",
                    step=f"video_gen_scene_{i:02d}",
                    amount_usd=amount,
                    resolution="480p",
                    timestamp="2026-04-02T00:00:00+00:00",
                )
            )

        total = tracker.get_run_total(workflow_id)
        assert total == pytest.approx(sum(amounts))

        breakdown = tracker.get_run_breakdown(workflow_id)
        assert len(breakdown) == 5
        assert all(e.workflow_id == workflow_id for e in breakdown)

    def test_cost_tracker_isolates_workflow_ids(self, tmp_path):
        """get_run_total only sums entries for the given workflow_id, not others."""
        from src.services.cost_tracker import CostEntry, CostTracker

        log_path = tmp_path / "cost_log.json"
        tracker = CostTracker(log_path=str(log_path))

        tracker.log(
            CostEntry(
                workflow_id="wf-A",
                channel_id="channel_01",
                service="fal.ai",
                step="video_gen_scene_00",
                amount_usd=1.00,
                timestamp="2026-04-02T00:00:00+00:00",
            )
        )
        tracker.log(
            CostEntry(
                workflow_id="wf-B",
                channel_id="channel_01",
                service="fal.ai",
                step="video_gen_scene_00",
                amount_usd=2.50,
                timestamp="2026-04-02T00:00:00+00:00",
            )
        )

        assert tracker.get_run_total("wf-A") == pytest.approx(1.00)
        assert tracker.get_run_total("wf-B") == pytest.approx(2.50)


# ---------------------------------------------------------------------------
# Section 4: API response shape tests
# ---------------------------------------------------------------------------


def _make_test_app():
    """Build a FastAPI TestClient without starting a real Temporal connection."""
    from contextlib import asynccontextmanager
    from typing import AsyncGenerator

    from fastapi import FastAPI

    @asynccontextmanager
    async def fake_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """No-op lifespan — inject a mock temporal_client into app.state."""
        app.state.temporal_client = MagicMock()
        yield

    from fastapi import FastAPI

    test_app = FastAPI(lifespan=fake_lifespan)
    from src.api.pipeline import router

    test_app.include_router(router)
    return test_app


class TestAPIResponseShapes:
    """FastAPI endpoint response shapes must match the UI-SPEC contract."""

    def test_trigger_response_shape(self):
        """POST /api/pipeline/trigger returns PipelineTriggerResponse fields."""
        app = _make_test_app()
        client = TestClient(app, raise_server_exceptions=True)

        # Mock the Temporal client start_workflow on app.state
        mock_client = MagicMock()
        mock_client.start_workflow = AsyncMock()
        app.state.temporal_client = mock_client

        with patch(
            "src.api.pipeline.load_channel_config",
            return_value=_make_channel_config(vgen_enabled=False),
        ):
            resp = client.post(
                "/api/pipeline/trigger",
                json={"topic": "비트코인 최신 동향", "channel_id": "channel_01"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert "workflow_id" in body
        assert body["status"] == "started"
        assert "channel_id" in body
        assert "topic" in body

    def test_status_response_shape(self):
        """GET /api/pipeline/status/{id} returns PipelineStatusResponse fields."""
        app = _make_test_app()
        client = TestClient(app, raise_server_exceptions=False)

        mock_desc = MagicMock()
        mock_desc.status.name = "RUNNING"
        mock_desc.start_time = None
        mock_desc.close_time = None

        mock_handle = MagicMock()
        mock_handle.describe = AsyncMock(return_value=mock_desc)
        mock_handle.result = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)
        app.state.temporal_client = mock_client

        resp = client.get("/api/pipeline/status/test-workflow-id-001")

        assert resp.status_code == 200
        body = resp.json()
        assert "workflow_id" in body
        assert "status" in body
        assert body["status"] in ("running", "completed", "failed", "unknown")
        # Optional fields must be present (even if null)
        assert "current_step" in body
        assert "cost_so_far_usd" in body
        assert "youtube_url" in body

    def test_cost_response_shape(self):
        """GET /api/pipeline/cost/{id} returns CostDetailResponse with breakdown array."""
        from src.services.cost_tracker import CostEntry, CostTracker

        app = _make_test_app()

        # Seed the cost_log used by the pipeline API module
        import tempfile

        tmp_dir = tempfile.mkdtemp()
        log_path = Path(tmp_dir) / "cost_log.json"
        tracker = CostTracker(log_path=str(log_path))
        test_wf_id = "cost-test-workflow-999"

        for i in range(3):
            tracker.log(
                CostEntry(
                    workflow_id=test_wf_id,
                    channel_id="channel_01",
                    service="fal.ai",
                    step=f"video_gen_scene_{i:02d}",
                    amount_usd=0.10 * (i + 1),
                    resolution="480p",
                    timestamp="2026-04-02T00:00:00+00:00",
                )
            )

        with patch("src.api.pipeline._cost_tracker", tracker):
            client = TestClient(app, raise_server_exceptions=True)
            resp = client.get(f"/api/pipeline/cost/{test_wf_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert "workflow_id" in body
        assert "channel_id" in body
        assert "total_cost_usd" in body
        assert "breakdown" in body
        assert isinstance(body["breakdown"], list)
        assert len(body["breakdown"]) == 3

        for item in body["breakdown"]:
            assert "service" in item
            assert "step" in item
            assert "amount_usd" in item

    def test_pipeline_params_serializes_with_workflow_params(self):
        """PipelineParams round-trips correctly (used by ContentPipelineWorkflow)."""
        from src.workflows.content_pipeline import PipelineParams

        params = PipelineParams(
            run_id="run-abc123",
            topic="비트코인 투자",
            channel_id="channel_01",
        )
        data = params.model_dump_json()
        restored = PipelineParams.model_validate_json(data)
        assert restored.run_id == "run-abc123"
        assert restored.channel_id == "channel_01"
