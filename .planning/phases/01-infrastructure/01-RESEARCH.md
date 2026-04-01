# Phase 1: Infrastructure - Research

**Researched:** 2026-04-01
**Domain:** Temporal Python SDK, SQLModel/Alembic, gspread, FastAPI, Docker
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Source code under `src/` with feature-module structure: `workflows/`, `activities/`, `models/`, `workers/`, `services/`, `api/`, `main.py`, `config.py`
- **D-02:** Temporal server via Docker Compose using `temporalio/auto-setup` image. One `docker-compose.yml` at project root.
- **D-03:** Temporal connection config in `src/config.py` via Pydantic Settings. Local default: `localhost:7233`.
- **D-04:** Three SQLModel tables: `content_items`, `pipeline_runs`, `sync_log`. Alembic migrations.
- **D-05:** SQLModel + Alembic. `DATABASE_URL` env var (default: `data/pipeline.db`).
- **D-06:** Three Task Queues: `gpu-queue` (maxConcurrent=1), `cpu-queue` (maxConcurrent=4), `api-queue` (maxConcurrent=8).
- **D-07:** Activities registered via `@activity.defn` + worker registration — not by convention.
- **D-08:** `PipelineValidationWorkflow` with stub activities to prove queue separation.
- **D-09:** Sheets sync via `POST /api/sync/sheets` FastAPI endpoint, async response (returns workflow_id).
- **D-10:** Sheets→SQLite upsert on `sheets_row_id`. SQLite→Sheets update after pipeline completion. Both through `sheets_service.py` using gspread.
- **D-11:** Google Sheets credentials from `GOOGLE_SHEETS_CREDENTIALS` env var (path to service account JSON). Spreadsheet ID from `GOOGLE_SHEETS_ID` env var.
- **D-12:** Scheduled sync deferred to Phase 3. Phase 1 only needs manual trigger.
- **D-13:** Artifact directory: `data/pipeline/{workflow_run_id}/` with subdirs `scripts/`, `images/`, `audio/`, `video/`, `thumbnails/`, `final/`.
- **D-14:** Cleanup deletes `scripts/`, `images/`, `audio/`, `video/`, `thumbnails/` after final MP4 confirmed. Never deletes `data/pipeline.db` or `data/cost_log.json`.
- **D-15:** `data/` is gitignored.
- **D-16:** `uv` for dependency management. `pyproject.toml` only (no setup.py, no requirements.txt).
- **D-17:** Dev workflow: `docker compose up -d`, then one `uv run` per process (FastAPI, GPU worker, CPU worker, API worker).
- **D-18:** `.env` file for secrets. `.env.example` in git. `.env` gitignored.
- **D-19:** `pytest tests/ -v --cov=src --cov-report=term-missing`. Phase 1 tests: Temporal worker integration (intentional fail + retry), SQLite upsert, Sheets mock sync.

### Claude's Discretion

