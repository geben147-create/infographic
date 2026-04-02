---
phase: 03-production-operations
plan: "01"
subsystem: quality-gate
tags: [temporal, signal, quality-gate, fastapi, tdd]
dependency_graph:
  requires: []
  provides: [quality-gate-signal, approval-endpoint, video-preview-endpoint]
  affects: [content-pipeline-workflow, pipeline-api, channel-config]
tech_stack:
  added: []
  patterns: [temporal-signal-handler, wait-condition, file-response]
key_files:
  created:
    - tests/test_quality_gate.py
    - tests/test_approve_endpoint.py
  modified:
    - src/workflows/content_pipeline.py
    - src/models/channel_config.py
    - src/schemas/pipeline.py
    - src/api/pipeline.py
    - src/channel_configs/channel_01.yaml
    - src/channel_configs/channel_02.yaml
decisions:
  - "__init__ with _approved/_reject_reason in ContentPipelineWorkflow — Temporal determinism requires signal state initialized in __init__, not run()"
  - "approve/video routes placed before DELETE route — FastAPI matches routes in declaration order; /{id}/approve and /{id}/video must precede /{id} to avoid path conflicts"
  - "ApprovalSignal imported inside imports_passed_through() block — keeps workflow worker process free of heavy activity deps"
metrics:
  duration_minutes: 6
  completed_date: "2026-04-02"
  tasks_completed: 2
  files_changed: 8
---

# Phase 3 Plan 01: Quality Gate — Human Approval Before YouTube Upload

Human-in-the-loop quality gate with Temporal signal handler, `wait_condition` pause between assembly and upload, operator approve/reject API, and per-channel toggle in `ChannelConfig`.

## What Was Built

Added a toggleable quality gate to `ContentPipelineWorkflow` that pauses execution between video assembly (Step 6) and YouTube upload (Step 7) when `quality_gate_enabled=True`. Operators review the assembled video via `GET /api/pipeline/{id}/video` and approve or reject it via `POST /api/pipeline/{id}/approve`.

## Tasks Completed

### Task 1: Quality gate signal, config toggle, schemas (TDD)

**Commit:** `7cc12dc`

- Added `waiting_approval` to `PipelineStatus` enum
- Added `ApprovalSignal`, `ApproveRequest`, `VideoPreviewResponse` schemas to `src/schemas/pipeline.py`
- Added `quality_gate_enabled: bool = False` to `ChannelConfig` (backward compat)
- Added `quality_gate_enabled: bool = False` to `PipelineParams` (backward compat)
- Added `quality_gate_enabled: false` to `channel_01.yaml` and `channel_02.yaml`
- Added `ContentPipelineWorkflow.__init__` with `_approved: bool = False` and `_reject_reason: str = ""`
- Added `@workflow.signal async def approve_video(self, payload)` handler
- Added `wait_condition` block guarded by `params.quality_gate_enabled` between Step 6 and Step 7
- Returns `status="rejected"` when operator rejects; `status="timeout_rejected"` after 24h timeout
- Tests: `tests/test_quality_gate.py` — 19 tests, all passing

### Task 2: Approval endpoint and video preview endpoint (TDD)

**Commit:** `a6d8cad`

- Added `POST /api/pipeline/{workflow_id}/approve` — sends `approve_video` Temporal signal with `ApprovalSignal` payload
- Added `GET /api/pipeline/{workflow_id}/video` — serves assembled `output.mp4` via `FileResponse`; returns 404 if file not found
- Both routes placed before `DELETE /{workflow_id}` to prevent FastAPI path conflict
- Tests: `tests/test_approve_endpoint.py` — 7 tests, all passing

## Test Results

```
26 passed in 1.04s
```

- `tests/test_quality_gate.py`: 19/19 passed
- `tests/test_approve_endpoint.py`: 7/7 passed

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all implemented paths are functional. The quality gate wire-up is complete:
- `wait_condition` blocks correctly when `quality_gate_enabled=True`
- Signal handler receives and stores approval state
- API endpoint sends the signal to Temporal
- Video preview endpoint serves the assembled file

## Self-Check: PASSED

Files created/modified:
- `tests/test_quality_gate.py` — FOUND
- `tests/test_approve_endpoint.py` — FOUND
- `src/workflows/content_pipeline.py` — contains `approve_video`, `wait_condition`, `quality_gate_enabled`
- `src/schemas/pipeline.py` — contains `ApprovalSignal`, `waiting_approval`
- `src/models/channel_config.py` — contains `quality_gate_enabled`
- `src/api/pipeline.py` — contains `approve_pipeline`, `get_pipeline_video`

Commits:
- `7cc12dc` — feat(03-01): add quality gate signal, config toggle, and schemas
- `a6d8cad` — feat(03-01): add approval endpoint and video preview endpoint
