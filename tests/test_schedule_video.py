"""Tests for scripts/schedule_video.py — mocked Temporal client."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from scripts.schedule_video import schedule_one


@pytest.fixture
def mock_client():
    """Mock Temporal client with create_schedule."""
    client = MagicMock()
    client.create_schedule = AsyncMock(return_value=None)
    return client


@pytest.mark.asyncio
async def test_schedule_one_calls_create_schedule(mock_client):
    """Test 4: schedule_one() calls client.create_schedule with ScheduleCalendarSpec using ScheduleRange wrappers."""
    publish_at = datetime(2026, 4, 15, 9, 0)

    schedule_id = await schedule_one(
        topic="AI trends 2026",
        channel_id="channel_01",
        publish_at=publish_at,
        client=mock_client,
    )

    # create_schedule must be called exactly once
    assert mock_client.create_schedule.call_count == 1

    # The schedule_id is returned
    assert isinstance(schedule_id, str)
    assert "channel_01" in schedule_id


@pytest.mark.asyncio
async def test_schedule_one_uses_schedule_range_wrappers(mock_client):
    """Test 4b: ScheduleCalendarSpec fields use ScheduleRange wrappers (not bare ints)."""
    from temporalio.client import ScheduleRange

    publish_at = datetime(2026, 4, 15, 9, 30)

    await schedule_one(
        topic="Bitcoin forecast",
        channel_id="channel_02",
        publish_at=publish_at,
        client=mock_client,
    )

    # Extract the Schedule object passed to create_schedule
    args, kwargs = mock_client.create_schedule.call_args
    schedule_obj = args[1]  # Second positional arg is the Schedule

    # Inspect ScheduleSpec.calendars[0]
    calendar = schedule_obj.spec.calendars[0]

    # Year field must be a list of ScheduleRange objects, not bare ints
    assert len(calendar.year) > 0
    assert isinstance(calendar.year[0], ScheduleRange)
    assert calendar.year[0].start == 2026

    assert isinstance(calendar.month[0], ScheduleRange)
    assert calendar.month[0].start == 4  # April

    assert isinstance(calendar.day_of_month[0], ScheduleRange)
    assert calendar.day_of_month[0].start == 15

    assert isinstance(calendar.hour[0], ScheduleRange)
    assert calendar.hour[0].start == 9

    assert isinstance(calendar.minute[0], ScheduleRange)
    assert calendar.minute[0].start == 30


@pytest.mark.asyncio
async def test_schedule_one_limited_actions(mock_client):
    """Test 5: schedule_one() sets limited_actions=True, remaining_actions=1 for one-time schedules."""
    publish_at = datetime(2026, 5, 1, 8, 0)

    await schedule_one(
        topic="One-time video",
        channel_id="channel_01",
        publish_at=publish_at,
        client=mock_client,
    )

    args, kwargs = mock_client.create_schedule.call_args
    schedule_obj = args[1]

    # ScheduleState must enforce one-time execution
    assert schedule_obj.state.limited_actions is True
    assert schedule_obj.state.remaining_actions == 1


@pytest.mark.asyncio
async def test_schedule_one_returns_schedule_id(mock_client):
    """Test: schedule_one() returns a non-empty schedule_id string."""
    publish_at = datetime(2026, 6, 10, 14, 0)

    schedule_id = await schedule_one(
        topic="Test topic",
        channel_id="channel_03",
        publish_at=publish_at,
        client=mock_client,
    )

    assert isinstance(schedule_id, str)
    assert len(schedule_id) > 0
    # Verify the same schedule_id is used as the first arg to create_schedule
    first_arg = mock_client.create_schedule.call_args[0][0]
    assert first_arg == schedule_id