- Exact Alembic migration file naming and structure
- FastAPI router file organization within `src/api/`
- Whether to use `temporalio` SDK connection pooling defaults or customize
- Specific Pydantic Settings field names (beyond what's named above)
- Docker Compose service names and port numbers (Temporal default: 7233, Web UI: 8080, FastAPI: 8000)

### Deferred Ideas (OUT OF SCOPE)

- Scheduled Sheets sync (polling interval) — Phase 3, OPS-04
- Cost tracking dashboard — Phase 3, OPS-05/OPS-06
- Quality gate human-in-the-loop — Phase 3, OPS-01/OPS-02
- Multi-channel config profiles — Phase 2, CHAN-01/CHAN-02
- Actual content activities (script, image, TTS, FFmpeg, upload) — Phase 2
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ORCH-01 | Temporal workflow orchestrates full pipeline (Activity-per-Service pattern) | Verified: `@workflow.defn` + `@activity.defn` pattern, `execute_activity()` with task_queue routing |
| ORCH-02 | GPU/CPU/API worker pools separated by Temporal Task Queue (GPU maxConcurrent=1) | Verified: `max_concurrent_activities=1` on Worker init; three separate Worker processes per queue |
| ORCH-03 | Durable retry — only failed Activity retries, not full workflow | Verified: Temporal default retry policy; custom `RetryPolicy` with `maximum_attempts`, `backoff_coefficient` |
| DATA-01 | Google Sheets → SQLite sync (Sheets is UI only, SQLite is SSOT) | Verified: gspread 6.x `service_account()` + `open_by_key()`; upsert on `sheets_row_id` via SQLModel |
| DATA-02 | All pipeline state read/written exclusively through SQLite during execution | Pattern: No gspread calls inside workflow activities except sync activities on api-queue |
| DATA-03 | Pipeline results written to Sheets after completion (YouTube URL, status) | Verified: gspread `update()` on row by ID via `sheets_service.py` |
| FILE-01 | Artifacts in `/data/pipeline/{workflow_run_id}/` directory tree | Pattern: setup activity creates dirs at workflow start; `pathlib.Path` operations |
| FILE-02 | Cleanup Activity deletes intermediate files after pipeline completion | Pattern: CPU-queue activity; confirm `final/` before deleting `images/`, `audio/`, etc. |
</phase_requirements>

---

## Summary

Phase 1 establishes the skeleton: Temporal orchestration, three typed worker pools, SQLite data layer, Google Sheets sync, and artifact directory management. All implementation is "wire-up only" — no real content generation. The `PipelineValidationWorkflow` with stub activities proves the infrastructure end-to-end before Phase 2 adds real model calls.

The Temporal Python SDK (`temporalio` 1.24.0) officially supports Python 3.10–3.14, so the system Python 3.14 on this machine is compatible. However, the spec targets Python 3.12+, and `uv` can pin a 3.12 virtual environment. The key concurrency invariant — GPU worker `max_concurrent_activities=1` — is enforced at the Worker constructor level, not in application code.

**Important discovery:** The decision in D-02 specifies `temporalio/auto-setup`. Research shows this image includes auto-namespace registration but is primarily designed for development. The official recommendation as of 2025 shifted to `temporal server start-dev` (Temporal CLI) for local dev and `temporalio/server` + separate admin-tools for more controlled setups. However, `temporalio/auto-setup` still works for dev and D-02 is a locked decision — the docker-compose should use it. See Pitfall 2 below for the multi-service compose complexity.

**Primary recommendation:** Use `temporalio/auto-setup` in docker-compose as decided. Use `pydantic_data_converter` for all activity inputs/outputs so Pydantic models (not dataclasses) are used throughout, enabling datetime support and startup-time serialization validation.

---

## Standard Stack

### Core (Phase 1)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `temporalio` | 1.24.0 | Temporal Python SDK — workflows, activities, workers | Official SDK; durable execution, GPU task routing |
| `fastapi` | 0.135.2 | REST API layer — sync trigger endpoint, status polling | Async, `Depends()` DI, lifespan for Temporal client |
| `uvicorn` | 0.42.0 | ASGI server for FastAPI | Standard pairing with FastAPI |
| `sqlmodel` | 0.0.37 | ORM — SQLModel table definitions | Pydantic + SQLAlchemy merged; FastAPI-native |
| `alembic` | 1.18.4 | Database migrations | SQLAlchemy-native; autogenerate from SQLModel metadata |
| `pydantic-settings` | 2.13.1 | Config/env var management (`src/config.py`) | `BaseSettings` reads `.env` + environment; type-safe |
| `gspread` | 6.2.1 | Google Sheets client | Service account auth, worksheet CRUD, batch ops |
| `google-auth` | latest | OAuth2 for gspread service account | Required by gspread for service account auth |
| `structlog` | 25.5.0 | Structured logging | JSON logs; easy to correlate with workflow_run_id |
| `pytest` | 9.0.2 | Test framework | Project CLAUDE.md mandates this exact command |
| `pytest-asyncio` | 1.3.0 | Async test support | Temporal workers/activities are async |
| `pytest-cov` | 7.1.0 | Coverage reporting | Project CLAUDE.md mandates `--cov=src` |

### Python Version

| Item | Value | Note |
|------|-------|------|
| Target | 3.12 | Spec requires 3.12+. Pin with `uv python pin 3.12` |
| System installed | 3.14.3 | Compatible with temporalio (3.10–3.14 supported) |
| uv available | 3.12.12 | `uv python install 3.12` if not already downloaded |

**Installation:**
```bash
uv init --python 3.12
uv add temporalio fastapi uvicorn sqlmodel alembic pydantic-settings gspread google-auth structlog
uv add --dev pytest pytest-asyncio pytest-cov
```

**Version verification (confirmed 2026-04-01 via PyPI):**
```
temporalio: 1.24.0  (published March 2026)
sqlmodel: 0.0.37
alembic: 1.18.4
gspread: 6.2.1
fastapi: 0.135.2
pydantic-settings: 2.13.1
```

---

## Architecture Patterns

### Recommended Project Structure

```
project_root/
├── docker-compose.yml          # Temporal server + Web UI
├── pyproject.toml              # uv project config, all deps
├── .env                        # secrets (gitignored)
├── .env.example                # template (committed)
├── alembic.ini                 # Alembic config (sqlalchemy.url overridden from env)
├── alembic/
│   ├── env.py                  # target_metadata = SQLModel.metadata
│   └── versions/               # migration files
├── src/
│   ├── config.py               # Pydantic Settings (BaseSettings)
│   ├── main.py                 # FastAPI app + lifespan
│   ├── api/
│   │   ├── sync.py             # POST /api/sync/sheets, GET /api/sync/status/{id}
│   │   └── health.py           # GET /health
│   ├── workflows/
│   │   └── pipeline_validation.py  # PipelineValidationWorkflow
│   ├── activities/
│   │   ├── sheets.py           # sync_sheets_to_sqlite, write_results_to_sheets
│   │   ├── pipeline.py         # setup_pipeline_dirs (FILE-01)
│   │   └── cleanup.py          # cleanup_intermediate_files (FILE-02)
│   ├── models/
│   │   ├── __init__.py         # imports all models (Alembic needs this)
│   │   ├── content_item.py
│   │   ├── pipeline_run.py
│   │   └── sync_log.py
│   ├── services/
│   │   ├── db_service.py       # SQLModel session factory, CRUD helpers
│   │   └── sheets_service.py   # gspread client, sheet operations
│   └── workers/
│       ├── gpu_worker.py       # max_concurrent_activities=1
│       ├── cpu_worker.py       # max_concurrent_activities=4
│       └── api_worker.py       # max_concurrent_activities=8
├── tests/
│   ├── conftest.py             # shared fixtures (Temporal env, DB session)
│   ├── test_workers.py         # integration: queue separation, retry
│   ├── test_db.py              # SQLite upsert, pipeline_run CRUD
│   └── test_sheets_sync.py     # mocked gspread, sync flow
└── data/                       # gitignored
    ├── pipeline.db
    └── pipeline/
        └── {workflow_run_id}/
```

---

### Pattern 1: Worker Process with max_concurrent_activities

**What:** Each worker is a separate Python process that polls one Task Queue.

**When to use:** Always. Three separate `uv run python -m src.workers.*` processes.

```python
# Source: https://python.temporal.io/temporalio.worker.Worker.html
# src/workers/gpu_worker.py
import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.contrib.pydantic import pydantic_data_converter
from src.config import settings
from src.activities.pipeline import setup_pipeline_dirs
from src.activities.cleanup import cleanup_intermediate_files

async def main():
    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
        data_converter=pydantic_data_converter,
    )
    worker = Worker(
        client,
        task_queue="gpu-queue",
        workflows=[],              # GPU worker runs no workflows — only activities
        activities=[
            setup_pipeline_dirs,  # stub for Phase 1 validation
        ],
        max_concurrent_activities=1,  # CRITICAL: serializes all GPU tasks
    )
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
```

**Key:** `max_concurrent_activities=1` is the parameter name (default is `None` which falls back to 100 slots). Setting it to `1` enforces serial GPU execution.

---

### Pattern 2: FastAPI Lifespan with Temporal Client

**What:** Temporal client initialized once at app startup via FastAPI lifespan, shared via `app.state`.

```python
# Source: FastAPI + Temporal integration pattern (verified multiple sources)
# src/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from src.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.temporal_client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
        data_converter=pydantic_data_converter,
    )
    yield
    # Client cleanup (if needed) goes here

app = FastAPI(lifespan=lifespan)
```

Access in routes via `request.app.state.temporal_client` or inject via a `Depends()` function.

---

### Pattern 3: Workflow Triggers Activity on Specific Task Queue

**What:** Workflow routes each activity to the correct worker pool by specifying `task_queue`.

```python
# Source: https://docs.temporal.io/develop/python/core-application
# src/workflows/pipeline_validation.py
from temporalio import workflow
from temporalio.common import RetryPolicy
from datetime import timedelta

@workflow.defn
class PipelineValidationWorkflow:
    @workflow.run
    async def run(self, params: ValidationParams) -> ValidationResult:
        # GPU activity — goes to gpu-queue (maxConcurrent=1)
        gpu_result = await workflow.execute_activity(
            stub_gpu_activity,
            params,
            task_queue="gpu-queue",
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        # CPU activity — goes to cpu-queue (maxConcurrent=4)
        cpu_result = await workflow.execute_activity(
            stub_cpu_activity,
            gpu_result,
            task_queue="cpu-queue",
            start_to_close_timeout=timedelta(seconds=30),
        )
        return ValidationResult(gpu=gpu_result, cpu=cpu_result)
```

**Critical:** `task_queue` in `execute_activity()` is how routing works. If omitted, it inherits the workflow's task queue (which runs on the Worker that started the workflow — not the specialized worker).

---

### Pattern 4: SQLModel Table Definition + Alembic

**What:** Define SQLModel table models; configure Alembic `env.py` to point at `SQLModel.metadata`.

```python
# Source: https://docs.temporal.io/develop/python + SQLModel docs
# src/models/content_item.py
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel

class ContentItem(SQLModel, table=True):
    __tablename__ = "content_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    sheets_row_id: str = Field(index=True, unique=True)  # upsert key
    topic: str
    channel_id: str
    status: str = "pending"  # pending / running / done / failed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

```python
# alembic/env.py — critical fix: import ALL models before target_metadata
from sqlmodel import SQLModel
from src.models import content_item, pipeline_run, sync_log  # noqa: F401

target_metadata = SQLModel.metadata
```

**Critical pitfall:** If model files are not imported before `target_metadata = SQLModel.metadata`, Alembic sees an empty schema and generates no migration.

---

### Pattern 5: gspread Service Account Auth

**What:** Authenticate with Google Sheets using a service account JSON file.

```python
# Source: https://github.com/burnash/gspread
# src/services/sheets_service.py
import gspread
from src.config import settings

def get_sheets_client() -> gspread.Client:
    return gspread.service_account(filename=settings.google_sheets_credentials)

def open_spreadsheet(client: gspread.Client) -> gspread.Spreadsheet:
    return client.open_by_key(settings.google_sheets_id)
```

---

### Pattern 6: Temporal Activity with Pydantic Input/Output

**What:** Activities use Pydantic models (not plain dicts) with `pydantic_data_converter` on the client and all workers.

```python
# Source: https://python.temporal.io/temporalio.contrib.pydantic.html
from temporalio import activity
from pydantic import BaseModel

class SetupDirsInput(BaseModel):
    workflow_run_id: str

class SetupDirsOutput(BaseModel):
    base_path: str
    created: bool

@activity.defn
async def setup_pipeline_dirs(params: SetupDirsInput) -> SetupDirsOutput:
    from pathlib import Path
    base = Path("data/pipeline") / params.workflow_run_id
    for subdir in ["scripts", "images", "audio", "video", "thumbnails", "final"]:
        (base / subdir).mkdir(parents=True, exist_ok=True)
    return SetupDirsOutput(base_path=str(base), created=True)
```

**Critical:** Both client and all workers must use the same `data_converter=pydantic_data_converter`. Mixing default converter with pydantic converter causes deserialization failures.

---

### Pattern 7: Alembic env.py Dynamic DB URL from Env Var

```python
# alembic/env.py
import os
from alembic import context

config = context.config
db_url = os.getenv("DATABASE_URL", "sqlite:///data/pipeline.db")
config.set_main_option("sqlalchemy.url", db_url)
```

---

### Anti-Patterns to Avoid

- **Specifying activities in the wrong worker:** Registering a GPU activity in the CPU worker means it runs with maxConcurrent=4, not 1. Assignments must be explicit.
- **Not importing models in `alembic/env.py`:** Alembic produces empty migrations. Import all model modules explicitly.
- **Using `asyncio.sleep()` in a workflow directly for timing:** Fine for Temporal (it replaces it with a durable timer), but confusing. Use `await workflow.execute_activity(sleep_stub, ...)` for explicit "wait" steps in validation workflows.
- **Not setting `task_queue` in `execute_activity()`:** Activity falls back to workflow's own queue, bypassing GPU/CPU/API routing.
- **Storing gspread client as a module-level singleton:** Activity workers reload on each task poll cycle. Initialize client inside the activity or use a service class with lazy init.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Workflow durable state | Custom state machine | Temporal SDK | Temporal handles crash recovery, retries, history replay automatically |
| Activity retry logic | `for attempt in range(N): try/except` | `RetryPolicy` in `execute_activity()` | Temporal retries survive worker restarts; custom loops do not |
| DB migrations | Raw `CREATE TABLE IF NOT EXISTS` | Alembic autogenerate | Schema drift detection, rollback, versioned history |
| ORM/DB sessions | `sqlite3.connect()` raw | SQLModel + SQLAlchemy session | Type safety, relationship management, Pydantic integration |
| Sheets auth | OAuth2 flow from scratch | gspread `service_account()` | gspread handles token refresh, retry on 429, batch operations |
| Concurrency limiting | `asyncio.Semaphore` around GPU calls | `max_concurrent_activities=1` on Worker | Worker-level enforcement survives crashes; semaphore does not |

**Key insight:** Temporal's value is that durable state and retry survive process restarts. Any custom retry/semaphore logic built in Python is ephemeral — it vanishes if the worker crashes.

---

## Common Pitfalls

### Pitfall 1: `max_concurrent_activities` Default is NOT 1 — It's Effectively 100

**What goes wrong:** Omitting `max_concurrent_activities` on the GPU worker means it defaults to `None`, which maps to 100 slots. Multiple GPU activities run in parallel, causing VRAM OOM.

**Why it happens:** The parameter name is non-obvious and the default is permissive. Devs assume the worker "knows" it's a GPU worker.

**How to avoid:** Explicitly set `max_concurrent_activities=1` in `gpu_worker.py`. Add a comment explaining why.

**Warning signs:** ComfyUI crashing mid-generation; Ollama process killed; two GPU tasks completing at same time in Temporal Web UI timeline.

---

### Pitfall 2: `temporalio/auto-setup` Docker Compose Complexity

**What goes wrong:** The `temporalio/auto-setup` image is simpler than the full `temporalio/server` stack but still requires PostgreSQL. The archived `temporalio/docker-compose` repo's default compose includes PostgreSQL + Elasticsearch (needed for visibility search). Running all services cold takes 30-60 seconds before Temporal is ready.

**What was found:** The official recommendation moved to `temporal server start-dev` (Temporal CLI) for zero-dependency local dev — it embeds SQLite internally, no Docker required, exposes gRPC on port 7233 and Web UI on port 8233. However, D-02 locks `temporalio/auto-setup` via docker-compose.

**The simplest `auto-setup` compose that works (PostgreSQL only, no Elasticsearch):**
```yaml
# Source: temporalio/docker-compose patterns (archived repo + samples-server)
services:
  postgresql:
    image: postgres:16
    environment:
      POSTGRES_USER: temporal
      POSTGRES_PASSWORD: temporal
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "temporal"]
      interval: 5s
      retries: 20

  temporal:
    image: temporalio/auto-setup:latest
    depends_on:
      postgresql:
        condition: service_healthy
    environment:
      - DB=postgres12
      - DB_PORT=5432
      - POSTGRES_USER=temporal
      - POSTGRES_PWD=temporal
      - POSTGRES_SEEDS=postgresql
    ports:
      - "7233:7233"

  temporal-ui:
    image: temporalio/ui:latest
    depends_on:
      - temporal
    environment:
      - TEMPORAL_ADDRESS=temporal:7233
    ports:
      - "8080:8080"
