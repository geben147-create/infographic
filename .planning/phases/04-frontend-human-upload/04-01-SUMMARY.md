---
phase: 04-frontend-human-upload
plan: "01"
subsystem: pipeline-workflow
tags: [workflow, api, download, manual-upload]
dependency_graph:
  requires: []
  provides: [ready_to_upload-status, download-endpoints, video_path-fields]
  affects: [content_pipeline_workflow, pipeline_run_model, dashboard_api]
tech_stack:
  added: []
  patterns: [FileResponse-attachment, status-enum-extension, model-field-addition]
key_files:
  created: []
  modified:
    - src/workflows/content_pipeline.py
    - src/schemas/pipeline.py
    - src/models/pipeline_run.py
    - src/api/pipeline.py
    - src/schemas/dashboard.py
    - src/api/dashboard.py
decisions:
  - "Kept video_id and youtube_url as None defaults in PipelineResult for backward compatibility"
  - "Cleanup step (Step 8) removed along with upload — operator needs files to remain for download"
  - "Content-Disposition attachment header added to both download endpoints to trigger browser save dialog"
  - "get_pipeline_status checks result.status field to correctly surface ready_to_upload over completed"
metrics:
  duration_minutes: 5
  completed_date: "2026-04-02"
  tasks_completed: 2
  files_modified: 6
---

# Phase 04 Plan 01: Remove YouTube Auto-Upload, Expose Download Endpoints Summary

YouTube auto-upload removed from ContentPipelineWorkflow; pipeline now stops after video assembly with status="ready_to_upload" and exposes /download and /thumbnail endpoints for manual operator upload.

## What Was Built

The ContentPipelineWorkflow previously automatically uploaded to YouTube as Step 7, then cleaned up intermediate files in Step 8. Both steps have been removed. The workflow now terminates after Step 6 (FFmpeg video assembly) + Step 6.5 (optional quality gate), returning the assembled video path and thumbnail path in the result with status `ready_to_upload`. Two new download API endpoints allow the operator to retrieve the files for manual YouTube upload.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Remove YouTube upload step, update models | 25f9115 | src/workflows/content_pipeline.py, src/schemas/pipeline.py, src/models/pipeline_run.py |
| 2 | Add download endpoints for video and thumbnail | 06a6dea | src/api/pipeline.py, src/schemas/dashboard.py, src/api/dashboard.py |

## Key Changes

### ContentPipelineWorkflow (src/workflows/content_pipeline.py)
- Removed `UploadInput`, `UploadOutput` imports from `imports_passed_through()` block
- Removed `_RETRY_UPLOAD` retry policy constant
- Added `video_path: str = ""` and `thumbnail_path: str = ""` to `PipelineResult`
- Changed `status` default from `"completed"` to `"ready_to_upload"`
- Removed Step 7 (upload_to_youtube activity call)
- Removed Step 8 (cleanup_intermediate_files activity call)
- Added `thumbnail_path_str` computation before quality gate block
- Updated quality gate non-approved returns to include `video_path` and `thumbnail_path`
- Final return now uses `status="ready_to_upload"` with both file paths

### PipelineStatus enum (src/schemas/pipeline.py)
- Added `ready_to_upload = "ready_to_upload"` after `waiting_approval`

### PipelineRun model (src/models/pipeline_run.py)
- Added `video_path: Optional[str] = Field(default=None)`
- Added `thumbnail_path: Optional[str] = Field(default=None)`

### Pipeline API (src/api/pipeline.py)
- Added `GET /{workflow_id}/download` endpoint — returns video as `attachment` with Content-Disposition
- Added `GET /{workflow_id}/thumbnail` endpoint — returns thumbnail as `attachment` with Content-Disposition
- Updated `get_pipeline_status` to check `result.status == "ready_to_upload"` and map to `PipelineStatus.ready_to_upload`

### Dashboard schema + API (src/schemas/dashboard.py, src/api/dashboard.py)
- Added `video_path: str | None = None` and `thumbnail_path: str | None = None` to `RunSummary`
- Updated `list_runs()` RunSummary constructor to pass `video_path=r.video_path` and `thumbnail_path=r.thumbnail_path`

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. The download endpoints correctly route to `data/pipeline/{workflow_id}/final/output.mp4` and `data/pipeline/{workflow_id}/thumbnails/thumbnail.jpg` — these are the actual paths produced by the video assembly and thumbnail activities.

## Self-Check: PASSED

- src/workflows/content_pipeline.py — exists, `upload_to_youtube` count = 0, `ready_to_upload` present
- src/schemas/pipeline.py — `ready_to_upload` enum value present
- src/models/pipeline_run.py — `video_path` and `thumbnail_path` fields present
- src/api/pipeline.py — `download_video` and `download_thumbnail` functions present, 4 Content-Disposition lines
- src/schemas/dashboard.py — `video_path` and `thumbnail_path` fields in RunSummary
- src/api/dashboard.py — `video_path=r.video_path` and `thumbnail_path=r.thumbnail_path` in list_runs()
- Commits 25f9115 and 06a6dea exist in git log
