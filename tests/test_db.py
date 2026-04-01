"""DB CRUD tests — validates all db_service functions and file management activities."""
import asyncio
from datetime import datetime

from src.activities.cleanup import CleanupInput, DIRS_TO_DELETE, DIRS_TO_KEEP, cleanup_intermediate_files
from src.activities.pipeline import PIPELINE_SUBDIRS, SetupDirsInput, setup_pipeline_dirs
from src.services.db_service import (
    create_pipeline_run,
    create_sync_log,
    update_pipeline_run,
    upsert_content_item,
)


def test_upsert_content_item_create(db_session):
    """Inserting a new row creates a ContentItem with id and status=pending."""
    item = upsert_content_item(
        db_session,
        {"sheets_row_id": "row-1", "topic": "Topic A", "channel_id": "ch1"},
    )
    assert item.id is not None
    assert item.sheets_row_id == "row-1"
    assert item.topic == "Topic A"
    assert item.status == "pending"


def test_upsert_content_item_update(db_session):
    """Upserting the same sheets_row_id twice returns the same id with updated topic."""
    first = upsert_content_item(
        db_session,
        {"sheets_row_id": "row-1", "topic": "Topic A", "channel_id": "ch1"},
    )
    second = upsert_content_item(
        db_session,
        {"sheets_row_id": "row-1", "topic": "Topic B", "channel_id": "ch1"},
    )
    assert first.id == second.id
    assert second.topic == "Topic B"


def test_create_pipeline_run(db_session):
    """Creates a PipelineRun with workflow_id and status=pending."""
    run = create_pipeline_run(
        db_session,
        {"workflow_id": "wf-test-1", "channel_id": "ch1", "status": "pending"},
    )
    assert run.id is not None
    assert run.workflow_id == "wf-test-1"
    assert run.status == "pending"


def test_update_pipeline_run(db_session):
    """Updates status and completed_at on an existing PipelineRun."""
    run = create_pipeline_run(
        db_session,
        {"workflow_id": "wf-test-2", "channel_id": "ch1"},
    )
    now = datetime.utcnow()
    updated = update_pipeline_run(
        db_session,
        "wf-test-2",
        {"status": "done", "completed_at": now},
    )
    assert updated is not None
    assert updated.status == "done"
    assert updated.completed_at == now


def test_create_sync_log(db_session):
    """Creates a SyncLog with rows_added and rows_updated counts."""
    log = create_sync_log(db_session, rows_added=5, rows_updated=3)
    assert log.id is not None
    assert log.rows_added == 5
    assert log.rows_updated == 3
    assert log.error is None


def test_setup_pipeline_dirs(tmp_pipeline_dir):
    """setup_pipeline_dirs creates base_path/{workflow_run_id}/ with all 6 subdirs."""
    result = asyncio.run(
        setup_pipeline_dirs(
            SetupDirsInput(workflow_run_id="run-001", base_path=tmp_pipeline_dir)
        )
    )
    assert result.created is True
    assert set(result.subdirs) == set(PIPELINE_SUBDIRS)
    import os

    base = os.path.join(tmp_pipeline_dir, "run-001")
    for subdir in PIPELINE_SUBDIRS:
        assert os.path.isdir(os.path.join(base, subdir)), f"Missing subdir: {subdir}"


def test_cleanup_intermediate_files(tmp_pipeline_dir):
    """Cleanup deletes intermediate dirs but keeps final/."""
    import os

    # First create all dirs
    run_id = "run-cleanup-001"
    asyncio.run(
        setup_pipeline_dirs(
            SetupDirsInput(workflow_run_id=run_id, base_path=tmp_pipeline_dir)
        )
    )
    base = os.path.join(tmp_pipeline_dir, run_id)

    # Put a dummy file in final/ to verify it survives
    with open(os.path.join(base, "final", "output.mp4"), "w") as f:
        f.write("dummy")

    result = asyncio.run(
        cleanup_intermediate_files(
            CleanupInput(workflow_run_id=run_id, base_path=tmp_pipeline_dir)
        )
    )
    assert result.success is True

    # Intermediate dirs should be gone
    for dirname in DIRS_TO_DELETE:
        assert not os.path.exists(os.path.join(base, dirname)), f"Should be deleted: {dirname}"

    # final/ and its contents should still exist
    for dirname in DIRS_TO_KEEP:
        assert os.path.isdir(os.path.join(base, dirname)), f"Should be kept: {dirname}"
    assert os.path.exists(os.path.join(base, "final", "output.mp4"))


def test_cleanup_skips_nonexistent(tmp_pipeline_dir):
    """Cleanup on an empty (no subdirs) run directory succeeds without error."""
    import os

    run_id = "run-empty"
    os.makedirs(os.path.join(tmp_pipeline_dir, run_id))

    result = asyncio.run(
        cleanup_intermediate_files(
            CleanupInput(workflow_run_id=run_id, base_path=tmp_pipeline_dir)
        )
    )
    assert result.success is True
    assert result.deleted_dirs == []