```

**Note:** Port 8080 is already occupied on this machine (something is already running there). Use `8081:8080` for the UI or stop the conflicting service. Verify with `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080`.

**Warning signs:** `temporal` container exits early; "namespace not found" errors on first workflow start.

---

### Pitfall 3: Alembic Misses Tables Because Models Weren't Imported

**What goes wrong:** Running `alembic revision --autogenerate` produces an empty migration with no `op.create_table()` calls.

**Why it happens:** SQLModel registers table metadata when model classes are defined (at import time). If `alembic/env.py` only imports `SQLModel` but not the model modules, the metadata is empty.

**How to avoid:**
```python
# alembic/env.py — import every model module explicitly
from src.models import content_item  # noqa: F401
from src.models import pipeline_run  # noqa: F401
from src.models import sync_log      # noqa: F401
```

Or create `src/models/__init__.py` that imports all models, then `from src import models` in env.py.

---

### Pitfall 4: pydantic_data_converter Must Match Across Client and All Workers

**What goes wrong:** Client uses `pydantic_data_converter`, GPU worker uses the default converter. Activity inputs deserialize as raw dicts instead of Pydantic models, causing `AttributeError` on `.topic` access.

**Why it happens:** The converter is per-connection. If client and worker disagree, Temporal stores Pydantic-encoded bytes but the worker tries to decode them as plain JSON.

**How to avoid:** Set `data_converter=pydantic_data_converter` on every `Client.connect()` call — in `src/main.py` (FastAPI), `src/workers/gpu_worker.py`, `src/workers/cpu_worker.py`, `src/workers/api_worker.py`, and in tests.

---

### Pitfall 5: No I/O or Non-Determinism Inside Workflow Code

**What goes wrong:** Developer puts `datetime.now()`, `random.randint()`, `os.path.exists()`, or `httpx.get()` directly inside a `@workflow.defn` class method. Temporal's sandbox raises non-determinism errors or the workflow produces different results on replay.

**Why it happens:** Workflows look like normal async Python. It's not obvious that they run in a restricted sandbox.

**How to avoid:** Workflows only call `workflow.execute_activity(...)`. All I/O, randomness, and system calls go inside `@activity.defn` functions.

---

### Pitfall 6: Docker Engine Not Running on Windows

**What goes wrong:** `docker compose up` fails with "open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified."

**Why it happens:** Docker Desktop for Windows requires the Docker Engine to be running. It doesn't auto-start.

**Current state:** Docker Desktop is installed (v28.0.1) but the engine is not running at research time.

**How to avoid:** Start Docker Desktop before running `docker compose up -d`. Add startup check to dev workflow docs.

---

### Pitfall 7: gspread 6.x Removed `oauth2client` Dependency

**What goes wrong:** Old gspread 5.x tutorials use `gspread.authorize(credentials)` with `oauth2client`. gspread 6.x uses `google-auth` instead.

**How to avoid:** Use `gspread.service_account(filename=path)` (not `gspread.authorize`). Ensure `google-auth` is in dependencies, not `oauth2client`.

---

## Code Examples

### Worker with maxConcurrent (Phase 1 Critical Pattern)

```python
# Source: https://python.temporal.io/temporalio.worker.Worker.html
from temporalio.worker import Worker

