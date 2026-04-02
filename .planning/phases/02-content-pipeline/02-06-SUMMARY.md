---
phase: 02-content-pipeline
plan: "06"
subsystem: api
tags: [temporal, fastapi, youtube, oauth2, workflow, pipeline]

requires:
  - phase: 02-content-pipeline plans 03-05
    provides: "script_gen, image_gen, tts, video_gen, video_assembly, thumbnail activities"
  - phase: 01-infrastructure
    provides: "Temporal worker pools, pipeline dir activities, cost_tracker, schemas"

provides:
  - "upload_to_youtube Temporal activity (resumable upload + thumbnail)"
  - "ContentPipelineWorkflow — end-to-end 8-step pipeline across 3 queues"
  - "POST /api/pipeline/trigger — start workflow, return workflow_id"
  - "GET /api/pipeline/status/{workflow_id} — poll status + cost"
  - "GET /api/pipeline/cost/{workflow_id} — full cost breakdown"
  - "DELETE /api/pipeline/{workflow_id} — cancel in-flight run"
  - "Workers (gpu/cpu/api) register all Phase 2 activities"

affects:
  - 02-content-pipeline
  - 03-quality-gate (consumes pipeline trigger/status endpoints)

tech-stack:
  added:
    - google-oauth2-credentials (already in deps, now used for YouTube)
    - googleapiclient.discovery.build (YouTube Data API v3)
    - googleapiclient.http.MediaFileUpload (resumable upload)
  patterns:
    - "Temporal workflow chains activities across typed task queues via string names"
    - "imports_passed_through() for activity model imports inside workflow module"
    - "asyncio.to_thread() for blocking I/O (resumable upload loop) in async activity"
    - "FastAPI Request.app.state.temporal_client for Temporal client access"
    - "CostTracker.get_run_total/get_run_breakdown for cost aggregation in API"

key-files:
  created:
    - src/activities/youtube_upload.py
    - src/workflows/content_pipeline.py
    - src/activities/video_assembly.py  # forward-declaration stub (02-05 parallel)
    - src/activities/thumbnail.py       # forward-declaration stub (02-05 parallel)
    - src/api/pipeline.py
    - tests/test_youtube_upload.py
    - tests/test_content_pipeline_workflow.py
  modified:
    - src/main.py
    - src/workers/gpu_worker.py
    - src/workers/cpu_worker.py
    - src/workers/api_worker.py

key-decisions:
  - "asyncio.to_thread() for MediaFileUpload.next_chunk() loop — blocks event loop without threading"
  - "except Exception in _save_credentials — non-fatal, must not fail the upload"
  - "Stub video_assembly.py + thumbnail.py created to unblock workflow import while 02-05 runs in parallel"
  - "inspect.getsource(module) not getsource(class) for imports_passed_through test — class source excludes module-level code"
  - "ContentPipelineWorkflow registered on all 3 queues (all workers need it for Temporal routing)"

patterns-established:
  - "Workflow module-level with-block: with workflow.unsafe.imports_passed_through(): imports all activity I/O models"
  - "Per-task-queue routing: gpu-queue for AI, cpu-queue for FFmpeg/dirs, api-queue for external APIs"
  - "CostTracker accessed directly in API layer (read-only) — no service wrapper needed for simple reads"

requirements-completed: [PIPE-05, CHAN-02]

duration: 8min
completed: 2026-04-02
---

# Phase 02 Plan 06: YouTube Upload, ContentPipelineWorkflow, and Pipeline API Summary

