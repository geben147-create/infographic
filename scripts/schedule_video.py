"""Schedule a video for future generation + upload.

Usage: uv run python scripts/schedule_video.py --topic "AI trends" --channel channel_01 --at "2026-04-15T09:00"
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from uuid import uuid4

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleCalendarSpec,
    ScheduleRange,
    ScheduleSpec,
    ScheduleState,
)
from temporalio.contrib.pydantic import pydantic_data_converter

from src.config import settings
from src.workflows.content_pipeline import ContentPipelineWorkflow, PipelineParams


async def schedule_one(
    topic: str,
    channel_id: str,
    publish_at: datetime,
    client: Client | None = None,
) -> str:
    """Create a one-time Temporal schedule for a pipeline run.

    Args:
        topic: Video topic.
        channel_id: Target channel.
        publish_at: When to trigger the workflow.
        client: Optional pre-connected Temporal client (for testing).

    Returns:
        The schedule_id string.
    """
    if client is None:
        client = await Client.connect(
            settings.temporal_host,
            namespace=settings.temporal_namespace,
            data_converter=pydantic_data_converter,
        )

    schedule_id = f"scheduled-{channel_id}-{uuid4().hex[:6]}"
    await client.create_schedule(
        schedule_id,
        Schedule(
            action=ScheduleActionStartWorkflow(
                ContentPipelineWorkflow.run,
                PipelineParams(
                    run_id=schedule_id,
                    topic=topic,
                    channel_id=channel_id,
                ),
                id=schedule_id,
                task_queue="gpu-queue",
            ),
            spec=ScheduleSpec(
                calendars=[
                    ScheduleCalendarSpec(
                        year=[ScheduleRange(start=publish_at.year)],
                        month=[ScheduleRange(start=publish_at.month)],
                        day_of_month=[ScheduleRange(start=publish_at.day)],
                        hour=[ScheduleRange(start=publish_at.hour)],
                        minute=[ScheduleRange(start=publish_at.minute)],
                    )
                ]
            ),
            state=ScheduleState(
                limited_actions=True,
                remaining_actions=1,
            ),
        ),
    )
    print(f"Scheduled {schedule_id} for {publish_at.isoformat()}")
    return schedule_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Schedule a video pipeline run")
    parser.add_argument("--topic", required=True, help="Video topic")
    parser.add_argument("--channel", required=True, help="Channel ID")
    parser.add_argument(
        "--at",
        required=True,
        help="Publish datetime (ISO format, e.g. 2026-04-15T09:00)",
    )
    args = parser.parse_args()
    publish_at = datetime.fromisoformat(args.at)
    asyncio.run(schedule_one(args.topic, args.channel, publish_at))
