"""
ContentPipelineWorkflow — the main Phase 2 end-to-end pipeline.

Chains all activities in order across typed task queues:
  gpu-queue  : script_gen, image_gen, tts, video_gen, thumbnail
  cpu-queue  : setup_dirs, assemble_video, cleanup
  api-queue  : youtube_upload

Activity model imports are guarded by imports_passed_through() so that
heavy dependencies (ComfyUI, fal.ai, googleapiclient) do not need to be
present in the workflow worker process.
"""
from __future__ import annotations

from datetime import timedelta

from pydantic import BaseModel
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.activities.cleanup import CleanupInput
    from src.activities.image_gen import ImageGenInput, ImageGenOutput
    from src.activities.pipeline import SetupDirsInput, SetupDirsOutput
    from src.activities.script_gen import ScriptGenInput, ScriptGenOutput
    from src.activities.tts import TTSInput, TTSOutput
    from src.activities.video_gen import VideoGenInput, VideoGenOutput
    from src.activities.youtube_upload import UploadInput, UploadOutput

    # 02-05 activities (video assembly + thumbnail) — parallel plan
    from src.activities.video_assembly import AssemblyInput, AssemblyOutput
    from src.activities.thumbnail import ThumbnailInput


_RETRY_DEFAULT = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
)

_RETRY_UPLOAD = RetryPolicy(
    maximum_attempts=5,
    initial_interval=timedelta(seconds=10),
    backoff_coefficient=2.0,
)


class PipelineParams(BaseModel):
    """Input parameters for ContentPipelineWorkflow."""

    run_id: str
    topic: str
    channel_id: str


class PipelineResult(BaseModel):
    """Output from ContentPipelineWorkflow."""

    video_id: str | None = None
    youtube_url: str | None = None
    total_cost_usd: float = 0.0
    scenes_count: int = 0
    status: str = "completed"


@workflow.defn
class ContentPipelineWorkflow:
    """End-to-end YouTube video production workflow.

    Queue routing:
    - gpu-queue: LLM script, SDXL images, TTS, video gen, thumbnail
    - cpu-queue: directory setup, FFmpeg assembly, cleanup
    - api-queue: YouTube upload
    """

    @workflow.run
    async def run(self, params: PipelineParams) -> PipelineResult:
        """Execute the full pipeline from topic to YouTube upload.

        Args:
            params: run_id, topic, channel_id

        Returns:
            PipelineResult with video_id, youtube_url, total_cost_usd, scenes_count.
        """
        total_cost: float = 0.0

        # ------------------------------------------------------------------ #
        # Step 1: Setup run directory tree (cpu-queue)                         #
        # ------------------------------------------------------------------ #
        setup_out: SetupDirsOutput = await workflow.execute_activity(
            "setup_pipeline_dirs",
            SetupDirsInput(workflow_run_id=params.run_id),
            task_queue="cpu-queue",
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_RETRY_DEFAULT,
            result_type=SetupDirsOutput,
        )
        run_dir: str = setup_out.base_path

        # ------------------------------------------------------------------ #
        # Step 2: Generate script (gpu-queue — Ollama/Qwen3 uses GPU)         #
        # ------------------------------------------------------------------ #
        script_out: ScriptGenOutput = await workflow.execute_activity(
            "generate_script",
            ScriptGenInput(
                topic=params.topic,
                channel_id=params.channel_id,
                run_dir=run_dir,
            ),
            task_queue="gpu-queue",
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=_RETRY_DEFAULT,
            result_type=ScriptGenOutput,
        )
        script = script_out.script

        # ------------------------------------------------------------------ #
        # Step 3: Per-scene image + TTS (gpu-queue, serial due to VRAM limit)  #
        # ------------------------------------------------------------------ #
        tts_outputs: list = []
        image_paths: list[str] = []

        for i, scene in enumerate(script.scenes):
            img_out: ImageGenOutput = await workflow.execute_activity(
                "generate_scene_image",
                ImageGenInput(
                    scene_index=i,
                    prompt=scene.image_prompt,
                    channel_id=params.channel_id,
                    run_dir=run_dir,
                ),
                task_queue="gpu-queue",
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=_RETRY_DEFAULT,
                result_type=ImageGenOutput,
            )
            image_paths.append(img_out.file_path)

            tts_out: TTSOutput = await workflow.execute_activity(
                "generate_tts_audio",
                TTSInput(
                    scene_index=i,
                    text=scene.narration,
                    channel_id=params.channel_id,
                    run_dir=run_dir,
                ),
                task_queue="gpu-queue",
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=_RETRY_DEFAULT,
                result_type=TTSOutput,
            )
            tts_outputs.append(tts_out)

        # ------------------------------------------------------------------ #
        # Step 4: Per-scene video generation (gpu-queue)                       #
        # ------------------------------------------------------------------ #
        for i, scene in enumerate(script.scenes):
            tts_out = tts_outputs[i]
            video_out: VideoGenOutput = await workflow.execute_activity(
                "generate_scene_video",
                VideoGenInput(
                    scene_index=i,
                    channel_id=params.channel_id,
                    run_dir=run_dir,
                    image_path=image_paths[i],
                    prompt=scene.image_prompt,
                    duration_seconds=tts_out.duration_seconds,
                ),
                task_queue="gpu-queue",
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=_RETRY_DEFAULT,
                result_type=VideoGenOutput,
            )
            total_cost += video_out.cost_usd

        # ------------------------------------------------------------------ #
        # Step 5: Generate thumbnail (gpu-queue — uses ComfyUI/Pillow)         #
        # ------------------------------------------------------------------ #
        await workflow.execute_activity(
            "generate_thumbnail",
            ThumbnailInput(
                title=script.title,
                channel_id=params.channel_id,
                run_dir=run_dir,
            ),
            task_queue="gpu-queue",
            start_to_close_timeout=timedelta(minutes=3),
            retry_policy=_RETRY_DEFAULT,
        )

        # ------------------------------------------------------------------ #
        # Step 6: Assemble final video (cpu-queue — FFmpeg)                    #
        # ------------------------------------------------------------------ #
        assembly_out: AssemblyOutput = await workflow.execute_activity(
            "assemble_video",
            AssemblyInput(
                scene_count=len(script.scenes),
                run_dir=run_dir,
            ),
            task_queue="cpu-queue",
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=_RETRY_DEFAULT,
            result_type=AssemblyOutput,
        )

        # ------------------------------------------------------------------ #
        # Step 7: Upload to YouTube (api-queue)                                #
        # ------------------------------------------------------------------ #
        upload_out: UploadOutput = await workflow.execute_activity(
            "upload_to_youtube",
            UploadInput(
                video_path=assembly_out.file_path,
                thumbnail_path=str(
                    __import__("pathlib").Path(run_dir) / "thumbnails" / "thumbnail.jpg"
                ),
                title=script.title,
                description=script.description,
                tags=script.tags,
                channel_id=params.channel_id,
            ),
            task_queue="api-queue",
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=_RETRY_UPLOAD,
            result_type=UploadOutput,
        )

        # ------------------------------------------------------------------ #
        # Step 8: Cleanup intermediate files (cpu-queue)                       #
        # ------------------------------------------------------------------ #
        await workflow.execute_activity(
            "cleanup_intermediate_files",
            CleanupInput(workflow_run_id=params.run_id),
            task_queue="cpu-queue",
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_RETRY_DEFAULT,
        )

        return PipelineResult(
            video_id=upload_out.video_id,
            youtube_url=upload_out.youtube_url,
            total_cost_usd=total_cost,
            scenes_count=len(script.scenes),
            status="completed",
        )