# GPU Worker — strictly serial
worker = Worker(
    client,
    task_queue="gpu-queue",
    workflows=[PipelineValidationWorkflow],  # only on GPU worker for Phase 1 validation
    activities=[stub_gpu_activity, setup_pipeline_dirs],
    max_concurrent_activities=1,             # enforces serial GPU execution
)

# CPU Worker
worker = Worker(
    client,
    task_queue="cpu-queue",
    workflows=[],
    activities=[stub_cpu_activity, cleanup_intermediate_files],
    max_concurrent_activities=4,
)

# API Worker
worker = Worker(
    client,
    task_queue="api-queue",
    workflows=[],
    activities=[sync_sheets_to_sqlite, write_results_to_sheets],
    max_concurrent_activities=8,
)
```

### RetryPolicy for Intentional Fail Test (ORCH-03 Validation)

```python
# Source: https://docs.temporal.io/develop/python/failure-detection
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError
from datetime import timedelta

@activity.defn
async def stub_gpu_activity(params: StubInput) -> StubOutput:
    attempt = activity.info().attempt
    if params.should_fail and attempt < 3:
        raise ApplicationError(
            f"Intentional failure on attempt {attempt}",
            next_retry_delay=timedelta(seconds=1),
        )
    return StubOutput(message="GPU activity succeeded", attempt=attempt)

