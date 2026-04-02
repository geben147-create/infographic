# Phase 3: Production Operations - Research

**Researched:** 2026-04-02
**Domain:** Temporal human-in-the-loop signals, scheduled workflows, batch queue, cost persistence, FastAPI dashboard
**Confidence:** HIGH

---

## Summary

Phase 3 adds five operational capabilities on top of the Phase 2 `ContentPipelineWorkflow`: a human approval gate before YouTube upload (OPS-01/02), a batch queue that runs multiple pipeline runs sequentially overnight (OPS-03), a Temporal-native schedule that fires the workflow at a configured future datetime without human intervention (OPS-04), and a cost-and-status dashboard visible both in Temporal Web UI and via FastAPI endpoints (OPS-05/06).

All six requirements can be implemented using Temporal Python SDK 1.24.0 features that are already installed and verified present. No new runtime dependencies are needed for the orchestration layer. The dashboard (OPS-05/06) needs one small addition: a `total_cost_usd` column on `pipeline_runs` and a SQL aggregate query surfaced through FastAPI. The quality gate (OPS-01/02) is a workflow modification — a `wait_condition` plus `@workflow.signal` inserted between FFmpeg assembly and YouTube upload. The batch runner (OPS-03) is a new Python script that calls `client.start_workflow()` in a loop with `id_reuse_policy=ALLOW_DUPLICATE` and sequential `await handle.result()`. The scheduler (OPS-04) uses `client.create_schedule()` from the Temporal client.

**Primary recommendation:** Implement OPS-01/02 as a workflow modification to `ContentPipelineWorkflow` (add `quality_gate_enabled` field to `PipelineParams`, insert a `@workflow.signal` + `workflow.wait_condition()` block between assembly and upload). Implement OPS-03/04 as standalone CLI scripts. Implement OPS-05/06 as two new FastAPI router endpoints plus one Alembic migration.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OPS-01 | Human review + approve/reject via Temporal signal before upload | Temporal `@workflow.signal` + `workflow.wait_condition()` pattern; `WorkflowHandle.signal()` from FastAPI or CLI; video preview via file path URL or file serve endpoint |
| OPS-02 | Quality gate on/off toggle in channel config | Add `quality_gate_enabled: bool` to `ChannelConfig` YAML; workflow reads it from `PipelineParams` or channel config and skips `wait_condition` block when False |
| OPS-03 | Batch mode — queue multiple pipeline runs, execute sequentially overnight | New `batch_runner.py` script that calls `client.start_workflow()` then `await handle.result()` in a for-loop; sequential due to GPU maxConcurrent=1 already enforced at worker level |
| OPS-04 | Scheduled workflow — Temporal Schedule triggers generation+upload at configured datetime | `client.create_schedule()` with `ScheduleSpec(calendars=[ScheduleCalendarSpec(...)])` or `ScheduleSpec(cron_expressions=["..."])` + `ScheduleActionStartWorkflow(ContentPipelineWorkflow.run, ...)` |
| OPS-05 | Per-video API cost tracking in dashboard | `CostTracker` already writes to `cost_log.json`; add `total_cost_usd` column to `pipeline_runs` table; new `GET /api/dashboard/costs` endpoint reads SQLite + cost_log |
| OPS-06 | Pipeline status dashboard — Temporal Web UI + FastAPI custom endpoint | Temporal Web UI (already on port 8081) shows all workflow states; new `GET /api/dashboard/runs` endpoint queries `pipeline_runs` table for list view |
</phase_requirements>

---

## Standard Stack

### Core (all already installed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `temporalio` | 1.24.0 | Signals, schedules, workflow wait | Already in use; all needed APIs verified present |
| `fastapi` | ≥0.135.0 | New dashboard endpoints | Already in use |
| `sqlmodel` | ≥0.0.37 | `pipeline_runs` schema extension | Already in use |
| `alembic` | ≥1.18.0 | DB migration for new column | Already in use |

### No new dependencies needed

All orchestration features (signals, schedules, batch) are part of `temporalio` 1.24.0. The dashboard reads from existing `cost_log.json` + `pipeline_runs` table.

