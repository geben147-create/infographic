"""DB CRUD tests — SQLite upsert, pipeline_run CRUD, sync_log, directory setup."""
import asyncio
from datetime import datetime
from pathlib import Path

from src.activities.cleanup import CleanupInput, cleanup_intermediate_files
from src.activities.pipeline import (
    PIPELINE_SUBDIRS,
    SetupDirsInput,
    setup_pipeline_dirs,
)
from src.services.db_service import (
    create_pipeline_run,
    create_sync_log,
    update_pipeline_run,
    upsert_content_item,
)


def test_upsert_content_item_create(db_session):
    """Inserting a new row creates a ContentItem with expected defaults."""
    item = upsert_content_item(
        db_session,
        {"sheets_row_id": "row-1", "topic": "topic A", "channel_id": "ch1"},
    )
    assert item.id is not None
    assert item.status == "pending"
    assert item.topic == "topic A"
    assert item.sheets_row_id == "row-1"


def test_upsert_content_item_update(db_session):
    """Upserting the same sheets_row_id updates the row and keeps the same id."""
    item_first = upsert_content_item(
        db_session,
        {"sheets_row_id": "row-1", "topic": "topic A", "channel_id": "ch1"},
    )
    original_id = item_first.id

    item_second = upsert_content_item(
        db_session,
        {"sheets_row_id": "row-1", "topic": "topic B", "channel_id": "ch1"},
    )
    assert item_second.id == original_id
    assert item_second.topic == "topic B"


def test_create_pipeline_run(db_session):
    """Creates a PipelineRun with workflow_id and expected defaults."""
    run = create_pipeline_run(
        db_session,
        {"workflow_id": "wf-test-1", "channel_id": "ch1"},
    )
    assert run.id is not None
    assert run.workflow_id == "wf-test-1"
    assert run.status == "pending"


def test_update_pipeline_run(db_session):
    """Updates status and completed_at on an existing PipelineRun."""
    create_pipeline_run(
        db_session,
        {"workflow_id": "wf-test-2", "channel_id": "ch1"},
    )
    completed = datetime.utcnow()
    updated = update_pipeline_run(
        db_session,
        "wf-test-2",
        {"status": "done", "completed_at": completed},
    )
    assert updated is not None
    assert updated.status == "done"
    assert updated.completed_at == completed


def test_update_pipeline_run_not_found(db_session):
    """update_pipeline_run returns None for a non-existent workflow_id."""
    result = update_pipeline_run(db_session, "no-such-id", {"status": "done"})
    assert result is None


def test_create_sync_log(db_session):
    """Creates a SyncLog with rows_added and rows_updated counts."""
    log = create_sync_log(db_session, rows_added=5, rows_updated=3)
    assert log.id is not None
    assert log.rows_added == 5
    assert log.rows_updated == 3
    assert log.error is None


def test_create_sync_log_with_error(db_session):
    """Creates a SyncLog with an error message when sync fails."""
    log = create_sync_log(db_session, rows_added=0, rows_updated=0, error="API timeout")
    assert log.error == "API timeout"


def test_setup_pipeline_dirs(tmp_pipeline_dir):
    """setup_pipeline_dirs creates base/{workflow_run_id}/ with all 6 subdirs."""
    result = asyncio.run(
        setup_pipeline_dirs(
            SetupDirsInput(workflow_run_id="test-wf-001", base_path=tmp_pipeline_dir)
        )
    )
    assert result.created is True
    base = Path(tmp_pipeline_dir) / "test-wf-001"
    for subdir in PIPELINE_SUBDIRS:
        assert (base / subdir).is_dir(), f"Expected {subdir}/ to exist"


def test_cleanup_intermediate_files(tmp_pipeline_dir):
    """cleanup_intermediate_files deletes 5 intermediate dirs but keeps final/."""
    # First create all dirs
    asyncio.run(
        setup_pipeline_dirs(
            SetupDirsInput(workflow_run_id="test-wf-002", base_path=tmp_pipeline_dir)
        )
    )
    base = Path(tmp_pipeline_dir) / "test-wf-002"

    # Put a dummy file in final/ to verify it survives
    dummy_file = base / "final" / "output.mp4"
    dummy_file.write_text("fake video content")

    result = asyncio.run(
        cleanup_intermediate_files(
            CleanupInput(workflow_run_id="test-wf-002", base_path=tmp_pipeline_dir)
        )
    )

    assert result.success is True

    # Intermediate dirs must be gone
    for dirname in ["scripts", "images", "audio", "video", "thumbnails"]:
        assert not (base / dirname).exists(), f"Expected {dirname}/ to be deleted"

    # final/ and its contents must survive
    assert (base / "final").is_dir()
    assert dummy_file.exists()


def test_cleanup_skips_nonexistent(tmp_pipeline_dir):
    """cleanup_intermediate_files on a non-existent dir succeeds without error."""
    result = asyncio.run(
        cleanup_intermediate_files(
            CleanupInput(workflow_run_id="no-such-run", base_path=tmp_pipeline_dir)
        )
    )
    assert result.success is True
    assert result.deleted_dirs == []
