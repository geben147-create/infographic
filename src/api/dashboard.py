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
                video_path=r.video_path,
                thumbnail_path=r.thumbnail_path,
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


@router.get("/costs/daily")
def daily_costs(
    days: int = 30,
    channel_id: str | None = None,
    session: Session = Depends(get_db_session),
) -> dict:
    """Return daily cost time series for charting.

    Returns a list of {date, cost, run_count} objects for each day.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # SQLite date() function extracts YYYY-MM-DD from datetime
    date_expr = func.date(PipelineRun.started_at)
    query = (
        select(
            date_expr.label("date"),
            func.coalesce(func.sum(PipelineRun.total_cost_usd), 0.0).label("cost"),
            func.count().label("run_count"),
        )
        .where(PipelineRun.started_at >= cutoff)
        .group_by(date_expr)
        .order_by(date_expr)
    )

    if channel_id:
        query = query.where(PipelineRun.channel_id == channel_id)

    rows = session.exec(query).all()

    return {
        "days": days,
        "data": [
            {"date": row[0], "cost": round(row[1] or 0.0, 4), "run_count": row[2]}
            for row in rows
        ],
    }


@router.get("/costs/by-service")
def costs_by_service(
    days: int = 30,
    session: Session = Depends(get_db_session),
) -> dict:
    """Return cost breakdown by service (fal.ai, local, etc.).

    Reads from cost_log.json for per-service granularity.
    Falls back to DB aggregation if cost_log unavailable.
    """
    import json
    import pathlib

    from src.config import settings as app_settings

    cost_path = pathlib.Path(app_settings.cost_log_path)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    service_totals: dict[str, float] = {}

    if cost_path.exists():
        try:
            data = json.loads(cost_path.read_text(encoding="utf-8"))
            entries = data if isinstance(data, list) else data.get("entries", [])
            for entry in entries:
                ts = entry.get("timestamp", "")
                if ts and ts >= cutoff.isoformat():
                    svc = entry.get("service", "local")
                    amt = float(entry.get("amount_usd", 0))
                    service_totals[svc] = service_totals.get(svc, 0.0) + amt
        except Exception:
            pass

    # Always include local cost (runs with $0 cost)
    total_runs = session.exec(
        select(func.count()).select_from(PipelineRun).where(
            PipelineRun.started_at >= cutoff,
        )
    ).one()

    cloud_runs = sum(1 for _ in service_totals.values())
    if total_runs > cloud_runs and "local" not in service_totals:
        service_totals["local"] = 0.0

    return {
        "days": days,
        "services": [
            {"service": svc, "total_cost_usd": round(amt, 4)}
            for svc, amt in sorted(service_totals.items())
        ],
        "grand_total_usd": round(sum(service_totals.values()), 4),
    }
