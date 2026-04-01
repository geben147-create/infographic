# Phase 1: Infrastructure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-01
**Phase:** 01-infrastructure
**Mode:** --auto (all areas auto-resolved)
**Areas discussed:** Project layout, Temporal deployment, SQLite schema, Worker pool design, Sheets sync trigger, Dev tooling

---

## Project Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Flat `src/` | All modules in one directory | |
| Feature-module `src/` | `workflows/`, `activities/`, `models/`, `workers/`, `services/`, `api/` | ✓ |
| Domain-driven (by channel/feature) | Group by business domain | |

**Auto-selected:** Feature-module layout
**Notes:** Matches FastAPI Depends() pattern from CLAUDE.md, aligns with layered architecture mandate (routers → services → DB). Clean separation of Temporal concerns (workflows, activities, workers) from application concerns (models, services, API).

---

## Temporal Deployment

| Option | Description | Selected |
|--------|-------------|----------|
| Temporal Cloud | Managed, no local infra | |
| Docker Compose (auto-setup) | Local dev, zero-ops, includes Web UI | ✓ |
| Manual Temporal server | Build from source, full control | |

**Auto-selected:** Docker Compose with `temporalio/auto-setup`
**Notes:** Matches Docker listed in tech spec. Includes Temporal Web UI for debugging workflow state. Zero-ops for solo operator setup.

---

## SQLite Schema

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal (1 table) | Single pipeline_runs table | |
| Three tables | content_items + pipeline_runs + sync_log | ✓ |
| Full schema upfront | All Phase 1-3 tables now | |

**Auto-selected:** Three tables (content_items, pipeline_runs, sync_log)
**Notes:** Covers all Phase 1 requirements (ORCH + DATA + FILE) without pre-building Phase 2/3 schema. Aligns with "don't design for hypothetical future requirements" principle.

---

## Worker Pool Design

| Option | Description | Selected |
|--------|-------------|----------|
| Single worker, all queues | One process handles everything | |
| Two queues (GPU vs non-GPU) | Separate GPU, combine CPU+API | |
| Three queues (GPU/CPU/API) | Full separation as in tech spec | ✓ |

**Auto-selected:** Three Task Queues (gpu-queue, cpu-queue, api-queue)
**Notes:** Directly required by ORCH-02. GPU maxConcurrent=1 is non-negotiable given RTX 4070 8GB VRAM constraint. API queue at maxConcurrent=8 allows concurrent cloud API calls without blocking local GPU work.

---

## Sheets Sync Trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Manual only (Phase 1) | POST endpoint, no scheduling | ✓ |
| Polling (cron-style) | Temporal scheduled workflow, fixed interval | |
| Webhook (Sheets App Script) | Real-time trigger on row change | |

**Auto-selected:** Manual trigger via FastAPI endpoint
**Notes:** Proves DATA-01/02/03 requirements without over-engineering. Scheduled sync deferred to Phase 3 where Temporal scheduled workflows are already in scope (OPS-04).

---

## Dev Tooling

| Option | Description | Selected |
|--------|-------------|----------|
| pip + requirements.txt | Traditional Python packaging | |
| uv + pyproject.toml | Modern, fast, matches CLAUDE.md commands | ✓ |
| Poetry + pyproject.toml | Alternative modern packaging | |

**Auto-selected:** `uv` + `pyproject.toml`
**Notes:** Matches CLAUDE.md build commands exactly (`uv sync`, `uv run uvicorn`). Faster than pip, lockfile support, consistent with project conventions.

---

## Claude's Discretion

- Alembic migration file naming and structure
- FastAPI router file organization within `src/api/`
- Temporal SDK connection pooling defaults
- Specific Pydantic Settings field names
- Docker Compose service names and port numbers

## Deferred Ideas

- Scheduled Sheets sync polling — Phase 3 (OPS-04)
- Cost tracking infrastructure — Phase 3 (OPS-05/06)
- Quality gate — Phase 3 (OPS-01/02)
