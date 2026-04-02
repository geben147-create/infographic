"""
Tests for the quality gate API endpoints (Plan 03-01, Task 2).

Covers:
- POST /api/pipeline/{id}/approve with approved=True calls handle.signal("approve_video", ...)
- POST /api/pipeline/{id}/approve with approved=False and reason sends correct signal
- GET /api/pipeline/{id}/video returns 404 when file does not exist
- GET /api/pipeline/{id}/video returns 200 with video/mp4 when file exists
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared helpers — same fake_lifespan pattern as test_pipeline_integration.py
# ---------------------------------------------------------------------------


def _make_test_app(mock_client: MagicMock | None = None) -> FastAPI:
    """Build a FastAPI test app with injected mock Temporal client."""

    @asynccontextmanager
    async def fake_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        app.state.temporal_client = mock_client or MagicMock()
        yield

    app = FastAPI(lifespan=fake_lifespan)
    from src.api.pipeline import router

    app.include_router(router)
    return app


# ---------------------------------------------------------------------------
# POST /api/pipeline/{id}/approve
# ---------------------------------------------------------------------------


class TestApproveEndpoint:
    """POST /api/pipeline/{workflow_id}/approve sends Temporal signal."""

    def test_approve_sends_signal_approved_true(self):
        """approved=True calls handle.signal('approve_video', ApprovalSignal(approved=True, reason=''))."""
        from src.schemas.pipeline import ApprovalSignal

        mock_handle = MagicMock()
        mock_handle.signal = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)

        app = _make_test_app(mock_client)
        client = TestClient(app, raise_server_exceptions=True)
        app.state.temporal_client = mock_client

        resp = client.post(
            "/api/pipeline/test-wf-001/approve",
            json={"approved": True},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["signalled"] is True
        assert body["workflow_id"] == "test-wf-001"
        assert body["approved"] is True

        # Verify the signal name and payload
        mock_client.get_workflow_handle.assert_called_once_with("test-wf-001")
        mock_handle.signal.assert_called_once()
        call_args = mock_handle.signal.call_args
        assert call_args[0][0] == "approve_video"
        signal_payload = call_args[0][1]
        assert isinstance(signal_payload, ApprovalSignal)
        assert signal_payload.approved is True
        assert signal_payload.reason == ""

    def test_approve_sends_signal_approved_false_with_reason(self):
        """approved=False with reason calls handle.signal with approved=False."""
        from src.schemas.pipeline import ApprovalSignal

        mock_handle = MagicMock()
        mock_handle.signal = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)

        app = _make_test_app(mock_client)
        client = TestClient(app, raise_server_exceptions=True)
        app.state.temporal_client = mock_client

        resp = client.post(
            "/api/pipeline/test-wf-002/approve",
            json={"approved": False, "reason": "bad audio quality"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["signalled"] is True
        assert body["approved"] is False

        call_args = mock_handle.signal.call_args
        signal_payload = call_args[0][1]
        assert isinstance(signal_payload, ApprovalSignal)
        assert signal_payload.approved is False
        assert signal_payload.reason == "bad audio quality"

    def test_approve_returns_workflow_id(self):
        """Response includes workflow_id matching the path parameter."""
        mock_handle = MagicMock()
        mock_handle.signal = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)

        app = _make_test_app(mock_client)
        client = TestClient(app, raise_server_exceptions=True)
        app.state.temporal_client = mock_client

        resp = client.post(
            "/api/pipeline/my-special-workflow-id/approve",
            json={"approved": True},
        )
        assert resp.status_code == 200
        assert resp.json()["workflow_id"] == "my-special-workflow-id"


# ---------------------------------------------------------------------------
# GET /api/pipeline/{id}/video
# ---------------------------------------------------------------------------


class TestVideoPreviewEndpoint:
    """GET /api/pipeline/{workflow_id}/video serves assembled MP4."""

    def test_video_returns_404_when_file_missing(self, tmp_path):
        """Returns 404 when no video file exists for the workflow."""
        mock_client = MagicMock()
        app = _make_test_app(mock_client)
        client = TestClient(app, raise_server_exceptions=False)
        app.state.temporal_client = mock_client

        resp = client.get("/api/pipeline/nonexistent-workflow/video")
        assert resp.status_code == 404

    def test_video_returns_200_with_mp4_content_type(self, tmp_path, monkeypatch):
        """Returns 200 with video/mp4 content type when file exists."""
        import pathlib

        from src.api import pipeline as pipeline_module

        workflow_id = "wf-with-video"

        # Create the expected file path: data/pipeline/{workflow_id}/final/output.mp4
        video_dir = tmp_path / "pipeline" / workflow_id / "final"
        video_dir.mkdir(parents=True)
        video_file = video_dir / "output.mp4"
        video_file.write_bytes(b"fake_mp4_content")

        # Patch pathlib.Path so the endpoint resolves to our tmp_path
        original_path_cls = pathlib.Path

        class PatchedPath:
            """Intercepts only the data/pipeline/... construction."""

            def __new__(cls, *args):  # type: ignore[override]
                joined = "/".join(str(a) for a in args)
                if joined.startswith("data/pipeline"):
                    # Replace 'data/pipeline' prefix with tmp_path / 'pipeline'
                    suffix = joined[len("data/pipeline"):]
                    return original_path_cls(str(tmp_path / "pipeline") + suffix)
                return original_path_cls(*args)

        monkeypatch.setattr(pipeline_module, "pathlib", type("M", (), {"Path": PatchedPath})())

        mock_client = MagicMock()
        app = _make_test_app(mock_client)
        client = TestClient(app, raise_server_exceptions=True)
        app.state.temporal_client = mock_client

        resp = client.get(f"/api/pipeline/{workflow_id}/video")
        assert resp.status_code == 200
        assert "video/mp4" in resp.headers.get("content-type", "")

    def test_video_endpoint_exists_in_router(self):
        """GET /api/pipeline/{id}/video route is registered (not 405 or 404 due to routing)."""
        mock_client = MagicMock()
        app = _make_test_app(mock_client)
        client = TestClient(app, raise_server_exceptions=False)
        app.state.temporal_client = mock_client

        # Should be 404 (file not found), NOT 405 (method not allowed)
        # which would indicate the route is not registered at all
        resp = client.get("/api/pipeline/some-id/video")
        assert resp.status_code != 405, "Route not registered — check router definition"
        assert resp.status_code == 404  # file not found is correct

    def test_approve_endpoint_does_not_conflict_with_delete(self):
        """POST /{id}/approve does not conflict with DELETE /{id}."""
        mock_handle = MagicMock()
        mock_handle.signal = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)

        app = _make_test_app(mock_client)
        client = TestClient(app, raise_server_exceptions=True)
        app.state.temporal_client = mock_client

        # Both routes must exist without 404/405 confusion
        resp = client.post(
            "/api/pipeline/conflict-test/approve",
            json={"approved": True},
        )
        assert resp.status_code == 200