# In workflow:
result = await workflow.execute_activity(
    stub_gpu_activity,
    StubInput(should_fail=True),
    task_queue="gpu-queue",
    start_to_close_timeout=timedelta(seconds=30),
    retry_policy=RetryPolicy(
        maximum_attempts=5,
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
    ),
)
```

### SQLModel Upsert Pattern (DATA-01)

```python
# src/services/db_service.py
from sqlmodel import Session, select
from src.models.content_item import ContentItem

def upsert_content_item(session: Session, data: dict) -> ContentItem:
    existing = session.exec(
        select(ContentItem).where(ContentItem.sheets_row_id == data["sheets_row_id"])
    ).first()
    if existing:
        for key, value in data.items():
            setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
        session.add(existing)
    else:
        item = ContentItem(**data)
        session.add(item)
    session.commit()
    return existing or item
```

### Pydantic Settings Config

```python
# src/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Temporal
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"

    # Database
    database_url: str = "sqlite:///data/pipeline.db"

    # Google Sheets (required — no defaults)
    google_sheets_credentials: str  # path to service account JSON
    google_sheets_id: str           # spreadsheet ID

settings = Settings()
```

### Directory Setup Activity (FILE-01)

```python
# src/activities/pipeline.py
from pathlib import Path
from temporalio import activity

