---
phase: 01-infrastructure
plan: 02
subsystem: infra
tags: [temporalio, pydantic, workers, activities, workflow, gpu-queue, cpu-queue, api-queue]

requires:
  - phase: 01-infrastructure/01-01
    provides: src/config.py with temporal_host/temporal_namespace, pyproject.toml with all deps, uv project scaffold

provides:
  - Three typed Temporal worker processes (gpu/cpu/api) with correct maxConcurrent values
  - PipelineValidationWorkflow routing activities to gpu-queue and cpu-queue
  - stub_gpu_activity and stub_cpu_activity with Pydantic I/O for ORCH-03 retry validation
  - setup_pipeline_dirs activity creating 6-subdir artifact tree (FILE-01)
  - cleanup_intermediate_files activity deleting intermediate dirs, keeping final/ (FILE-02)

affects:
  - 01-03 (api_worker.py hosts future Sheets sync activities)
  - 01-04 (test_workers.py stubs ready for integration test implementation)
  - 02-xx (all Phase 2 content activities extend gpu/cpu/api worker registrations)

tech-stack:
  added: []
  patterns:
    - "Temporal workflow imports inside workflow.unsafe.imports_passed_through() to avoid sandbox non-determinism"
    - "String-based activity names in execute_activity() for cross-queue routing (activity registered on different worker than workflow)"
    - "pydantic_data_converter on all Client.connect() calls — client and all workers must match"
    - "GPU worker hosts PipelineValidationWorkflow (thin orchestration only); CPU/API workers host no workflows"
    - "max_concurrent_activities=1 on GPU worker enforces VRAM serialization at infrastructure level"

key-files:
  created:
    - src/activities/__init__.py
    - src/activities/stubs.py
    - src/activities/pipeline.py
    - src/activities/cleanup.py
    - src/workflows/__init__.py
    - src/workflows/pipeline_validation.py
    - src/workers/__init__.py
    - src/workers/gpu_worker.py
    - src/workers/cpu_worker.py
    - src/workers/api_worker.py
  modified: []

key-decisions:
  - "PipelineValidationWorkflow registered on gpu-queue worker (D-06 Open Question 3): workflow is thin orchestration; GPU worker hosts it to co-locate with GPU activity registration"
  - "String-based activity names in execute_activity() for cross-queue calls: activity function not imported on workflow worker, string name matches @activity.defn registration"
  - "ApplicationError(non_retryable=False) for intentional retry test: NOT activity.complete_with_error which doesn't exist in Temporal Python SDK"
  - "workflow.unsafe.imports_passed_through() for activity model imports: prevents Temporal sandbox from blocking pydantic/temporalio imports at workflow code load time"

patterns-established:
  - "Pattern: GPU worker owns PipelineValidationWorkflow — workflow is orchestration code only, no I/O"
  - "Pattern: Cross-queue activity calls use string names, not function references"
  - "Pattern: uv run --with ruff ruff check . and uv run --with mypy mypy src/ for tool invocation in this project"

requirements-completed:
  - ORCH-01
  - ORCH-02
  - ORCH-03
  - FILE-01
  - FILE-02

duration: 6min
completed: 2026-04-02
---

# Phase 1 Plan 02: Temporal Workers and Activities Summary

**Three typed Temporal workers (gpu/cpu/api) with PipelineValidationWorkflow, stub activities for retry testing, and real file management activities (dir setup + cleanup) — all verified with ruff + mypy clean.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-01T23:17:39Z
- **Completed:** 2026-04-01T23:23:13Z
- **Tasks:** 2
- **Files created:** 10

## Accomplishments

- Four activities with Pydantic I/O models: stub_gpu_activity (with ApplicationError for ORCH-03 retry test), stub_cpu_activity, setup_pipeline_dirs (FILE-01), cleanup_intermediate_files (FILE-02)
- PipelineValidationWorkflow with 4-step sequential execution routing to gpu-queue and cpu-queue per D-08
- RetryPolicy(maximum_attempts=5, backoff_coefficient=2.0) on GPU activity for ORCH-03 validation
- Three Worker processes with correct maxConcurrent: gpu=1 (VRAM safety), cpu=4, api=8 — all use pydantic_data_converter
- ruff check and mypy src/ both pass with no issues

