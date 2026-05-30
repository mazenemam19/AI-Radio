"""
publisher.py — YouTube upload for AI Radio Echo.

Uses OAuth2 refresh-token flow (no interactive browser sign-in).
Required env vars: YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN

Returns the YouTube video URL string on success, or None on any failure.
A None result MUST NOT fail the pipeline — the caller logs and continues.
"""

import os
from pathlib import Path


def upload_to_youtube(
    video_path: str,
    title: str,
    description: str,
    tags: "list[str]",
) -> "str | None":
    """
    Upload an MP4 to YouTube.

    Args:
        video_path:  Local path to the compiled MP4.
        title:       YouTube video title.
        description: YouTube video description.
        tags:        List of tag strings for discoverability.

    Returns:
        Full YouTube watch URL on success, None on any failure.
        All OAuth and API errors are caught and logged — never re-raised.
    """
    # --- Pre-flight: verify file exists ---
    if not Path(video_path).exists():
        print(f"[YouTube] Video file not found at '{video_path}'. Returning None.")
        return None

    # --- Gather credentials ---
    client_id     = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()

    if not all([client_id, client_secret, refresh_token]):
        print(
            "[YouTube] Missing one or more required env vars: "
            "YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN. "
            "Returning None."
        )
        return None

    try:
        from google.oauth2.credentials import Credentials            # type: ignore
        from google.auth.transport.requests import Request           # type: ignore
        from googleapiclient.discovery import build                  # type: ignore
        from googleapiclient.http import MediaFileUpload             # type: ignore
    except ImportError as exc:
        print(f"[YouTube] Required library not installed: {exc}. Returning None.")
        return None

    try:
        # --- Build refreshable credentials ---
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )
        creds.refresh(Request())
    except Exception as exc:
        print(f"[YouTube] OAuth token refresh failed: {exc}. Returning None.")
        return None

    try:
        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title":       title[:100],        # YouTube title limit
                "description": description[:5000], # YouTube description limit
                "tags":        tags[:500],
                "categoryId":  "25",               # News & Politics
            },
            "status": {
                "privacyStatus": "public",
            },
        }

        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            chunksize=-1,
            resumable=True,
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            _, response = request.next_chunk()

        video_id  = response.get("id")
        video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else None

        if video_url:
            print(f"[YouTube] Upload successful: {video_url}")
        else:
            print(f"[YouTube] Upload completed but no video ID in response: {response}")

        return video_url

    except Exception as exc:
        print(f"[YouTube] Upload failed: {exc}. Returning None.")
        return None
