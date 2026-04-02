"""Tests for GET /api/pipeline/{id}/download and /api/pipeline/{id}/thumbnail."""
import pathlib
import shutil

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.pipeline import router


def _make_app():
    app = FastAPI()
    app.include_router(router)
    return app


class TestDownloadVideo:
    def test_download_404_when_missing(self):
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/pipeline/nonexistent-run/download")
        assert resp.status_code == 404

    def test_download_200_when_file_exists(self, tmp_path):
        workflow_id = "test-download-run"
        # Create file at the path the endpoint expects (relative to CWD)
        expected_dir = pathlib.Path("data/pipeline") / workflow_id / "final"
        expected_dir.mkdir(parents=True, exist_ok=True)
        video_file = expected_dir / "output.mp4"
        video_file.write_bytes(b"\x00" * 100)

        app = _make_app()
        client = TestClient(app)

        try:
            resp = client.get(f"/api/pipeline/{workflow_id}/download")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "video/mp4"
            assert "attachment" in resp.headers.get("content-disposition", "")
        finally:
            shutil.rmtree(pathlib.Path("data/pipeline") / workflow_id, ignore_errors=True)


class TestDownloadThumbnail:
    def test_thumbnail_404_when_missing(self):
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/pipeline/nonexistent-run/thumbnail")
        assert resp.status_code == 404

    def test_thumbnail_200_when_file_exists(self, tmp_path):
        workflow_id = "test-thumb-run"
        expected_dir = pathlib.Path("data/pipeline") / workflow_id / "thumbnails"
        expected_dir.mkdir(parents=True, exist_ok=True)
        thumb_file = expected_dir / "thumbnail.jpg"
        thumb_file.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)

        app = _make_app()
        client = TestClient(app)

        try:
            resp = client.get(f"/api/pipeline/{workflow_id}/thumbnail")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "image/jpeg"
            assert "attachment" in resp.headers.get("content-disposition", "")
        finally:
            shutil.rmtree(pathlib.Path("data/pipeline") / workflow_id, ignore_errors=True)
