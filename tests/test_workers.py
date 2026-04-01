"""Temporal workflow integration tests — skeletal scaffold with skip markers.
Plan 01-04 replaces these with full implementations after
src/workflows/ and src/workers/ are built.
"""
import pytest


@pytest.mark.skip(reason="Scaffold — implemented in Plan 01-04")
async def test_pipeline_validation_workflow():
    pass


@pytest.mark.skip(reason="Scaffold — implemented in Plan 01-04")
async def test_gpu_retry_succeeds():
    pass
