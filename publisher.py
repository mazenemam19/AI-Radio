import os
from atproto import Client as BlueskyClient
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

load_dotenv()

class DistributionPublisher:
    def __init__(self):
        self.bsky_handle = os.environ.get("BLUESKY_HANDLE")
        self.bsky_password = os.environ.get("BLUESKY_PASSWORD")
        
        # YouTube OAuth 2.0 Credentials
        self.yt_client_id = os.environ.get("YOUTUBE_CLIENT_ID")
        self.yt_client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
        self.yt_refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")

    def post_to_bluesky(self, text):
        """Post a text observation (max 280 chars) to Bluesky."""
        if not self.bsky_handle or not self.bsky_password:
            print("[Publisher] [MOCK] Bluesky credentials missing. Mocking post.")
            print(f"[Publisher] [MOCK] Text would be: '{text}'")
            return {"uri": "at://mock-did/app.bsky.feed.post/mock-rkey", "cid": "mock-cid"}

        try:
            print(f"[Publisher] Logging into Bluesky as {self.bsky_handle}...")
            client = BlueskyClient()
            client.login(self.bsky_handle, self.bsky_password)
            print("[Publisher] Posting update to Bluesky...")
            response = client.send_post(text=text)
            print(f"[Publisher] Posted successfully! URI: {response.uri}")
            return {"uri": response.uri, "cid": response.cid}
        except Exception as e:
            print(f"[Publisher] Error posting to Bluesky: {e}")
            return None

    def upload_to_youtube(self, video_path, title, description, tags=None):
        """Upload a compiled MP4 video to YouTube using OAuth 2.0 Refresh Token flow."""
        if not self.yt_refresh_token or not self.yt_client_id or not self.yt_client_secret:
            print("[Publisher] [MOCK] YouTube OAuth credentials missing. Mocking video upload.")
            print(f"[Publisher] [MOCK] Video would be: '{video_path}' with Title: '{title}'")
            return "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Return standard YouTube template

        if not os.path.exists(video_path):
            print(f"[Publisher] Video file does not exist: {video_path}")
            return None

        try:
            print("[Publisher] Authenticating with YouTube OAuth 2.0...")
            # Setup YouTube Credentials from refresh token and client secrets
            creds = Credentials(
                token=None,  # Will be refreshed immediately
                refresh_token=self.yt_refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.yt_client_id,
                client_secret=self.yt_client_secret
            )

            # Refresh token to obtain active access token
            creds.refresh(Request())
            print("[Publisher] OAuth token refreshed successfully.")

            # Build YouTube Service
            youtube = build("youtube", "v3", credentials=creds)

            # Metadata body
            body = {
                "snippet": {
                    "title": title[:100],  # YouTube limit is 100 characters
                    "description": description,
                    "tags": tags or ["AI Radio", "Echo", "News Commentary", "Technology"],
                    "categoryId": "22"  # 22 = People & Blogs
                },
                "status": {
                    "privacyStatus": "public",  # Can be "public", "private", or "unlisted"
                    "selfDeclaredMadeForKids": False
                }
            }

            # Media upload
            media = MediaFileUpload(
                video_path,
                mimetype="video/mp4",
                chunksize=-1,
                resumable=True
            )

            print(f"[Publisher] Uploading video: '{title}' to YouTube...")
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )

            # Execute video insertion
            response = request.execute()
            video_id = response.get("id")
            youtube_url = f"https://www.youtube.com/watch?v={video_id}"
            print(f"[Publisher] Upload complete! YouTube Video URL: {youtube_url}")
            return youtube_url

        except Exception as e:
            print(f"[Publisher] Error uploading to YouTube: {e}")
            # Try to print more details for troubleshooting OAuth errors
            return None