---

## Architecture Patterns

### Pattern 1: Temporal Human-in-the-Loop Signal (OPS-01/02)

**What:** Pause workflow execution until an external signal arrives. The workflow sets a boolean flag via `@workflow.signal`, then `workflow.wait_condition()` blocks until that flag becomes True (or a timeout fires).

**Verified:** `workflow.signal` decorator and `workflow.wait_condition()` are both present in `temporalio` 1.24.0 (confirmed via introspection above).

**Insertion point in `ContentPipelineWorkflow`:** Between Step 6 (assemble_video) and Step 7 (upload_to_youtube).

```python
# In ContentPipelineWorkflow class body — add signal handler:

@workflow.signal
async def approve_video(self, approved: bool, reason: str = "") -> None:
    """Receive human approval decision before upload."""
    self._approved = approved
    self._reject_reason = reason

# In run() method — add instance variables at top of run():
self._approved: bool = False
self._reject_reason: str = ""

# After assembly_out (Step 6), before upload (Step 7):
if params.quality_gate_enabled:
    # Block until approve_video signal received or 24h timeout
    await workflow.wait_condition(
        lambda: self._approved or self._reject_reason != "",
        timeout=timedelta(hours=24),
        timeout_summary="quality-gate-approval",
    )
    if self._reject_reason:
        return PipelineResult(
            status="rejected",
            video_id=None,
            youtube_url=None,
            total_cost_usd=total_cost,
            scenes_count=len(script.scenes),
        )
```

**Sending the signal from FastAPI:**

```python
# New endpoint: POST /api/pipeline/{workflow_id}/approve
@router.post("/{workflow_id}/approve")
async def approve_pipeline(
    workflow_id: str,
    body: ApproveRequest,   # {approved: bool, reason: str}
    request: Request,
) -> dict:
    handle = request.app.state.temporal_client.get_workflow_handle(workflow_id)
    await handle.signal("approve_video", approved=body.approved, reason=body.reason or "")
    return {"signalled": True, "workflow_id": workflow_id}
```

**Signal method signature:** `WorkflowHandle.signal(signal, arg, *, args, rpc_metadata, rpc_timeout)` — verified in SDK 1.24.0.

**Timeout handling:** `workflow.wait_condition()` raises `asyncio.TimeoutError` on timeout. Catch this in the workflow and treat as auto-reject or re-raise depending on channel policy.

### Pattern 2: `PipelineParams` Extension for Quality Gate Toggle (OPS-02)

Add `quality_gate_enabled: bool = False` to `PipelineParams`. The FastAPI `/trigger` endpoint reads `ChannelConfig.quality_gate_enabled` and passes it through. This keeps the workflow logic channel-aware without reloading YAML inside the workflow (Temporal determinism constraint — no I/O inside workflow code).

Also add `quality_gate_enabled: bool = False` to `ChannelConfig` YAML schema and the Pydantic model.

```python
# PipelineParams extension
class PipelineParams(BaseModel):
    run_id: str
    topic: str
    channel_id: str
    quality_gate_enabled: bool = False  # NEW

# ChannelConfig extension
class ChannelConfig(BaseModel, frozen=True):
    ...
    quality_gate_enabled: bool = False  # NEW
```

### Pattern 3: Batch Queue Runner (OPS-03)

**What:** A standalone Python script (not a Temporal workflow) that reads a list of `(topic, channel_id)` pairs and runs them sequentially by awaiting each `handle.result()` before starting the next.

**Why sequential (not parallel):** GPU worker already enforces `max_concurrent_activities=1`. Running parallel workflows would just queue at the GPU worker anyway. Sequential at the batch runner level gives cleaner error reporting and cost isolation.

