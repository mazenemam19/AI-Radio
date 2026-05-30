"""
tests/integration_suite.py — AI Radio Echo
Full integration test: runs `python main.py --env local --dry-run`.
Requirements: FFmpeg, edge-tts. Zero API keys needed.
Verifies:
  1. Exit code 0
  2. Output MP4 exists in output/
  3. Output MP4 size > 100 KB
  4. NO DB row inserted (dry-run skips DB write)
Exit 0 if all pass, exit 1 if any fail.
"""

import glob
import os
import sqlite3
import subprocess
import sys
import time

# Locate repo root (one level up from tests/)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_PASS = "  ✔ PASS"
_FAIL = "  ✗ FAIL"

_DB_PATH = os.path.join(_REPO_ROOT, "ai_radio_dev.db")


def _header(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_db_row_count() -> int:
    """Return current row count in memory_log (0 if DB doesn't exist yet)."""
    if not os.path.exists(_DB_PATH):
        return 0
    try:
        conn = sqlite3.connect(_DB_PATH)
        cur  = conn.execute("SELECT COUNT(*) FROM memory_log")
        count = cur.fetchone()[0]
        conn.close()
        return count
    except sqlite3.OperationalError:
        return 0


def _find_output_mp4(after_time: float) -> str | None:
    """Return path of the newest MP4 in output/ created after `after_time`."""
    pattern = os.path.join(_REPO_ROOT, "output", "*.mp4")
    candidates = [
        p for p in glob.glob(pattern)
        if os.path.getmtime(p) > after_time
    ]
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_exit_code(result: subprocess.CompletedProcess) -> bool:
    _header("Test 1 — Exit Code 0")
    ok = result.returncode == 0
    if not ok:
        print(f"    Exit code: {result.returncode}")
        # Print last 40 lines of combined output for diagnostics
        lines = (result.stdout + result.stderr).splitlines()
        for line in lines[-40:]:
            print(f"    │ {line}")
    else:
        print(f"    Exit code: {result.returncode}")
    print(_PASS if ok else _FAIL)
    return ok


def test_mp4_exists(after_time: float) -> tuple[bool, str | None]:
    _header("Test 2 — MP4 File Exists in output/")
    mp4_path = _find_output_mp4(after_time)
    ok = mp4_path is not None
    if ok:
        print(f"    Found: {mp4_path}")
    else:
        print("    No MP4 file found in output/ created during this run.")
    print(_PASS if ok else _FAIL)
    return ok, mp4_path


def test_mp4_size(mp4_path: str | None) -> bool:
    _header("Test 3 — MP4 Size > 100 KB")
    if mp4_path is None:
        print("    MP4 path not available (prior test failed).")
        print(_FAIL)
        return False
    size = os.path.getsize(mp4_path)
    ok   = size > 100 * 1024
    print(f"    File size: {size:,} bytes ({size / 1024:.1f} KB)")
    print(_PASS if ok else _FAIL)
    return ok


def test_no_db_write(rows_before: int) -> bool:
    _header("Test 4 — No DB Row Inserted (dry-run)")
    rows_after = _get_db_row_count()
    ok = rows_after == rows_before
    print(f"    Rows before: {rows_before}  │  Rows after: {rows_after}")
    if not ok:
        print(f"    ✗ {rows_after - rows_before} unexpected row(s) were inserted!")
    print(_PASS if ok else _FAIL)
    return ok


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    print("\n╔══════════════════════════════════════════════════╗")
    print("║   AI Radio — Echo  ·  Integration Test Suite    ║")
    print("╚══════════════════════════════════════════════════╝")
    print(f"\n  Working directory  : {_REPO_ROOT}")
    print(f"  Python interpreter : {sys.executable}")

    # Snapshot state before run
    rows_before = _get_db_row_count()
    print(f"  DB rows before run : {rows_before}")
    start_time  = time.time()

    # Run the pipeline
    print(f"\n  Running: python main.py --env local --dry-run")
    print(f"  {'─' * 50}")
    result = subprocess.run(
        [sys.executable, "main.py", "--env", "local", "--dry-run"],
        cwd=_REPO_ROOT,
        capture_output=False,   # Let output stream to terminal for visibility
        timeout=300,
    )
    # Re-run with capture for diagnostics in test_exit_code if it failed
    if result.returncode != 0:
        result = subprocess.run(
            [sys.executable, "main.py", "--env", "local", "--dry-run"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )

    # Run tests
    ok1         = test_exit_code(result)
    ok2, mp4    = test_mp4_exists(after_time=start_time)
    ok3         = test_mp4_size(mp4)
    ok4         = test_no_db_write(rows_before)

    elapsed = time.time() - start_time

    # Summary
    results = {"exit_code": ok1, "mp4_exists": ok2, "mp4_size": ok3, "no_db_write": ok4}
    print(f"\n{'═' * 60}")
    print("  SUMMARY")
    print(f"{'═' * 60}")
    all_passed = True
    for name, passed in results.items():
        icon = "✔" if passed else "✗"
        print(f"  {icon}  {name:<20}  {'PASS' if passed else 'FAIL'}")
        if not passed:
            all_passed = False
    print(f"{'═' * 60}")
    print(f"  Elapsed: {elapsed:.1f}s")

    if all_passed:
        print("  All integration tests passed.\n")
        sys.exit(0)
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"  {len(failed)} test(s) FAILED: {', '.join(failed)}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
