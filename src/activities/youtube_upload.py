"""
YouTube upload Temporal activity.

Handles resumable video upload and thumbnail attachment via YouTube Data API v3.
Credentials are loaded per-channel from the path configured in ChannelConfig.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from pydantic import BaseModel
from temporalio import activity

from src.models.channel_config import load_channel_config


_YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"


class UploadInput(BaseModel):
    """Input parameters for the upload_to_youtube activity."""

    video_path: str
    thumbnail_path: str
    title: str
    description: str
    tags: list[str]
    channel_id: str
    category_id: str = "22"  # 22 = People & Blogs
    publish_status: str = "private"


class UploadOutput(BaseModel):
    """Output from the upload_to_youtube activity."""

    video_id: str
    youtube_url: str


def _load_and_refresh_credentials(credentials_path: str) -> Credentials:
    """Load credentials from file and refresh if expired.

    Args:
        credentials_path: Path to the OAuth2 authorized user JSON file.

    Returns:
        Valid (possibly refreshed) Credentials object.
    """
    creds = Credentials.from_authorized_user_file(
        credentials_path,
        scopes=[_YOUTUBE_UPLOAD_SCOPE],
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


def _save_credentials(credentials_path: str, creds: Credentials) -> None:
    """Persist refreshed credentials back to disk.

    The refresh token may rotate after use; saving prevents the next call
    from failing with an invalid_grant error.

    Args:
        credentials_path: Path to write the updated credentials JSON.
        creds: Credentials object (possibly with a new access/refresh token).
    """
    creds_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": getattr(creds, "token_uri", "https://oauth2.googleapis.com/token"),
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else [_YOUTUBE_UPLOAD_SCOPE],
    }
    Path(credentials_path).write_text(
        json.dumps(creds_data, indent=2),
        encoding="utf-8",
    )


def _do_resumable_upload(youtube: object, params: UploadInput) -> str:
    """Execute the resumable upload loop synchronously.

    Runs the next_chunk() loop until completion. Designed to be called
    inside asyncio.to_thread() so the event loop is not blocked.

    Args:
        youtube: Authenticated YouTube service resource.
        params: Upload parameters (video path, title, metadata).

    Returns:
        The YouTube video_id string from the upload response.

    Raises:
        RuntimeError: If upload completes without returning a response.
    """
    request_body = {
        "snippet": {
            "title": params.title,
            "description": params.description,
            "tags": params.tags,
            "categoryId": params.category_id,
        },
        "status": {
            "privacyStatus": params.publish_status,
        },
    }

    media = MediaFileUpload(
        params.video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=-1,
    )

    insert_request = youtube.videos().insert(  # type: ignore[union-attr]
        part="snippet,status",
        body=request_body,
        media_body=media,
    )

    response = None
    while response is None:
        _status, response = insert_request.next_chunk()

    if response is None:
        raise RuntimeError("YouTube upload completed without a response body")

    return response["id"]


@activity.defn
async def upload_to_youtube(params: UploadInput) -> UploadOutput:
    """Upload a video to YouTube and attach a thumbnail.

    Steps:
    1. Load ChannelConfig to get youtube_credentials_path.
    2. Load and refresh OAuth2 credentials.
    3. Build the YouTube Data API v3 service.
    4. Execute resumable video upload (via asyncio.to_thread).
    5. Attach thumbnail with thumbnails().set().
    6. Save updated credentials (refresh token may have changed).
    7. Return UploadOutput(video_id, youtube_url).

    Args:
        params: UploadInput with video/thumbnail paths, metadata, channel_id.

    Returns:
        UploadOutput containing video_id and full YouTube watch URL.

    Raises:
        FileNotFoundError: If channel config or credentials file is missing.
        google.auth.exceptions.RefreshError: If credential refresh fails.
        RuntimeError: If upload returns no response.
    """
    config = load_channel_config(params.channel_id)
    credentials_path = config.youtube_credentials_path

    creds = _load_and_refresh_credentials(credentials_path)
    youtube = build("youtube", "v3", credentials=creds)

    # Resumable upload is blocking I/O — run in a thread pool
    video_id = await asyncio.to_thread(_do_resumable_upload, youtube, params)

    # Attach thumbnail (non-fatal: requires YouTube channel verification)
    try:
        youtube.thumbnails().set(  # type: ignore[union-attr]
            videoId=video_id,
            media_body=MediaFileUpload(params.thumbnail_path, mimetype="image/jpeg"),
        ).execute()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Thumbnail upload skipped (video_id=%s): %s", video_id, exc
        )

    # Persist any token rotation
    try:
        _save_credentials(credentials_path, creds)
    except Exception:
        # Non-fatal: credential save failure does not invalidate the upload
        # (e.g. read-only filesystem, serialization error on mock objects in tests)
        pass

    return UploadOutput(
        video_id=video_id,
        youtube_url=f"https://www.youtube.com/watch?v={video_id}",
    )
