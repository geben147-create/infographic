"""
Tests for image generation activity, ComfyUI provider, fal.ai image provider, and cost tracker.

Tests use mocks for all external I/O (WebSocket, HTTP, fal_client).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# CostTracker tests
# ---------------------------------------------------------------------------


def test_cost_tracker_log_creates_file(tmp_path: Path) -> None:
    """CostTracker.log() creates cost_log.json if it doesn't exist."""
    from src.services.cost_tracker import CostEntry, CostTracker

    log_path = tmp_path / "cost_log.json"
    tracker = CostTracker(log_path=str(log_path))
    entry = CostEntry(
        workflow_id="wf-001",
        channel_id="ch-tech",
        service="fal.ai",
        step="video_gen_scene_00",
        amount_usd=0.35,
        timestamp="2026-04-02T00:00:00Z",
    )
    tracker.log(entry)
    assert log_path.exists()
    data = json.loads(log_path.read_text())
    assert len(data) == 1
    assert data[0]["workflow_id"] == "wf-001"
    assert data[0]["amount_usd"] == pytest.approx(0.35)


def test_cost_tracker_log_appends(tmp_path: Path) -> None:
    """CostTracker.log() appends without overwriting existing entries."""
    from src.services.cost_tracker import CostEntry, CostTracker

    log_path = tmp_path / "cost_log.json"
    tracker = CostTracker(log_path=str(log_path))

    for i in range(3):
        tracker.log(
            CostEntry(
                workflow_id="wf-001",
                channel_id="ch-tech",
                service="fal.ai",
                step=f"step_{i}",
                amount_usd=0.10,
                timestamp="2026-04-02T00:00:00Z",
            )
        )

    data = json.loads(log_path.read_text())
    assert len(data) == 3


def test_cost_tracker_get_run_total(tmp_path: Path) -> None:
    """CostTracker.get_run_total() sums entries for a given workflow_id."""
    from src.services.cost_tracker import CostEntry, CostTracker

    log_path = tmp_path / "cost_log.json"
    tracker = CostTracker(log_path=str(log_path))

    tracker.log(
        CostEntry(
            workflow_id="wf-001",
            channel_id="ch",
            service="fal.ai",
            step="s1",
            amount_usd=0.10,
            timestamp="2026-04-02T00:00:00Z",
        )
    )
    tracker.log(
        CostEntry(
            workflow_id="wf-001",
            channel_id="ch",
            service="fal.ai",
            step="s2",
            amount_usd=0.25,
            timestamp="2026-04-02T00:00:00Z",
        )
    )
    tracker.log(
        CostEntry(
            workflow_id="wf-999",
            channel_id="ch",
            service="fal.ai",
            step="s3",
            amount_usd=5.00,
            timestamp="2026-04-02T00:00:00Z",
        )
    )

    total = tracker.get_run_total("wf-001")
    assert total == pytest.approx(0.35)


def test_cost_tracker_get_run_breakdown(tmp_path: Path) -> None:
    """CostTracker.get_run_breakdown() returns all entries for workflow_id."""
    from src.services.cost_tracker import CostEntry, CostTracker

    log_path = tmp_path / "cost_log.json"
    tracker = CostTracker(log_path=str(log_path))

    tracker.log(
        CostEntry(
            workflow_id="wf-A",
            channel_id="ch",
            service="fal.ai",
            step="s1",
            amount_usd=0.10,
            timestamp="2026-04-02T00:00:00Z",
        )
    )
    tracker.log(
        CostEntry(
            workflow_id="wf-B",
            channel_id="ch",
            service="fal.ai",
            step="s2",
            amount_usd=0.20,
            timestamp="2026-04-02T00:00:00Z",
        )
    )

    breakdown = tracker.get_run_breakdown("wf-A")
    assert len(breakdown) == 1
    assert breakdown[0].step == "s1"


def test_cost_tracker_empty_log_returns_zero(tmp_path: Path) -> None:
    """get_run_total returns 0.0 when log file does not exist."""
    from src.services.cost_tracker import CostTracker

    log_path = tmp_path / "does_not_exist.json"
    tracker = CostTracker(log_path=str(log_path))
    assert tracker.get_run_total("any-id") == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# ComfyUIProvider tests
# ---------------------------------------------------------------------------


