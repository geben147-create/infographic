"""Temporal activities for Google Sheets <-> SQLite sync.

Runs on api-queue (per D-07, D-09).
All gspread calls are isolated to these activities — workflow code never
calls Sheets directly.
"""
from pydantic import BaseModel
from sqlmodel import select
from temporalio import activity

from src.models.content_item import ContentItem
from src.services.db_service import create_sync_log, get_session, upsert_content_item
from src.services.sheets_service import (
    get_sheets_client,
    open_spreadsheet,
    read_content_rows,
    update_sheets_row,
)


class SheetsSyncInput(BaseModel):
    pass  # No input needed — reads config from settings


class SheetsSyncOutput(BaseModel):
    rows_added: int
    rows_updated: int
    error: str | None = None


class WriteResultInput(BaseModel):
    sheets_row_id: str
    status: str
    youtube_url: str = ""


class WriteResultOutput(BaseModel):
    success: bool
    error: str | None = None


@activity.defn
async def sync_sheets_to_sqlite(params: SheetsSyncInput) -> SheetsSyncOutput:
    """Sync Google Sheets rows into SQLite content_items (DATA-01).

    Upserts on sheets_row_id — Sheets is input layer, SQLite is SSOT (DATA-02).
    Logs each sync operation to sync_log table.
    """
    try:
        client = get_sheets_client()
        spreadsheet = open_spreadsheet(client)
        rows = read_content_rows(spreadsheet)

        session = get_session()
        added = 0
        updated = 0

        for row_data in rows:
            existing = session.exec(
                select(ContentItem).where(
                    ContentItem.sheets_row_id == row_data["sheets_row_id"]
                )
            ).first()

            upsert_content_item(session, row_data)

            if existing:
                updated += 1
            else:
                added += 1

        create_sync_log(session, rows_added=added, rows_updated=updated)
        session.close()

        return SheetsSyncOutput(rows_added=added, rows_updated=updated)

    except Exception as e:
        # Log the error in sync_log before returning
        try:
            err_session = get_session()
            create_sync_log(err_session, rows_added=0, rows_updated=0, error=str(e))
            err_session.close()
        except Exception:
            pass
        return SheetsSyncOutput(rows_added=0, rows_updated=0, error=str(e))


@activity.defn
async def write_results_to_sheets(params: WriteResultInput) -> WriteResultOutput:
    """Write pipeline results back to Google Sheets (DATA-03).

    Updates status and YouTube URL in the originating Sheets row.
    Called after pipeline completion to close the Sheets -> SQLite -> Sheets loop.
    """
    try:
        client = get_sheets_client()
        spreadsheet = open_spreadsheet(client)
        row_number = int(params.sheets_row_id)
        update_sheets_row(
            spreadsheet,
            row_number=row_number,
            status=params.status,
            youtube_url=params.youtube_url,
        )
        return WriteResultOutput(success=True)
    except Exception as e:
        return WriteResultOutput(success=False, error=str(e))
