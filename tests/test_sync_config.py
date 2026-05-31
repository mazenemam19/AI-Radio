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
CONFIG_JS = PROJ_ROOT / "config.js"

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

    # Backup existing config.js if it exists
    backup = None
    if CONFIG_JS.exists():
        backup = CONFIG_JS.read_text(encoding="utf-8")

    try:
        # Test 1: local mode
        print("\n[Test] Running sync_config.py --env local...")
        subprocess.run([sys.executable, str(SYNC_CONFIG_PY), "--env", "local"], cwd=str(PROJ_ROOT), check=True)
        if CONFIG_JS.exists():
            content = CONFIG_JS.read_text(encoding="utf-8")
            if "window.CONFIG =" in content and '"mode": "local"' in content:
                _ok("Local config generated correctly")
            else:
                _fail("Local config format mismatch", content[:100])
        else:
            _fail("config.js not created for local mode")

        # Test 2: production mode (requires env vars)
        print("\n[Test] Running sync_config.py --env production...")
        env = os.environ.copy()
        env["SUPABASE_URL"] = "https://example.supabase.co"
        env["SUPABASE_KEY"] = "fake-key"
        subprocess.run([sys.executable, str(SYNC_CONFIG_PY), "--env", "production"], cwd=str(PROJ_ROOT), check=True, env=env)
        if CONFIG_JS.exists():
            content = CONFIG_JS.read_text(encoding="utf-8")
            if "window.CONFIG =" in content and '"mode": "production"' in content and "example.supabase.co" in content:
                _ok("Production config generated correctly")
            else:
                _fail("Production config format mismatch", content[:100])
        else:
            _fail("config.js not created for production mode")

    finally:
        # Restore backup
        if backup is not None:
            CONFIG_JS.write_text(backup, encoding="utf-8")
        elif CONFIG_JS.exists():
            CONFIG_JS.unlink()

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