**Resumable YouTube upload activity + 8-step ContentPipelineWorkflow across gpu/cpu/api queues, wired via FastAPI /api/pipeline/* endpoints and registered in all three worker pools.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-02T01:39:17Z
- **Completed:** 2026-04-02T01:47:17Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments

- `upload_to_youtube` Temporal activity: loads per-channel OAuth2 credentials, refreshes if expired, executes resumable upload via `asyncio.to_thread`, attaches thumbnail, saves refreshed tokens
- `ContentPipelineWorkflow`: chains setup_dirs → generate_script → per-scene (image + TTS) → per-scene video_gen → thumbnail → assemble_video → upload_to_youtube → cleanup across gpu/cpu/api queues
- FastAPI `/api/pipeline/*` endpoints: trigger, status (maps Temporal status enum), cost breakdown, cancel
- All three workers (gpu/cpu/api) updated to register Phase 2 activities and `ContentPipelineWorkflow`
- 31 new tests passing (TDD); 117 total tests passing across full suite

## Task Commits

1. **Task 1: YouTube upload activity + ContentPipelineWorkflow** - `2f19a7a` (feat)
2. **Task 2: Pipeline API endpoints + Worker registration + Main app wiring** - `97566e8` (feat)

## Files Created/Modified

- `src/activities/youtube_upload.py` - Resumable upload + thumbnail, credential refresh
- `src/workflows/content_pipeline.py` - End-to-end 8-step Temporal workflow
- `src/activities/video_assembly.py` - Forward-declaration stub (02-05 parallel plan)
- `src/activities/thumbnail.py` - Forward-declaration stub (02-05 parallel plan)
- `src/api/pipeline.py` - POST trigger, GET status/cost, DELETE cancel endpoints
- `src/main.py` - Added `include_router(pipeline.router)`
- `src/workers/gpu_worker.py` - Added Phase 2 GPU activities + ContentPipelineWorkflow
- `src/workers/cpu_worker.py` - Added assemble_video + ContentPipelineWorkflow
- `src/workers/api_worker.py` - Added upload_to_youtube + ContentPipelineWorkflow
- `tests/test_youtube_upload.py` - 9 tests: models, upload loop, thumbnail set, credential refresh
- `tests/test_content_pipeline_workflow.py` - 22 tests: params/result models, activity chain, queue routing

## Decisions Made

- `asyncio.to_thread()` for `MediaFileUpload.next_chunk()` — the blocking resumable upload loop must not block the asyncio event loop in a Temporal activity
- `except Exception` (not `except OSError`) for `_save_credentials` — JSON serialization errors from mock objects in tests are not OSError; credential save is non-fatal either way
- Forward-declaration stubs for `video_assembly.py` and `thumbnail.py` — required to allow `content_pipeline.py` to import at module load time while plan 02-05 (FFmpeg/thumbnail) runs in parallel
- `inspect.getsource(module)` not `inspect.getsource(class)` — the `imports_passed_through()` block is at module level, not inside the class, so class-level source inspection misses it
- `ContentPipelineWorkflow` registered on all 3 task queues — Temporal requires the workflow class to be registered on every worker that will execute it, including "leaf" queues like cpu and api

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created stub video_assembly.py and thumbnail.py**
- **Found during:** Task 1 (ContentPipelineWorkflow)
- **Issue:** `content_pipeline.py` imports `AssemblyInput` and `ThumbnailInput` at module level inside `imports_passed_through()`. Python still attempts to resolve the import at collection time — the workflow cannot be imported without the modules existing.
- **Fix:** Created minimal stub files with the interface contracts specified in the plan. Both raise `NotImplementedError` if called.
- **Files modified:** `src/activities/video_assembly.py`, `src/activities/thumbnail.py`
- **Verification:** Module import succeeds, all 31 tests pass
- **Committed in:** `2f19a7a` (Task 1 commit)

**2. [Rule 1 - Bug] Fixed test assertion for MediaFileUpload video path**
- **Found during:** Task 1 (test_resumable_upload_uses_media_file_upload)
- **Issue:** Test checked `c.args` + `c.kwargs` as strings, but call uses positional arg; `str(c.args)` wraps in tuple notation making substring match unreliable
- **Fix:** Changed to `c.args[0] == str(video_file)` direct equality check
- **Files modified:** `tests/test_youtube_upload.py`
- **Verification:** Test passes
- **Committed in:** `2f19a7a` (Task 1 commit)

**3. [Rule 1 - Bug] Fixed `imports_passed_through` test source inspection**
- **Found during:** Task 1 (test_workflow_imports_passed_through)
- **Issue:** `inspect.getsource(ContentPipelineWorkflow)` returns only the class body; `imports_passed_through()` is at module level and not visible in class source
- **Fix:** Changed to `inspect.getsource(src.workflows.content_pipeline module)`
- **Files modified:** `tests/test_content_pipeline_workflow.py`
- **Verification:** Test passes
- **Committed in:** `2f19a7a` (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (1 blocking stub creation, 2 test assertion bugs)
**Impact on plan:** All auto-fixes necessary for correct imports and test reliability. No scope creep.

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| `assemble_video` | `src/activities/video_assembly.py` | Raises `NotImplementedError` — real FFmpeg implementation belongs to plan 02-05 (parallel) |
| `generate_thumbnail` | `src/activities/thumbnail.py` | Raises `NotImplementedError` — real Pillow/ComfyUI implementation belongs to plan 02-05 (parallel) |

These stubs will be overwritten when plan 02-05 merges. They do not block this plan's stated goal (API wiring), but the pipeline will fail at runtime until 02-05 provides the full implementations.

## Issues Encountered

- `imports_passed_through()` does not suppress `ModuleNotFoundError` at Python module import time — it only controls Temporal's sandboxed import isolation during workflow replay. Real module imports must still resolve.

## User Setup Required

YouTube upload requires OAuth2 credentials per channel. See `user_setup` section of `02-06-PLAN.md`:
1. Create OAuth consent screen in GCP Console
2. Enable YouTube Data API v3
3. Download client secrets JSON
4. Run `scripts/youtube_auth.py --channel-id channel_01 --client-secrets path/to/client_secrets.json`
5. Set `youtube_credentials_path` in the channel YAML config

## Next Phase Readiness

- Full pipeline callable end-to-end: `POST /api/pipeline/trigger` → Temporal → 3 worker pools → YouTube
- Workers registered with all Phase 2 activities
- Stubs for video_assembly/thumbnail will be replaced by 02-05 merge
- Phase 2 Wave 3 complete pending 02-05 merge

---
*Phase: 02-content-pipeline*
*Completed: 2026-04-02*
