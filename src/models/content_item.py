from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class ContentItem(SQLModel, table=True):
    __tablename__ = "content_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    sheets_row_id: str = Field(index=True, unique=True)
    topic: str
    channel_id: str
    status: str = Field(default="pending")  # pending / running / done / failed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
