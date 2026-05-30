"""
db_client.py — AI Radio Echo
Database abstraction layer.
  - SQLite backend: local, prod-models
  - Supabase backend: prod-db, production
Public interface is identical regardless of backend.
"""

import json
import mimetypes
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")

SUPABASE_ENVS = {"prod-db", "production"}
SQLITE_ENVS   = {"local", "prod-models"}

_SCHEMA_COLUMNS_CACHE: set[str] | None = None


def _parse_schema_columns() -> set[str]:
    """Parse column names from schema.sql CREATE TABLE block."""
    global _SCHEMA_COLUMNS_CACHE
    if _SCHEMA_COLUMNS_CACHE is not None:
        return _SCHEMA_COLUMNS_CACHE

    with open(SCHEMA_PATH, "r") as fh:
        sql = fh.read()

    match = re.search(
        r"CREATE TABLE IF NOT EXISTS memory_log\s*\((.*?)\);",
        sql,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        raise RuntimeError("Could not parse CREATE TABLE from schema.sql")

    columns: set[str] = set()
    for raw_line in match.group(1).strip().splitlines():
        line = raw_line.strip().rstrip(",")
        if not line:
            continue
        first_token = line.split()[0].upper()
        # Skip constraint keywords and SQL comments
        if first_token in ("PRIMARY", "UNIQUE", "CHECK", "FOREIGN", "CONSTRAINT", "--"):
            continue
        if line.startswith("--"):
            continue
        col_name = line.split()[0]
        if col_name:
            columns.add(col_name)

    _SCHEMA_COLUMNS_CACHE = columns
    return columns


class DBClient:
    """Unified database interface for SQLite and Supabase."""

    def __init__(self, env: str):
        if env not in SUPABASE_ENVS | SQLITE_ENVS:
            raise ValueError(f"Unknown env '{env}'. Must be one of: local, prod-models, prod-db, production")
        self.env = env
        self._use_supabase = env in SUPABASE_ENVS

        if self._use_supabase:
            self._init_supabase()
        else:
            self._init_sqlite()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_sqlite(self):
        self._db_path = "ai_radio_dev.db"
        with open(SCHEMA_PATH, "r") as fh:
            schema_sql = fh.read()
        conn = sqlite3.connect(self._db_path)
        conn.executescript(schema_sql)
        conn.commit()
        conn.close()
        print(f"[DB] SQLite initialised: {self._db_path}")

    def _init_supabase(self):
        supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        supabase_key = os.environ.get("SUPABASE_KEY", "")
        if not supabase_url or not supabase_key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_KEY must be set for env='prod-db' or 'production'."
            )
        self._supabase_url = supabase_url
        self._headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
        }
        self._validate_supabase_columns()
        print(f"[DB] Supabase initialised: {supabase_url}")

    def _validate_supabase_columns(self):
        """Raise RuntimeError if any schema.sql column is missing in Supabase."""
        import requests

        expected = _parse_schema_columns()
        try:
            resp = requests.get(
                f"{self._supabase_url}/rest/v1/",
                headers={**self._headers, "Accept": "application/openapi+json"},
                timeout=15,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Cannot reach Supabase for schema validation: {exc}") from exc

        if resp.status_code != 200:
            raise RuntimeError(
                f"Supabase schema validation request failed: {resp.status_code} {resp.text[:200]}"
            )

        try:
            spec = resp.json()
            props = (
                spec.get("definitions", {})
                    .get("memory_log", {})
                    .get("properties", {})
            )
            actual = set(props.keys())
        except (json.JSONDecodeError, AttributeError) as exc:
            print(f"[DB] Warning: Could not parse Supabase OpenAPI spec for column validation: {exc}")
            return

        missing = expected - actual
        if missing:
            raise RuntimeError(
                f"Supabase table 'memory_log' is missing columns defined in schema.sql: "
                f"{', '.join(sorted(missing))}"
            )
        print(f"[DB] Supabase schema validation passed ({len(actual)} columns found).")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def fetch_recent_memory(self, limit: int = 20) -> list[dict]:
        """Return up to `limit` most recent episodes, newest first."""
        if self._use_supabase:
            return self._supabase_fetch_recent(limit)
        return self._sqlite_fetch_recent(limit)

    def insert_post(self, data: dict) -> dict | None:
        """Insert a new episode row. Returns the inserted row or None on failure."""
        if self._use_supabase:
            return self._supabase_insert(data)
        return self._sqlite_insert(data)

    def delete_old_episodes(self, days_to_keep: int):
        """Delete episodes older than `days_to_keep` days."""
        cutoff = (datetime.utcnow() - timedelta(days=days_to_keep)).isoformat()
        if self._use_supabase:
            self._supabase_delete_old(cutoff)
        else:
            self._sqlite_delete_old(cutoff)

    # ------------------------------------------------------------------
    # SQLite implementations
    # ------------------------------------------------------------------

    def _sqlite_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _sqlite_fetch_recent(self, limit: int) -> list[dict]:
        conn = self._sqlite_conn()
        try:
            cur = conn.execute(
                "SELECT * FROM memory_log ORDER BY created_at DESC LIMIT ?", (limit,)
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def _sqlite_insert(self, data: dict) -> dict | None:
        # Serialise list/dict values to JSON strings for SQLite text affinity
        safe_data = {
            k: (json.dumps(v) if isinstance(v, (list, dict)) else v)
            for k, v in data.items()
        }
        cols = ", ".join(safe_data.keys())
        placeholders = ", ".join(["?" for _ in safe_data])
        vals = list(safe_data.values())

        conn = self._sqlite_conn()
        try:
            cur = conn.execute(
                f"INSERT INTO memory_log ({cols}) VALUES ({placeholders})", vals
            )
            conn.commit()
            row_id = cur.lastrowid
            row = conn.execute(
                "SELECT * FROM memory_log WHERE id = ?", (row_id,)
            ).fetchone()
            return dict(row) if row else None
        except sqlite3.Error as exc:
            print(f"[DB] SQLite insert error: {exc}")
            return None
        finally:
            conn.close()

    def _sqlite_delete_old(self, cutoff_iso: str):
        conn = self._sqlite_conn()
        try:
            cur = conn.execute(
                "DELETE FROM memory_log WHERE created_at < ?", (cutoff_iso,)
            )
            conn.commit()
            print(f"[DB] Deleted {cur.rowcount} old SQLite episodes (cutoff: {cutoff_iso}).")
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Supabase implementations
    # ------------------------------------------------------------------

    def _supabase_fetch_recent(self, limit: int) -> list[dict]:
        import requests

        resp = requests.get(
            f"{self._supabase_url}/rest/v1/memory_log",
            headers=self._headers,
            params={"select": "*", "order": "created_at.desc", "limit": str(limit)},
            timeout=20,
        )
        if resp.status_code != 200:
            print(f"[DB] Supabase fetch error: {resp.status_code} {resp.text[:200]}")
            return []
        return resp.json()

    def _supabase_insert(self, data: dict) -> dict | None:
        import requests

        resp = requests.post(
            f"{self._supabase_url}/rest/v1/memory_log",
            headers={**self._headers, "Prefer": "return=representation"},
            json=data,
            timeout=20,
        )
        if resp.status_code not in (200, 201):
            print(f"[DB] Supabase insert error: {resp.status_code} {resp.text[:200]}")
            return None
        result = resp.json()
        return result[0] if result else None

    def _supabase_delete_old(self, cutoff_iso: str):
        import requests

        resp = requests.delete(
            f"{self._supabase_url}/rest/v1/memory_log",
            headers=self._headers,
            params={"created_at": f"lt.{cutoff_iso}"},
            timeout=20,
        )
        if resp.status_code not in (200, 204):
            print(f"[DB] Supabase delete error: {resp.status_code} {resp.text[:200]}")
        else:
            print(f"[DB] Supabase old episodes deleted (cutoff: {cutoff_iso}).")

    def upload_file(self, local_path: str, bucket: str = "broadcasts") -> str | None:
        """
        Upload a file to Supabase Storage (if in Supabase mode) or return
        a local reference URI (if in SQLite mode).

        Returns:
            The public URL or local:// URI string, or None on failure.
        """
        from pathlib import Path
        p = Path(local_path)
        if not p.exists():
            print(f"[DB] upload_file failed: {local_path} does not exist.")
            return None

        if not self._use_supabase:
            # Return a 'local://' URI that the dashboard frontend can recognize.
            return f"local://{p.name}"

        # Supabase Storage
        file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{p.name}"
        url = f"{self._supabase_url}/storage/v1/object/{bucket}/{file_name}"

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
                public_url = f"{self._supabase_url}/storage/v1/object/public/{bucket}/{file_name}"
                print(f"[DB] Uploaded to Supabase Storage: {public_url}")
                return public_url

            print(f"[DB] Supabase upload failed ({resp.status_code}): {resp.text}")
            return None
        except Exception as e:
            print(f"[DB] upload_file error: {e}")
            return None
