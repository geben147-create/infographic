"""Google Sheets service — handles read/write operations via gspread 6.x.

Uses service_account() auth (not authorize() — deprecated in 6.x per Pitfall 7).
Credentials path and spreadsheet ID come from Pydantic Settings (D-11).
"""
from typing import Any

import gspread

from src.config import settings


def get_sheets_client() -> gspread.Client:
    """Create authenticated gspread client using service account JSON (per D-11)."""
    return gspread.service_account(filename=settings.google_sheets_credentials)


def open_spreadsheet(client: gspread.Client) -> gspread.Spreadsheet:
    """Open the configured spreadsheet by ID (per D-11)."""
    return client.open_by_key(settings.google_sheets_id)


def read_content_rows(
    spreadsheet: gspread.Spreadsheet, sheet_name: str = "Sheet1"
) -> list[dict[str, Any]]:
    """Read all rows from the content sheet.

    Expected columns: topic, channel_id, status, youtube_url.
    Row number is used as sheets_row_id (row 1 = header, data rows start at 2).
    Returns list of dicts with sheets_row_id = row number string.
    """
    worksheet = spreadsheet.worksheet(sheet_name)
    records = worksheet.get_all_records()
    rows = []
    for i, record in enumerate(records, start=2):  # row 1 is header
        rows.append(
            {
                "sheets_row_id": str(i),
                "topic": record.get("topic", ""),
                "channel_id": record.get("channel_id", ""),
                "status": record.get("status", "pending"),
            }
        )
    return rows


def update_sheets_row(
    spreadsheet: gspread.Spreadsheet,
    row_number: int,
    status: str,
    youtube_url: str = "",
    sheet_name: str = "Sheet1",
) -> None:
    """Update status and youtube_url columns in a specific row (per D-10).

    Column layout assumed:
        A = topic, B = channel_id, C = original_status, D = status, E = youtube_url
    Columns D and E are updated with pipeline results.
    """
    worksheet = spreadsheet.worksheet(sheet_name)
    worksheet.update_cell(row_number, 4, status)  # column D = status
    if youtube_url:
        worksheet.update_cell(row_number, 5, youtube_url)  # column E = youtube_url
