from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class PipelineRun(SQLModel, table=True):
    __tablename__ = "pipeline_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    workflow_id: str = Field(index=True, unique=True)
    channel_id: str
    content_item_id: Optional[int] = Field(default=None, foreign_key="content_items.id")
    status: str = Field(default="pending")  # pending / running / done / failed
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    result_json: Optional[str] = Field(default=None)
    total_cost_usd: Optional[float] = Field(default=None)
    video_path: Optional[str] = Field(default=None)
    thumbnail_path: Optional[str] = Field(default=None)
