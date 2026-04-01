---
phase: 01-infrastructure
plan: 01
subsystem: infra
tags: [python, uv, sqlmodel, alembic, pydantic-settings, temporalio, docker, sqlite, gspread]

requires: []
provides:
  - uv project with all Phase 1 dependencies installed (temporalio, fastapi, sqlmodel, alembic, pydantic-settings, gspread)
  - Docker Compose for Temporal server + PostgreSQL + Web UI
  - Pydantic Settings config reading TEMPORAL_HOST, DATABASE_URL, GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_ID
  - Three SQLModel tables (content_items, pipeline_runs, sync_log) with Alembic migration
  - db_service with upsert_content_item, create_pipeline_run, update_pipeline_run, create_sync_log
  - Skeletal test scaffold with skip markers for all Phase 1 test categories
affects:
  - 01-02 (workers/activities need config.py and models)
  - 01-03 (FastAPI needs db_service.py and config.py)
  - 01-04 (test implementation needs conftest.py fixtures and db_service)

tech-stack:
  added:
    - temporalio==1.24.0
    - fastapi==0.135.2
    - uvicorn==0.42.0
    - sqlmodel==0.0.37
    - alembic==1.18.4
    - pydantic-settings==2.13.1
    - gspread==6.2.1
    - google-auth
    - structlog==25.5.0
    - pytest==9.0.2
    - pytest-asyncio==1.3.0
    - pytest-cov==7.1.0
    - ruff
    - mypy
  patterns:
    - "Pydantic Settings with extra=ignore for .env compatibility with legacy env vars"
    - "SQLModel tables with explicit __tablename__ and Field(index=True, unique=True) for upsert keys"
    - "Alembic env.py reads DATABASE_URL from os.getenv, ensures data/ dir, imports all models before target_metadata"
    - "db_service upsert pattern: select-first, then update or create, always commit+refresh"
    - "Docker Compose UI port remapped to 8081 to avoid local 8080 conflict"

key-files:
  created:
    - pyproject.toml
    - docker-compose.yml
    - .env.example
    - .gitignore
    - src/config.py
    - src/models/content_item.py
    - src/models/pipeline_run.py
    - src/models/sync_log.py
    - src/models/__init__.py
    - src/services/db_service.py
    - alembic.ini
    - alembic/env.py
    - alembic/versions/f87e03439726_create_phase1_tables.py
    - tests/conftest.py
    - tests/test_db.py
    - tests/test_workers.py
    - tests/test_sheets_sync.py
  modified:
    - docker-compose.yml (replaced n8n compose with Temporal stack)

key-decisions:
  - "Settings extra=ignore to tolerate pre-existing n8n .env vars without failing"
  - "Alembic migration uses sa.String() instead of sqlmodel.sql.sqltypes.AutoString() to avoid missing import at migration time"
  - "Temporal Web UI mapped to 8081:8080 to avoid port 8080 conflict per RESEARCH.md"
  - "db_service uses upsert (select-first) pattern on sheets_row_id as the stable natural key"

patterns-established:
  - "Pattern: uv sync --extra dev for dependency installation across all phases"
  - "Pattern: uv run <cmd> for all tool invocations (alembic, pytest, ruff, mypy)"
  - "Pattern: Alembic env.py must import all SQLModel model modules before setting target_metadata"
  - "Pattern: db_service functions take Session as first arg, caller owns session lifecycle"

requirements-completed:
  - ORCH-02
  - DATA-01
  - DATA-02

duration: 9min
completed: 2026-04-02
---

# Phase 1 Plan 01: Project Foundation Summary

**Python project scaffold with SQLModel DB layer (content_items, pipeline_runs, sync_log), Alembic migrations, Pydantic Settings config, db_service CRUD, and Docker Compose for Temporal — all verified with ruff + mypy clean.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-04-01T23:01:08Z
- **Completed:** 2026-04-02T00:10:00Z
- **Tasks:** 4 (Task 0 + Tasks 1-3)
- **Files created:** 17

## Accomplishments

- All Phase 1 Python dependencies installed via uv with Python 3.12 (temporalio, fastapi, sqlmodel, alembic, pydantic-settings, gspread, structlog + dev tools)
- Docker Compose validated: Temporal auto-setup + PostgreSQL + Web UI (UI on 8081 to avoid 8080 conflict)
- Three SQLModel tables defined and migrated to SQLite: content_items (sheets_row_id unique index), pipeline_runs (workflow_id unique index, FK to content_items), sync_log
- db_service with upsert_content_item (idempotent on sheets_row_id), create_pipeline_run, update_pipeline_run, create_sync_log
- 13 skeletal test stubs created (8 DB, 2 Temporal, 3 Sheets) all collected by pytest and skipped
- ruff check and mypy src/ both pass with no issues

## Task Commits

1. **Task 0: Skeletal test scaffold** - `c156161` (test)
2. **Task 1: Project scaffold** - `b934fd7` (chore)
3. **Task 2: Pydantic Settings + SQLModel models** - `2977801` (feat)
4. **Task 3: Alembic migrations + db_service** - `1296a4b` (feat)
5. **Cleanup: alembic README** - `826a611` (chore)
6. **Cleanup: ruff format migration** - `2514d75` (chore)

## Files Created/Modified

