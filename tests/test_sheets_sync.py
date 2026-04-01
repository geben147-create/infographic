"""Sheets sync activity tests — gspread mocked, SQLite in-memory."""
from unittest.mock import MagicMock, patch

from sqlmodel import Session, SQLModel, create_engine
from temporalio.testing import ActivityEnvironment

import src.activities.sheets as sheets_mod
from src.activities.sheets import (
    SheetsSyncInput,
    WriteResultInput,
    sync_sheets_to_sqlite,
    write_results_to_sheets,
)


def _make_in_memory_session():
    """Return an open Session backed by an in-memory SQLite DB with schema created."""
    engine = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(engine)
    return Session(engine)


async def test_sync_sheets_to_sqlite():
    """Mocked gspread returns 1 row; activity upserts it, returns rows_added=1."""
    mock_worksheet = MagicMock()
    mock_worksheet.get_all_records.return_value = [
        {"topic": "Test Topic", "channel_id": "ch1", "status": "pending"}
    ]
    mock_spreadsheet = MagicMock()
    mock_spreadsheet.worksheet.return_value = mock_worksheet

    test_session = _make_in_memory_session()

    with (
        patch.object(sheets_mod, "get_sheets_client", return_value=MagicMock()),
        patch.object(sheets_mod, "open_spreadsheet", return_value=mock_spreadsheet),
        patch.object(sheets_mod, "get_session", return_value=test_session),
        patch.object(sheets_mod, "create_sync_log"),
    ):
        env = ActivityEnvironment()
        result = await env.run(sync_sheets_to_sqlite, SheetsSyncInput())

    test_session.close()

    assert result.rows_added == 1
    assert result.rows_updated == 0
    assert result.error is None


async def test_sync_sheets_upsert_updates_existing():
    """Calling twice with same row yields rows_added=0, rows_updated=1."""
    mock_worksheet = MagicMock()
    mock_worksheet.get_all_records.return_value = [
        {"topic": "Test Topic", "channel_id": "ch1", "status": "pending"}
    ]
    mock_spreadsheet = MagicMock()
    mock_spreadsheet.worksheet.return_value = mock_worksheet

    test_session = _make_in_memory_session()

    with (
        patch.object(sheets_mod, "get_sheets_client", return_value=MagicMock()),
        patch.object(sheets_mod, "open_spreadsheet", return_value=mock_spreadsheet),
        patch.object(sheets_mod, "get_session", return_value=test_session),
        patch.object(sheets_mod, "create_sync_log"),
    ):
        env = ActivityEnvironment()
        # First sync — should add the row
        await env.run(sync_sheets_to_sqlite, SheetsSyncInput())
        # Second sync — same sheets_row_id, should update
        result = await env.run(sync_sheets_to_sqlite, SheetsSyncInput())

    test_session.close()

    assert result.rows_added == 0
    assert result.rows_updated == 1


async def test_write_results_to_sheets():
    """Mocked gspread worksheet; activity calls update_cell with correct args."""
    mock_worksheet = MagicMock()
    mock_spreadsheet = MagicMock()
    mock_spreadsheet.worksheet.return_value = mock_worksheet

    with (
        patch.object(sheets_mod, "get_sheets_client", return_value=MagicMock()),
        patch.object(sheets_mod, "open_spreadsheet", return_value=mock_spreadsheet),
    ):
        env = ActivityEnvironment()
        result = await env.run(
            write_results_to_sheets,
            WriteResultInput(
                sheets_row_id="2",
                status="done",
                youtube_url="https://youtube.com/test",
            ),
        )

    assert result.success is True
    assert result.error is None

    # Verify update_cell called correctly: column D (4) = status, column E (5) = url
    mock_worksheet.update_cell.assert_any_call(2, 4, "done")
    mock_worksheet.update_cell.assert_any_call(2, 5, "https://youtube.com/test")


async def test_sync_handles_error():
    """When gspread raises, activity returns SheetsSyncOutput with error field set."""
    with (
        patch.object(
            sheets_mod, "get_sheets_client", side_effect=Exception("API unreachable")
        ),
        patch.object(sheets_mod, "get_session", return_value=_make_in_memory_session()),
        patch.object(sheets_mod, "create_sync_log"),
    ):
        env = ActivityEnvironment()
        result = await env.run(sync_sheets_to_sqlite, SheetsSyncInput())

    assert result.error is not None
    assert "API unreachable" in result.error
    assert result.rows_added == 0
    assert result.rows_updated == 0