@activity.defn
async def setup_pipeline_dirs(params: SetupDirsInput) -> SetupDirsOutput:
    base = Path("data/pipeline") / params.workflow_run_id
    subdirs = ["scripts", "images", "audio", "video", "thumbnails", "final"]
    for subdir in subdirs:
        (base / subdir).mkdir(parents=True, exist_ok=True)
    return SetupDirsOutput(base_path=str(base), created=True)
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | Temporal server via docker-compose | AVAILABLE (engine stopped) | Docker 28.0.1 | Start Docker Desktop before `docker compose up -d` |
| Docker Compose | Temporal server | AVAILABLE | v2.33.1-desktop.1 | — |
| Python 3.12+ | `uv` project | AVAILABLE via uv download | 3.12.12 (downloadable), 3.14.3 (installed) | `uv python install 3.12` |
| `uv` | Dependency management | AVAILABLE | 0.9.30 | — |
| Port 7233 | Temporal gRPC | CLEAR | — | — |
| Port 8080 | Temporal Web UI | OCCUPIED | Something running | Use `8081:8080` in docker-compose |
| Port 8000 | FastAPI | CLEAR (assumed) | — | — |
| Temporal CLI | `temporal server start-dev` (alternative) | NOT FOUND | — | Use docker-compose per D-02 |