```python
# scripts/batch_runner.py
import asyncio, json, sys
from temporalio.client import Client
from src.config import settings
from src.workflows.content_pipeline import ContentPipelineWorkflow, PipelineParams

async def run_batch(batch_file: str) -> None:
    """Run multiple pipeline workflows sequentially from a JSON batch file."""
    with open(batch_file) as f:
        items = json.load(f)   # [{topic, channel_id, quality_gate_enabled?}, ...]

    client = await Client.connect(settings.temporal_host, ...)
    for item in items:
        wf_id = f"batch-{uuid4().hex[:8]}"
        handle = await client.start_workflow(
            ContentPipelineWorkflow.run,
            PipelineParams(
                run_id=wf_id,
                topic=item["topic"],
                channel_id=item["channel_id"],
                quality_gate_enabled=item.get("quality_gate_enabled", False),
            ),
            id=wf_id,
            task_queue="gpu-queue",
        )
        print(f"Started {wf_id} — {item['topic']}")
        result = await handle.result()
        print(f"Completed {wf_id}: {result.youtube_url}, cost=${result.total_cost_usd:.2f}")

if __name__ == "__main__":
    asyncio.run(run_batch(sys.argv[1]))
```

**Batch file format:**
```json
[
  {"topic": "AI 트렌드 2026", "channel_id": "channel_01"},
  {"topic": "비트코인 전망", "channel_id": "channel_01"},
  {"topic": "헬스케어 혁신", "channel_id": "channel_02"}
]
```

### Pattern 4: Temporal Schedule for Content Calendar (OPS-04)

**What:** `client.create_schedule()` creates a durable schedule stored in Temporal Server. The schedule fires `ContentPipelineWorkflow` at a configured datetime/cron without a running process.

**Verified:** `Schedule`, `ScheduleSpec`, `ScheduleActionStartWorkflow`, `ScheduleCalendarSpec`, `ScheduleIntervalSpec`, `ScheduleRange` all importable from `temporalio.client` in 1.24.0.

```python
# scripts/schedule_video.py — schedule a one-time run at a specific datetime
from temporalio.client import (
    Client, Schedule, ScheduleSpec, ScheduleActionStartWorkflow,
    ScheduleCalendarSpec, ScheduleRange, ScheduleState,
)

async def schedule_video(topic: str, channel_id: str, publish_at: datetime) -> None:
    client = await Client.connect(settings.temporal_host, ...)
    schedule_id = f"scheduled-{channel_id}-{uuid4().hex[:6]}"

    await client.create_schedule(
        schedule_id,
        Schedule(
            action=ScheduleActionStartWorkflow(
                ContentPipelineWorkflow.run,
                PipelineParams(
                    run_id=schedule_id,
                    topic=topic,
                    channel_id=channel_id,
                    quality_gate_enabled=False,  # overnight = auto-approve
                ),
                id=schedule_id,
                task_queue="gpu-queue",
            ),
            spec=ScheduleSpec(
                calendars=[
                    ScheduleCalendarSpec(
                        year=[ScheduleRange(publish_at.year)],
                        month=[ScheduleRange(publish_at.month)],
                        day_of_month=[ScheduleRange(publish_at.day)],
                        hour=[ScheduleRange(publish_at.hour)],
                        minute=[ScheduleRange(publish_at.minute)],
                    )
                ]
            ),
            state=ScheduleState(
                note=f"Scheduled video: {topic} for {channel_id}",
                limited_actions=True,
                remaining_actions=1,  # fire once only
            ),
        ),
    )
```

**Cron alternative** (simpler for recurring daily publishing):
```python
spec=ScheduleSpec(cron_expressions=["0 9 * * 1"])  # every Monday at 09:00
```

**Viewing schedules:** Temporal Web UI (`localhost:8081`) shows all schedules. Also accessible via `client.list_schedules()`.

**CRITICAL: Temporal determinism constraint.** `ScheduleCalendarSpec` fields take `Sequence[ScheduleRange]`, not bare integers. Always wrap values in `ScheduleRange(start=N)`.

### Pattern 5: Cost Persistence to SQLite (OPS-05)

**Current state:** `CostTracker` writes to `data/cost_log.json` (file-based). `pipeline_runs` table has no cost column.

**Extension:** Add `total_cost_usd: float` column to `pipeline_runs`. At workflow completion, the `PipelineResult.total_cost_usd` is already computed — write it to the DB row.

