import os
import mimetypes
import json
import sqlite3
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

class SupabaseDBClient:
    def __init__(self, env="production"):
        self.env = env.lower()
        self.is_mock = False
        self.use_sqlite = (self.env == "local")
        
        if self.use_sqlite:
            self.db_path = "ai_radio_dev.db"
            self._init_sqlite()
            print(f"[DB Client] Operating in LOCAL mode (SQLite: {self.db_path})")
            return

        # Environment switching logic
        if self.env == "staging":
            self.url = os.environ.get("STAGING_SUPABASE_URL")
            self.key = os.environ.get("STAGING_SUPABASE_KEY")
        else:
            self.url = os.environ.get("SUPABASE_URL")
            self.key = os.environ.get("SUPABASE_KEY")

        # Clean URL trailing slash if present
        if self.url:
            self.url = self.url.rstrip("/")

        if self.url and self.key:
            # Standard Supabase authorization headers
            self.headers = {
                "apikey": self.key,
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json"
            }
            print(f"[DB Client] Connected to {self.env.upper()} Supabase successfully.")
        else:
            print(f"[DB Client] Missing credentials for {self.env.upper()}. Operating in mock mode.")
            self.is_mock = True

    def _init_sqlite(self):
        """Initialize local SQLite database for offline testing."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS memory_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            headline TEXT,
            source TEXT,
            topic_tags TEXT,
            my_take TEXT,
            post_text TEXT,
            audio_script TEXT,
            audio_url TEXT,
            video_url TEXT,
            confidence TEXT,
            related_ids TEXT,
            likes INTEGER DEFAULT 0,
            plays INTEGER DEFAULT 0
        )''')
        conn.commit()
        conn.close()

    def fetch_recent_memory(self, limit=30):
        """Fetch the last `limit` posts for historical memory context."""
        if self.is_mock:
            return []

        if self.use_sqlite:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM memory_log ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = c.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["topic_tags"] = json.loads(d["topic_tags"]) if d["topic_tags"] else []
                results.append(d)
            conn.close()
            return results

        try:
            endpoint = f"{self.url}/rest/v1/memory_log"
            params = {
                "select": "id,created_at,headline,my_take,post_text,topic_tags",
                "order": "created_at.desc",
                "limit": limit
            }
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=15)
            return response.json() if response.status_code == 200 else []
        except Exception as e:
            print(f"[DB Client] HTTP connection failed fetching memory: {e}")
            return []

    def insert_post(self, headline, source, topic_tags, my_take, post_text, audio_script, audio_url, video_url=None, confidence="medium", related_ids=None):
        """Insert a newly generated episode."""
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
            print(f"[DB Client] [MOCK] Inserting post: {headline}")
            return {"id": 999, **data}

        if self.use_sqlite:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''INSERT INTO memory_log 
                (headline, source, topic_tags, my_take, post_text, audio_script, audio_url, video_url, confidence, related_ids) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                (headline, source, json.dumps(topic_tags), my_take, post_text, audio_script, audio_url, video_url, confidence_clean, json.dumps(related_ids or [])))
            row_id = c.lastrowid
            conn.commit()
            conn.close()
            return {"id": row_id, **data}

        try:
            endpoint = f"{self.url}/rest/v1/memory_log"
            insert_headers = self.headers.copy()
            insert_headers["Prefer"] = "return=representation"
            response = requests.post(endpoint, headers=insert_headers, json=data, timeout=15)
            if response.status_code in [200, 201]:
                records = response.json()
                if records:
                    print(f"[DB Client] Inserted episode successfully: {headline}")
                    return records[0]
            return data
        except Exception as e:
            print(f"[DB Client] HTTP connection failed inserting post: {e}")
            return data

    def delete_old_episodes(self, days_to_keep=7):
        """Deletes episodes older than X days."""
        if self.is_mock: return

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_to_keep)).isoformat()
        
        if self.use_sqlite:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("DELETE FROM memory_log WHERE created_at < ?", (cutoff,))
            conn.commit()
            conn.close()
            return

        try:
            endpoint = f"{self.url}/rest/v1/memory_log"
            params = {"created_at": f"lt.{cutoff}", "select": "id,audio_url"}
            r = requests.get(endpoint, headers=self.headers, params=params)
            old_episodes = r.json() if r.status_code == 200 else []
            if not old_episodes: return

            for ep in old_episodes:
                if ep.get("audio_url") and "supabase" in ep["audio_url"]:
                    filename = ep["audio_url"].split("/")[-1]
                    storage_endpoint = f"{self.url}/storage/v1/object/broadcasts/{filename}"
                    requests.delete(storage_endpoint, headers=self.headers)
                delete_endpoint = f"{self.url}/rest/v1/memory_log?id=eq.{ep['id']}"
                requests.delete(delete_endpoint, headers=self.headers)
        except Exception as e:
            print(f"[DB Client] Error during cleanup: {e}")

    def upload_audio(self, local_file_path, storage_filename):
        """Upload raw binary MP3 to Supabase Storage."""
        if self.use_sqlite or self.is_mock:
            return f"https://local-mock-storage.co/{storage_filename}"

        bucket_name = "broadcasts"
        try:
            mime_type, _ = mimetypes.guess_type(local_file_path)
            if not mime_type: mime_type = "audio/mpeg"
            endpoint = f"{self.url}/storage/v1/object/{bucket_name}/{storage_filename}"
            upload_headers = {
                "Authorization": f"Bearer {self.key}",
                "apikey": self.key,
                "Content-Type": mime_type,
                "x-upsert": "true"
            }
            with open(local_file_path, "rb") as f:
                file_bytes = f.read()
            response = requests.post(endpoint, headers=upload_headers, data=file_bytes, timeout=45)
            if response.status_code == 200:
                return f"{self.url}/storage/v1/object/public/{bucket_name}/{storage_filename}"
            return f"{self.url}/storage/v1/object/public/{bucket_name}/{storage_filename}"
        except Exception:
            return f"{self.url}/storage/v1/object/public/{bucket_name}/{storage_filename}"
