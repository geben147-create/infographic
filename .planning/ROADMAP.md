# Roadmap: YouTube Video Automation Pipeline

## Overview

Three phases deliver the project: first, lay the infrastructure skeleton (Temporal, SQLite, worker pools, file layout) so the pipeline has a foundation to run on. Second, build the full end-to-end content pipeline — script generation through YouTube upload — for a single channel, including optional fal.ai video generation and multi-channel config support. Third, add production operations (quality gate, batch processing, content calendar, cost dashboard) that make the system operationally mature and trustworthy for sustained daily use.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Infrastructure** - Temporal orchestration, SQLite data layer, worker pools, artifact directory structure (completed 2026-04-01)
- [ ] **Phase 2: Content Pipeline** - End-to-end script → image/video → TTS → FFmpeg → YouTube, multi-channel config, optional fal.ai
- [ ] **Phase 3: Production Operations** - Quality gate, batch processing, content calendar, cost tracking, status dashboard

## Phase Details

### Phase 1: Infrastructure
**Goal**: The project skeleton runs locally — Temporal server, SQLite schema, typed worker pools, and artifact directory structure are all wired and verifiable before any content is generated.
**Depends on**: Nothing (first phase)
**Requirements**: ORCH-01, ORCH-02, ORCH-03, DATA-01, DATA-02, DATA-03, FILE-01, FILE-02
**Success Criteria** (what must be TRUE):
  1. A Temporal workflow can be triggered, executes a GPU activity and a CPU activity sequentially, and durable retry works when an activity is intentionally failed
  2. Google Sheets rows sync into SQLite and pipeline run state can be read and written exclusively through SQLite during execution
  3. Results (YouTube URL, status) written to SQLite are reflected back in the originating Sheets row after pipeline completion
  4. A pipeline run creates the `/data/pipeline/{workflow_run_id}/` directory tree and a cleanup activity removes intermediate files after completion
  5. GPU worker maxConcurrent=1 is enforced — submitting two GPU tasks at once results in queued sequential execution, not parallel
**Plans:** 4/4 plans complete

Plans:
- [x] 01-01-PLAN.md — Project scaffold + Config + DB models + Alembic
- [x] 01-02-PLAN.md — Temporal workers + Validation workflow + Activities
- [x] 01-03-PLAN.md — FastAPI app + Sheets sync + API routes
- [x] 01-04-PLAN.md — Integration tests + End-to-end validation

### Phase 2: Content Pipeline
**Goal**: A single topic input produces a complete YouTube video with title, description, tags, and thumbnail — uploaded automatically — for any configured channel, using provider-swappable AI models.
**Depends on**: Phase 1
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05, PIPE-06, VGEN-01, VGEN-02, VGEN-03, CHAN-01, CHAN-02
**Success Criteria** (what must be TRUE):
  1. Entering a topic keyword produces a structured script JSON (title, description, per-scene narration + image prompt + duration, tags) via LLM provider
  2. Each scene yields an image via provider; Korean narration yields a TTS audio file; FFmpeg assembles them into an MP4 with transitions using NVENC encoding
  3. The finished video uploads to YouTube with correct metadata and a thumbnail with Korean text overlay attached
  4. When a fal.ai API key is set and VGEN is enabled in channel config, scenes use AI video clips; when the key is absent or VGEN is off, Ken Burns effects on still images are used instead — and the per-video cost is shown in real time and written to cost_log.json
  5. Two channels with different checkpoints, TTS voices, and prompt templates both produce valid videos through the same workflow code (channel_id parameter only)
**Plans:** 6/7 plans executed

Plans:
- [x] 02-01-PLAN.md — Provider abstraction + Channel config + Pydantic models + API schemas
- [x] 02-02-PLAN.md — Channel config YAMLs + Prompt templates + Setup scripts
- [x] 02-03-PLAN.md — Script generation (LLM) + TTS audio activities
- [x] 02-04-PLAN.md — Image generation + Video generation + Cost tracker
- [x] 02-05-PLAN.md — FFmpeg video assembly + Thumbnail generation
- [x] 02-06-PLAN.md — YouTube upload + ContentPipelineWorkflow + API endpoints + Worker registration
- [x] 02-07-PLAN.md — Integration tests + Multi-channel validation + Human verification

