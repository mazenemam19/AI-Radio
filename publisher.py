"""
publisher.py — AI Radio Echo
Uploads compiled MP4 episodes to YouTube via OAuth2.
Returns None on any failure (does NOT abort the pipeline).
"""

import os
from pathlib import Path


def upload_to_youtube(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
) -> str | None:
    """
    Upload an MP4 file to YouTube.

    Args:
        video_path:  Local path to the compiled .mp4 file.
        title:       Video title.
        description: Video description.
        tags:        List of tag strings.

    Returns:
        YouTube video URL (str) on success, or None on any failure.
        A None return does NOT cause the pipeline to exit — the caller
        must handle it gracefully and continue.

    Failure modes handled:
        - video_path does not exist → return None immediately.
        - Missing OAuth credentials → return None.
        - Any OAuth / API exception  → return None with message logged.
    """
    # Guard: file must exist before attempting upload
    if not Path(video_path).exists():
        print(f"[YouTube] Video file not found: {video_path}. Skipping upload.")
        return None

    client_id     = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        missing = [
            k for k, v in {
                "YOUTUBE_CLIENT_ID":     client_id,
                "YOUTUBE_CLIENT_SECRET": client_secret,
                "YOUTUBE_REFRESH_TOKEN": refresh_token,
            }.items()
            if not v
        ]
        print(f"[YouTube] Missing OAuth credentials: {missing}. Skipping upload.")
        return None

    try:
        import google.oauth2.credentials
        import googleapiclient.discovery
        import googleapiclient.http

        credentials = google.oauth2.credentials.Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
        )

        youtube = googleapiclient.discovery.build(
            "youtube", "v3", credentials=credentials
        )

        body = {
            "snippet": {
                "title":       title[:100],       # YouTube title limit
                "description": description[:5000], # YouTube description limit
                "tags":        [str(t) for t in (tags or [])],
                "categoryId":  "25",              # News & Politics
            },
            "status": {
                "privacyStatus": "public",
            },
        }

        media = googleapiclient.http.MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        print(f"[YouTube] Starting upload: {video_path}")
        response = None
        while response is None:
            _, response = request.next_chunk()

        video_id  = response.get("id")
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"[YouTube] Upload complete: {video_url}")
        return video_url

    except Exception as e:
        print(f"[YouTube] Upload failed: {e}")
        return None
