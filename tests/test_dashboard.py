"""
Tests for dashboard API endpoints.

Tests the /api/dashboard/runs and /api/dashboard/costs endpoints
using FastAPI TestClient with in-memory SQLite.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from src.models.pipeline_run import PipelineRun
from src.models.content_item import ContentItem  # noqa: F401 — register table in metadata
from src.models.sync_log import SyncLog  # noqa: F401 — register table in metadata


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(name="engine")
def engine_fixture():
    """In-memory SQLite engine with all tables created.

    Uses StaticPool so all connections (including those spawned by FastAPI
    request handling) share the same in-memory database instance.
    """
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="session")
def session_fixture(engine):
    """Session bound to the in-memory engine."""
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(engine):
    """TestClient with DB dependency overridden to use in-memory engine."""
    from fastapi import FastAPI
    from sqlmodel import Session
    from src.api.dashboard import router, get_db_session

    app = FastAPI()
    app.include_router(router)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_session
    with TestClient(app) as c:
        yield c


def make_run(
    workflow_id: str,
    channel_id: str,
    status: str = "done",
    total_cost_usd: float | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> PipelineRun:
    return PipelineRun(
        workflow_id=workflow_id,
        channel_id=channel_id,
        status=status,
        total_cost_usd=total_cost_usd,
        started_at=started_at,
        completed_at=completed_at,
    )


# ---------------------------------------------------------------------------
# Test 1: Empty DB returns zero-value response
# ---------------------------------------------------------------------------

def test_list_runs_empty_db(client):
    """GET /api/dashboard/runs returns 200 with empty runs list when DB is empty."""
    response = client.get("/api/dashboard/runs")
    assert response.status_code == 200
    data = response.json()
    assert data["runs"] == []
    assert data["total"] == 0


# ---------------------------------------------------------------------------
# Test 2: Runs are returned sorted by started_at descending
# ---------------------------------------------------------------------------

def test_list_runs_sorted_by_started_at_desc(client, engine):
    """GET /api/dashboard/runs returns runs sorted by started_at descending."""
    now = datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc)
    with Session(engine) as session:
        session.add(make_run("wf-01", "ch-01", started_at=now - timedelta(hours=2)))
        session.add(make_run("wf-02", "ch-01", started_at=now - timedelta(hours=1)))
        session.add(make_run("wf-03", "ch-01", started_at=now))
        session.commit()

    response = client.get("/api/dashboard/runs")
    assert response.status_code == 200
    data = response.json()
    assert len(data["runs"]) == 3
    assert data["total"] == 3
    # Most recent first
    assert data["runs"][0]["workflow_id"] == "wf-03"
    assert data["runs"][1]["workflow_id"] == "wf-02"
    assert data["runs"][2]["workflow_id"] == "wf-01"


# ---------------------------------------------------------------------------
# Test 3: channel_id filter
# ---------------------------------------------------------------------------

def test_list_runs_filter_by_channel_id(client, engine):
    """GET /api/dashboard/runs?channel_id=ch-01 filters to that channel."""
    with Session(engine) as session:
        session.add(make_run("wf-A", "ch-01"))
        session.add(make_run("wf-B", "ch-02"))
        session.add(make_run("wf-C", "ch-01"))
        session.commit()

    response = client.get("/api/dashboard/runs?channel_id=ch-01")
    assert response.status_code == 200
    data = response.json()
    returned_ids = {r["workflow_id"] for r in data["runs"]}
    assert returned_ids == {"wf-A", "wf-C"}
    assert data["total"] == 2


# ---------------------------------------------------------------------------
# Test 4: Empty DB returns zero costs
# ---------------------------------------------------------------------------

def test_cost_summary_empty_db(client):
    """GET /api/dashboard/costs returns 200 with zero total when DB is empty."""
    response = client.get("/api/dashboard/costs")
    assert response.status_code == 200
    data = response.json()
    assert data["total_cost_usd"] == 0.0
    assert data["by_channel"] == []


# ---------------------------------------------------------------------------
# Test 5: days filter only includes recent runs
# ---------------------------------------------------------------------------

def test_cost_summary_days_filter(client, engine):
    """GET /api/dashboard/costs?days=7 excludes runs older than 7 days."""
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        # recent run — within 7 days
        session.add(make_run(
            "wf-recent", "ch-01",
            total_cost_usd=1.0,
            started_at=now - timedelta(days=3),
        ))
        # old run — older than 7 days
        session.add(make_run(
            "wf-old", "ch-01",
            total_cost_usd=5.0,
            started_at=now - timedelta(days=10),
        ))
        session.commit()

    response = client.get("/api/dashboard/costs?days=7")
    assert response.status_code == 200
    data = response.json()
    # Only the recent run should appear
    assert data["total_cost_usd"] == pytest.approx(1.0)
    assert len(data["by_channel"]) == 1
    assert data["by_channel"][0]["channel_id"] == "ch-01"
    assert data["by_channel"][0]["total_cost_usd"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Test 6: Cost aggregation groups by channel_id
# ---------------------------------------------------------------------------

def test_cost_summary_aggregates_by_channel(client, engine):
    """GET /api/dashboard/costs groups total_cost_usd by channel_id."""
    now = datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc)
    with Session(engine) as session:
        session.add(make_run("wf-1", "ch-01", total_cost_usd=1.50, started_at=now - timedelta(days=1)))
        session.add(make_run("wf-2", "ch-01", total_cost_usd=2.50, started_at=now - timedelta(days=1)))
        session.add(make_run("wf-3", "ch-02", total_cost_usd=3.00, started_at=now - timedelta(days=1)))
        # Run with no cost — should be excluded from aggregation
        session.add(make_run("wf-4", "ch-01", total_cost_usd=None, started_at=now - timedelta(days=1)))
        session.commit()

    response = client.get("/api/dashboard/costs?days=30")
    assert response.status_code == 200
    data = response.json()

    assert data["total_cost_usd"] == pytest.approx(7.0)

    by_channel = {row["channel_id"]: row for row in data["by_channel"]}
    assert "ch-01" in by_channel
    assert "ch-02" in by_channel
    assert by_channel["ch-01"]["total_cost_usd"] == pytest.approx(4.0)
    assert by_channel["ch-01"]["run_count"] == 2
    assert by_channel["ch-02"]["total_cost_usd"] == pytest.approx(3.0)
    assert by_channel["ch-02"]["run_count"] == 1