**Alembic migration:**
```python
# alembic/versions/xxxx_add_cost_to_pipeline_runs.py
def upgrade():
    op.add_column(
        "pipeline_runs",
        sa.Column("total_cost_usd", sa.Float(), nullable=True, default=0.0),
    )
```

**Where to write:** In the FastAPI `/trigger` endpoint callback OR by adding a `db_service.update_run_cost(workflow_id, cost)` call triggered after workflow completion. The cleanest approach: call `db_service.update_run_result()` in `GET /api/pipeline/status/{workflow_id}` when status transitions to `completed` (already fetches the result).

### Pattern 6: Dashboard FastAPI Endpoints (OPS-06)

**Two new endpoints:**

```python
# GET /api/dashboard/runs — paginated list of all pipeline runs
@router.get("/runs", response_model=DashboardRunsResponse)
async def list_runs(
    limit: int = 20,
    offset: int = 0,
    channel_id: str | None = None,
) -> DashboardRunsResponse:
    # Query pipeline_runs table with optional channel_id filter
    # Return status, cost, started_at, completed_at, youtube_url

# GET /api/dashboard/costs — cost summary by channel and date range
@router.get("/costs", response_model=DashboardCostsResponse)
async def cost_summary(
    channel_id: str | None = None,
    days: int = 30,
) -> DashboardCostsResponse:
    # Aggregate total_cost_usd from pipeline_runs grouped by channel_id
    # Also read cost_log.json for per-service breakdown
```

**File-based cost_log vs SQLite:** For OPS-05, persist `total_cost_usd` in SQLite for easy SQL aggregation. Keep `cost_log.json` for per-call granularity (already used by `/cost/{workflow_id}` endpoint).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Workflow pause for human input | Custom polling / DB flag | `@workflow.signal` + `workflow.wait_condition()` | Temporal persists signal state durably; app restarts don't lose approval state |
| Recurring/one-time job scheduler | cron daemon, APScheduler, custom retry loop | Temporal `client.create_schedule()` | Durable across restarts, visible in Web UI, no separate process needed |
| Batch job queue | Redis queue, custom DB-backed queue | Sequential `await handle.result()` loop | GPU worker already serializes; Temporal tracks each run independently |
| Workflow signal routing | Custom HTTP webhooks to workflow | `WorkflowHandle.signal()` via Temporal client | SDK handles message routing, retry, and correlation |
| Cost aggregation | Parse cost_log.json on every request | `total_cost_usd` column on `pipeline_runs` + SQL aggregate | Indexed column is O(1) for sum; JSON scan is O(n) with file lock |

**Key insight:** Temporal is already the orchestration backbone. Every "operational maturity" feature in this phase is a native Temporal feature, not a custom solution.

---

## Common Pitfalls

### Pitfall 1: Workflow Instance Variables Not Initialized Before Signal Arrival

**What goes wrong:** Temporal can deliver signals before `run()` body executes (during replay). If `self._approved` is only set inside `run()`, it may not exist when the signal handler fires during replay.

**Why it happens:** Temporal workflow replay replays the entire execution history. Signal handlers can be invoked at any point.

**How to avoid:** Initialize all signal-related instance variables in `__init__`:
```python
@workflow.defn
class ContentPipelineWorkflow:
    def __init__(self) -> None:
        self._approved: bool = False
        self._reject_reason: str = ""
```

**Warning signs:** `AttributeError: 'ContentPipelineWorkflow' object has no attribute '_approved'` in Temporal Worker logs during workflow replay.

### Pitfall 2: Reading Channel Config Inside Workflow Code

**What goes wrong:** `load_channel_config()` reads a YAML file — I/O inside a workflow method violates Temporal's determinism requirement. The workflow will fail with a non-determinism error.

**Why it happens:** Temporal replays workflow code to reconstruct state. Any non-deterministic I/O (file reads, time calls, random) inside the workflow body causes replay to diverge.

**How to avoid:** Read `ChannelConfig` BEFORE starting the workflow (in the FastAPI trigger endpoint or CLI script) and pass relevant flags (like `quality_gate_enabled`) through `PipelineParams`. Never call `load_channel_config()` inside `ContentPipelineWorkflow.run()`.

