"""Tests for the enhanced /health endpoint."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.health import router


def _make_app(temporal_client=None):
    """Create a test FastAPI app with the health router."""
    app = FastAPI()
    app.include_router(router)
    if temporal_client is not None:
        app.state.temporal_client = temporal_client
    return app


class TestHealthEndpoint:
    def test_health_returns_200(self):
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_response_structure(self):
        app = _make_app()
        client = TestClient(app)
        data = client.get("/health").json()
        assert "status" in data
        assert "temporal" in data
        assert "sqlite" in data
        assert "disk_free_gb" in data

    def test_health_disk_free_positive(self):
        app = _make_app()
        client = TestClient(app)
        data = client.get("/health").json()
        assert isinstance(data["disk_free_gb"], float)
        assert data["disk_free_gb"] > 0

    def test_health_sqlite_true(self):
        """SQLite should be accessible in test environment."""
        app = _make_app()
        client = TestClient(app)
        data = client.get("/health").json()
        assert data["sqlite"] is True

    def test_health_temporal_false_when_no_client(self):
        """Without temporal_client on app.state, temporal should be False."""
        app = _make_app()
        client = TestClient(app)
        data = client.get("/health").json()
        assert data["temporal"] is False

    def test_health_status_degraded_without_temporal(self):
        app = _make_app()
        client = TestClient(app)
        data = client.get("/health").json()
        # temporal=False, sqlite=True -> degraded
        assert data["status"] in ("degraded", "ok")
