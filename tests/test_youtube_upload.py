"""
Tests for the YouTube upload activity.

Covers:
- UploadInput / UploadOutput serialization
- upload_to_youtube calls videos().insert() with correct metadata
- upload_to_youtube calls thumbnails().set() after video upload
- Credential loading and refresh
- Resumable upload loop returns video_id
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

# ---- Import under test ----
from src.activities.youtube_upload import UploadInput, UploadOutput, upload_to_youtube


class TestUploadInputOutput:
    """Validate model fields and defaults."""

    def test_upload_input_required_fields(self) -> None:
        inp = UploadInput(
            video_path="/tmp/video.mp4",
            thumbnail_path="/tmp/thumb.jpg",
            title="Test Video",
            description="A test description",
            tags=["test", "video"],
            channel_id="channel_01",
        )
        assert inp.video_path == "/tmp/video.mp4"
        assert inp.thumbnail_path == "/tmp/thumb.jpg"
        assert inp.title == "Test Video"
        assert inp.description == "A test description"
        assert inp.tags == ["test", "video"]
        assert inp.channel_id == "channel_01"
        assert inp.category_id == "22"  # default
        assert inp.publish_status == "private"  # default

    def test_upload_input_custom_defaults(self) -> None:
        inp = UploadInput(
            video_path="/v.mp4",
            thumbnail_path="/t.jpg",
            title="T",
            description="D",
            tags=[],
            channel_id="ch1",
            category_id="24",
            publish_status="public",
        )
        assert inp.category_id == "24"
        assert inp.publish_status == "public"

    def test_upload_input_missing_required_raises(self) -> None:
        with pytest.raises(ValidationError):
            UploadInput(
                video_path="/v.mp4",
                # missing title, description, tags, channel_id
            )  # type: ignore[call-arg]

    def test_upload_output_fields(self) -> None:
        out = UploadOutput(video_id="abc123", youtube_url="https://www.youtube.com/watch?v=abc123")
        assert out.video_id == "abc123"
        assert out.youtube_url == "https://www.youtube.com/watch?v=abc123"


def _make_upload_input(
    video_path: str = "/tmp/test_video.mp4",
    thumbnail_path: str = "/tmp/test_thumb.jpg",
) -> UploadInput:
    return UploadInput(
        video_path=video_path,
        thumbnail_path=thumbnail_path,
        title="Test Title",
        description="Test Description",
        tags=["tag1", "tag2"],
        channel_id="channel_01",
    )


class TestUploadToYoutube:
    """Test the upload_to_youtube Temporal activity."""

    def _make_mock_youtube(self, video_id: str = "test_video_id_123") -> MagicMock:
        """Create a mock YouTube service."""
        mock_youtube = MagicMock()

        # Mock the resumable upload: next_chunk returns (None, response) then done
        mock_response = {"id": video_id}
        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (None, mock_response)
        mock_youtube.videos.return_value.insert.return_value = mock_request

        # Mock thumbnails
        mock_thumb_req = MagicMock()
        mock_thumb_req.execute.return_value = {}
        mock_youtube.thumbnails.return_value.set.return_value = mock_thumb_req

        return mock_youtube

    def _make_mock_credentials(self, expired: bool = False) -> MagicMock:
        """Create a mock Google credentials object."""
        mock_creds = MagicMock()
        mock_creds.expired = expired
        mock_creds.refresh_token = "refresh_token"
        mock_creds.token = "access_token"
        mock_creds.client_id = "client_id"
        mock_creds.client_secret = "client_secret"
        mock_creds.scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        return mock_creds

    @pytest.mark.asyncio
    async def test_upload_returns_video_id_and_url(
        self, tmp_path: Path
    ) -> None:
        """upload_to_youtube returns UploadOutput with video_id and correct URL."""
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"fake video content")
        thumb_file = tmp_path / "thumb.jpg"
        thumb_file.write_bytes(b"fake thumbnail content")

        # Write a minimal channel config
        config_dir = tmp_path / "configs"
        config_dir.mkdir()
        (config_dir / "channel_01.yaml").write_text(
            "channel_id: channel_01\nniche: test\nyoutube_credentials_path: /fake/creds.json\n",
            encoding="utf-8",
        )

        mock_youtube = self._make_mock_youtube("vid_abc_123")
        mock_creds = self._make_mock_credentials(expired=False)

        with (
            patch("src.activities.youtube_upload.load_channel_config") as mock_load_config,
            patch("src.activities.youtube_upload.Credentials") as mock_creds_cls,
            patch("src.activities.youtube_upload.build") as mock_build,
            patch("src.activities.youtube_upload.MediaFileUpload") as mock_media,
        ):
            mock_config = MagicMock()
            mock_config.youtube_credentials_path = str(tmp_path / "creds.json")
            mock_load_config.return_value = mock_config

            mock_creds_cls.from_authorized_user_file.return_value = mock_creds
            mock_build.return_value = mock_youtube

            inp = UploadInput(
                video_path=str(video_file),
                thumbnail_path=str(thumb_file),
                title="Test Title",
                description="Test Description",
                tags=["tag1"],
                channel_id="channel_01",
            )

            result = await upload_to_youtube(inp)

        assert isinstance(result, UploadOutput)
        assert result.video_id == "vid_abc_123"
        assert result.youtube_url == "https://www.youtube.com/watch?v=vid_abc_123"

    @pytest.mark.asyncio
    async def test_upload_calls_videos_insert_with_metadata(
        self, tmp_path: Path
    ) -> None:
        """videos().insert() is called with correct snippet and status metadata."""
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"x")
        thumb_file = tmp_path / "thumb.jpg"
        thumb_file.write_bytes(b"x")

        mock_youtube = self._make_mock_youtube("vid_123")
        mock_creds = self._make_mock_credentials()

        with (
            patch("src.activities.youtube_upload.load_channel_config") as mock_load_config,
            patch("src.activities.youtube_upload.Credentials") as mock_creds_cls,
            patch("src.activities.youtube_upload.build") as mock_build,
            patch("src.activities.youtube_upload.MediaFileUpload"),
        ):
            mock_config = MagicMock()
            mock_config.youtube_credentials_path = "/fake/creds.json"
            mock_load_config.return_value = mock_config
            mock_creds_cls.from_authorized_user_file.return_value = mock_creds
            mock_build.return_value = mock_youtube

            inp = UploadInput(
                video_path=str(video_file),
                thumbnail_path=str(thumb_file),
                title="My Test Video",
                description="My Description",
                tags=["foo", "bar"],
                channel_id="channel_01",
                category_id="28",
                publish_status="unlisted",
            )

            await upload_to_youtube(inp)

        # Verify videos().insert() was called
        mock_youtube.videos.return_value.insert.assert_called_once()
        call_kwargs = mock_youtube.videos.return_value.insert.call_args[1]

        body = call_kwargs["body"]
        assert body["snippet"]["title"] == "My Test Video"
        assert body["snippet"]["description"] == "My Description"
        assert body["snippet"]["tags"] == ["foo", "bar"]
        assert body["snippet"]["categoryId"] == "28"
        assert body["status"]["privacyStatus"] == "unlisted"

    @pytest.mark.asyncio
    async def test_upload_calls_thumbnails_set_after_video(
        self, tmp_path: Path
    ) -> None:
        """thumbnails().set() is called with the video_id after upload completes."""
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"x")
        thumb_file = tmp_path / "thumb.jpg"
        thumb_file.write_bytes(b"x")

        mock_youtube = self._make_mock_youtube("vid_thumb_test")
        mock_creds = self._make_mock_credentials()

        with (
            patch("src.activities.youtube_upload.load_channel_config") as mock_load_config,
            patch("src.activities.youtube_upload.Credentials") as mock_creds_cls,
            patch("src.activities.youtube_upload.build") as mock_build,
            patch("src.activities.youtube_upload.MediaFileUpload"),
        ):
            mock_config = MagicMock()
            mock_config.youtube_credentials_path = "/fake/creds.json"
            mock_load_config.return_value = mock_config
            mock_creds_cls.from_authorized_user_file.return_value = mock_creds
            mock_build.return_value = mock_youtube

            inp = _make_upload_input(
                video_path=str(video_file),
                thumbnail_path=str(thumb_file),
            )

            await upload_to_youtube(inp)

        # thumbnails().set() must have been called with the correct video_id
        mock_youtube.thumbnails.return_value.set.assert_called_once_with(
            videoId="vid_thumb_test",
            media_body=mock_youtube.thumbnails.return_value.set.call_args[1]["media_body"],
        )
        mock_youtube.thumbnails.return_value.set.return_value.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_expired_credentials_are_refreshed(
        self, tmp_path: Path
    ) -> None:
        """If credentials are expired, refresh() is called before using them."""
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"x")
        thumb_file = tmp_path / "thumb.jpg"
        thumb_file.write_bytes(b"x")

        mock_youtube = self._make_mock_youtube("vid_refreshed")
        mock_creds = self._make_mock_credentials(expired=True)

        with (
            patch("src.activities.youtube_upload.load_channel_config") as mock_load_config,
            patch("src.activities.youtube_upload.Credentials") as mock_creds_cls,
            patch("src.activities.youtube_upload.Request") as mock_request_cls,
            patch("src.activities.youtube_upload.build") as mock_build,
            patch("src.activities.youtube_upload.MediaFileUpload"),
        ):
            mock_config = MagicMock()
            mock_config.youtube_credentials_path = "/fake/creds.json"
            mock_load_config.return_value = mock_config
            mock_creds_cls.from_authorized_user_file.return_value = mock_creds
            mock_build.return_value = mock_youtube

            inp = _make_upload_input(
                video_path=str(video_file),
                thumbnail_path=str(thumb_file),
            )

            await upload_to_youtube(inp)

        # refresh() must have been called once on the expired credentials
        mock_creds.refresh.assert_called_once_with(mock_request_cls.return_value)

    @pytest.mark.asyncio
    async def test_resumable_upload_uses_media_file_upload(
        self, tmp_path: Path
    ) -> None:
        """MediaFileUpload is called with the video path and resumable=True."""
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"x")
        thumb_file = tmp_path / "thumb.jpg"
        thumb_file.write_bytes(b"x")

        mock_youtube = self._make_mock_youtube("vid_resumable")
        mock_creds = self._make_mock_credentials()

        with (
            patch("src.activities.youtube_upload.load_channel_config") as mock_load_config,
            patch("src.activities.youtube_upload.Credentials") as mock_creds_cls,
            patch("src.activities.youtube_upload.build") as mock_build,
            patch("src.activities.youtube_upload.MediaFileUpload") as mock_media_cls,
        ):
            mock_config = MagicMock()
            mock_config.youtube_credentials_path = "/fake/creds.json"
            mock_load_config.return_value = mock_config
            mock_creds_cls.from_authorized_user_file.return_value = mock_creds
            mock_build.return_value = mock_youtube

            inp = _make_upload_input(
                video_path=str(video_file),
                thumbnail_path=str(thumb_file),
            )

            await upload_to_youtube(inp)

        # Check MediaFileUpload called at least once
        assert mock_media_cls.call_count >= 1, "MediaFileUpload was not called"

        # At least one call must have the video path as the first positional arg
        calls = mock_media_cls.call_args_list
        video_upload_call = next(
            (
                c for c in calls
                if c.args and c.args[0] == str(video_file)
            ),
            None,
        )
        assert video_upload_call is not None, (
            f"MediaFileUpload was not called with the video path '{video_file}'. "
            f"Actual calls: {calls}"
        )

        # That same call (or another) must have resumable=True
        resumable_call = next(
            (c for c in calls if c.kwargs.get("resumable") is True),
            None,
        )
        assert resumable_call is not None, (
            f"MediaFileUpload was not called with resumable=True. Calls: {calls}"
        )
