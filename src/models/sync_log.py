from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class SyncLog(SQLModel, table=True):
    __tablename__ = "sync_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    synced_at: datetime = Field(default_factory=datetime.utcnow)
    rows_added: int = Field(default=0)
    rows_updated: int = Field(default=0)
    error: Optional[str] = Field(default=None)