def _make_ws_messages() -> list:
    """Generate a realistic sequence of ComfyUI WebSocket messages.

    Includes an 'executed' message with image info so the production code
    can skip the history endpoint fallback.
    """
    return [
        json.dumps({"type": "status", "data": {"status": {"exec_info": {"queue_remaining": 1}}}}),
        json.dumps({"type": "execution_start", "data": {"prompt_id": "test-prompt-id"}}),
        json.dumps({"type": "executing", "data": {"node": "4", "prompt_id": "test-prompt-id"}}),
        json.dumps({
            "type": "executed",
            "data": {
                "node": "9",
                "prompt_id": "test-prompt-id",
                "output": {
                    "images": [{"filename": "gsd_output_00001_.png", "subfolder": "", "type": "output"}]
                },
            },
        }),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "test-prompt-id"}}),
    ]


def test_comfyui_provider_returns_bytes() -> None:
    """ComfyUIProvider.generate() returns PNG bytes after WebSocket completion."""
    fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    ws_messages = _make_ws_messages()
    msg_iter = iter(ws_messages)

    class FakeWS:
        def settimeout(self, t: float) -> None:
            pass

        def send(self, data: str) -> None:
            pass

        def recv(self) -> str:
            return next(msg_iter)

        def close(self) -> None:
            pass

    with (
        patch("websocket.create_connection", return_value=FakeWS()),
        patch("httpx.post") as mock_post,
        patch("httpx.get") as mock_get,
    ):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"prompt_id": "test-prompt-id"},
        )
        mock_get.return_value = MagicMock(
            status_code=200, content=fake_image_bytes
        )

        from src.services.comfyui_client import ComfyUIProvider

        provider = ComfyUIProvider(
            base_url="http://localhost:8188",
            checkpoint="sdxl.safetensors",
        )
        import asyncio
        result = asyncio.run(
            provider.generate(prompt="A mountain landscape", width=512, height=512)
        )

    assert isinstance(result, bytes)
    assert len(result) > 0


def test_comfyui_provider_sets_timeout() -> None:
    """ComfyUIProvider sets WebSocket timeout of 120 seconds."""
    timeouts: list[float] = []
    ws_messages = _make_ws_messages()
    msg_iter = iter(ws_messages)

    class FakeWS:
        def settimeout(self, t: float) -> None:
            timeouts.append(t)

        def send(self, data: str) -> None:
            pass

        def recv(self) -> str:
            return next(msg_iter)

        def close(self) -> None:
            pass

    with (
        patch("websocket.create_connection", return_value=FakeWS()),
        patch("httpx.post") as mock_post,
        patch("httpx.get") as mock_get,
    ):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"prompt_id": "test-prompt-id"},
        )
        mock_get.return_value = MagicMock(
            status_code=200, content=b"\x89PNG\r\n\x1a\n"
        )

        from src.services.comfyui_client import ComfyUIProvider

        provider = ComfyUIProvider(
            base_url="http://localhost:8188",
            checkpoint="sdxl.safetensors",
        )
        import asyncio
        asyncio.run(provider.generate(prompt="Test"))

    assert 120 in timeouts


# ---------------------------------------------------------------------------
# FalImageProvider tests
# ---------------------------------------------------------------------------


