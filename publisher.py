"""
publisher.py — AI Radio Echo
YouTube upload via OAuth2 (client_id + client_secret + refresh_token).
  - Missing video file: return None immediately with clear log.
  - Any OAuth or upload error: return None with specific exception logged.
  - YouTube failure NEVER fails the whole pipeline (caller's responsibility).
"""

import os


def upload_to_youtube(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
) -> str | None:
    """
    Upload an MP4 to YouTube.

    Returns:
        YouTube video URL on success, None on any failure.
    """
    if not os.path.exists(video_path):
        print(f"[YouTube] Video file not found: {video_path}. Cannot upload.")
        return None

    client_id      = os.environ.get("YOUTUBE_CLIENT_ID", "")
    client_secret  = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
    refresh_token  = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

    if not client_id or not client_secret or not refresh_token:
        print("[YouTube] Missing OAuth credentials (YOUTUBE_CLIENT_ID / CLIENT_SECRET / REFRESH_TOKEN).")
        return None

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:
        print(f"[YouTube] google-api-python-client not installed: {exc}")
        return None

    # Build credentials from stored refresh token (no interactive flow)
    try:
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
        print(f"[YouTube] OAuth token refresh failed: {exc}")
        return None

    try:
        youtube = build("youtube", "v3", credentials=creds)

        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title[:100],
                    "description": description[:5000],
                    "tags": tags[:500],
                    "categoryId": "25",   # News & Politics
                    "defaultLanguage": "en",
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False,
                },
            },
            media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True),
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                print(f"[YouTube] Uploading… {pct}%")

        video_id = response.get("id")
        if not video_id:
            print(f"[YouTube] Upload succeeded but no video ID returned: {response}")
            return None

        url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"[YouTube] Upload complete: {url}")
        return url

    except Exception as exc:
        print(f"[YouTube] Upload failed: {exc}")
        return None
