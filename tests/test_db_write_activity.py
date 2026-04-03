"""
Tests for the save_pipeline_run_result activity (src/activities/db_write.py).

Covers:
- SaveRunResultInput model round-trip
- Activity updates status, video_path, thumbnail_path, total_cost_usd, completed_at
- Activity sets error_message when provided
- Activity is a no-op (no crash) when workflow_id row does not exist
- trigger_pipeline inserts a pipeline_runs row (integration)
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.activities.db_write import SaveRunResultInput, save_pipeline_run_result
from src.models.pipeline_run import PipelineRun
from src.services.db_service import create_pipeline_run, update_pipeline_run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _in_memory_engine():
    """Create a fresh in-memory SQLite engine with all tables."""
    engine = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_run(engine, workflow_id: str, channel_id: str = "channel_01") -> PipelineRun:
    """Insert a running PipelineRun row and return it."""
    with Session(engine) as session:
        run = create_pipeline_run(
            session,
            {
                "workflow_id": workflow_id,
                "channel_id": channel_id,
                "status": "running",
                "started_at": datetime.now(timezone.utc),
            },
        )
    return run


# ---------------------------------------------------------------------------
# SaveRunResultInput serialization
# ---------------------------------------------------------------------------


class TestSaveRunResultInput:
    def test_round_trip(self):
        inp = SaveRunResultInput(
            workflow_id="pipeline-abc123",
            status="ready_to_upload",
            video_path="/data/pipeline/pipeline-abc123/final/output.mp4",
            thumbnail_path="/data/pipeline/pipeline-abc123/thumbnails/thumbnail.jpg",
            total_cost_usd=1.25,
            scenes_count=5,
        )
        restored = SaveRunResultInput.model_validate_json(inp.model_dump_json())
        assert restored == inp

    def test_error_message_defaults_to_empty_string(self):
        inp = SaveRunResultInput(
            workflow_id="wf-x",
            status="ready_to_upload",
            video_path="",
            thumbnail_path="",
            total_cost_usd=0.0,
            scenes_count=0,
        )
        assert inp.error_message == ""


# ---------------------------------------------------------------------------
# save_pipeline_run_result activity
# ---------------------------------------------------------------------------


class TestSavePipelineRunResultActivity:
    @pytest.mark.asyncio
    async def test_updates_status_and_paths(self):
        """Activity sets status, video_path, thumbnail_path, total_cost_usd."""
        mem_engine = _in_memory_engine()
        wf_id = "pipeline-test-001"
        _seed_run(mem_engine, wf_id)

        params = SaveRunResultInput(
            workflow_id=wf_id,
            status="ready_to_upload",
            video_path="/data/pipeline/pipeline-test-001/final/output.mp4",
            thumbnail_path="/data/pipeline/pipeline-test-001/thumbnails/thumbnail.jpg",
            total_cost_usd=2.50,
            scenes_count=5,
        )

        with patch("src.activities.db_write.engine", mem_engine):
            await save_pipeline_run_result(params)

        with Session(mem_engine) as session:
            from sqlmodel import select
            run = session.exec(
                select(PipelineRun).where(PipelineRun.workflow_id == wf_id)
            ).first()

        assert run is not None
        assert run.status == "ready_to_upload"
        assert run.video_path == "/data/pipeline/pipeline-test-001/final/output.mp4"
        assert run.thumbnail_path == "/data/pipeline/pipeline-test-001/thumbnails/thumbnail.jpg"
        assert run.total_cost_usd == pytest.approx(2.50)

    @pytest.mark.asyncio
    async def test_sets_completed_at(self):
        """Activity sets completed_at to a recent datetime."""
        mem_engine = _in_memory_engine()
        wf_id = "pipeline-test-002"
        _seed_run(mem_engine, wf_id)

        params = SaveRunResultInput(
            workflow_id=wf_id,
            status="ready_to_upload",
            video_path="/data/pipeline/pipeline-test-002/final/output.mp4",
            thumbnail_path="/data/pipeline/pipeline-test-002/thumbnails/thumbnail.jpg",
            total_cost_usd=0.0,
            scenes_count=3,
        )

        before = datetime.now(timezone.utc)
        with patch("src.activities.db_write.engine", mem_engine):
            await save_pipeline_run_result(params)
        after = datetime.now(timezone.utc)

        with Session(mem_engine) as session:
            from sqlmodel import select
            run = session.exec(
                select(PipelineRun).where(PipelineRun.workflow_id == wf_id)
            ).first()

        assert run.completed_at is not None
        # completed_at must be between before and after (timezone-aware comparison)
        completed = run.completed_at.replace(tzinfo=timezone.utc) if run.completed_at.tzinfo is None else run.completed_at
        assert before <= completed <= after

    @pytest.mark.asyncio
    async def test_sets_error_message_on_failure(self):
        """Activity stores error_message when provided (failed runs)."""
        mem_engine = _in_memory_engine()
        wf_id = "pipeline-test-003"
        _seed_run(mem_engine, wf_id)

        params = SaveRunResultInput(
            workflow_id=wf_id,
            status="failed",
            video_path="",
            thumbnail_path="",
            total_cost_usd=0.0,
            scenes_count=0,
            error_message="FFmpeg assembly failed: codec not found",
        )

        with patch("src.activities.db_write.engine", mem_engine):
            await save_pipeline_run_result(params)

        with Session(mem_engine) as session:
            from sqlmodel import select
            run = session.exec(
                select(PipelineRun).where(PipelineRun.workflow_id == wf_id)
            ).first()

        assert run.status == "failed"
        assert run.error_message == "FFmpeg assembly failed: codec not found"

    @pytest.mark.asyncio
    async def test_empty_paths_stored_as_none(self):
        """Empty video_path / thumbnail_path are stored as NULL, not empty string."""
        mem_engine = _in_memory_engine()
        wf_id = "pipeline-test-004"
        _seed_run(mem_engine, wf_id)

        params = SaveRunResultInput(
            workflow_id=wf_id,
            status="failed",
            video_path="",
            thumbnail_path="",
            total_cost_usd=0.0,
            scenes_count=0,
        )

        with patch("src.activities.db_write.engine", mem_engine):
            await save_pipeline_run_result(params)

        with Session(mem_engine) as session:
            from sqlmodel import select
            run = session.exec(
                select(PipelineRun).where(PipelineRun.workflow_id == wf_id)
            ).first()

        assert run.video_path is None
        assert run.thumbnail_path is None

    @pytest.mark.asyncio
    async def test_no_crash_when_row_missing(self):
        """Activity does not raise if no row exists for workflow_id (update_pipeline_run returns None)."""
        mem_engine = _in_memory_engine()

        params = SaveRunResultInput(
            workflow_id="nonexistent-workflow",
            status="ready_to_upload",
            video_path="",
            thumbnail_path="",
            total_cost_usd=0.0,
            scenes_count=0,
        )

        # Should not raise even if update_pipeline_run returns None
        with patch("src.activities.db_write.engine", mem_engine):
            await save_pipeline_run_result(params)


# ---------------------------------------------------------------------------
# trigger_pipeline DB insert (integration)
# ---------------------------------------------------------------------------


class TestTriggerPipelineDBInsert:
    """POST /api/pipeline/trigger must insert a pipeline_runs row."""

    def test_trigger_inserts_pipeline_run(self):
        """Calling trigger_pipeline creates a PipelineRun row with status=running."""
        from contextlib import asynccontextmanager
        from typing import AsyncGenerator
        from unittest.mock import AsyncMock

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        # Import all models to ensure SQLModel.metadata is populated before create_all
        import src.models.pipeline_run  # noqa: F401
        import src.models.content_item  # noqa: F401
        from sqlalchemy.pool import StaticPool
        from sqlmodel import SQLModel as _SQLModel

        # Use StaticPool so all connections share the same in-memory DB instance
        mem_engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        _SQLModel.metadata.create_all(mem_engine)

        @asynccontextmanager
        async def fake_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
            app.state.temporal_client = MagicMock()
            yield

        test_app = FastAPI(lifespan=fake_lifespan)
        from src.api.pipeline import router
        test_app.include_router(router)

        mock_client = MagicMock()
        mock_client.start_workflow = AsyncMock()
        test_app.state.temporal_client = mock_client

        from src.models.channel_config import ChannelConfig

        fake_config = ChannelConfig(
            channel_id="channel_01",
            niche="general",
            language="ko",
            llm_model="local:qwen3",
            image_model="local:sdxl",
            tts_model="local:cosyvoice2",
            video_model="local:wan2gp",
            prompt_template="script_default.j2",
            tags=[],
            vgen_enabled=False,
        )

        with (
            patch("src.api.pipeline.load_channel_config", return_value=fake_config),
            patch("src.api.pipeline.engine", mem_engine),
        ):
            client = TestClient(test_app, raise_server_exceptions=True)
            resp = client.post(
                "/api/pipeline/trigger",
                json={"topic": "AI 시대", "channel_id": "channel_01"},
            )

        assert resp.status_code == 200
        workflow_id = resp.json()["workflow_id"]

        # Verify DB row was created
        with Session(mem_engine) as session:
            from sqlmodel import select
            run = session.exec(
                select(PipelineRun).where(PipelineRun.workflow_id == workflow_id)
            ).first()

        assert run is not None, "pipeline_runs row was not created by trigger"
        assert run.status == "running"
        assert run.channel_id == "channel_01"
        assert run.started_at is not None
