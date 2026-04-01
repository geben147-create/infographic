"""GPU Worker — max_concurrent_activities=1 (per D-06).

Enforces serial GPU execution for ComfyUI, Ollama, IndexTTS-2.
RTX 4070 8GB cannot run multiple GPU tasks concurrently.
"""

import asyncio

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from src.activities.stubs import stub_gpu_activity
from src.config import settings
from src.workflows.pipeline_validation import PipelineValidationWorkflow


async def main() -> None:
    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
        data_converter=pydantic_data_converter,
    )
    worker = Worker(
        client,
        task_queue="gpu-queue",
        workflows=[PipelineValidationWorkflow],
        activities=[stub_gpu_activity],
        max_concurrent_activities=1,
    )
    print("GPU worker started on gpu-queue (max_concurrent_activities=1)")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