def test_fal_image_provider_calls_run() -> None:
    """FalImageProvider.generate() calls fal_client.run with correct model."""
    fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50

    async def fake_run_async(model: str, arguments: dict) -> dict:
        return {"images": [{"url": "https://example.com/image.png"}]}

    with (
        patch("fal_client.run_async", side_effect=fake_run_async),
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_resp = MagicMock()
        mock_resp.content = fake_image_bytes
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        from src.services.fal_client import FalImageProvider

        provider = FalImageProvider(model="flux-kontext")
        import asyncio
        result = asyncio.run(
            provider.generate(prompt="A sunset", width=1024, height=1024)
        )

    assert isinstance(result, bytes)


def test_fal_video_provider_calls_submit() -> None:
    """FalVideoProvider.generate() calls upload_file_async then submit_async."""
    fake_video_bytes = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100

    async def fake_upload(path: str) -> str:
        return "https://cdn.fal.ai/tmp/image.png"

    class FakeHandle:
        async def __aiter__(self):
            yield {"type": "progress", "completed": 1, "total": 5}

        async def get(self) -> dict:
            return {"video": {"url": "https://cdn.fal.ai/tmp/video.mp4"}}

    async def fake_submit_async(model: str, arguments: dict) -> FakeHandle:
        return FakeHandle()

    with (
        patch("fal_client.upload_file_async", side_effect=fake_upload),
        patch("fal_client.submit_async", side_effect=fake_submit_async),
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_resp = MagicMock()
        mock_resp.content = fake_video_bytes
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        from src.services.fal_client import FalVideoProvider
        import tempfile, asyncio

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n")
            img_path = f.name

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                provider = FalVideoProvider(model="kling-2.5-turbo")
                video_path, cost = asyncio.run(
                    provider.generate(
                        image_path=img_path,
                        prompt="cinematic pan",
                        duration_seconds=5.0,
                    )
                )
        finally:
            os.unlink(img_path)

    assert video_path.endswith(".mp4")
    assert cost == pytest.approx(0.35)  # 0.07 * 5


# ---------------------------------------------------------------------------
# generate_scene_image activity tests
# ---------------------------------------------------------------------------


def _make_channel_config(
    image_model: str = "local:sdxl-juggernaut",
    channel_id: str = "test-channel",
) -> "ChannelConfig":  # type: ignore[name-defined]
    from src.models.channel_config import ChannelConfig

    return ChannelConfig(
        channel_id=channel_id,
        niche="tech",
        image_model=image_model,
    )


async def test_generate_scene_image_uses_comfyui_for_local(tmp_path: Path) -> None:
    """generate_scene_image selects ComfyUIProvider when image_model is 'local:*'."""
    from src.activities.image_gen import ImageGenInput, generate_scene_image
    from temporalio.testing import ActivityEnvironment

    fake_bytes = b"\x89PNG\r\n\x1a\nFAKE"

    cfg = _make_channel_config(image_model="local:sdxl-juggernaut")

    with (
        patch("src.activities.image_gen.load_channel_config", return_value=cfg),
        patch(
            "src.activities.image_gen.ComfyUIProvider.generate",
            new_callable=AsyncMock,
            return_value=fake_bytes,
        ),
    ):
        env = ActivityEnvironment()
        result = await env.run(
            generate_scene_image,
            ImageGenInput(
                scene_index=3,
                prompt="A mountain",
                channel_id="test-channel",
                run_dir=str(tmp_path),
            ),
        )

    expected = tmp_path / "images" / "scene_03.png"
    assert result.file_path == str(expected)
    assert expected.exists()
    assert expected.read_bytes() == fake_bytes


async def test_generate_scene_image_uses_fal_for_fal(tmp_path: Path) -> None:
    """generate_scene_image selects FalImageProvider when image_model is 'fal:*'."""
    from src.activities.image_gen import ImageGenInput, generate_scene_image
    from temporalio.testing import ActivityEnvironment

    fake_bytes = b"\x89PNG\r\n\x1a\nFAKEFAL"
    cfg = _make_channel_config(image_model="fal:flux-kontext")

    with (
        patch("src.activities.image_gen.load_channel_config", return_value=cfg),
        patch(
            "src.activities.image_gen.FalImageProvider.generate",
            new_callable=AsyncMock,
            return_value=fake_bytes,
        ),
    ):
        env = ActivityEnvironment()
        result = await env.run(
            generate_scene_image,
            ImageGenInput(
                scene_index=0,
                prompt="A sunset",
                channel_id="test-channel",
                run_dir=str(tmp_path),
            ),
        )

    expected = tmp_path / "images" / "scene_00.png"
    assert result.file_path == str(expected)
    assert expected.exists()


async def test_generate_scene_image_path_format(tmp_path: Path) -> None:
    """generate_scene_image saves to {run_dir}/images/scene_{NN}.png with zero-padded index."""
    from src.activities.image_gen import ImageGenInput, generate_scene_image
    from temporalio.testing import ActivityEnvironment

    fake_bytes = b"\x89PNG\r\n\x1a\n"
    cfg = _make_channel_config(image_model="local:sdxl")

    with (
        patch("src.activities.image_gen.load_channel_config", return_value=cfg),
        patch(
            "src.activities.image_gen.ComfyUIProvider.generate",
            new_callable=AsyncMock,
            return_value=fake_bytes,
        ),
    ):
        env = ActivityEnvironment()
        result = await env.run(
            generate_scene_image,
            ImageGenInput(
                scene_index=7,
                prompt="Test",
                channel_id="test-channel",
                run_dir=str(tmp_path),
            ),
        )

    assert result.file_path.endswith("scene_07.png")
