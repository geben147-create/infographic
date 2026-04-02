"""GPU Worker — max_concurrent_activities=1 (per D-06).

Enforces serial GPU execution for ComfyUI, Ollama, IndexTTS-2.
RTX 4070 8GB cannot run multiple GPU tasks concurrently.
"""

import asyncio

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from src.activities.image_gen import generate_scene_image
from src.activities.script_gen import generate_script
from src.activities.stubs import stub_gpu_activity
from src.activities.thumbnail import generate_thumbnail
from src.activities.tts import generate_tts_audio
from src.activities.video_gen import generate_scene_video
from src.config import settings
from src.workflows.content_pipeline import ContentPipelineWorkflow
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
        workflows=[PipelineValidationWorkflow, ContentPipelineWorkflow],
        activities=[
            stub_gpu_activity,
            generate_script,
            generate_scene_image,
            generate_tts_audio,
            generate_scene_video,
            generate_thumbnail,
        ],
        max_concurrent_activities=1,
    )
    print("GPU worker started on gpu-queue (max_concurrent_activities=1)")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
