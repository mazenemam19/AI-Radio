"""
db_client.py — AI Radio Echo
Unified database interface for SQLite (local/prod-models) and Supabase (prod-db/production).
Public API is identical regardless of backend.
"""

import os
import sqlite3
import json
import requests
import mimetypes
from datetime import datetime, timedelta, timezone
from pathlib import Path


SQLITE_ENVS = {"local", "prod-models"}
SUPABASE_ENVS = {"prod-db", "production"}

EXPECTED_COLUMNS = {
    "id", "created_at", "headline", "original_headline", "source",
    "topic_tags", "my_take", "post_text", "audio_script", "audio_url",
    "video_url", "confidence", "related_ids", "likes", "plays",
    "broadcast_duration", "healer_used", "writer_model", "narrator_model",
}


class DBClient:
    def __init__(self, env: str):
        self.env = env

        if env in SQLITE_ENVS:
            self._backend = "sqlite"
            db_name = "ai_radio_dev.db"
            self.conn = sqlite3.connect(db_name)
            self.conn.row_factory = sqlite3.Row
            self._init_sqlite()

        elif env in SUPABASE_ENVS:
            self._backend = "supabase"
            self.supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
            self.supabase_key = os.environ.get("SUPABASE_KEY", "")
            if not self.supabase_url or not self.supabase_key:
                raise RuntimeError(
                    "SUPABASE_URL and SUPABASE_KEY are required for "
                    f"'{env}' environment."
                )
            self._headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json",
            }
            self._headers_return = {
                **self._headers,
                "Prefer": "return=representation",
            }
            self._validate_supabase_schema()

        else:
            raise ValueError(
                f"Unknown environment '{env}'. "
                f"Valid values: {sorted(SQLITE_ENVS | SUPABASE_ENVS)}"
            )

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    def _init_sqlite(self):
        schema_path = Path(__file__).parent / "schema.sql"
        if not schema_path.exists():
            raise RuntimeError(f"schema.sql not found at {schema_path}")
        schema_sql = schema_path.read_text(encoding="utf-8")
        self.conn.executescript(schema_sql)
        self.conn.commit()

    def _validate_supabase_schema(self):
        """
        Verify that every column defined in schema.sql exists in Supabase.
        Strategy 1: Parse the PostgREST OpenAPI spec (preferred — reports ALL missing).
        Strategy 2: Attempt a zero-row SELECT with all column names (fallback).
        Raises RuntimeError listing missing columns if any are absent.
        """
        missing = self._check_via_openapi()
        if missing is None:
            # OpenAPI parse failed; fall back to SELECT probe
            missing = self._check_via_select()
        if missing:
            raise RuntimeError(
                f"Supabase schema is missing columns required by schema.sql: "
                f"{sorted(missing)}"
            )

    def _check_via_openapi(self) -> set | None:
        """
        Returns set of missing columns, empty set if all present,
        or None if the check itself could not be completed.
        """
        url = f"{self.supabase_url}/rest/v1/"
        try:
            resp = requests.get(url, headers={"apikey": self.supabase_key}, timeout=10)
            if resp.status_code != 200:
                return None
            spec = resp.json()
            definitions = spec.get("definitions", {})
            table_def = definitions.get("memory_log", {})
            actual = set(table_def.get("properties", {}).keys())
            if not actual:
                return None  # No column info — try fallback
            # schema.sql has 'id' as auto column; PostgREST may omit from write defs
            # Check read-relevant columns (everything except 'id' for insert safety)
            check_cols = EXPECTED_COLUMNS - {"id"}
            return check_cols - actual
        except Exception as e:
            print(f"[DB] OpenAPI schema probe failed ({e}); trying select fallback.")
            return None

    def _check_via_select(self) -> set:
        """
        Probe by selecting 0 rows with all expected columns.
        PostgREST returns 400 with the first missing column in the error message.
        Returns set of detected missing columns (may be incomplete — only first error).
        """
        cols = sorted(EXPECTED_COLUMNS)
        url = f"{self.supabase_url}/rest/v1/memory_log"
        params = {"select": ",".join(cols), "limit": "0"}
        try:
            resp = requests.get(url, headers=self._headers, params=params, timeout=10)
            if resp.status_code == 200:
                return set()
            error = resp.json() if resp.content else {}
            msg = error.get("message", resp.text)
            raise RuntimeError(f"Supabase schema validation failed: {msg}")
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Supabase schema validation error: {e}") from e

    # ------------------------------------------------------------------ #
    #  Public interface                                                    #
    # ------------------------------------------------------------------ #

    def fetch_recent_memory(self, limit: int) -> list[dict]:
        """Return the most recent `limit` episodes, newest first."""
        if self._backend == "sqlite":
            cursor = self.conn.execute(
                "SELECT * FROM memory_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

        # Supabase
        url = f"{self.supabase_url}/rest/v1/memory_log"
        params = {
            "select": "*",
            "order": "created_at.desc",
            "limit": str(limit),
        }
        try:
            resp = requests.get(url, headers=self._headers, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            print(f"[DB] fetch_recent_memory failed ({resp.status_code}): {resp.text}")
            return []
        except Exception as e:
            print(f"[DB] fetch_recent_memory error: {e}")
            return []

    def insert_post(self, data: dict) -> dict | None:
        """Insert a new episode row. Returns the inserted row or None on failure."""
        if self._backend == "sqlite":
            columns = list(data.keys())
            placeholders = ", ".join("?" for _ in columns)
            col_str = ", ".join(columns)
            values = [data[c] for c in columns]
            try:
                cursor = self.conn.execute(
                    f"INSERT INTO memory_log ({col_str}) VALUES ({placeholders})",
                    values,
                )
                self.conn.commit()
                row_id = cursor.lastrowid
                row = self.conn.execute(
                    "SELECT * FROM memory_log WHERE id = ?", (row_id,)
                ).fetchone()
                return dict(row) if row else None
            except Exception as e:
                print(f"[DB] insert_post failed: {e}")
                return None

        # Supabase
        url = f"{self.supabase_url}/rest/v1/memory_log"
        try:
            resp = requests.post(
                url, headers=self._headers_return, json=data, timeout=15
            )
            if resp.status_code in (200, 201):
                result = resp.json()
                return result[0] if result else None
            print(f"[DB] insert_post failed ({resp.status_code}): {resp.text}")
            return None
        except Exception as e:
            print(f"[DB] insert_post error: {e}")
            return None

    def delete_old_episodes(self, days_to_keep: int):
        """Delete episodes older than `days_to_keep` days using the created_at index."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

        if self._backend == "sqlite":
            cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
            try:
                self.conn.execute(
                    "DELETE FROM memory_log WHERE created_at < ?", (cutoff_str,)
                )
                self.conn.commit()
                print(f"[DB] Deleted episodes older than {days_to_keep} days.")
            except Exception as e:
                print(f"[DB] delete_old_episodes failed: {e}")
            return

        # Supabase
        cutoff_iso = cutoff.isoformat()
        url = f"{self.supabase_url}/rest/v1/memory_log"
        params = {"created_at": f"lt.{cutoff_iso}"}
        try:
            resp = requests.delete(url, headers=self._headers, params=params, timeout=15)
            if resp.status_code in (200, 204):
                print(f"[DB] Deleted episodes older than {days_to_keep} days.")
            else:
                print(f"[DB] delete_old_episodes failed ({resp.status_code}): {resp.text}")
        except Exception as e:
            print(f"[DB] delete_old_episodes error: {e}")

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
