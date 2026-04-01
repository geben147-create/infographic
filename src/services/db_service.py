from datetime import datetime
from typing import Optional

from sqlmodel import Session, create_engine, select

from src.config import settings
from src.models.content_item import ContentItem
from src.models.pipeline_run import PipelineRun
from src.models.sync_log import SyncLog

engine = create_engine(settings.database_url, echo=False)


def get_session() -> Session:
    """Return a new SQLModel session using the configured engine."""
    return Session(engine)


def upsert_content_item(session: Session, data: dict) -> ContentItem:  # type: ignore[type-arg]
    """Create or update a ContentItem by sheets_row_id (upsert key)."""
    existing = session.exec(
        select(ContentItem).where(ContentItem.sheets_row_id == data["sheets_row_id"])
    ).first()
    if existing:
        for key, value in data.items():
            if key != "id":
                setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    item = ContentItem(**data)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def create_pipeline_run(session: Session, data: dict) -> PipelineRun:  # type: ignore[type-arg]
    """Create a new PipelineRun row."""
    run = PipelineRun(**data)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def update_pipeline_run(
    session: Session, workflow_id: str, updates: dict  # type: ignore[type-arg]
) -> Optional[PipelineRun]:
    """Update an existing PipelineRun by workflow_id. Returns None if not found."""
    run = session.exec(
        select(PipelineRun).where(PipelineRun.workflow_id == workflow_id)
    ).first()
    if not run:
        return None
    for key, value in updates.items():
        setattr(run, key, value)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def create_sync_log(
    session: Session,
    rows_added: int,
    rows_updated: int,
    error: Optional[str] = None,
) -> SyncLog:
    """Create a new SyncLog entry recording the results of a Sheets sync."""
    log = SyncLog(rows_added=rows_added, rows_updated=rows_updated, error=error)
    session.add(log)
    session.commit()
    session.refresh(log)
    return log
