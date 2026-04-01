"""API Worker — max_concurrent_activities=8 (per D-06).

Handles fal.ai, YouTube API, Google Sheets, Gemini API calls.
Sheets sync activities (sync_sheets_to_sqlite, write_results_to_sheets) will be
registered here by Plan 01-03.
"""

import asyncio

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from src.config import settings


async def main() -> None:
    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
        data_converter=pydantic_data_converter,
    )
    worker = Worker(
        client,
        task_queue="api-queue",
        workflows=[],
        activities=[],  # Sheets sync activities registered in Plan 01-03
        max_concurrent_activities=8,
    )
    print("API worker started on api-queue (max_concurrent_activities=8)")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