**Warning signs:** `temporalio.exceptions.WorkflowAlreadyStartedError` or non-determinism errors in Temporal Worker logs.

### Pitfall 3: `ScheduleCalendarSpec` Requires `Sequence[ScheduleRange]`, Not Bare Integers

**What goes wrong:** `ScheduleCalendarSpec(year=2026, month=12)` raises `ValidationError` — all fields require `Sequence[ScheduleRange]`.

**How to avoid:**
```python
# WRONG
ScheduleCalendarSpec(year=2026, month=4, day_of_month=15)

# CORRECT
ScheduleCalendarSpec(
    year=[ScheduleRange(start=2026)],
    month=[ScheduleRange(start=4)],
    day_of_month=[ScheduleRange(start=15)],
    hour=[ScheduleRange(start=9)],
    minute=[ScheduleRange(start=0)],
)
```

**Verified:** `ScheduleCalendarSpec.__init__` signature confirmed to take `Sequence[ScheduleRange]` for each field.

### Pitfall 4: `wait_condition` Timeout Raises `asyncio.TimeoutError`, Not a Custom Exception

**What goes wrong:** Uncaught `asyncio.TimeoutError` propagates and marks the workflow as failed.

**How to avoid:** Wrap `workflow.wait_condition()` in a try/except:
```python
try:
    await workflow.wait_condition(
        lambda: self._approved or bool(self._reject_reason),
        timeout=timedelta(hours=24),
    )
except asyncio.TimeoutError:
    # Auto-reject or auto-approve based on channel policy
    return PipelineResult(status="timeout_rejected", ...)
```

### Pitfall 5: Signal Method Cannot Have Keyword-Only Parameters

**What goes wrong:** `@workflow.signal` handlers only accept positional parameters. `def approve_video(self, *, approved: bool)` will fail at registration time.

**How to avoid:** Use a single Pydantic model as the signal payload:
```python
class ApprovalSignal(BaseModel):
    approved: bool
    reason: str = ""

@workflow.signal
async def approve_video(self, payload: ApprovalSignal) -> None:
    self._approved = payload.approved
    self._reject_reason = payload.reason
```

Then send via: `await handle.signal("approve_video", ApprovalSignal(approved=True))`

### Pitfall 6: Batch Runner Blocks Event Loop on `await handle.result()`

**What goes wrong:** `await handle.result()` in a long-running batch can hold the event loop for hours. If the batch runner process dies, the already-started workflows continue in Temporal but the runner loses track.

**How to avoid:** The batch runner is a CLI tool meant to run overnight — blocking is acceptable. Add signal handling (`SIGINT`) to print status and exit cleanly without cancelling already-running workflows. For resilience, write `workflow_id` list to a recovery file so a crashed batch runner can resume polling.

### Pitfall 7: `PipelineRun.status` Not Updated for Quality-Gate-Paused Workflows

**What goes wrong:** The Temporal workflow is in `RUNNING` state while waiting for approval, but the DB `pipeline_runs.status` still shows `running` — indistinguishable from active generation.

**How to avoid:** Add a `waiting_approval` status value to `PipelineRun.status`. When the FastAPI status endpoint sees `RUNNING` and the workflow's search attributes (or a workflow query) indicate it's in the approval gate, map to `waiting_approval`. Alternatively, add a `@workflow.query` method that returns the current step name.

---

## Code Examples

### Verified: Send Signal From FastAPI

```python
# Source: temporalio SDK 1.24.0 WorkflowHandle.signal() — verified via inspect
handle = client.get_workflow_handle(workflow_id)
await handle.signal("approve_video", ApprovalSignal(approved=True, reason="Looks good"))
```

### Verified: Create One-Time Schedule

