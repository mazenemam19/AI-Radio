"""
db_client.py — Unified database interface for AI Radio Echo.

SQLite is used for envs: local, prod-models
Supabase is used for envs: prod-db, production

The public interface is identical regardless of backend.
"""

import os
import sqlite3
import json
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
