"""DB CRUD tests — skeletal scaffold with skip markers.
Plan 01-04 replaces these with full implementations after
src/services/db_service.py and src/models/ are built.
"""
import pytest


@pytest.mark.skip(reason="Scaffold — implemented in Plan 01-04")
def test_upsert_content_item_create(db_session):
    pass


@pytest.mark.skip(reason="Scaffold — implemented in Plan 01-04")
def test_upsert_content_item_update(db_session):
    pass


@pytest.mark.skip(reason="Scaffold — implemented in Plan 01-04")
def test_create_pipeline_run(db_session):
    pass


@pytest.mark.skip(reason="Scaffold — implemented in Plan 01-04")
def test_update_pipeline_run(db_session):
    pass


@pytest.mark.skip(reason="Scaffold — implemented in Plan 01-04")
def test_create_sync_log(db_session):
    pass


@pytest.mark.skip(reason="Scaffold — implemented in Plan 01-04")
def test_setup_pipeline_dirs(tmp_pipeline_dir):
    pass


@pytest.mark.skip(reason="Scaffold — implemented in Plan 01-04")
def test_cleanup_intermediate_files(tmp_pipeline_dir):
    pass


@pytest.mark.skip(reason="Scaffold — implemented in Plan 01-04")
def test_cleanup_skips_nonexistent(tmp_pipeline_dir):
    pass