```python
# Source: temporalio.client imports — verified importable in 1.24.0
from temporalio.client import (
    Schedule, ScheduleSpec, ScheduleActionStartWorkflow,
    ScheduleCalendarSpec, ScheduleRange, ScheduleState,
)

await client.create_schedule(
    schedule_id,
    Schedule(
        action=ScheduleActionStartWorkflow(
            ContentPipelineWorkflow.run,
            PipelineParams(...),
            id=schedule_id,
            task_queue="gpu-queue",
        ),
        spec=ScheduleSpec(
            calendars=[
                ScheduleCalendarSpec(
                    year=[ScheduleRange(start=2026)],
                    month=[ScheduleRange(start=4)],
                    day_of_month=[ScheduleRange(start=15)],
                    hour=[ScheduleRange(start=9)],
                    minute=[ScheduleRange(start=0)],
                )
            ]
        ),
        state=ScheduleState(
            limited_actions=True,
            remaining_actions=1,
        ),
    ),
)
```

### Verified: `workflow.wait_condition` Signature

```python
# Source: temporalio.workflow.wait_condition — verified via help()
# Signature: async wait_condition(fn, *, timeout, timeout_summary) -> None
await workflow.wait_condition(
    lambda: self._approved or bool(self._reject_reason),
    timeout=timedelta(hours=24),
    timeout_summary="quality-gate-approval",
)
```

### Verified: `@workflow.signal` Decorator

```python
# Source: temporalio.workflow.signal — verified via inspect.getsource()
@workflow.signal
async def approve_video(self, payload: ApprovalSignal) -> None:
    self._approved = payload.approved
    self._reject_reason = payload.reason
```

---

## Architecture: What Changes in Each Existing File

| File | Change Type | What Changes |
|------|-------------|--------------|
| `src/workflows/content_pipeline.py` | Modify | Add `__init__` with signal state, `@workflow.signal approve_video`, `wait_condition` block between Step 6 and 7 |
| `src/models/channel_config.py` | Modify | Add `quality_gate_enabled: bool = False` field |
| `src/channel_configs/channel_01.yaml` | Modify | Add `quality_gate_enabled: false` |
| `src/channel_configs/channel_02.yaml` | Modify | Add `quality_gate_enabled: false` |
| `src/schemas/pipeline.py` | Modify | Add `ApprovalSignal`, `ApproveRequest`, `DashboardRunsResponse`, `DashboardCostsResponse` schemas |
| `src/api/pipeline.py` | Modify | Add `POST /{workflow_id}/approve` endpoint; update `status` endpoint to persist cost on completion |
| `src/models/pipeline_run.py` | Modify | Add `total_cost_usd: float = 0.0` column |
| `src/workflows/content_pipeline.py` | Modify | `PipelineParams` gets `quality_gate_enabled: bool = False` |
| `src/main.py` | Modify | Include new dashboard router |

**New files:**

| File | Purpose |
|------|---------|
| `src/api/dashboard.py` | `GET /api/dashboard/runs` and `GET /api/dashboard/costs` endpoints |
| `scripts/batch_runner.py` | CLI batch queue runner |
| `scripts/schedule_video.py` | CLI one-time / recurring schedule creator |
| `alembic/versions/xxxx_add_cost_to_pipeline_runs.py` | Migration for `total_cost_usd` column |

---

## Recommended Plan Breakdown

