import asyncio

from pydantic import BaseModel
from temporalio import activity
from temporalio.exceptions import ApplicationError


class StubInput(BaseModel):
    workflow_run_id: str
    should_fail: bool = False


class StubOutput(BaseModel):
    message: str
    attempt: int


@activity.defn
async def stub_gpu_activity(params: StubInput) -> StubOutput:
    """Stub GPU activity for Phase 1 validation. Simulates GPU work."""
    attempt = activity.info().attempt
    if params.should_fail and attempt < 3:
        raise ApplicationError(
            f"Intentional failure on attempt {attempt}",
            non_retryable=False,
        )
    await asyncio.sleep(1)  # simulate GPU work
    return StubOutput(
        message=f"GPU activity completed for {params.workflow_run_id}",
        attempt=attempt,
    )


@activity.defn
async def stub_cpu_activity(params: StubInput) -> StubOutput:
    """Stub CPU activity for Phase 1 validation. Simulates CPU work."""
    await asyncio.sleep(0.5)  # simulate CPU work
    return StubOutput(
        message=f"CPU activity completed for {params.workflow_run_id}",
        attempt=activity.info().attempt,
    )