- `pyproject.toml` - All Phase 1 deps + dev tools, pytest asyncio_mode=auto, ruff+mypy config
- `docker-compose.yml` - Replaced n8n compose with Temporal auto-setup + PostgreSQL + Web UI (8081)
- `.env.example` - Template with TEMPORAL_HOST, DATABASE_URL, GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_ID
- `.gitignore` - Excludes .env, data/, .venv/, __pycache__/
- `src/config.py` - Pydantic Settings with all 5 env vars, extra=ignore
- `src/models/content_item.py` - ContentItem SQLModel table
- `src/models/pipeline_run.py` - PipelineRun SQLModel table with FK to content_items
- `src/models/sync_log.py` - SyncLog SQLModel table
- `src/models/__init__.py` - Re-exports all 3 models
- `src/services/db_service.py` - Full CRUD: upsert_content_item, create/update_pipeline_run, create_sync_log
- `alembic.ini` - Cleared sqlalchemy.url (overridden in env.py)
- `alembic/env.py` - Imports all models, reads DATABASE_URL, ensures data/ dir exists
- `alembic/versions/f87e03439726_create_phase1_tables.py` - Creates all 3 tables with indexes
- `tests/conftest.py` - db_session (in-memory SQLite) and tmp_pipeline_dir fixtures
- `tests/test_db.py` - 8 skipped DB CRUD stubs
- `tests/test_workers.py` - 2 skipped Temporal integration stubs
- `tests/test_sheets_sync.py` - 3 skipped Sheets sync stubs

## Decisions Made

- Used `extra="ignore"` in Settings to tolerate pre-existing n8n env vars in `.env` without validation errors
- Migration file uses `sa.String()` instead of `sqlmodel.sql.sqltypes.AutoString()` — autogenerate produced invalid code missing the sqlmodel import
- Temporal Web UI mapped to `8081:8080` per RESEARCH.md Open Question 1 (port 8080 occupied)
- `google_sheets_credentials` and `google_sheets_id` default to empty string so app starts without Sheets config (graceful degradation)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Pydantic Settings crash on extra env vars**
- **Found during:** Task 2 (config.py verification)
- **Issue:** Existing `.env` file contains n8n vars (N8N_USER, N8N_PASSWORD, N8N_ENCRYPTION_KEY). Pydantic Settings raises ValidationError "Extra inputs are not permitted" by default.
- **Fix:** Added `extra="ignore"` to `SettingsConfigDict` in `src/config.py`
- **Files modified:** `src/config.py`
- **Verification:** `uv run python -c "from src.config import settings"` succeeds
- **Committed in:** `2977801` (Task 2 commit)

**2. [Rule 1 - Bug] Fixed Alembic migration missing sqlmodel import**
- **Found during:** Task 3 (alembic upgrade head)
- **Issue:** Autogenerated migration used `sqlmodel.sql.sqltypes.AutoString()` without importing sqlmodel, causing `NameError: name 'sqlmodel' is not defined`
- **Fix:** Replaced all `sqlmodel.sql.sqltypes.AutoString()` with `sa.String()` in the migration file (equivalent for SQLite)
- **Files modified:** `alembic/versions/f87e03439726_create_phase1_tables.py`
- **Verification:** `alembic upgrade head` completes without errors, tables verified in SQLite
- **Committed in:** `1296a4b` (Task 3 commit)

**3. [Rule 1 - Bug] Fixed ruff import ordering violations**
- **Found during:** Task 3 (ruff check)
- **Issue:** `src/services/db_service.py` had unused `SQLModel` import; `tests/conftest.py` had unsorted imports
- **Fix:** Removed unused import; fixed import ordering in conftest.py
- **Files modified:** `src/services/db_service.py`, `tests/conftest.py`
- **Verification:** `ruff check src/ tests/` exits 0
- **Committed in:** `1296a4b` (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 bugs)
**Impact on plan:** All auto-fixes were necessary for correctness. No scope creep.

## Issues Encountered

- Windows file locking prevented `os.remove('data/pipeline.db')` in the upsert verification script — harmless, the DB file remained but the upsert logic was confirmed correct (UPSERT_OK printed before the error)
- `alembic init` produced a migration referencing `sqlmodel.sql.sqltypes.AutoString` without the import — this is a known SQLModel+Alembic autogenerate issue, fixed by using standard `sa.String()`

## User Setup Required

None — no external service configuration required for this plan. The `.env.example` shows what variables are needed; the user must copy it to `.env` and fill in Google Sheets credentials when plan 01-03 (Sheets sync) runs.

## Next Phase Readiness

- Plan 01-02 can proceed: config.py, models, and project structure are ready for worker and activity scaffolding
- Plan 01-03 can proceed: db_service and config provide the foundation for FastAPI and Sheets sync endpoint
- Plan 01-04 can proceed: test fixtures in conftest.py are ready; db_service functions are available to test
- Docker Desktop must be started before `docker compose up -d` (Docker engine was not running at research time)

## Self-Check: PASSED

- All 14 key files verified present on disk
- All 4 task commits found in git history (c156161, b934fd7, 2977801, 1296a4b)
- ruff check src/ tests/ exits 0
- mypy src/ exits 0
- pytest --co collects 13 tests (all skipped as expected)
- alembic upgrade head creates 3 tables (content_items, pipeline_runs, sync_log)
- upsert_content_item creates and updates by sheets_row_id (idempotent)

---
*Phase: 01-infrastructure*
*Completed: 2026-04-02*