Phase 3 fits cleanly into 3 plans (matching Phase 2's granularity):

| Plan | Scope | Files |
|------|-------|-------|
| **03-01** | Quality gate: signal handler in workflow, PipelineParams extension, ChannelConfig toggle, `/approve` endpoint | `content_pipeline.py`, `channel_config.py`, `channel_configs/*.yaml`, `schemas/pipeline.py`, `api/pipeline.py` |
| **03-02** | Batch runner + Scheduler: CLI scripts, Alembic migration, `total_cost_usd` persistence | `scripts/batch_runner.py`, `scripts/schedule_video.py`, `models/pipeline_run.py`, migration file |
| **03-03** | Dashboard endpoints + integration tests | `src/api/dashboard.py`, `src/main.py`, `tests/test_dashboard.py`, `tests/test_batch_runner.py` |

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Custom DB polling for approval gate | Temporal `@workflow.signal` + `wait_condition` | Durable, survives restarts, no polling loop |
| APScheduler / cron for content calendar | Temporal `client.create_schedule()` | Visible in Web UI, durable, no separate process |
| File-only cost tracking (cost_log.json) | SQLite column + JSON file dual-write | SQL aggregation for dashboard, file for per-call detail |

---

## Environment Availability

Step 2.6: SKIPPED — Phase 3 has no new external dependencies. All required tools (`temporalio` 1.24.0, `fastapi`, `sqlmodel`, `alembic`) are already installed and verified.

Temporal Web UI is already running on port 8081 (confirmed in Phase 1 decisions: "Temporal Web UI mapped to 8081:8080 to avoid port 8080 conflict").

---

## Open Questions

1. **Preview URL for quality gate**
   - What we know: The assembled video is at `{run_dir}/final/output.mp4` on the local filesystem
   - What's unclear: How does the operator view it before signalling approval? Options: (a) serve it via a new `GET /api/pipeline/{workflow_id}/preview` endpoint that streams the file, (b) operator opens the file directly via filesystem path shown in terminal, (c) generate a presigned URL if cloud storage is added later
   - Recommendation: For v1, add a `GET /api/pipeline/{workflow_id}/preview` endpoint using FastAPI `FileResponse` — simplest, no cloud dependency. Show the local path in the status endpoint response too.

2. **`PipelineParams` backward compatibility**
   - What we know: `PipelineParams` is a Pydantic `BaseModel`, not a frozen dataclass. Adding `quality_gate_enabled: bool = False` is backward compatible (default False).
   - What's unclear: Temporal replays existing workflow runs using the serialized history. If a live Phase 2 workflow exists during Phase 3 deployment, Temporal may encounter a serialized `PipelineParams` without `quality_gate_enabled`.
   - Recommendation: The default `False` value means Pydantic will fill it in on deserialization — safe. Verify with a quick test.

3. **`pipeline_runs` status enum for approval-pending state**
   - What we know: Current `status` field is a plain `str` with values `pending / running / done / failed`
   - What's unclear: Whether to add `waiting_approval` as a formal status or use a separate `current_step` column
   - Recommendation: Add `waiting_approval` as a valid status string. Update the workflow to call a `notify_approval_pending` activity (on api-queue) that writes this status to the DB before entering `wait_condition`.

---

## Sources

### Primary (HIGH confidence)
- `temporalio` 1.24.0 SDK — verified via `uv run python -c "import temporalio; print(temporalio.__version__)"` → `1.24.0`
- `workflow.signal` — source-inspected via `inspect.getsource(workflow.signal)` in running environment
- `workflow.wait_condition` — inspected via `help(workflow.wait_condition)` — confirmed signature `async wait_condition(fn, *, timeout, timeout_summary)`
- `WorkflowHandle.signal` — inspected via `inspect.signature(WorkflowHandle.signal)` — confirmed `(self, signal, arg, *, args, rpc_metadata, rpc_timeout)`
- `ScheduleCalendarSpec.__init__` — inspected via `inspect.signature(ScheduleCalendarSpec.__init__)` — confirmed all fields are `Sequence[ScheduleRange]`
- All Schedule imports — confirmed importable: `Schedule, ScheduleSpec, ScheduleActionStartWorkflow, ScheduleIntervalSpec, ScheduleCalendarSpec, ScheduleRange, ScheduleHandle, ScheduleState`

### Secondary (MEDIUM confidence)
- Temporal Python SDK docs pattern for human-in-the-loop: matches SDK source code inspection
- Phase 1/2 project code (`content_pipeline.py`, `config.py`, `pipeline_run.py`, `cost_tracker.py`, `api/pipeline.py`) — read directly

---

## Metadata

**Confidence breakdown:**
- OPS-01/02 (quality gate): HIGH — all Temporal signal APIs verified in installed SDK
- OPS-03 (batch runner): HIGH — straightforward sequential client calls, no new APIs
- OPS-04 (schedule): HIGH — all Schedule classes confirmed importable + signature verified
- OPS-05 (cost dashboard): HIGH — SQLite column extension is trivial Alembic migration; existing CostTracker already provides the data
- OPS-06 (status dashboard): HIGH — existing `/status` endpoint already covers 80% of this; new dashboard endpoint is a SQLite query

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (Temporal SDK is stable; schedule APIs unlikely to change)
