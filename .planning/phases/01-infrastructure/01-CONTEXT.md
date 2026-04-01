# Phase 1: Infrastructure - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Stand up the project skeleton so a Temporal workflow can run end-to-end through typed worker pools, Google Sheets data can sync into SQLite, and pipeline artifacts land in the right directory structure — all verifiable before any content generation begins.

**In scope:** Temporal server config, SQLite schema + migrations, worker pool separation (GPU/CPU/API), Sheets ↔ SQLite sync, file/directory layout, project structure, dev tooling.

**Not in scope:** Actual content generation (script, image, TTS, video, upload) — those are Phase 2.

</domain>

<decisions>
## Implementation Decisions

### Project Layout
- **D-01:** Source code lives under `src/` with feature-module structure:
  - `src/workflows/` — Temporal workflow definitions
  - `src/activities/` — Temporal activity implementations (one file per domain: sheets, pipeline, cleanup)
  - `src/models/` — SQLModel DB models
  - `src/workers/` — Worker entry points (gpu_worker.py, cpu_worker.py, api_worker.py)
  - `src/services/` — Business logic called by activities (sheets_service.py, db_service.py)
  - `src/api/` — FastAPI routers
  - `src/main.py` — FastAPI app entry point
  - `src/config.py` — Pydantic Settings (env vars, channel configs)

### Temporal Deployment
- **D-02:** Temporal server runs via Docker Compose using `temporalio/auto-setup` image (includes Temporal server + PostgreSQL + Temporal Web UI). One `docker-compose.yml` at project root covers the full local dev stack.
- **D-03:** Temporal connection config (host, namespace, TLS) lives in `src/config.py` via Pydantic Settings, not hardcoded. Local default: `localhost:7233`.

### SQLite Schema (Phase 1 tables)
- **D-04:** Three tables needed for Phase 1, defined as SQLModel models with Alembic migrations:
  - `content_items` — rows synced from Google Sheets (topic, channel_id, status, sheets_row_id, created_at, updated_at)
  - `pipeline_runs` — one row per Temporal workflow execution (workflow_id, channel_id, content_item_id, status, started_at, completed_at, error_message, result_json)
  - `sync_log` — tracks each Sheets sync operation (synced_at, rows_added, rows_updated, error)
- **D-05:** SQLModel (Pydantic + SQLAlchemy) for all DB models. Alembic for migrations. DB file path configurable via `DATABASE_URL` env var (default: `data/pipeline.db`).

### Worker Pool Design
- **D-06:** Three Temporal Task Queues map to three separate worker processes:
  - `gpu-queue` → `src/workers/gpu_worker.py` — maxConcurrent=1 (enforces serial GPU usage: ComfyUI, IndexTTS-2, Ollama)
  - `cpu-queue` → `src/workers/cpu_worker.py` — maxConcurrent=4 (FFmpeg, file ops, thumbnail)
  - `api-queue` → `src/workers/api_worker.py` — maxConcurrent=8 (fal.ai, YouTube API, Gemini, Sheets)
- **D-07:** Activities are registered to the correct queue via `@activity.defn` + worker registration, not by convention. GPU activities: ComfyUI, IndexTTS-2, Ollama calls. CPU activities: FFmpeg, Pillow, file cleanup. API activities: fal.ai, YouTube, Sheets, Gemini.
- **D-08:** For Phase 1 validation, a `PipelineValidationWorkflow` runs a stub GPU activity and a stub CPU activity sequentially, with intentional-fail retry test, to prove the queue separation works before real content activities exist.

### Google Sheets ↔ SQLite Sync
- **D-09:** Sync is triggered manually via `POST /api/sync/sheets` FastAPI endpoint, which enqueues a Temporal activity on `api-queue`. Response is async (returns workflow_id; caller polls status via `GET /api/sync/status/{workflow_id}`).
- **D-10:** Sheets → SQLite direction: upsert on `sheets_row_id`. SQLite → Sheets direction: update status/URL columns in the originating row after pipeline completion. Both directions go through `src/services/sheets_service.py` using `gspread`.
- **D-11:** Google Sheets credentials: service account JSON path from `GOOGLE_SHEETS_CREDENTIALS` env var. Spreadsheet ID from `GOOGLE_SHEETS_ID` env var. Never hardcoded.
- **D-12:** Scheduled sync (polling interval) is deferred to Phase 3 (OPS-04 covers scheduled Temporal workflows). Phase 1 only needs manual trigger to validate the data flow.

