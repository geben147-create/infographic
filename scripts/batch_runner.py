"""Batch video pipeline runner.

Usage: uv run python scripts/batch_runner.py batch.json

batch.json format:
[
  {"topic": "AI trends 2026", "channel_id": "channel_01"},
  {"topic": "Bitcoin forecast", "channel_id": "channel_01", "quality_gate_enabled": true}
]
"""
from __future__ import annotations

import asyncio
import json
import sys
from uuid import uuid4

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from src.config import settings
from src.workflows.content_pipeline import ContentPipelineWorkflow, PipelineParams


async def run_batch(batch_file: str, client: Client | None = None) -> list[dict]:
    """Run multiple pipeline workflows sequentially.

    Args:
        batch_file: Path to JSON file with list of {topic, channel_id, quality_gate_enabled?}.
        client: Optional pre-connected Temporal client (for testing).

    Returns:
        List of result dicts with workflow_id, status, youtube_url, cost.
    """
    with open(batch_file) as f:
        items = json.load(f)

    if client is None:
        client = await Client.connect(
            settings.temporal_host,
            namespace=settings.temporal_namespace,
            data_converter=pydantic_data_converter,
        )

    results = []
    for i, item in enumerate(items):
        wf_id = f"batch-{uuid4().hex[:8]}"
        print(f"[{i+1}/{len(items)}] Starting {wf_id}: {item['topic']}")
        try:
            handle = await client.start_workflow(
                ContentPipelineWorkflow.run,
                PipelineParams(
                    run_id=wf_id,
                    topic=item["topic"],
                    channel_id=item["channel_id"],
                ),
                id=wf_id,
                task_queue="gpu-queue",
            )
            result = await handle.result()
            results.append(
                {
                    "workflow_id": wf_id,
                    "status": result.status,
                    "youtube_url": result.youtube_url,
                    "cost_usd": result.total_cost_usd,
                }
            )
            print(f"  Completed: {result.youtube_url}, cost=${result.total_cost_usd:.2f}")
        except Exception as exc:
            results.append(
                {
                    "workflow_id": wf_id,
                    "status": "failed",
                    "error": str(exc),
                }
            )
            print(f"  Failed: {exc}")
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/batch_runner.py <batch.json>")
        sys.exit(1)
    asyncio.run(run_batch(sys.argv[1]))