**Missing dependencies with no fallback:**
- Docker Engine not running at research time — must start Docker Desktop before running `docker compose up -d`

**Missing dependencies with fallback:**
- Port 8080 conflict: map Temporal Web UI to `8081:8080` in docker-compose

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `gspread.authorize(oauth2client_creds)` | `gspread.service_account(filename=...)` | gspread 6.x (2024) | `oauth2client` removed — do not use |
| Alembic `sqlalchemy.url` in alembic.ini | Override in `env.py` via `os.getenv()` | Established practice | Enables 12-factor config, DATABASE_URL env var |
| Temporal docker-compose `temporalio/docker-compose` repo | `temporalio/samples-server/compose` (archived → samples) | 2024 | Use samples-server compose patterns |
| Worker `maxConcurrentActivities` missing → default 100 | Must be explicit: `max_concurrent_activities=1` | Always true — just easily missed | GPU VRAM safety |
| Pydantic v1 in Temporal | `temporalio.contrib.pydantic` (v2 only) | Temporal SDK ~1.6+ | Use `pydantic_data_converter`; Pydantic v1 not supported |

**Deprecated/outdated:**
- `gspread.authorize()` with `oauth2client`: removed in gspread 6.x
- `temporalio/docker-compose` GitHub repo: archived, use `temporalio/samples-server/compose`

---

## Open Questions

1. **Port 8080 conflict**
   - What we know: Something is listening on localhost:8080 (returns HTTP 200)
   - What's unclear: What service is occupying it (likely n8n on 5678 per existing docker-compose.yml — but 8080 is something else)
   - Recommendation: Map Temporal Web UI to `8081:8080` in docker-compose. Investigate the 8080 occupant separately.

2. **`temporalio/auto-setup` latest tag stability**
   - What we know: D-02 specifies this image; it is recommended for dev not production
   - What's unclear: Whether `latest` tag is stable enough or if we should pin a specific version (e.g., `1.26.2`)
   - Recommendation: Pin a specific version tag (check Docker Hub for latest `temporalio/auto-setup` tag). Using `latest` risks unexpected upgrades breaking the dev stack.

3. **Temporal workflow registration: which worker hosts `PipelineValidationWorkflow`?**
   - What we know: D-06 says GPU worker, CPU worker, API worker each own their task queues
   - What's unclear: Workflows must be registered on exactly one worker's task queue — D-08 says the validation workflow uses both gpu-queue and cpu-queue activities but must be started on some queue
   - Recommendation: Register `PipelineValidationWorkflow` on the GPU worker's task queue (`gpu-queue`). The workflow itself is thin orchestration code; it only schedules activities on other queues. The GPU worker hosts the workflow definition.

---

## Sources