### File / Artifact Layout
- **D-13:** Artifact directory: `data/pipeline/{workflow_run_id}/` created at workflow start by a setup activity. Subdirectories: `scripts/`, `images/`, `audio/`, `video/`, `thumbnails/`, `final/`.
- **D-14:** Cleanup activity deletes `scripts/`, `images/`, `audio/`, `video/`, `thumbnails/` after the final MP4 is confirmed in `final/`. `data/pipeline.db` and `data/cost_log.json` are never deleted by cleanup.
- **D-15:** `data/` directory is gitignored. All pipeline output stays local.

### Dev Tooling
- **D-16:** `uv` for dependency management and virtual environment. `pyproject.toml` at project root is the single config file (no setup.py, no requirements.txt).
- **D-17:** Dev workflow:
  - `docker compose up -d` — start Temporal server + Web UI
  - `uv run uvicorn src.main:app --reload` — start FastAPI
  - `uv run python -m src.workers.gpu_worker` — start GPU worker
  - `uv run python -m src.workers.cpu_worker` — start CPU worker
  - `uv run python -m src.workers.api_worker` — start API worker
- **D-18:** `.env` file for all secrets and config. `.env.example` checked into git. `.env` gitignored.
- **D-19:** `pytest tests/ -v --cov=src --cov-report=term-missing` for tests. Phase 1 tests: Temporal worker integration test (intentional fail + retry), SQLite upsert test, Sheets mock sync test.

### Claude's Discretion
- Exact Alembic migration file naming and structure
- FastAPI router file organization within `src/api/`
- Whether to use `temporalio` SDK 1.x connection pooling defaults or customize
- Specific Pydantic Settings field names (beyond what's named above)
- Docker Compose service names and port numbers (Temporal default: 7233, Web UI: 8080, FastAPI: 8000)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Tech Spec
- `CLAUDE.md` (project root) — Full technology stack, architecture decisions, local vs cloud split, cost estimates, all alternatives considered. This is the primary spec document.

### Requirements
- `.planning/REQUIREMENTS.md` — Full requirement IDs with acceptance criteria (ORCH-01 through FILE-02)
- `.planning/ROADMAP.md` — Phase 1 success criteria (5 verifiable conditions)
- `.planning/PROJECT.md` — Core value, non-goals, key decisions

### External Docs (no local copies — use context7 or web search)
- Temporal Python SDK: `temporalio` — Activity registration, Task Queue config, maxConcurrent setting, durable retry
- SQLModel + Alembic — Model definition, migration generation
- `gspread` 6.x — Service account auth, worksheet read/write
- Docker Compose `temporalio/auto-setup` — Official Temporal dev server image

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None yet — greenfield project. No existing components to reuse.

### Established Patterns
- None yet — patterns will be established in Phase 1 and carried forward.

### Integration Points
- FastAPI app (`src/main.py`) will be the single entry point for all HTTP-triggered operations (sync, status checks, dashboard endpoints in Phase 3)
- Temporal client initialized once in FastAPI lifespan, shared across all endpoints via FastAPI `Depends()`
- SQLModel engine created once, session factory via `Depends()` — no direct DB access in routers

</code_context>

<specifics>
## Specific Ideas

- **GPU worker maxConcurrent=1** is the critical correctness constraint — must be verifiable in Phase 1 success criteria (submit two GPU tasks simultaneously, confirm queued serial execution)
- **Validation workflow** (`PipelineValidationWorkflow`) uses stub activities (sleep + echo) to prove Temporal plumbing without real model dependencies — this lets Phase 1 succeed even before ComfyUI/IndexTTS-2 are installed
- **RTX 4070 8GB VRAM constraint** means GPU worker must serialize ALL GPU activities — ComfyUI, Ollama, IndexTTS-2 cannot run concurrently. maxConcurrent=1 enforces this at the queue level.

</specifics>

<deferred>
## Deferred Ideas

- Scheduled Sheets sync (polling interval) — deferred to Phase 3 with OPS-04 scheduled workflows
- Cost tracking dashboard — Phase 3 (OPS-05, OPS-06)
- Quality gate human-in-the-loop — Phase 3 (OPS-01, OPS-02)
- Multi-channel config profiles (CHAN-01, CHAN-02) — Phase 2
- Actual content activities (script, image, TTS, FFmpeg, upload) — Phase 2

</deferred>

---

*Phase: 01-infrastructure*
*Context gathered: 2026-04-01*
