"""
Tests for TTS providers and generate_tts_audio Temporal activity.

TDD RED phase — tests written before implementation.
CosyVoice2 and Kokoro are not installed in the test environment;
they are mocked throughout.
"""
from __future__ import annotations

import io
import struct
import wave
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers — minimal valid WAV bytes
# ---------------------------------------------------------------------------


def _make_wav_bytes(duration_seconds: float = 2.0, sample_rate: int = 22050) -> bytes:
    """Return minimal valid WAV bytes for the given duration."""
    num_frames = int(duration_seconds * sample_rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_frames)
    return buf.getvalue()


SAMPLE_WAV_BYTES = _make_wav_bytes(duration_seconds=3.0)


# ---------------------------------------------------------------------------
# CosyVoiceTTSProvider tests
# ---------------------------------------------------------------------------


class TestCosyVoiceTTSProvider:
    """Tests for CosyVoiceTTSProvider."""

    @pytest.mark.asyncio
    async def test_synthesize_raises_application_error_when_not_installed(self):
        """CosyVoiceTTSProvider raises ApplicationError when CosyVoice2 not installed."""
        from temporalio.exceptions import ApplicationError

        from src.services.tts_client import CosyVoiceTTSProvider

        provider = CosyVoiceTTSProvider()

        # CosyVoice2 is not installed — import must fail gracefully
        with patch.dict("sys.modules", {"cosyvoice": None, "CosyVoice2": None}):
            with pytest.raises(ApplicationError, match="CosyVoice2 not installed"):
                await provider.synthesize("안녕하세요")

    @pytest.mark.asyncio
    async def test_synthesize_returns_wav_bytes_when_installed(self):
        """CosyVoiceTTSProvider returns WAV bytes from the inference result."""
        from src.services.tts_client import CosyVoiceTTSProvider

        fake_model = MagicMock()
        fake_model.inference_sft.return_value = [{"tts_speech": MagicMock(numpy=lambda: b"fakewav")}]

        mock_cosyvoice2 = MagicMock(return_value=fake_model)

        with patch("src.services.tts_client._synthesize_cosyvoice", AsyncMock(return_value=SAMPLE_WAV_BYTES)):
            provider = CosyVoiceTTSProvider()
            result = await provider.synthesize("안녕하세요")

        assert isinstance(result, bytes)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# KokoroTTSProvider tests
# ---------------------------------------------------------------------------


class TestKokoroTTSProvider:
    """Tests for KokoroTTSProvider."""

    @pytest.mark.asyncio
    async def test_synthesize_raises_application_error_when_not_installed(self):
        """KokoroTTSProvider raises ApplicationError when kokoro not installed."""
        from temporalio.exceptions import ApplicationError

        from src.services.tts_client import KokoroTTSProvider

        provider = KokoroTTSProvider()

        with patch.dict("sys.modules", {"kokoro": None}):
            with pytest.raises(ApplicationError, match="Kokoro not installed"):
                await provider.synthesize("Hello world")

    @pytest.mark.asyncio
    async def test_synthesize_returns_wav_bytes_when_installed(self):
        """KokoroTTSProvider returns WAV bytes from inference."""
        from src.services.tts_client import KokoroTTSProvider

        with patch("src.services.tts_client._synthesize_kokoro", AsyncMock(return_value=SAMPLE_WAV_BYTES)):
            provider = KokoroTTSProvider()
            result = await provider.synthesize("Hello world")

        assert isinstance(result, bytes)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# get_tts_provider tests
# ---------------------------------------------------------------------------


class TestGetTTSProvider:
    """Tests for the get_tts_provider factory function."""

    def test_cosyvoice2_model_spec_returns_cosyvoice_provider(self):
        """get_tts_provider('local:cosyvoice2') returns CosyVoiceTTSProvider."""
        from src.services.tts_client import CosyVoiceTTSProvider, get_tts_provider

        provider = get_tts_provider("local:cosyvoice2")
        assert isinstance(provider, CosyVoiceTTSProvider)

    def test_kokoro_model_spec_returns_kokoro_provider(self):
        """get_tts_provider('local:kokoro') returns KokoroTTSProvider."""
        from src.services.tts_client import KokoroTTSProvider, get_tts_provider

        provider = get_tts_provider("local:kokoro")
        assert isinstance(provider, KokoroTTSProvider)

    def test_unknown_model_spec_raises_value_error(self):
        """get_tts_provider raises ValueError for unknown model."""
        from src.services.tts_client import get_tts_provider

        with pytest.raises(ValueError, match="Unsupported TTS model"):
            get_tts_provider("local:unknown-tts-model")


# ---------------------------------------------------------------------------
# generate_tts_audio activity tests
# ---------------------------------------------------------------------------


