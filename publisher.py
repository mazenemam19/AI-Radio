"""
publisher.py — AI Radio Echo
YouTube upload and statistics retrieval via Google OAuth2.

Spec rules:
  - If video_path does not exist → return None immediately with a clear log.
  - All OAuth errors → return None with the specific exception message logged.
  - All upload errors → return None (logged). Never raises.
"""

import os
import re
from pathlib import Path
from typing import Optional


def get_youtube_stats_batch(video_ids: list[str]) -> dict[str, dict[str, int]]:
    """
    Fetch viewCount and likeCount for a list of YouTube videos in a single batch.
    Max 50 IDs per request (YouTube API limit).

    Args:
        video_ids: A list of 11-character YouTube video IDs.

    Returns:
        A dict mapping video_id to {'plays': N, 'likes': M}. Defaults to {} on error.
    """
    client_id = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()

    if not all([client_id, client_secret, refresh_token]) or not video_ids:
        return {}

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        import google.auth.transport.requests as google_auth_requests

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )
        creds.refresh(google_auth_requests.Request())

        youtube = build("youtube", "v3", credentials=creds)

        # Batch request: comma-separated IDs
        request = youtube.videos().list(part="statistics", id=",".join(video_ids))
        response = request.execute()

        results = {}
        for item in response.get("items", []):
            v_id = item["id"]
            stats = item["statistics"]
            results[v_id] = {
                "plays": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
            }
        return results
    except Exception as exc:
        print(f"[YouTube] Batch fetch failed for {len(video_ids)} IDs: {exc}")
        return {}


def sync_engagement_stats(db) -> None:
    """
    Fetch all episodes with YouTube URLs, get fresh stats in batches, and update DB.

    Args:
        db: An instance of DBClient to perform updates.
    """
    print("[YouTube] Starting high-performance batch sync...")
    # Fetch all episodes (up to 1000)
    episodes = db.fetch_recent_memory(limit=1000)
    
    # 1. Collect all video IDs and map them to DB IDs
    id_map = {}
    video_ids = []
    for ep in episodes:
        url = ep.get("video_url")
        if not url or "youtube.com" not in url:
            continue
        
        match = re.search(r"v=([a-zA-Z0-9_-]+)", url)
        if match:
            v_id = match.group(1)
            video_ids.append(v_id)
            id_map[v_id] = ep["id"]

    if not video_ids:
        print("[YouTube] No YouTube URLs found to sync.")
        return

    # 2. Fetch stats in batches of 50
    all_stats = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        batch_results = get_youtube_stats_batch(batch)
        all_stats.update(batch_results)

    # 3. Update DB
    updated_count = 0
    for v_id, stats in all_stats.items():
        db_id = id_map.get(v_id)
        if db_id is not None and db.update_post_stats(db_id, stats["plays"], stats["likes"]):
            updated_count += 1

    print(f"[YouTube] Sync complete. Processed {len(video_ids)} videos, updated {updated_count} rows in DB.")

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
