"""
Response schemas for the dashboard API endpoints.

Exports: DashboardRunsResponse, DashboardCostsResponse, RunSummary, ChannelCostSummary
"""
from __future__ import annotations

from pydantic import BaseModel


class RunSummary(BaseModel):
    """Summary of a single pipeline run for dashboard listing."""

    workflow_id: str
    channel_id: str
    status: str
    total_cost_usd: float | None = None
    youtube_url: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None


class DashboardRunsResponse(BaseModel):
    """Response for GET /api/dashboard/runs — paginated pipeline run list."""

    runs: list[RunSummary]
    total: int
    limit: int
    offset: int


class ChannelCostSummary(BaseModel):
    """Aggregated cost for a single channel."""

    channel_id: str
    total_cost_usd: float
    run_count: int


class DashboardCostsResponse(BaseModel):
    """Response for GET /api/dashboard/costs — cost aggregation by channel."""

    total_cost_usd: float
    days: int
    by_channel: list[ChannelCostSummary]
