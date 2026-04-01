"""Sheets sync tests — skeletal scaffold with skip markers.
Plan 01-04 replaces these with full implementations after
src/activities/sheets.py and src/services/sheets_service.py are built.
"""
import pytest


@pytest.mark.skip(reason="Scaffold — implemented in Plan 01-04")
async def test_sync_sheets_to_sqlite():
    pass


@pytest.mark.skip(reason="Scaffold — implemented in Plan 01-04")
async def test_write_results_to_sheets():
    pass


@pytest.mark.skip(reason="Scaffold — implemented in Plan 01-04")
async def test_sync_handles_error():
    pass
