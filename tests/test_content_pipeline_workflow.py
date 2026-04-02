"""
Tests for ContentPipelineWorkflow.

Covers:
- PipelineParams / PipelineResult serialization
- Workflow is decorated with @workflow.defn
- Workflow chains all expected activity names
- Workflow uses correct task queues (gpu-queue, cpu-queue, api-queue)
"""
from __future__ import annotations

import inspect

import pytest

from src.workflows.content_pipeline import (
    ContentPipelineWorkflow,
    PipelineParams,
    PipelineResult,
)


class TestPipelineParamsResult:
    """Validate Pydantic model serialization."""

    def test_pipeline_params_fields(self) -> None:
        p = PipelineParams(run_id="run_abc", topic="AI 시대", channel_id="channel_01")
        assert p.run_id == "run_abc"
        assert p.topic == "AI 시대"
        assert p.channel_id == "channel_01"

    def test_pipeline_params_missing_required_raises(self) -> None:
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PipelineParams(topic="test")  # type: ignore[call-arg]

    def test_pipeline_result_defaults(self) -> None:
        r = PipelineResult()
        assert r.video_id is None
        assert r.youtube_url is None
        assert r.total_cost_usd == 0.0
        assert r.scenes_count == 0
        assert r.status == "ready_to_upload"

    def test_pipeline_result_with_values(self) -> None:
        r = PipelineResult(
            video_id="vid_123",
            youtube_url="https://www.youtube.com/watch?v=vid_123",
            total_cost_usd=1.50,
            scenes_count=5,
            status="completed",
        )
        assert r.video_id == "vid_123"
        assert r.total_cost_usd == 1.50
        assert r.scenes_count == 5


class TestContentPipelineWorkflowStructure:
    """Inspect workflow class structure without running Temporal."""

    def test_workflow_defn_decorator_applied(self) -> None:
        """ContentPipelineWorkflow must be decorated with @workflow.defn."""
        # Temporal marks workflow classes with _temporal_workflow attribute
        assert hasattr(ContentPipelineWorkflow, "__temporal_workflow_definition"), (
            "ContentPipelineWorkflow is missing @workflow.defn"
        )

    def test_workflow_has_run_method(self) -> None:
        assert hasattr(ContentPipelineWorkflow, "run"), (
            "ContentPipelineWorkflow must have a 'run' method"
        )
        assert callable(ContentPipelineWorkflow.run)

    def test_run_is_coroutine(self) -> None:
        assert inspect.iscoroutinefunction(ContentPipelineWorkflow.run), (
            "ContentPipelineWorkflow.run must be async"
        )

    def _get_source(self) -> str:
        import src.workflows.content_pipeline as _mod
        return inspect.getsource(_mod)

    def test_workflow_calls_generate_script(self) -> None:
        src = self._get_source()
        assert "generate_script" in src, (
            "ContentPipelineWorkflow must call generate_script activity"
        )

    def test_workflow_calls_generate_scene_image(self) -> None:
        src = self._get_source()
        assert "generate_scene_image" in src, (
            "ContentPipelineWorkflow must call generate_scene_image activity"
        )

    def test_workflow_calls_generate_tts_audio(self) -> None:
        src = self._get_source()
        assert "generate_tts_audio" in src, (
            "ContentPipelineWorkflow must call generate_tts_audio activity"
        )

    def test_workflow_calls_generate_scene_video(self) -> None:
        src = self._get_source()
        assert "generate_scene_video" in src, (
            "ContentPipelineWorkflow must call generate_scene_video activity"
        )

    def test_workflow_calls_assemble_video(self) -> None:
        src = self._get_source()
        assert "assemble_video" in src, (
            "ContentPipelineWorkflow must call assemble_video activity"
        )

    def test_workflow_calls_generate_thumbnail(self) -> None:
        src = self._get_source()
        assert "generate_thumbnail" in src, (
            "ContentPipelineWorkflow must call generate_thumbnail activity"
        )

    def test_workflow_does_not_call_upload_to_youtube(self) -> None:
        src = self._get_source()
        assert "upload_to_youtube" not in src, (
            "ContentPipelineWorkflow must NOT call upload_to_youtube — Phase 4 removed auto-upload"
        )

    def test_workflow_does_not_call_cleanup_intermediate_files(self) -> None:
        src = self._get_source()
        assert "cleanup_intermediate_files" not in src, (
            "ContentPipelineWorkflow must NOT call cleanup — Phase 4 removed cleanup after upload removed"
        )

    def test_workflow_calls_setup_pipeline_dirs(self) -> None:
        src = self._get_source()
        assert "setup_pipeline_dirs" in src, (
            "ContentPipelineWorkflow must call setup_pipeline_dirs activity"
        )

    def test_workflow_uses_gpu_queue(self) -> None:
        src = self._get_source()
        assert "gpu-queue" in src, (
            "ContentPipelineWorkflow must use gpu-queue for AI generation activities"
        )

    def test_workflow_uses_cpu_queue(self) -> None:
        src = self._get_source()
        assert "cpu-queue" in src, (
            "ContentPipelineWorkflow must use cpu-queue for FFmpeg/assembly activities"
        )

    def test_workflow_uses_api_queue(self) -> None:
        src = self._get_source()
        assert "api-queue" in src, (
            "ContentPipelineWorkflow must use api-queue for YouTube upload"
        )

    def test_workflow_imports_passed_through(self) -> None:
        """Workflow must use imports_passed_through for activity I/O models."""
        src = self._get_source()
        assert "imports_passed_through" in src, (
            "ContentPipelineWorkflow must use workflow.unsafe.imports_passed_through() "
            "for importing activity models"
        )

    def test_pipeline_params_used_in_workflow(self) -> None:
        src = self._get_source()
        assert "PipelineParams" in src

    def test_pipeline_result_used_in_workflow(self) -> None:
        src = self._get_source()
        assert "PipelineResult" in src
