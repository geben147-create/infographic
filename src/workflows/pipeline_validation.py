from datetime import timedelta

from pydantic import BaseModel
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.activities.cleanup import CleanupInput
    from src.activities.pipeline import SetupDirsInput
    from src.activities.stubs import StubInput


class ValidationParams(BaseModel):
    workflow_run_id: str
    test_gpu_retry: bool = False


class ValidationResult(BaseModel):
    setup_ok: bool
    gpu_ok: bool
    cpu_ok: bool
    cleanup_ok: bool
    message: str


@workflow.defn
class PipelineValidationWorkflow:
    """Phase 1 validation workflow (D-08).

    Proves: queue routing, GPU serialization, durable retry, directory setup/cleanup.
    """

    @workflow.run
    async def run(self, params: ValidationParams) -> ValidationResult:
        # Step 1: Setup pipeline directories (cpu-queue)
        await workflow.execute_activity(
            "setup_pipeline_dirs",
            SetupDirsInput(workflow_run_id=params.workflow_run_id),
            task_queue="cpu-queue",
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Step 2: Stub GPU activity (gpu-queue, maxConcurrent=1)
        await workflow.execute_activity(
            "stub_gpu_activity",
            StubInput(
                workflow_run_id=params.workflow_run_id,
                should_fail=params.test_gpu_retry,
            ),
            task_queue="gpu-queue",
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(
                maximum_attempts=5,
                initial_interval=timedelta(seconds=1),
                backoff_coefficient=2.0,
            ),
        )

        # Step 3: Stub CPU activity (cpu-queue)
        await workflow.execute_activity(
            "stub_cpu_activity",
            StubInput(workflow_run_id=params.workflow_run_id),
            task_queue="cpu-queue",
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Step 4: Cleanup intermediate files (cpu-queue)
        await workflow.execute_activity(
            "cleanup_intermediate_files",
            CleanupInput(workflow_run_id=params.workflow_run_id),
            task_queue="cpu-queue",
            start_to_close_timeout=timedelta(seconds=30),
        )

        return ValidationResult(
            setup_ok=True,
            gpu_ok=True,
            cpu_ok=True,
            cleanup_ok=True,
            message=f"Validation complete for {params.workflow_run_id}",
        )
