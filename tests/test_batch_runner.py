"""Tests for scripts/batch_runner.py — mocked Temporal client."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import the module under test
from scripts.batch_runner import run_batch
from src.workflows.content_pipeline import PipelineParams, PipelineResult


@pytest.fixture
def sample_batch_file():
    """Create a temporary batch JSON file with two items."""
    items = [
        {"topic": "AI trends 2026", "channel_id": "channel_01"},
        {"topic": "Bitcoin forecast", "channel_id": "channel_01", "quality_gate_enabled": True},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(items, f)
        return f.name


@pytest.fixture
def mock_client():
    """Mock Temporal client with start_workflow and handle.result."""
    client = MagicMock()
    handle = AsyncMock()
    handle.result = AsyncMock(
        return_value=PipelineResult(
            video_id="vid_abc123",
            youtube_url="https://youtu.be/abc123",
            total_cost_usd=1.50,
            scenes_count=5,
            status="completed",
        )
    )
    client.start_workflow = AsyncMock(return_value=handle)
    return client, handle


@pytest.mark.asyncio
async def test_run_batch_calls_start_workflow_for_each_item(sample_batch_file, mock_client):
    """Test 1: run_batch() reads JSON file and calls client.start_workflow for each item."""
    client, handle = mock_client

    results = await run_batch(sample_batch_file, client=client)

    # Should have called start_workflow twice (one per item)
    assert client.start_workflow.call_count == 2


@pytest.mark.asyncio
async def test_run_batch_sequential_execution(sample_batch_file, mock_client):
    """Test 2: run_batch() awaits handle.result() before starting next workflow (sequential)."""
    client, handle = mock_client

    call_order = []

    async def tracked_start_workflow(*args, **kwargs):
        call_order.append("start")
        return handle

    async def tracked_result():
        call_order.append("result")
        return PipelineResult(
            video_id="vid_x",
            youtube_url="https://youtu.be/x",
            total_cost_usd=1.0,
            scenes_count=3,
            status="completed",
        )

    client.start_workflow = tracked_start_workflow
    handle.result = tracked_result

    await run_batch(sample_batch_file, client=client)

    # Sequential pattern: start, result, start, result (not start, start, result, result)
    assert call_order == ["start", "result", "start", "result"]


@pytest.mark.asyncio
async def test_run_batch_handles_workflow_failure(sample_batch_file, mock_client):
    """Test 3: run_batch() handles workflow failure gracefully — logs error, continues."""
    client, handle = mock_client

    call_count = 0

    async def failing_then_succeeding(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Workflow execution failed")
        return PipelineResult(
            video_id="vid_ok",
            youtube_url="https://youtu.be/ok",
            total_cost_usd=1.0,
            scenes_count=3,
            status="completed",
        )

    handle.result = failing_then_succeeding
    client.start_workflow = AsyncMock(return_value=handle)

    results = await run_batch(sample_batch_file, client=client)

    # Both items processed — first failed, second succeeded
    assert len(results) == 2
    assert results[0]["status"] == "failed"
    assert "error" in results[0]
    assert results[1]["status"] == "completed"


@pytest.mark.asyncio
async def test_run_batch_passes_correct_pipeline_params(sample_batch_file, mock_client):
    """Test 1b: run_batch() passes correct PipelineParams (topic, channel_id) to start_workflow."""
    client, handle = mock_client

    captured_params = []

    async def capture_start_workflow(workflow_fn, params, **kwargs):
        captured_params.append(params)
        return handle

    client.start_workflow = capture_start_workflow

    await run_batch(sample_batch_file, client=client)

    assert len(captured_params) == 2
    assert captured_params[0].topic == "AI trends 2026"
    assert captured_params[0].channel_id == "channel_01"
    assert captured_params[1].topic == "Bitcoin forecast"
    assert captured_params[1].channel_id == "channel_01"
