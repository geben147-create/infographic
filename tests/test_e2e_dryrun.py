"""
E2E dry-run tests: verify ContentPipelineWorkflow no longer uploads to YouTube.

These tests verify at the source level that the upload step is removed,
and at the model level that PipelineResult supports ready_to_upload status.
"""
import inspect

import pytest

from src.workflows.content_pipeline import (
    ContentPipelineWorkflow,
    PipelineResult,
)


class TestPipelineResultModel:
    """Verify PipelineResult supports the new ready_to_upload flow."""

    def test_ready_to_upload_status(self):
        result = PipelineResult(
            video_path="/data/pipeline/test-run/final/output.mp4",
            thumbnail_path="/data/pipeline/test-run/thumbnails/thumbnail.jpg",
            total_cost_usd=1.50,
            scenes_count=5,
            status="ready_to_upload",
        )
        assert result.status == "ready_to_upload"

    def test_video_path_set(self):
        result = PipelineResult(
            video_path="/data/pipeline/test-run/final/output.mp4",
            thumbnail_path="/test.jpg",
            status="ready_to_upload",
        )
        assert result.video_path.endswith(".mp4")

    def test_thumbnail_path_set(self):
        result = PipelineResult(
            video_path="/test.mp4",
            thumbnail_path="/data/pipeline/test-run/thumbnails/thumbnail.jpg",
            status="ready_to_upload",
        )
        assert result.thumbnail_path.endswith(".jpg")

    def test_cost_tracking_preserved(self):
        result = PipelineResult(
            video_path="/test.mp4",
            thumbnail_path="/test.jpg",
            total_cost_usd=2.50,
            scenes_count=3,
            status="ready_to_upload",
        )
        assert result.total_cost_usd == 2.50
        assert result.scenes_count == 3

    def test_backward_compat_fields(self):
        """video_id and youtube_url still exist but default to None."""
        result = PipelineResult(status="ready_to_upload", video_path="x", thumbnail_path="y")
        assert result.video_id is None
        assert result.youtube_url is None


class TestWorkflowSourceNoUpload:
    """Verify upload_to_youtube is completely removed from workflow source."""

    def test_no_upload_to_youtube_in_run_method(self):
        source = inspect.getsource(ContentPipelineWorkflow.run)
        assert "upload_to_youtube" not in source, (
            "upload_to_youtube should be removed from ContentPipelineWorkflow.run()"
        )

    def test_no_cleanup_in_run_method(self):
        source = inspect.getsource(ContentPipelineWorkflow.run)
        assert "cleanup_intermediate_files" not in source, (
            "cleanup_intermediate_files should be removed — operator needs files for download"
        )

    def test_ready_to_upload_in_run_method(self):
        source = inspect.getsource(ContentPipelineWorkflow.run)
        assert "ready_to_upload" in source, (
            "Workflow run() must set status to ready_to_upload"
        )

    def test_no_upload_import(self):
        """UploadInput/UploadOutput should not be imported in workflow module."""
        import src.workflows.content_pipeline as wf_module

        source = inspect.getsource(wf_module)
        assert "UploadInput" not in source
        assert "UploadOutput" not in source


class TestPipelineStatusEnum:
    """Verify PipelineStatus enum includes ready_to_upload."""

    def test_ready_to_upload_enum_value(self):
        from src.schemas.pipeline import PipelineStatus

        assert hasattr(PipelineStatus, "ready_to_upload")
        assert PipelineStatus.ready_to_upload.value == "ready_to_upload"


class TestPipelineRunModel:
    """Verify PipelineRun DB model has video_path and thumbnail_path."""

    def test_video_path_field(self):
        from src.models.pipeline_run import PipelineRun

        run = PipelineRun(
            workflow_id="test-123",
            channel_id="ch1",
            video_path="/data/pipeline/test-123/final/output.mp4",
        )
        assert run.video_path == "/data/pipeline/test-123/final/output.mp4"

    def test_thumbnail_path_field(self):
        from src.models.pipeline_run import PipelineRun

        run = PipelineRun(
            workflow_id="test-123",
            channel_id="ch1",
            thumbnail_path="/data/pipeline/test-123/thumbnails/thumbnail.jpg",
        )
        assert run.thumbnail_path == "/data/pipeline/test-123/thumbnails/thumbnail.jpg"

    def test_paths_optional(self):
        from src.models.pipeline_run import PipelineRun

        run = PipelineRun(workflow_id="test-456", channel_id="ch1")
        assert run.video_path is None
        assert run.thumbnail_path is None
