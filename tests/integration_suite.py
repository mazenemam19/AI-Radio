"""
tests/integration_suite.py — AI Radio Echo
Full dry-run integration test.
Requires: FFmpeg + edge-tts installed. Zero API keys needed.

Tests:
  1. Run pipeline with --env local --dry-run, verify exit code 0.
  2. Verify output MP4 file exists in output/.
  3. Verify output MP4 size > 100 KB.
  4. Verify no DB row was inserted (dry-run skips DB write).

Exit 0 if all pass, exit 1 if any fail.
"""

import sqlite3
import subprocess
import sys
from pathlib import Path

# Resolve project root (parent of tests/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run_pipeline() -> subprocess.CompletedProcess:
    """Execute the pipeline in dry-run mode and return the result."""
    return subprocess.run(
        [sys.executable, "main.py", "--env", "local", "--dry-run"],
        capture_output=True,
        text=True,
        cwd=str(_PROJECT_ROOT),
    )


# ------------------------------------------------------------------ #
#  Tests                                                              #
# ------------------------------------------------------------------ #

def test_exit_code(result: subprocess.CompletedProcess) -> bool:
    print("\n[Test 1] Pipeline exit code must be 0")
    if result.returncode == 0:
        print("[Test 1] PASS — exit code 0")
        return True
    print(f"[Test 1] FAIL — exit code {result.returncode}")
    print("--- STDOUT (last 2000 chars) ---")
    print(result.stdout[-2000:])
    print("--- STDERR (last 500 chars) ---")
    print(result.stderr[-500:])
    return False


def test_mp4_exists() -> bool:
    print("\n[Test 2] Output MP4 must exist in output/")
    output_dir = _PROJECT_ROOT / "output"
    mp4_files  = sorted(output_dir.glob("episode_*.mp4"), key=lambda f: f.stat().st_mtime)

    if not mp4_files:
        print(f"[Test 2] FAIL — no episode_*.mp4 found in {output_dir}")
        return False

    latest = mp4_files[-1]
    print(f"[Test 2] PASS — found {latest.name}")
    return True


def test_mp4_size() -> bool:
    print("\n[Test 3] Output MP4 must be > 100 KB")
    output_dir = _PROJECT_ROOT / "output"
    mp4_files  = sorted(output_dir.glob("episode_*.mp4"), key=lambda f: f.stat().st_mtime)

    if not mp4_files:
        print("[Test 3] FAIL — no episode_*.mp4 found (Test 2 may have failed)")
        return False

    latest = mp4_files[-1]
    size   = latest.stat().st_size
    limit  = 100 * 1024  # 100 KB

    if size > limit:
        print(f"[Test 3] PASS — {latest.name} is {size:,} bytes (> 100 KB)")
        return True

    print(f"[Test 3] FAIL — {latest.name} is only {size:,} bytes (must be > 100 KB)")
    return False


def test_no_db_write(initial_count: int) -> bool:
    print("\n[Test 4] Dry-run must NOT insert any DB rows")
    db_path = _PROJECT_ROOT / "ai_radio_dev.db"

    if not db_path.exists():
        print("[Test 4] PASS — DB file not created (expected for dry-run)")
        return True

    try:
        conn  = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM memory_log").fetchone()[0]
        conn.close()
    except Exception as exc:
        print(f"[Test 4] FAIL — could not query DB: {exc}")
        return False

    if count == initial_count:
        print(f"[Test 4] PASS — memory_log count unchanged at {count}")
        return True

    print(f"[Test 4] FAIL — memory_log has {count} rows; expected {initial_count}")
    return False


# ------------------------------------------------------------------ #
#  Runner                                                             #
# ------------------------------------------------------------------ #

def main() -> None:
    print("=" * 60)
    print("  AI Radio — Echo  |  Integration Test Suite")
    print("=" * 60)
    print("\nRunning: python main.py --env local --dry-run …")

    # Get initial count
    initial_count = 0
    db_path = _PROJECT_ROOT / "ai_radio_dev.db"
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        initial_count = conn.execute("SELECT COUNT(*) FROM memory_log").fetchone()[0]
        conn.close()

    result = _run_pipeline()

    results = {
        "exit_code":    test_exit_code(result),
        "mp4_exists":   test_mp4_exists(),
        "mp4_size":     test_mp4_size(),
        "no_db_write":  test_no_db_write(initial_count),
    }

    print("\n" + "=" * 60)
    print("  Integration Test Summary")
    print("=" * 60)
    all_pass = True
    for name, ok in results.items():
        status = "PASS ✓" if ok else "FAIL ✗"
        print(f"  {name:<16} {status}")
        if not ok:
            all_pass = False
    print("=" * 60)

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
