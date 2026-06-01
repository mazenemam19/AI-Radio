#!/usr/bin/env python3
"""
tests/test_sync_config.py — AI Radio Echo
Tests for sync_config.py.
"""

import os
import subprocess
import sys
import json
from pathlib import Path

PROJ_ROOT = Path(__file__).parent.parent
SYNC_CONFIG_PY = PROJ_ROOT / "sync_config.py"
CONFIG_JSON = PROJ_ROOT / "config.json"

_passed: list[str] = []
_failed: list[str] = []


def _ok(label: str, detail: str = "") -> None:
    msg = f"  [PASS] {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    _passed.append(label)


def _fail(label: str, detail: str = "") -> None:
    msg = f"  [FAIL] {label}"
    if detail:
        msg += f" — {detail}"
    print(msg, file=sys.stderr)
    _failed.append(label)


def run() -> None:
    print("=" * 60)
    print("  AI Radio Echo — Sync Config Test")
    print(f"  Project root: {PROJ_ROOT}")
    print("=" * 60)

    # Backup existing config.json if it exists
    backup = None
    if CONFIG_JSON.exists():
        backup = CONFIG_JSON.read_text(encoding="utf-8")

    try:
        # Test 1: local mode
        print("\n[Test] Running sync_config.py --env local...")
        if CONFIG_JSON.exists(): CONFIG_JSON.unlink()
        subprocess.run([sys.executable, str(SYNC_CONFIG_PY), "--env", "local"], cwd=str(PROJ_ROOT), check=True)
        if CONFIG_JSON.exists():
            data = json.loads(CONFIG_JSON.read_text(encoding="utf-8"))
            if data.get("mode") == "local":
                _ok("Local config generated correctly")
            else:
                _fail("Local config mode mismatch", str(data))
        else:
            _fail("config.json not created for local mode")

        # Test 2: production mode (requires env vars)
        print("\n[Test] Running sync_config.py --env production...")
        if CONFIG_JSON.exists(): CONFIG_JSON.unlink()
        # Note: In the new 'Static Bake' mode, production sync requires Supabase credentials 
        # to be set in the environment so it can fetch episodes.
        env = os.environ.copy()
        env["SUPABASE_URL"] = "https://example.supabase.co"
        env["SUPABASE_KEY"] = "fake-key"
        
        # We expect this to fail if the key is fake, so we mock the fetch or just check the call.
        result = subprocess.run([sys.executable, str(SYNC_CONFIG_PY), "--env", "production"], 
                              cwd=str(PROJ_ROOT), capture_output=True, text=True, env=env)
        
        if CONFIG_JSON.exists():
            data = json.loads(CONFIG_JSON.read_text(encoding="utf-8"))
            if data.get("mode") == "production":
                _ok("Production config generated correctly")
            else:
                _fail("Production config mode mismatch", str(data))
        else:
            # If it failed because of fake key, that's expected but we should verify the attempt.
            if "ERROR: Could not fetch from Supabase" in result.stdout:
                _ok("Production sync attempted and failed securely (expected)")
            else:
                _fail("config.json not created for production mode", result.stdout)

    finally:
        # Restore backup
        if backup is not None:
            CONFIG_JSON.write_text(backup, encoding="utf-8")
        elif CONFIG_JSON.exists():
            CONFIG_JSON.unlink()

    # Summary
    total = len(_passed) + len(_failed)
    print("\n" + "=" * 60)
    print(f"  Results: {len(_passed)}/{total} passed", end="")
    if _failed:
        print(f"  |  FAILED: {', '.join(_failed)}", end="")
    print("\n" + "=" * 60)

    sys.exit(0 if not _failed else 1)


if __name__ == "__main__":
    run()
