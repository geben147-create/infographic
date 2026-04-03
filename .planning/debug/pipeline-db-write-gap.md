---
status: awaiting_human_verify
trigger: "pipeline-db-write-gap: ContentPipelineWorkflow completes successfully but never writes to pipeline_runs table"
created: 2026-04-02T00:00:00Z
updated: 2026-04-02T00:01:00Z
---

## Current Focus

hypothesis: CONFIRMED — Neither trigger_pipeline endpoint nor ContentPipelineWorkflow write to pipeline_runs table. The model, DB service functions (create_pipeline_run, update_pipeline_run), and read-side (dashboard) all exist but no code path ever calls create_pipeline_run or update_pipeline_run.
test: Searched all source files — zero calls to create_pipeline_run or update_pipeline_run outside db_service.py itself.
expecting: Fix inserts row on trigger, updates row on workflow completion via new activity.
next_action: Implement Option C — insert on trigger, add save_pipeline_run_result activity called at end of workflow

## Symptoms

expected: After ContentPipelineWorkflow completes, pipeline_runs table should have a row with workflow_id, channel_id, status, timestamps, cost, video_path, thumbnail_path.
actual: pipeline_runs table stays empty after workflow execution. Dashboard/Pipelines API returns empty results.
errors: No errors — the workflow runs fine, it just never writes to the DB.
reproduction: Run POST /api/pipeline/trigger with any topic+channel → workflow completes → GET /api/dashboard/runs returns 0 runs.
started: Has never worked. The workflow was built without DB write logic.

## Eliminated

- hypothesis: DB schema / migration missing (pipeline_runs table not created)
  evidence: PipelineRun SQLModel table definition exists in src/models/pipeline_run.py with all required columns
  timestamp: 2026-04-02T00:01:00Z

- hypothesis: Dashboard API reads from wrong table or has query bug
  evidence: dashboard.py reads correctly from PipelineRun table — the table is just empty
  timestamp: 2026-04-02T00:01:00Z

## Evidence

- timestamp: 2026-04-02T00:01:00Z
  checked: src/api/pipeline.py trigger_pipeline function
  found: Calls client.start_workflow() then returns PipelineTriggerResponse. No DB insert anywhere.
  implication: No PipelineRun row is created at trigger time.

- timestamp: 2026-04-02T00:01:00Z
  checked: src/workflows/content_pipeline.py ContentPipelineWorkflow.run()
  found: Chains 6 activities (setup_dirs, script_gen, image_gen×N, tts×N, video_gen×N, thumbnail, assemble_video). Returns PipelineResult. No DB write activity called.
  implication: Workflow completes without writing to DB.

- timestamp: 2026-04-02T00:01:00Z
  checked: src/services/db_service.py
  found: create_pipeline_run() and update_pipeline_run() functions exist and are correct. Zero callers in any other file.
  implication: DB write functions ready, never invoked.

- timestamp: 2026-04-02T00:01:00Z
  checked: src/models/pipeline_run.py
  found: PipelineRun model has all needed columns: workflow_id, channel_id, status, started_at, completed_at, error_message, total_cost_usd, video_path, thumbnail_path
  implication: Schema is complete, just never written to.

## Resolution

root_cause: The pipeline_runs table has a complete model and read/write service functions, but no code path ever calls them. trigger_pipeline() starts the Temporal workflow without inserting a DB row; ContentPipelineWorkflow chains all production activities but never calls a DB-write activity. The write functions (create_pipeline_run, update_pipeline_run) exist in db_service.py as dead code.
fix: Option C — (1) Insert PipelineRun row in trigger_pipeline() with status=running, started_at=now. (2) Add new save_pipeline_run_result Temporal activity that accepts PipelineResult + workflow metadata and calls update_pipeline_run(). (3) Call this activity as the final step in ContentPipelineWorkflow.run(), also add error handling via try/except wrapping the whole run body.
verification: 255 tests passed (0 failures). 8 new tests for db_write activity all pass. Full suite clean.
files_changed:
  - src/api/pipeline.py
  - src/workflows/content_pipeline.py
  - src/activities/db_write.py (new)
  - tests/test_db_write_activity.py (new)
