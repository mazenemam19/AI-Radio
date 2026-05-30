"""
db_client.py — Unified database interface for AI Radio Echo.

SQLite is used for envs: local, prod-models
Supabase is used for envs: prod-db, production

The public interface is identical regardless of backend.
"""

import os
import sqlite3
import json
import requests
import mimetypes
from pathlib import Path
from datetime import datetime, timedelta, timezone

SQLITE_ENVS = {"local", "prod-models"}
SUPABASE_ENVS = {"prod-db", "production"}

# All columns defined in schema.sql — single source of truth for validation.
SCHEMA_COLUMNS = [
    "id",
    "created_at",
    "headline",
    "original_headline",
    "source",
    "topic_tags",
    "my_take",
    "post_text",
    "audio_script",
    "audio_url",
    "video_url",
    "confidence",
    "related_ids",
    "likes",
    "plays",
    "broadcast_duration",
    "healer_used",
    "writer_model",
    "narrator_model",
]

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class DBClient:
    """
    Unified DB interface. Instantiate once with the active env string.
    All public methods behave identically regardless of the underlying backend.
    """

    def __init__(self, env: str):
        if env not in SQLITE_ENVS and env not in SUPABASE_ENVS:
            raise ValueError(
                f"Unknown env '{env}'. Valid values: {sorted(SQLITE_ENVS | SUPABASE_ENVS)}"
            )
        self.env = env
        self._backend = "sqlite" if env in SQLITE_ENVS else "supabase"

        if self._backend == "sqlite":
            self._init_sqlite()
        else:
            self._init_supabase()

    # ------------------------------------------------------------------ #
    # Init helpers                                                         #
    # ------------------------------------------------------------------ #

    def _init_sqlite(self):
        db_name = "ai_radio_dev.db"
        if not SCHEMA_PATH.exists():
            raise FileNotFoundError(f"schema.sql not found at {SCHEMA_PATH}")
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

        self._conn = sqlite3.connect(db_name, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(schema_sql)
        self._conn.commit()
        print(f"[DB] SQLite initialised: {db_name}")

    def _init_supabase(self):
        url = os.environ.get("SUPABASE_URL", "").strip()
        key = os.environ.get("SUPABASE_KEY", "").strip()
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_KEY environment variables are required "
                f"for env='{self.env}' but were not found."
            )
        try:
            from supabase import create_client  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "supabase-py is not installed. Run: pip install supabase"
            ) from exc

        self.supabase_url = url
        self._headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
        }
        self._supa = create_client(url, key)
        self._validate_supabase_schema()
        print(f"[DB] Supabase initialised: {url}")

    def _validate_supabase_schema(self):
        """
        Verify every column in SCHEMA_COLUMNS exists in the Supabase table.
        Raises RuntimeError with the specific missing column names if any are absent.
        Uses limit(0) per-column to probe the PostgREST endpoint — returns an
        error for unknown column names without touching real data.
        """
        missing = []
        for col in SCHEMA_COLUMNS:
            try:
                self._supa.table("memory_log").select(col).limit(0).execute()
            except Exception:
                missing.append(col)

        if missing:
            raise RuntimeError(
                f"Supabase schema mismatch. The following columns defined in "
                f"schema.sql are missing from the 'memory_log' table: {missing}. "
                "Apply schema.sql to your Supabase project before running this env."
            )
        print("[DB] Supabase schema validation passed.")

    # ------------------------------------------------------------------ #
    # Public interface                                                     #
    # ------------------------------------------------------------------ #

    def fetch_recent_memory(self, limit: int = 20) -> list[dict]:
        """Return the most recent `limit` episodes, newest first."""
        if self._backend == "sqlite":
            cur = self._conn.execute(
                "SELECT * FROM memory_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]
        else:
            result = (
                self._supa.table("memory_log")
                .select("*")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []

    def insert_post(self, data: dict) -> "dict | None":
        """
        Insert a new episode row. Returns the inserted row as a dict, or None on failure.
        Never saves a fake success — if the insert fails, returns None with a logged reason.
        """
        if self._backend == "sqlite":
            cols = ", ".join(data.keys())
            placeholders = ", ".join(["?" for _ in data])
            vals = list(data.values())
            try:
                cur = self._conn.execute(
                    f"INSERT INTO memory_log ({cols}) VALUES ({placeholders})", vals
                )
                self._conn.commit()
                inserted = self._conn.execute(
                    "SELECT * FROM memory_log WHERE id = ?", (cur.lastrowid,)
                ).fetchone()
                return dict(inserted) if inserted else None
            except Exception as exc:
                print(f"[DB] SQLite insert failed: {exc}")
                return None
        else:
            try:
                result = (
                    self._supa.table("memory_log").insert(data).execute()
                )
                return result.data[0] if result.data else None
            except Exception as exc:
                print(f"[DB] Supabase insert failed: {exc}")
                return None

    def upload_file(self, local_path: str, bucket: str = "broadcasts") -> str | None:
        """
        Upload a file to Supabase Storage (if in Supabase mode) or return
        a local reference URI (if in SQLite mode).

        Returns:
            The public URL or local:// URI string, or None on failure.
        """
        p = Path(local_path)
        if not p.exists():
            print(f"[DB] upload_file failed: {local_path} does not exist.")
            return None

        if self._backend == "sqlite":
            # Return a 'local://' URI that the dashboard frontend can recognize.
            return f"local://{p.name}"

        # Supabase Storage
        file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{p.name}"
        url = f"{self.supabase_url}/storage/v1/object/{bucket}/{file_name}"

        mime_type, _ = mimetypes.guess_type(local_path)
        headers = {
            **self._headers,
            "Content-Type": mime_type or "application/octet-stream",
        }

        try:
            with open(local_path, "rb") as f:
                resp = requests.post(url, headers=headers, data=f, timeout=60)

            if resp.status_code == 200:
                # Construct public URL
                public_url = f"{self.supabase_url}/storage/v1/object/public/{bucket}/{file_name}"
                print(f"[DB] Uploaded to Supabase Storage: {public_url}")
                return public_url

            print(f"[DB] Supabase upload failed ({resp.status_code}): {resp.text}")
            return None
        except Exception as e:
            print(f"[DB] upload_file error: {e}")
            return None

    def delete_old_episodes(self, days_to_keep: int = 30):
        """
        Delete episodes older than `days_to_keep` days.
        Uses the idx_memory_log_created_at index for efficient deletion.
        """
        cutoff = (
            datetime.now(tz=timezone.utc) - timedelta(days=days_to_keep)
        ).isoformat()

        if self._backend == "sqlite":
            try:
                self._conn.execute(
                    "DELETE FROM memory_log WHERE created_at < ?", (cutoff,)
                )
                self._conn.commit()
                print(f"[DB] Deleted episodes older than {days_to_keep} days (cutoff: {cutoff}).")
            except Exception as exc:
                print(f"[DB] delete_old_episodes failed: {exc}")
        else:
            try:
                self._supa.table("memory_log").delete().lt("created_at", cutoff).execute()
                print(f"[DB] Supabase: deleted episodes older than {days_to_keep} days.")
            except Exception as exc:
                print(f"[DB] Supabase delete_old_episodes failed: {exc}")
