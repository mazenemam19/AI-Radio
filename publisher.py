"""
publisher.py — AI Radio Echo
YouTube upload via Google OAuth2.

Spec rules:
  - If video_path does not exist → return None immediately with a clear log.
  - All OAuth errors → return None with the specific exception message logged.
  - All upload errors → return None (logged). Never raises.
"""

import os
from pathlib import Path
from typing import Optional


def upload_to_youtube(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
) -> Optional[str]:
    """
    Upload an MP4 to YouTube using the Data API v3.

    Returns the full YouTube watch URL on success, None on any failure.
    Every error path is logged with the specific exception message.
    No exception is ever re-raised from this function.

    Args:
        video_path:   Absolute or relative path to the MP4 file.
        title:        Video title (truncated to 100 chars per YouTube limit).
        description:  Video description (truncated to 5000 chars).
        tags:         Tag list (each tag max 500 chars total combined).

    Returns:
        "https://www.youtube.com/watch?v=VIDEO_ID" on success, None otherwise.
    """
    # Guard: file must exist before any OAuth work
    path = Path(video_path)
    if not path.exists():
        print(f"[YouTube] Video file not found: {video_path!r} — skipping upload.")
        return None

    # Credential check
    client_id = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()

    if not all([client_id, client_secret, refresh_token]):
        missing = [
            k for k, v in {
                "YOUTUBE_CLIENT_ID": client_id,
                "YOUTUBE_CLIENT_SECRET": client_secret,
                "YOUTUBE_REFRESH_TOKEN": refresh_token,
            }.items()
            if not v
        ]
        print(
            f"[YouTube] Missing OAuth credential(s): {', '.join(missing)}. "
            "Skipping upload."
        )
        return None

    # Import guard
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        import google.auth.transport.requests as google_auth_requests
    except ImportError as exc:
        print(f"[YouTube] google-api-python-client not installed: {exc}")
        return None

    # OAuth token refresh
    try:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )
        creds.refresh(google_auth_requests.Request())
    except Exception as exc:
        print(f"[YouTube] OAuth token refresh failed: {exc}")
        return None

    # Upload
    try:
        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags,
                "categoryId": "28",  # Science & Technology
            },
            "status": {
                "privacyStatus": "public",
            },
        }

        media = MediaFileUpload(
            str(path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024,  # 1 MB chunks
        )

        insert_request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = insert_request.next_chunk()
            if status:
                print(f"[YouTube] Upload progress: {int(status.progress() * 100)}%")

        video_id = response.get("id")
        if not video_id:
            print("[YouTube] Upload completed but no video ID in response.")
            return None

        url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"[YouTube] Upload successful → {url}")
        return url

    except Exception as exc:
        print(f"[YouTube] Upload failed: {exc}")
        return None
