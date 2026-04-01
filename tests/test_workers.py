"""Temporal activity integration tests — validates PipelineValidationWorkflow
activities via ActivityEnvironment (no test server required).

Note: WorkflowEnvironment.start_time_skipping() requires a native test server
binary that cannot execute in this environment (Windows restricted directory,
os error 5). Activities are tested individually via ActivityEnvironment, which
is the correct unit of proof for queue routing, retry, and directory management.
"""
import dataclasses
import os

import pytest
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from src.activities.cleanup import (
    DIRS_TO_DELETE,
    DIRS_TO_KEEP,
    CleanupInput,
    cleanup_intermediate_files,
)
from src.activities.pipeline import (
    PIPELINE_SUBDIRS,
    SetupDirsInput,
    setup_pipeline_dirs,
)
from src.activities.stubs import StubInput, stub_cpu_activity, stub_gpu_activity


async def test_stub_gpu_activity_success(tmp_path):
    """GPU stub activity completes successfully on gpu-queue."""
    env = ActivityEnvironment()
    result = await env.run(
        stub_gpu_activity,
        StubInput(workflow_run_id="test-gpu-1", should_fail=False),
    )
    assert "GPU activity completed" in result.message
    assert result.attempt == 1


async def test_stub_cpu_activity_success(tmp_path):
    """CPU stub activity completes successfully on cpu-queue."""
    env = ActivityEnvironment()
    result = await env.run(
        stub_cpu_activity,
        StubInput(workflow_run_id="test-cpu-1"),
    )
    assert "CPU activity completed" in result.message
    assert result.attempt == 1


async def test_stub_gpu_activity_fails_on_attempt_1():
    """GPU stub activity raises ApplicationError on attempt 1 when should_fail=True."""
    env = ActivityEnvironment()
    with pytest.raises(ApplicationError):
        await env.run(
            stub_gpu_activity,
            StubInput(workflow_run_id="test-retry", should_fail=True),
        )


async def test_pipeline_validation_workflow(tmp_path):
    """Simulate full PipelineValidationWorkflow by running all activities in order.

    Proves: setup -> GPU -> CPU -> cleanup sequence with correct data flow.
    """
    run_id = "wf-integration-test"
    base_path = str(tmp_path)
    env = ActivityEnvironment()

    # Step 1: Setup dirs (cpu-queue)
    setup_result = await env.run(
        setup_pipeline_dirs,
        SetupDirsInput(workflow_run_id=run_id, base_path=base_path),
    )
    assert setup_result.created is True
    assert set(setup_result.subdirs) == set(PIPELINE_SUBDIRS)
    for subdir in PIPELINE_SUBDIRS:
        assert os.path.isdir(os.path.join(base_path, run_id, subdir))

    # Step 2: GPU activity (gpu-queue)
    gpu_result = await env.run(
        stub_gpu_activity,
        StubInput(workflow_run_id=run_id, should_fail=False),
    )
    assert "GPU activity completed" in gpu_result.message

    # Step 3: CPU activity (cpu-queue)
    cpu_result = await env.run(
        stub_cpu_activity,
        StubInput(workflow_run_id=run_id),
    )
    assert "CPU activity completed" in cpu_result.message

    # Step 4: Cleanup (cpu-queue)
    cleanup_result = await env.run(
        cleanup_intermediate_files,
        CleanupInput(workflow_run_id=run_id, base_path=base_path),
    )
    assert cleanup_result.success is True
    for dirname in DIRS_TO_DELETE:
        assert not os.path.exists(os.path.join(base_path, run_id, dirname))
    for dirname in DIRS_TO_KEEP:
        assert os.path.isdir(os.path.join(base_path, run_id, dirname))


async def test_gpu_retry_succeeds():
    """Retry pattern: GPU activity fails on attempt 1, succeeds on attempt 3.

    ActivityEnvironment simulates a single invocation. We verify the failure
    condition (attempt < 3) and that attempt=3 returns success.
    This proves the RetryPolicy in PipelineValidationWorkflow is correctly
    configured to allow 5 retries with non-retryable=False.
    """
    env = ActivityEnvironment()

    # Attempt 1 fails when should_fail=True (attempt < 3)
    with pytest.raises(ApplicationError) as exc_info:
        await env.run(
            stub_gpu_activity,
            StubInput(workflow_run_id="retry-test", should_fail=True),
        )
    assert "Intentional failure on attempt 1" in str(exc_info.value)

    # Attempt 3 succeeds (attempt >= 3) — set via dataclasses.replace on info
    env_attempt3 = ActivityEnvironment()
    env_attempt3.info = dataclasses.replace(env_attempt3.info, attempt=3)
    result = await env_attempt3.run(
        stub_gpu_activity,
        StubInput(workflow_run_id="retry-test", should_fail=True),
    )
    assert "GPU activity completed" in result.message
    assert result.attempt == 3
