"""
ContentPipelineWorkflow — the main Phase 2 end-to-end pipeline.

Chains all activities in order across typed task queues:
  gpu-queue  : script_gen, image_gen, tts, video_gen, thumbnail
  cpu-queue  : setup_dirs, assemble_video
  (no api-queue step — YouTube upload is manual by operator)

Activity model imports are guarded by imports_passed_through() so that
heavy dependencies (ComfyUI, fal.ai) do not need to be present in the
workflow worker process.
"""
from __future__ import annotations

from datetime import timedelta

from pydantic import BaseModel
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.activities.image_gen import ImageGenInput, ImageGenOutput
    from src.activities.pipeline import SetupDirsInput, SetupDirsOutput
    from src.activities.script_gen import ScriptGenInput, ScriptGenOutput
    from src.activities.tts import TTSInput, TTSOutput
    from src.activities.video_gen import VideoGenInput, VideoGenOutput

    # 02-05 activities (video assembly + thumbnail) — parallel plan
    from src.activities.video_assembly import AssemblyInput, AssemblyOutput
    from src.activities.thumbnail import ThumbnailInput

    # 03-01: quality gate signal payload
    from src.schemas.pipeline import ApprovalSignal


_RETRY_DEFAULT = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
)


class PipelineParams(BaseModel):
    """Input parameters for ContentPipelineWorkflow."""

    run_id: str
    topic: str
    channel_id: str
    quality_gate_enabled: bool = False


class PipelineResult(BaseModel):
    """Output from ContentPipelineWorkflow."""

    video_id: str | None = None
    youtube_url: str | None = None
    video_path: str = ""
    thumbnail_path: str = ""
    total_cost_usd: float = 0.0
    scenes_count: int = 0
    status: str = "ready_to_upload"


@workflow.defn
class ContentPipelineWorkflow:
    """End-to-end YouTube video production workflow.

    Queue routing:
    - gpu-queue: LLM script, SDXL images, TTS, video gen, thumbnail
    - cpu-queue: directory setup, FFmpeg assembly, cleanup
    - api-queue: YouTube upload
    """

    def __init__(self) -> None:
        """Initialize signal state for quality gate.

        CRITICAL for Temporal determinism: signal state MUST be initialized
        in __init__, not inside run(), so signals arriving before run() starts
        are captured correctly.
        """
        self._approved: bool = False
        self._reject_reason: str = ""

    @workflow.signal
    async def approve_video(self, payload: "ApprovalSignal") -> None:
        """Signal handler for quality gate approval/rejection.

        Called by the operator via POST /api/pipeline/{id}/approve.
        Sets _approved and _reject_reason to unblock wait_condition.
        """
        self._approved = payload.approved
        self._reject_reason = payload.reason

    @workflow.run
    async def run(self, params: PipelineParams) -> PipelineResult:
        """Execute the full pipeline from topic to video assembly.

        Stops after video assembly + thumbnail generation and returns
        status="ready_to_upload" so the operator can manually upload
        to YouTube via the download endpoints.

        Args:
            params: run_id, topic, channel_id

        Returns:
            PipelineResult with video_path, thumbnail_path, total_cost_usd, scenes_count.
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
        # Build paths for video and thumbnail (used in return and quality gate)#
        # ------------------------------------------------------------------ #
        thumbnail_path_str = str(
            __import__("pathlib").Path(run_dir) / "thumbnails" / "thumbnail.jpg"
        )

        # ------------------------------------------------------------------ #
        # Step 6.5: Quality gate — wait for human approval (preview only)      #
        # ------------------------------------------------------------------ #
        if params.quality_gate_enabled:
            import asyncio as _asyncio

            try:
                await workflow.wait_condition(
                    lambda: self._approved or bool(self._reject_reason),
                    timeout=timedelta(hours=24),
                )
            except _asyncio.TimeoutError:
                return PipelineResult(
                    status="timeout_rejected",
                    video_id=None,
                    youtube_url=None,
                    video_path=assembly_out.file_path,
                    thumbnail_path=thumbnail_path_str,
                    total_cost_usd=total_cost,
                    scenes_count=len(script.scenes),
                )
            if not self._approved:
                return PipelineResult(
                    status="rejected",
                    video_id=None,
                    youtube_url=None,
                    video_path=assembly_out.file_path,
                    thumbnail_path=thumbnail_path_str,
                    total_cost_usd=total_cost,
                    scenes_count=len(script.scenes),
                )

        # ------------------------------------------------------------------ #
        # Pipeline complete — files ready for manual YouTube upload            #
        # ------------------------------------------------------------------ #
        return PipelineResult(
            video_path=assembly_out.file_path,
            thumbnail_path=thumbnail_path_str,
            total_cost_usd=total_cost,
            scenes_count=len(script.scenes),
            status="ready_to_upload",
        )
