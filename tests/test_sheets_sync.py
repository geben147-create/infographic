"""Sheets sync activity tests — validates sync_sheets_to_sqlite and
write_results_to_sheets using mocked gspread via ActivityEnvironment.
"""
from unittest.mock import MagicMock, patch

from temporalio.testing import ActivityEnvironment

from src.activities.sheets import (
    SheetsSyncInput,
    WriteResultInput,
    sync_sheets_to_sqlite,
    write_results_to_sheets,
)


def _make_mock_spreadsheet(records: list[dict]) -> MagicMock:  # type: ignore[type-arg]
    """Build a mock gspread Spreadsheet returning given records."""
    mock_worksheet = MagicMock()
    mock_worksheet.get_all_records.return_value = records
    mock_spreadsheet = MagicMock()
    mock_spreadsheet.worksheet.return_value = mock_worksheet
    return mock_spreadsheet


async def test_sync_sheets_to_sqlite():
    """Mocked gspread returns one row; activity upserts it, returns rows_added=1."""
    records = [{"topic": "Test Topic", "channel_id": "ch1", "status": "pending"}]
    mock_spreadsheet = _make_mock_spreadsheet(records)

    with (
        patch("src.activities.sheets.get_sheets_client", return_value=MagicMock()),
        patch("src.activities.sheets.open_spreadsheet", return_value=mock_spreadsheet),
        patch(
            "src.activities.sheets.read_content_rows",
            return_value=[
                {
                    "sheets_row_id": "2",
                    "topic": "Test Topic",
                    "channel_id": "ch1",
                    "status": "pending",
                }
            ],
        ),
        patch("src.activities.sheets.get_session") as mock_get_session,
        patch("src.activities.sheets.upsert_content_item"),
        patch("src.activities.sheets.create_sync_log"),
    ):
        # simulate no existing row so it counts as added
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        mock_get_session.return_value = mock_session

        env = ActivityEnvironment()
        result = await env.run(sync_sheets_to_sqlite, SheetsSyncInput())

    assert result.rows_added == 1
    assert result.rows_updated == 0
    assert result.error is None


async def test_write_results_to_sheets():
    """write_results_to_sheets calls update_sheets_row with correct args."""
    mock_spreadsheet = MagicMock()

    with (
        patch("src.activities.sheets.get_sheets_client", return_value=MagicMock()),
        patch("src.activities.sheets.open_spreadsheet", return_value=mock_spreadsheet),
        patch("src.activities.sheets.update_sheets_row") as mock_update,
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
    mock_update.assert_called_once_with(
        mock_spreadsheet,
        row_number=2,
        status="done",
        youtube_url="https://youtube.com/test",
    )


async def test_sync_handles_error():
    """When gspread raises, sync returns error message in SheetsSyncOutput."""
    with (
        patch(
            "src.activities.sheets.get_sheets_client",
            side_effect=Exception("Credentials not found"),
        ),
    ):
        env = ActivityEnvironment()
        result = await env.run(sync_sheets_to_sqlite, SheetsSyncInput())

    assert result.rows_added == 0
    assert result.rows_updated == 0
    assert result.error is not None
    assert "Credentials not found" in result.error
