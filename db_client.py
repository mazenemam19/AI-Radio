"""
db_client.py — AI Radio Echo
Unified database client.

Backend routing (set exclusively by --env flag):
  local       → SQLite  (ai_radio_dev.db)
  prod-models → SQLite  (ai_radio_dev.db)
  prod-db     → Supabase REST API  (production project)
  production  → Supabase REST API  (production project)

Public interface is identical across all backends.
"""

import json
import mimetypes
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# ── Environment routing ───────────────────────────────────────────────────────

SQLITE_ENVS: frozenset[str] = frozenset({"local", "prod-models"})
SUPABASE_ENVS: frozenset[str] = frozenset({"prod-db", "production"})

# Fields that hold lists in the logical schema.
# SQLite stores them as JSON strings; Supabase stores them as native TEXT.
_LIST_FIELDS: tuple[str, ...] = ("topic_tags", "related_ids")

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


# ── Schema introspection ──────────────────────────────────────────────────────

def _parse_schema_columns(schema_sql: str) -> set[str]:
    """
    Extract the set of column names declared in the CREATE TABLE block.

    Rules:
    - Non-greedy match captures content between `memory_log (` and `);`
    - Lines that start with SQL structural keywords (PRIMARY, UNIQUE …) are skipped.
    - Inline comments (`-- …`) are ignored because we only take `line.split()[0]`.

    Raises RuntimeError if the CREATE TABLE block cannot be found.
    """
    match = re.search(
        r"CREATE TABLE IF NOT EXISTS memory_log\s*\((.+?)\);",
        schema_sql,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        raise RuntimeError("[DB] Could not locate 'memory_log' CREATE TABLE in schema.sql")

    _SKIP_KEYWORDS = frozenset(
        {"PRIMARY", "UNIQUE", "CHECK", "FOREIGN", "CONSTRAINT", "INDEX", "CREATE"}
    )

    columns: set[str] = set()
    for raw_line in match.group(1).splitlines():
        # Strip leading/trailing whitespace and any leading comma from the raw line
        line = raw_line.strip().lstrip(",").strip()
        if not line or line.startswith("--"):
            continue
        first_token = line.split()[0].upper()
        if first_token in _SKIP_KEYWORDS:
            continue
        # Column name is always the first token before the type declaration
        columns.add(line.split()[0])

    return columns


# ── DBClient ──────────────────────────────────────────────────────────────────

class DBClient:
    """
    Unified database interface for AI Radio — Echo.

    Usage:
        db = DBClient("local")
        rows = db.fetch_recent_memory(limit=5)
        inserted = db.insert_post({...})
        db.delete_old_episodes(days_to_keep=30)
    """

    def __init__(self, env: str) -> None:
        if env not in SQLITE_ENVS | SUPABASE_ENVS:
            raise ValueError(
                f"[DB] Unknown environment: '{env}'. "
                f"Valid values: {sorted(SQLITE_ENVS | SUPABASE_ENVS)}"
            )
        self.env = env

        if env in SQLITE_ENVS:
            self._init_sqlite()
        else:
            self._init_supabase()

    # ── SQLite backend ────────────────────────────────────────────────────────

    def _init_sqlite(self) -> None:
        """
        Open (or create) ai_radio_dev.db and apply schema.sql.
        schema.sql is the single source of truth — no inline DDL here.
        """
        db_path = Path(__file__).parent / "ai_radio_dev.db"
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        # executescript runs the full file; both CREATE TABLE and CREATE INDEX
        # are idempotent via IF NOT EXISTS.
        self._conn.executescript(schema_sql)
        self._conn.commit()
        print(f"[DB] SQLite ready → {db_path.resolve()}")

    def _sqlite_row_to_dict(self, row: sqlite3.Row) -> dict:
        """Convert a Row to a plain dict; deserialise JSON-encoded list fields."""
        d = dict(row)
        for field in _LIST_FIELDS:
            raw = d.get(field)
            if isinstance(raw, str):
                try:
                    d[field] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    d[field] = []
            elif raw is None:
                d[field] = []
        return d

    def _prepare_for_sqlite(self, data: dict) -> dict:
        """Serialise list fields to JSON strings before inserting into SQLite."""
        payload = dict(data)
        for field in _LIST_FIELDS:
            val = payload.get(field)
            if isinstance(val, (list, tuple)):
                payload[field] = json.dumps(val)
        return payload

    # ── Supabase backend ──────────────────────────────────────────────────────

    def _init_supabase(self) -> None:
        """
        Initialise the Supabase client and validate the live table schema.
        Raises RuntimeError immediately if credentials are missing or the
        table schema does not match schema.sql.
        """
        url = os.environ.get("SUPABASE_URL", "").strip()
        key = os.environ.get("SUPABASE_KEY", "").strip()

        if not url or not key:
            raise RuntimeError(
                f"[DB] SUPABASE_URL and SUPABASE_KEY must be set "
                f"for environment '{self.env}'."
            )

        try:
            from supabase import create_client
        except ImportError as exc:
            raise RuntimeError(
                "[DB] 'supabase' package is not installed. "
                "Run: pip install supabase"
            ) from exc

        self._sb = create_client(url, key)
        self._supabase_url = url
        self._supabase_key = key
        self._validate_supabase_schema()
        print(f"[DB] Supabase ready → {url}")

    def _validate_supabase_schema(self) -> None:
        """
        Fetch the PostgREST OpenAPI spec and confirm that every column defined
        in schema.sql exists in the live 'memory_log' table.

        Supports both OpenAPI 2.x ('definitions') and 3.x ('components/schemas').

        Raises RuntimeError listing all missing column names.
        Does NOT silently degrade or mock — a schema mismatch is a hard error.
        """
        import requests  # already a dep via news_fetcher; safe to import here

        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        expected = _parse_schema_columns(schema_sql)

        headers = {
            "apikey": self._supabase_key,
            "Authorization": f"Bearer {self._supabase_key}",
        }
        try:
            resp = requests.get(
                f"{self._supabase_url}/rest/v1/",
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
        except Exception as exc:
            raise RuntimeError(
                f"[DB] Cannot reach Supabase to validate schema: {exc}"
            ) from exc

        openapi = resp.json()

        # PostgREST OpenAPI 2.x uses 'definitions'; 3.x uses 'components/schemas'
        table_def = openapi.get("definitions", {}).get("memory_log") or (
            openapi.get("components", {}).get("schemas", {}).get("memory_log")
        )
        if not table_def:
            raise RuntimeError(
                "[DB] Table 'memory_log' was not found in the Supabase OpenAPI spec. "
                "Create the table before starting the pipeline."
            )

        actual = set(table_def.get("properties", {}).keys())
        missing = expected - actual
        if missing:
            raise RuntimeError(
                f"[DB] Supabase 'memory_log' is missing "
                f"{len(missing)} column(s): {', '.join(sorted(missing))}"
            )

    # ── Public interface ──────────────────────────────────────────────────────

    def fetch_recent_memory(self, limit: int = 20) -> list[dict]:
        """
        Return up to `limit` most recent episodes, ordered newest-first.
        Returns an empty list (never None) on any error.
        """
        if self.env in SQLITE_ENVS:
            try:
                cursor = self._conn.execute(
                    "SELECT * FROM memory_log ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
                return [self._sqlite_row_to_dict(r) for r in cursor.fetchall()]
            except Exception as exc:
                print(f"[DB] fetch_recent_memory failed (SQLite): {exc}")
                return []
        else:
            try:
                resp = (
                    self._sb.table("memory_log")
                    .select("*")
                    .order("created_at", desc=True)
                    .limit(limit)
                    .execute()
                )
                return resp.data or []
            except Exception as exc:
                print(f"[DB] fetch_recent_memory failed (Supabase): {exc}")
                return []

    def insert_post(self, data: dict) -> Optional[dict]:
        """
        Insert one episode row.

        Returns the inserted row as a dict on success, or None on failure.
        Never raises — all exceptions are caught, logged, and None is returned.
        The caller must check the return value; None means the write did not happen.
        """
        if self.env in SQLITE_ENVS:
            payload = self._prepare_for_sqlite(data)
            cols = ", ".join(payload.keys())
            placeholders = ", ".join("?" * len(payload))
            try:
                cursor = self._conn.execute(
                    f"INSERT INTO memory_log ({cols}) VALUES ({placeholders})",
                    list(payload.values()),
                )
                self._conn.commit()
                row = self._conn.execute(
                    "SELECT * FROM memory_log WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
                return self._sqlite_row_to_dict(row) if row else None
            except Exception as exc:
                print(f"[DB] insert_post failed (SQLite): {exc}")
                return None
        else:
            try:
                resp = self._sb.table("memory_log").insert(data).execute()
                return resp.data[0] if resp.data else None
            except Exception as exc:
                print(f"[DB] insert_post failed (Supabase): {exc}")
                return None

    def delete_old_episodes(self, days_to_keep: int) -> None:
        """
        Delete all episodes whose `created_at` is older than `days_to_keep` days.
        Logs failures but does not raise — a failed cleanup is non-fatal.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        cutoff_iso = cutoff.isoformat()

        if self.env in SQLITE_ENVS:
            try:
                self._conn.execute(
                    "DELETE FROM memory_log WHERE created_at < ?", (cutoff_iso,)
                )
                self._conn.commit()
                print(f"[DB] Pruned episodes older than {days_to_keep} day(s) from SQLite.")
            except Exception as exc:
                print(f"[DB] delete_old_episodes failed (SQLite): {exc}")
        else:
            try:
                self._sb.table("memory_log").delete().lt(
                    "created_at", cutoff_iso
                ).execute()
                print(f"[DB] Pruned Supabase episodes older than {days_to_keep} day(s).")
            except Exception as exc:
                print(f"[DB] delete_old_episodes failed (Supabase): {exc}")

    def upload_file(self, local_path: Path) -> Optional[str]:
        """
        Register a file artifact.
        
        Logic:
          - Local/Prod-Models: Returns 'local://' URI.
          - Production/Prod-DB: 
            - Video: Usually handled by YouTube URL in main.py.
            - Audio: Returns 'placeholder' (Supabase Storage is disabled).
        """
        if not local_path.exists():
            print(f"[DB] upload_file failed: {local_path} does not exist.")
            return None

        # Base case: return local URI for local/dev envs
        if self.env in SQLITE_ENVS:
            return f"local://{local_path.name}"

        # Production/Cloud DB case
        # We no longer use Supabase buckets (workaround for free-tier limits).
        # Videos are stored on YouTube; Audio is not currently cloud-hosted.
        is_audio = local_path.suffix.lower() in (".mp3", ".wav", ".ogg")
        
        if is_audio:
            print(f"[DB] Audio upload skipped (env={self.env}) — using placeholder.")
            return "placeholder"
        else:
            # For non-audio (like images or video fallbacks), we return local URI
            # so the system doesn't break, though YouTube should be used for video.
            return f"local://{local_path.name}"