## Task Commits

1. **Task 1: Activities (stubs + pipeline + cleanup)** - `4b82f65` (feat)
2. **Task 2: Workflow + three workers** - `2bfcdf0` (feat)

## Files Created/Modified

- `src/activities/__init__.py` - Empty package init
- `src/activities/stubs.py` - stub_gpu_activity (with intentional retry via ApplicationError) and stub_cpu_activity
- `src/activities/pipeline.py` - setup_pipeline_dirs creates 6 subdirs under data/pipeline/{run_id}/
- `src/activities/cleanup.py` - cleanup_intermediate_files deletes 5 intermediate dirs, keeps final/
- `src/workflows/__init__.py` - Empty package init
- `src/workflows/pipeline_validation.py` - PipelineValidationWorkflow: setup -> GPU -> CPU -> cleanup with queue routing
- `src/workers/__init__.py` - Empty package init
- `src/workers/gpu_worker.py` - max_concurrent_activities=1, hosts PipelineValidationWorkflow + stub_gpu_activity
- `src/workers/cpu_worker.py` - max_concurrent_activities=4, hosts stub_cpu + setup_pipeline_dirs + cleanup
- `src/workers/api_worker.py` - max_concurrent_activities=8, placeholder for Plan 01-03 Sheets activities

## Decisions Made

- String-based activity names in `execute_activity()` for cross-queue calls: the GPU workflow calls CPU-queue activities by string name because the CPU activities are not imported on the GPU worker. String names match the `@activity.defn` name registration.
- `workflow.unsafe.imports_passed_through()` wraps activity model imports (StubInput, SetupDirsInput, CleanupInput) inside the workflow file: prevents Temporal's sandbox from blocking pydantic/temporalio module loads at workflow code import time.
- PipelineValidationWorkflow registered on gpu-queue (D-06 Open Question 3 resolution): the workflow is pure orchestration — it has no I/O itself, only schedules activities. Placing it on the GPU worker is correct; the workflow code runs on whichever worker owns that task queue.
- ApplicationError with non_retryable=False for the retry test: `activity.complete_with_error` does not exist in the Temporal Python SDK. ApplicationError is the correct exception type that triggers retry behavior.

## Deviations from Plan

None — plan executed exactly as written. The plan already corrected the `activity.complete_with_error` mistake in the task body with an IMPORTANT note, and specified `ApplicationError` as the correct approach.

## Issues Encountered

- `uv tool run mypy src/` and `uv run mypy src/` both failed ("program not found") because mypy is a dev dependency in the project venv, not a globally installed tool. Fixed by using `uv run --with mypy mypy src/` to run mypy through the project environment. Same pattern applies to ruff: `uv run --with ruff ruff check .`

## User Setup Required

None — no external service configuration required for this plan. Workers require a running Temporal server (`docker compose up -d`) before they can connect, but that is covered by Plan 01-01's Docker Compose setup.

## Next Phase Readiness

- Plan 01-03 can proceed: api_worker.py has a placeholder activities=[] list ready for Sheets sync activities
- Plan 01-04 can proceed: tests/test_workers.py stubs exist; activities and workers are all importable for test implementation
- Workers connect to Temporal on localhost:7233 — Docker Desktop must be running before `docker compose up -d`

## Self-Check: PASSED

- All 10 files verified present on disk
- Both task commits found in git history (4b82f65, 2bfcdf0)
- All 4 activities importable: stub_gpu_activity, stub_cpu_activity, setup_pipeline_dirs, cleanup_intermediate_files
- All 3 workers importable: gpu_main, cpu_main, api_main
- PipelineValidationWorkflow importable
- ruff check exits 0 (via uv run --with ruff)
- mypy src/ exits 0 (via uv run --with mypy) — 18 source files, no issues
- 15/15 acceptance criteria checks pass

---
*Phase: 01-infrastructure*
*Completed: 2026-04-02*