### Phase 3: Production Operations
**Goal**: The operator can review and approve videos before they go live, queue a week of content for overnight generation, schedule future publish dates, and see cost and status at a glance.
**Depends on**: Phase 2
**Requirements**: OPS-01, OPS-02, OPS-03, OPS-04, OPS-05, OPS-06
**Success Criteria** (what must be TRUE):
  1. Before upload, the operator can view a preview of the assembled video and either approve (pipeline continues to upload) or reject (pipeline stops and logs reason) via a Temporal human-in-the-loop signal
  2. Quality gate can be toggled off in channel config so videos upload automatically without manual review
  3. Multiple videos can be queued in a single batch command and execute sequentially overnight without manual intervention
  4. A scheduled Temporal workflow triggers video generation and upload at a configured future date/time without manual triggering
  5. A FastAPI dashboard endpoint and the Temporal Web UI together show per-video API costs (fal.ai, Gemini) and current pipeline run status
**Plans:** 1/3 plans executed

Plans:
- [x] 03-01-PLAN.md — Quality gate: signal handler, approval endpoint, video preview, config toggle
- [x] 03-02-PLAN.md — Batch runner CLI + Schedule CLI + cost DB migration
- [x] 03-03-PLAN.md — Dashboard endpoints + integration verification

### Phase 4: Frontend & Human-in-the-loop Upload
**Goal**: The operator sees a live web dashboard showing pipeline runs, costs, and video preview — and the workflow delivers a finished video file ready for manual YouTube upload instead of auto-uploading, putting final publish control in human hands.
**Depends on**: Phase 3
**Requirements**: UI-01, UI-02, UI-03, PIPE-07, MON-01
**Success Criteria** (what must be TRUE):
  1. A React/HTML frontend dashboard deployed to Netlify displays pipeline run history, per-channel cost breakdown, and video preview/download links — updated without a page reload
  2. The ContentPipelineWorkflow stops after video assembly and thumbnail generation; the YouTube upload step is removed from the automated pipeline; status is set to `ready_to_upload` with the final video file path exposed via API
  3. The operator can download the assembled video and thumbnail directly from the dashboard, then upload manually to YouTube Studio
  4. A `/api/health` endpoint returns system status (Temporal connection, SQLite, disk space); critical errors (Temporal unreachable, disk full) are logged to a structured alert log
  5. E2E verification confirms ContentPipelineWorkflow source no longer references upload_to_youtube, PipelineResult.status supports ready_to_upload value, and download endpoint tests verify FileResponse behavior with mocked file paths
**Plans:** 4/4 plans complete

Plans:
- [x] 04-01-PLAN.md — Remove YouTube auto-upload from workflow; add download endpoints; status=ready_to_upload
- [x] 04-02-PLAN.md — Frontend dashboard (vanilla HTML/CSS/JS) — runs table, cost cards, download buttons + CORS
- [x] 04-03-PLAN.md — Netlify deploy config + enhanced health endpoint + structured alert log
- [x] 04-04-PLAN.md — E2E dry-run tests + health/download endpoint tests

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure | 4/4 | Complete | 2026-04-02 |
| 2. Content Pipeline | 7/7 | Complete | 2026-04-02 |
| 3. Production Operations | 3/3 | Complete | 2026-04-02 |
| 4. Frontend & Human Upload | 4/4 | Complete | 2026-04-02 |
| 5. Complete Frontend Site | 1/1 | Complete | 2026-04-02 |

### Phase 5: Complete Frontend Site — React + Tailwind + shadcn/ui 7페이지 프론트엔드 + 10개 백엔드 API 추가

**Goal:** 기본 바닐라 대시보드를 React + Tailwind CSS + Recharts 기반 완전한 SPA로 재구축. 7개 페이지 (Dashboard, Pipelines, PipelineDetail, Trigger, Costs, Channels, Settings) + 7개 새 백엔드 API.
**Requirements**: UI-01, UI-02, UI-03 extended
**Depends on:** Phase 4
**Plans:** 1/1 plans complete

Plans:
- [x] 05-01-PLAN.md — React frontend rebuild + backend API additions (channels, system, daily costs)
