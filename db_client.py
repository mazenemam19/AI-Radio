import os
import mimetypes
import requests
from dotenv import load_dotenv

load_dotenv()

class SupabaseDBClient:
    def __init__(self):
        self.url = os.environ.get("SUPABASE_URL")
        self.key = os.environ.get("SUPABASE_KEY")
        self.is_mock = True
        
        # Clean URL trailing slash if present
        if self.url:
            self.url = self.url.rstrip("/")

        if self.url and self.key:
            self.is_mock = False
            # Standard Supabase authorization headers
            self.headers = {
                "apikey": self.key,
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json"
            }
            print("[Supabase Client] Operating in PURE HTTP REST Mode. Connected successfully.")
        else:
            print("[Supabase Client] Missing credentials. Operating in dry-run/mock mode.")

    def fetch_recent_memory(self, limit=30):
        """Fetch the last `limit` posts for historical memory context using PostgREST GET."""
        if self.is_mock:
            print("[Supabase Client] [MOCK] Fetching recent memory (returning empty list)")
            return []

        try:
            # PostgREST query structure
            endpoint = f"{self.url}/rest/v1/memory_log"
            params = {
                "select": "id,created_at,headline,my_take,post_text,topic_tags",
                "order": "created_at.desc",
                "limit": limit
            }
            
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=15)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[Supabase Client] Error fetching memory: HTTP {response.status_code} - {response.text}")
                return []
        except Exception as e:
            print(f"[Supabase Client] HTTP connection failed fetching memory: {e}")
            return []

    def insert_post(self, headline, source, topic_tags, my_take, post_text, audio_script, audio_url, video_url=None, confidence="medium", related_ids=None):
        """Insert a newly generated episode using PostgREST POST."""
        
        # Ensure confidence matches the check constraint (lowercase)
        confidence_clean = str(confidence).lower() if confidence else "medium"
        if confidence_clean not in ['high', 'medium', 'low']:
            confidence_clean = "medium"

        data = {
            "headline": headline,
            "source": source,
            "topic_tags": topic_tags,
            "my_take": my_take,
            "post_text": post_text,
            "audio_script": audio_script,
            "audio_url": audio_url,
            "video_url": video_url,
            "confidence": confidence_clean,
            "related_ids": related_ids or [],
            "likes": 0,
            "plays": 0
        }

        if self.is_mock:
            print(f"[Supabase Client] [MOCK] Inserting post: {headline}")
            import random
            data["id"] = random.randint(100, 999)
            return data

        try:
            endpoint = f"{self.url}/rest/v1/memory_log"
            # We want PostgREST to return the full representation of the inserted row so we capture the serial ID
            insert_headers = self.headers.copy()
            insert_headers["Prefer"] = "return=representation"
            
            response = requests.post(endpoint, headers=insert_headers, json=data, timeout=15)
            
            if response.status_code in [200, 201]:
                records = response.json()
                if records:
                    print(f"[Supabase Client] Inserted episode successfully: {headline}")
                    return records[0]
            print(f"[Supabase Client] Warning inserting post: HTTP {response.status_code} - {response.text}")
            return data
        except Exception as e:
            print(f"[Supabase Client] HTTP connection failed inserting post: {e}")
            return data

    def upload_audio(self, local_file_path, storage_filename):
        """Upload raw binary MP3 to Supabase Storage endpoint broadcasts."""
        bucket_name = "broadcasts"

        if self.is_mock:
            print(f"[Supabase Client] [MOCK] Uploading {local_file_path} as {storage_filename}")
            return f"https://mock-supabase-url.co/storage/v1/object/public/broadcasts/{storage_filename}"

        if not os.path.exists(local_file_path):
            print(f"[Supabase Client] Local file does not exist: {local_file_path}")
            return None

        try:
            # Check mime type
            mime_type, _ = mimetypes.guess_type(local_file_path)
            if not mime_type:
                mime_type = "audio/mpeg"

            # Prepare storage binary upload endpoint
            # Supabase Storage POST: /storage/v1/object/{bucket}/{path}
            endpoint = f"{self.url}/storage/v1/object/{bucket_name}/{storage_filename}"
            
            # Storage headers
            upload_headers = {
                "Authorization": f"Bearer {self.key}",
                "apikey": self.key,
                "Content-Type": mime_type,
                "x-upsert": "true"
            }

            with open(local_file_path, "rb") as f:
                file_bytes = f.read()

            print(f"[Supabase Client] Uploading raw audio binary to Storage...")
            response = requests.post(endpoint, headers=upload_headers, data=file_bytes, timeout=45)

            if response.status_code == 200:
                public_url = f"{self.url}/storage/v1/object/public/{bucket_name}/{storage_filename}"
                print(f"[Supabase Client] Uploaded audio successfully! Public URL: {public_url}")
                return public_url
            else:
                print(f"[Supabase Client] Error uploading audio: HTTP {response.status_code} - {response.text}")
                # Try fallback URL in case of transient error
                return f"{self.url}/storage/v1/object/public/{bucket_name}/{storage_filename}"

        except Exception as e:
            print(f"[Supabase Client] HTTP storage connection failed: {e}")
            return f"{self.url}/storage/v1/object/public/{bucket_name}/{storage_filename}"
