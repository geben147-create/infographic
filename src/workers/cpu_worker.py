"""CPU Worker — max_concurrent_activities=4 (per D-06).

Handles FFmpeg, file ops, thumbnail generation, directory setup/cleanup.
"""

import asyncio

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from src.activities.cleanup import cleanup_intermediate_files
from src.activities.pipeline import setup_pipeline_dirs
from src.activities.stubs import stub_cpu_activity
from src.activities.video_assembly import assemble_video
from src.config import settings
from src.workflows.content_pipeline import ContentPipelineWorkflow


async def main() -> None:
    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
        data_converter=pydantic_data_converter,
    )
    worker = Worker(
        client,
        task_queue="cpu-queue",
        workflows=[ContentPipelineWorkflow],
        activities=[
            stub_cpu_activity,
            setup_pipeline_dirs,
            cleanup_intermediate_files,
            assemble_video,
        ],
        max_concurrent_activities=4,
    )
    print("CPU worker started on cpu-queue (max_concurrent_activities=4)")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