### Primary (HIGH confidence)
- [Temporal Python SDK — Core Application](https://docs.temporal.io/develop/python/core-application) — `@workflow.defn`, `@activity.defn`, Worker init patterns
- [temporalio.worker.Worker API reference](https://python.temporal.io/temporalio.worker.Worker.html) — `max_concurrent_activities` parameter, full `__init__` signature
- [Temporal Python SDK — Failure Detection](https://docs.temporal.io/develop/python/failure-detection) — `RetryPolicy`, `ApplicationError`, `next_retry_delay`
- [Temporal Python SDK — Testing](https://docs.temporal.io/develop/python/testing-suite) — `ActivityEnvironment`, `WorkflowEnvironment`, mocked activities
- [temporalio.contrib.pydantic](https://python.temporal.io/temporalio.contrib.pydantic.html) — `pydantic_data_converter`, Pydantic v2 support
- [SQLModel Docs — Create Tables](https://sqlmodel.tiangolo.com/tutorial/create-db-and-table/) — table definition, `create_engine`, SQLite URL
- [Alembic Autogenerate](https://alembic.sqlalchemy.org/en/latest/autogenerate.html) — `env.py` setup, autogenerate commands
- [gspread GitHub — oauth2.rst](https://github.com/burnash/gspread/blob/master/docs/oauth2.rst) — `service_account()`, `service_account_from_dict()`, `open_by_key()`
- [PyPI — temporalio](https://pypi.org/project/temporalio/) — version 1.24.0, Python 3.10-3.14 support confirmed

### Secondary (MEDIUM confidence)
- [Temporal docker-compose archived repo](https://github.com/temporalio/docker-compose) — auto-setup image reference, PostgreSQL compose pattern
- [FastAPI + Temporal integration (hoop.dev)](https://hoop.dev/blog/fastapi-temporal-explained-real-workflow-automation-without-the-waiting/) — lifespan pattern, `app.state.temporal_client`
- [SQLModel + Alembic (Thorne Wolfenbarger)](https://blog.thornewolf.com/alembic-migrations-with-sqlmodel-micro-tutorial/) — env.py model import pattern, uv run alembic commands
- [Temporal CLI — server start-dev](https://docs.temporal.io/cli/server) — alternative to docker-compose for local dev

### Tertiary (LOW confidence)
- [Temporal Python SDK — Worker Performance](https://docs.temporal.io/develop/worker-performance) — 404 at time of research; defaults inferred from Worker API reference and forum posts
- Community forum: max_concurrent_activities defaults (confirmed via [Temporal Community](https://community.temporal.io/t/clarification-combination-max-concurrent-activities-and-start-to-close-timeout/13274))

---

## Project Constraints (from CLAUDE.md)

These directives apply to all implementation in this phase:

| Directive | Source | Impact on Phase 1 |
|-----------|--------|-------------------|
| `uv sync` for deps, `uvicorn src.main:app --reload` for server | CLAUDE.md §2 | Worker run commands must use `uv run python -m src.workers.*` |
| `pytest tests/ -v --cov=src --cov-report=term-missing` | CLAUDE.md §2 | Test infrastructure must match exactly |
| `alembic upgrade head` / `alembic revision --autogenerate` | CLAUDE.md §2 | Alembic commands standardized |
| `ruff check .` + `ruff format .` | CLAUDE.md §2 | Add `ruff` to dev deps in pyproject.toml |
| `mypy src/` | CLAUDE.md §2 | Add `mypy` to dev deps; type annotations required on all functions |
| `Depends()` for service/DB injection | CLAUDE.md §3.1 | DB session and Temporal client injected via FastAPI `Depends()`, not globals |
| Routers handle HTTP only; business logic in services | CLAUDE.md §3.1 | `src/api/*.py` delegates to `src/services/*.py` |
| No DB queries in routers | CLAUDE.md §3.1 | API routes call `db_service.py` functions only |
| No secrets hardcoded | CLAUDE.md §1.1 | All credentials via `.env` + Pydantic Settings |
| TDD: write tests first | CLAUDE.md §1.2 | Phase 1 tests (D-19) must be written before implementation |
| One task at a time from plan.md | CLAUDE.md §1.1 | Planner must produce fine-grained sequential tasks |
| Files max 800 lines | coding-style.md | Split large worker/service files |

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified against PyPI on 2026-04-01
- Temporal Worker API (`max_concurrent_activities`): HIGH — verified against official Python API reference
- Docker compose pattern: MEDIUM — auto-setup pattern confirmed but port conflict discovered; compose file needs adjustment
- Alembic+SQLModel integration: HIGH — multiple official and community sources consistent
- gspread 6.x: HIGH — verified against official GitHub docs

**Research date:** 2026-04-01
**Valid until:** 2026-05-01 (stable stack; Temporal SDK releases frequently but patterns are stable)
