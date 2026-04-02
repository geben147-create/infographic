"""
Dashboard API endpoints for pipeline run visibility and cost aggregation.

Endpoints:
  GET /api/dashboard/runs   — paginated, filterable list of pipeline runs
  GET /api/dashboard/costs  — aggregated cost summary by channel and date range
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Generator

from fastapi import APIRouter, Depends
from sqlmodel import Session, col, func, select

from src.models.pipeline_run import PipelineRun
from src.schemas.dashboard import (
    ChannelCostSummary,
    DashboardCostsResponse,
    DashboardRunsResponse,
    RunSummary,
)
from src.services.db_service import engine

router = APIRouter(prefix="/api/dashboard")


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLModel session."""
    with Session(engine) as session:
        yield session


@router.get("/runs", response_model=DashboardRunsResponse)
def list_runs(
    limit: int = 20,
    offset: int = 0,
    channel_id: str | None = None,
    session: Session = Depends(get_db_session),
) -> DashboardRunsResponse:
    """Return a paginated list of pipeline runs, sorted by started_at descending.

    Args:
        limit: Maximum number of runs to return (default 20).
        offset: Number of runs to skip for pagination (default 0).
        channel_id: Optional filter — only return runs for this channel.
        session: SQLModel session (injected by FastAPI).

    Returns:
        DashboardRunsResponse with runs list, total count, limit, and offset.
    """
    query = select(PipelineRun)
    count_query = select(func.count()).select_from(PipelineRun)

    if channel_id:
        query = query.where(PipelineRun.channel_id == channel_id)
        count_query = count_query.where(PipelineRun.channel_id == channel_id)

    query = query.order_by(col(PipelineRun.started_at).desc())
    query = query.offset(offset).limit(limit)

    runs = session.exec(query).all()
    total = session.exec(count_query).one()

    return DashboardRunsResponse(
        runs=[
            RunSummary(
                workflow_id=r.workflow_id,
                channel_id=r.channel_id,
                status=r.status,
                total_cost_usd=r.total_cost_usd,
                started_at=r.started_at.isoformat() if r.started_at else None,
                completed_at=r.completed_at.isoformat() if r.completed_at else None,
                error_message=r.error_message,
            )
            for r in runs
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/costs", response_model=DashboardCostsResponse)
def cost_summary(
    channel_id: str | None = None,
    days: int = 30,
    session: Session = Depends(get_db_session),
) -> DashboardCostsResponse:
    """Return aggregated cost summary grouped by channel for the given time window.

    Args:
        channel_id: Optional filter — only aggregate costs for this channel.
        days: Number of days back to include (default 30).
        session: SQLModel session (injected by FastAPI).

    Returns:
        DashboardCostsResponse with grand total, days window, and per-channel breakdown.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    query = (
        select(
            PipelineRun.channel_id,
            func.sum(PipelineRun.total_cost_usd).label("total"),
            func.count().label("cnt"),
        )
        .where(
            PipelineRun.started_at >= cutoff,
            PipelineRun.total_cost_usd.is_not(None),  # type: ignore[union-attr]
        )
        .group_by(PipelineRun.channel_id)
    )

    if channel_id:
        query = query.where(PipelineRun.channel_id == channel_id)

    rows = session.exec(query).all()

    by_channel = [
        ChannelCostSummary(
            channel_id=row[0],
            total_cost_usd=row[1] or 0.0,
            run_count=row[2],
        )
        for row in rows
    ]
    grand_total = sum(c.total_cost_usd for c in by_channel)

    return DashboardCostsResponse(
        total_cost_usd=grand_total,
        days=days,
        by_channel=by_channel,
    )
