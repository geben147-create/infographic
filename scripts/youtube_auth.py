"""YouTube OAuth2 one-time setup script.

Run this once per channel to generate the OAuth2 token file needed for automated uploads.
The token file is saved to data/yt_token_{channel_id}.json and auto-refreshes at upload time.

Usage:
    uv run python scripts/youtube_auth.py --channel-id channel_01 --client-secrets client_secrets.json
"""

import argparse
import json
import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_token_path(channel_id: str) -> Path:
    return Path("data") / f"yt_token_{channel_id}.json"


def load_existing_credentials(token_path: Path) -> Credentials | None:
    """Load existing credentials from token file, refresh if expired."""
    if not token_path.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds.expired and creds.refresh_token:
        print(f"Token expired — refreshing credentials for {token_path.name}...")
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
        print(f"Refreshed and saved credentials to {token_path}")
    return creds


def run_oauth_flow(client_secrets: str, token_path: Path) -> Credentials:
    """Run the OAuth2 authorization flow in the browser."""
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets, SCOPES)
    creds = flow.run_local_server(port=0)
    return creds


def main() -> None:
    parser = argparse.ArgumentParser(
        description="YouTube OAuth2 one-time setup. Generates a token file for automated uploads."
    )
    parser.add_argument(
        "--channel-id",
        required=True,
        help="Channel identifier (e.g. channel_01). Token saved as data/yt_token_{channel_id}.json",
    )
    parser.add_argument(
        "--client-secrets",
        default="client_secrets.json",
        help="Path to the GCP OAuth2 client secrets JSON file (default: client_secrets.json)",
    )
    args = parser.parse_args()

    channel_id: str = args.channel_id
    client_secrets: str = args.client_secrets
    token_path = get_token_path(channel_id)

    # Ensure data/ directory exists
    token_path.parent.mkdir(parents=True, exist_ok=True)

    # Check for existing valid credentials
    existing = load_existing_credentials(token_path)
    if existing and existing.valid:
        print(f"YouTube credentials for {channel_id} are already valid.")
        print(f"Token file: {token_path}")
        return

    # Verify client secrets file exists
    if not Path(client_secrets).exists():
        print(f"ERROR: Client secrets file not found: {client_secrets}", file=sys.stderr)
        print("Download it from GCP Console → APIs & Services → Credentials", file=sys.stderr)
        sys.exit(1)

    print(f"Starting OAuth2 authorization flow for channel: {channel_id}")
    print("Your browser will open for Google account consent...")

    creds = run_oauth_flow(client_secrets, token_path)
    token_path.write_text(creds.to_json(), encoding="utf-8")

    print(f"Saved YouTube credentials to {token_path}")


if __name__ == "__main__":
    main()
