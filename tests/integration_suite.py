#!/usr/bin/env python3
"""
tests/integration_suite.py — AI Radio Echo
Full dry-run integration test. Requires: FFmpeg + edge-tts. Zero API keys needed.

Tests (in order):
  1. Run: python main.py --env local --dry-run → exit code must be 0.
  2. An MP4 file exists in output/ that was created during this run.
  3. That MP4 file is larger than 100 KB.
  4. SQLite row count is unchanged from before the run (dry-run skips DB write).

Exit 0 = all pass.
Exit 1 = one or more failures.
"""

import sqlite3
import subprocess
import sys
import time
from pathlib import Path

PROJ_ROOT = Path(__file__).parent.parent
MAIN_PY = PROJ_ROOT / "main.py"
OUTPUT_DIR = PROJ_ROOT / "output"
DB_PATH = PROJ_ROOT / "ai_radio_dev.db"
MIN_MP4_SIZE = 100 * 1024  # 100 KB

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


def _db_row_count() -> int:
    """Return current row count in memory_log, or 0 if DB / table doesn't exist."""
    if not DB_PATH.exists():
        return 0
    try:
        conn = sqlite3.connect(str(DB_PATH))
        count = conn.execute("SELECT COUNT(*) FROM memory_log").fetchone()[0]
        conn.close()
        return count
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        return 0


def run() -> None:
    print("=" * 60)
    print("  AI Radio Echo — Integration Suite")
    print(f"  Project root: {PROJ_ROOT}")
    print("=" * 60)

    # ── Record pre-run state ──────────────────────────────────────────────────
    rows_before = _db_row_count()
    run_start = time.time()
    print(f"\n[Pre-run] DB rows: {rows_before}")
    print("[Pre-run] Starting pipeline (--env local --dry-run)...\n")

    # ── Test 1: Run main.py --env local --dry-run ─────────────────────────────
    result = subprocess.run(
        [sys.executable, str(MAIN_PY), "--env", "local", "--dry-run"],
        cwd=str(PROJ_ROOT),
        capture_output=False,   # stream stdout/stderr live for visibility
    )
    run_end = time.time()
    elapsed = run_end - run_start
    print(f"\n[Post-run] Elapsed: {elapsed:.1f}s | Exit code: {result.returncode}")

    if result.returncode == 0:
        _ok("Exit code 0", f"elapsed={elapsed:.1f}s")
    else:
        _fail("Exit code 0", f"got exit code {result.returncode}")
        # Still run remaining checks so the user sees the full picture
        print("  (Continuing remaining checks despite non-zero exit...)\n")

    # ── Test 2: MP4 file exists in output/ ───────────────────────────────────
    OUTPUT_DIR.mkdir(exist_ok=True)
    new_mp4s = sorted(
        [
            f for f in OUTPUT_DIR.glob("*.mp4")
            if f.stat().st_mtime >= run_start
        ],
        key=lambda f: f.stat().st_mtime,
    )

    if new_mp4s:
        newest = new_mp4s[-1]
        _ok("MP4 exists in output/", newest.name)
    else:
        _fail("MP4 exists in output/", "no .mp4 file created during this run")
        newest = None

    # ── Test 5: Cover image exists in output/ ────────────────────────────────
    new_covers = sorted(
        [
            f for f in OUTPUT_DIR.glob("*.png")
            if f.stat().st_mtime >= run_start
        ],
        key=lambda f: f.stat().st_mtime,
    )
    if new_covers:
        _ok("Cover PNG exists in output/", new_covers[-1].name)
    else:
        _fail("Cover PNG exists in output/", "no .png file created during this run")

    # ── Test 3: MP4 size > 100 KB ─────────────────────────────────────────────
    if newest is not None:
        size = newest.stat().st_size
        if size > MIN_MP4_SIZE:
            _ok("MP4 size > 100 KB", f"{size:,} bytes ({size // 1024} KB)")
        else:
            _fail("MP4 size > 100 KB", f"only {size:,} bytes")
    else:
        _fail("MP4 size > 100 KB", "skipped — no MP4 file found")

    # ── Test 4: No DB row inserted ────────────────────────────────────────────
    rows_after = _db_row_count()
    if rows_after == rows_before:
        _ok("No DB row inserted", f"count unchanged at {rows_before}")
    else:
        _fail(
            "No DB row inserted",
            f"count changed: {rows_before} → {rows_after} "
            f"(dry-run must not write to DB)",
        )

    # ── Summary ───────────────────────────────────────────────────────────────
    total = len(_passed) + len(_failed)
    print("\n" + "=" * 60)
    print(f"  Results: {len(_passed)}/{total} passed", end="")
    if _failed:
        print(f"  |  FAILED: {', '.join(_failed)}", end="")
    print("\n" + "=" * 60)

    sys.exit(0 if not _failed else 1)


if __name__ == "__main__":
    run()