class TestGenerateTTSAudioActivity:
    """Tests for the generate_tts_audio Temporal activity."""

    @pytest.mark.asyncio
    async def test_activity_saves_wav_to_correct_path(self, tmp_path):
        """generate_tts_audio saves WAV file to {run_dir}/audio/scene_NN.wav."""
        from src.activities.tts import TTSInput, generate_tts_audio

        run_dir = tmp_path / "run001"
        (run_dir / "audio").mkdir(parents=True)

        with (
            patch(
                "src.activities.tts.load_channel_config",
                return_value=_make_channel_config("test_ch"),
            ),
            patch(
                "src.services.tts_client._synthesize_cosyvoice",
                AsyncMock(return_value=SAMPLE_WAV_BYTES),
            ),
        ):
            params = TTSInput(
                scene_index=3,
                text="안녕하세요, 오늘의 주제는 투자입니다.",
                channel_id="test_ch",
                run_dir=str(run_dir),
            )
            output = await generate_tts_audio(params)

        wav_path = run_dir / "audio" / "scene_03.wav"
        assert wav_path.exists(), f"Expected WAV at {wav_path}"
        assert output.file_path == str(wav_path)

    @pytest.mark.asyncio
    async def test_activity_returns_correct_duration(self, tmp_path):
        """generate_tts_audio returns duration_seconds from WAV header."""
        from src.activities.tts import TTSInput, generate_tts_audio

        run_dir = tmp_path / "run002"
        (run_dir / "audio").mkdir(parents=True)

        # 3.0 second WAV
        wav_bytes = _make_wav_bytes(duration_seconds=3.0, sample_rate=22050)

        with (
            patch(
                "src.activities.tts.load_channel_config",
                return_value=_make_channel_config("test_ch"),
            ),
            patch(
                "src.services.tts_client._synthesize_cosyvoice",
                AsyncMock(return_value=wav_bytes),
            ),
        ):
            params = TTSInput(
                scene_index=0,
                text="테스트 텍스트입니다.",
                channel_id="test_ch",
                run_dir=str(run_dir),
            )
            output = await generate_tts_audio(params)

        # Allow small float tolerance
        assert abs(output.duration_seconds - 3.0) < 0.1

    @pytest.mark.asyncio
    async def test_activity_uses_scene_index_zero_padded(self, tmp_path):
        """Filename uses zero-padded scene index: scene_01, scene_10, etc."""
        from src.activities.tts import TTSInput, generate_tts_audio

        run_dir = tmp_path / "run003"
        (run_dir / "audio").mkdir(parents=True)

        with (
            patch(
                "src.activities.tts.load_channel_config",
                return_value=_make_channel_config("test_ch"),
            ),
            patch(
                "src.services.tts_client._synthesize_cosyvoice",
                AsyncMock(return_value=SAMPLE_WAV_BYTES),
            ),
        ):
            params = TTSInput(
                scene_index=1,
                text="두 번째 장면",
                channel_id="test_ch",
                run_dir=str(run_dir),
            )
            output = await generate_tts_audio(params)

        assert output.file_path.endswith("scene_01.wav")

    @pytest.mark.asyncio
    async def test_activity_raises_application_error_on_provider_failure(self, tmp_path):
        """generate_tts_audio re-raises ApplicationError when provider fails."""
        from temporalio.exceptions import ApplicationError

        from src.activities.tts import TTSInput, generate_tts_audio

        run_dir = tmp_path / "run004"
        (run_dir / "audio").mkdir(parents=True)

        async def failing_synth(text, voice_ref=""):
            raise ApplicationError("CosyVoice2 not installed")

        with (
            patch(
                "src.activities.tts.load_channel_config",
                return_value=_make_channel_config("test_ch"),
            ),
            patch(
                "src.services.tts_client._synthesize_cosyvoice",
                failing_synth,
            ),
        ):
            params = TTSInput(
                scene_index=0,
                text="테스트",
                channel_id="test_ch",
                run_dir=str(run_dir),
            )
            with pytest.raises(ApplicationError, match="CosyVoice2 not installed"):
                await generate_tts_audio(params)

    @pytest.mark.asyncio
    async def test_activity_provider_selected_from_channel_config(self, tmp_path):
        """Provider is selected based on tts_model in channel config."""
        from src.activities.tts import TTSInput, generate_tts_audio

        run_dir = tmp_path / "run005"
        (run_dir / "audio").mkdir(parents=True)

        kokoro_config = _make_channel_config("test_ch", tts_model="local:kokoro")

        with (
            patch(
                "src.activities.tts.load_channel_config",
                return_value=kokoro_config,
            ),
            patch(
                "src.services.tts_client._synthesize_kokoro",
                AsyncMock(return_value=SAMPLE_WAV_BYTES),
            ),
        ):
            params = TTSInput(
                scene_index=0,
                text="Hello world",
                channel_id="test_ch",
                run_dir=str(run_dir),
            )
            output = await generate_tts_audio(params)

        assert output.file_path.endswith("scene_00.wav")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_channel_config(channel_id: str, tts_model: str = "local:cosyvoice2"):
    """Create a minimal ChannelConfig for testing."""
    from src.models.channel_config import ChannelConfig

    return ChannelConfig(
        channel_id=channel_id,
        niche="금융",
        language="ko",
        llm_model="local:qwen3:14b",
        tts_model=tts_model,
        tts_voice_reference="voices/default_ko.wav",
        prompt_template="script_default.j2",
        tags=["투자", "금융"],
    )
