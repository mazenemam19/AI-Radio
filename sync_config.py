"""
sync_config.py — AI Radio Echo
Writes config.js for the frontend HTML dashboard.

Routing (controlled by --env, never inferred):
  local / prod-models → read SQLite, embed 20 most recent episodes as JS data.
  prod-db / production → write baked episode data from Supabase.

config.json must be listed in .gitignore to avoid data conflicts between environments.
All failures are logged but non-fatal — config sync does not abort the pipeline.
"""

import json
import os
from pathlib import Path

# ── dotenv (optional — CI has no .env file) ───────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_CONFIG_PATH = Path("config.json")
_SQLITE_ENVS: frozenset[str] = frozenset({"local", "prod-models"})
_SUPABASE_ENVS: frozenset[str] = frozenset({"prod-db", "production"})

# No header needed for JSON


def sync_env_to_config(env: str) -> None:
    """
    Write config.json appropriate to the environment.

    Never raises — failures are caught and logged.
    """
    try:
        if env in _SQLITE_ENVS:
            _write_sqlite_config(env)
        elif env in _SUPABASE_ENVS:
            _write_supabase_config(env)
        else:
            print(f"[Config] Unknown env '{env}' — skipping config.js sync.")
    except Exception as exc:
        print(f"[Config] sync_env_to_config failed unexpectedly: {exc}")


def _write_sqlite_config(env: str) -> None:
    """
    Read the 20 most recent episodes from SQLite and embed them as static JS data.
    The frontend reads CONFIG.episodes directly without a network call.
    """
    from db_client import DBClient

    db = DBClient(env)
    episodes = db.fetch_recent_memory(limit=20)

    website_url = os.environ.get("WEBSITE_URL", "http://localhost:8080")

    config = {
        "mode": "local",
        "env": env,
        "website_url": website_url,
        "episodes": episodes,
    }

    _CONFIG_PATH.write_text(json.dumps(config, indent=2, default=str), encoding="utf-8")
    print(
        f"[Config] config.json written (SQLite mode, {len(episodes)} episode(s)) "
        f"→ {_CONFIG_PATH.resolve()}"
    )


def _write_supabase_config(env: str) -> None:
    """
    Connect to Supabase, fetch recent episodes, and bake them into config.json.
    This ensures no credentials are ever exposed to the user's browser.
    """
    from db_client import DBClient
    
    # DBClient automatically pulls URL/KEY from environment
    try:
        db = DBClient(env)
        episodes = db.fetch_recent_memory(limit=20)
    except Exception as exc:
        print(f"[Config] ERROR: Could not fetch from Supabase: {exc}")
        import sys
        sys.exit(1)
    
    website_url = os.environ.get("WEBSITE_URL", "").strip()

    config = {
        "mode": "production",
        "env": env,
        "website_url": website_url,
        "episodes": episodes,
    }

    _CONFIG_PATH.write_text(json.dumps(config, indent=2, default=str), encoding="utf-8")
    print(
        f"[Config] config.json written (Production/Baked mode, {len(episodes)} episode(s)) "
        f"→ {_CONFIG_PATH.resolve()}"
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sync config.js for the dashboard.")
    parser.add_argument(
        "--env",
        choices=["local", "prod-db", "prod-models", "production"],
        default="local",
        help="Environment profile to sync.",
    )
    args = parser.parse_args()

    sync_env_to_config(args.env)
