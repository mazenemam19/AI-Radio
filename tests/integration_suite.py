"""
tests/integration_suite.py — Full dry-run integration test.

Requirements:
  - FFmpeg installed
  - edge-tts installed
  - Zero API keys required

Checks:
  1. Run: python main.py --env local --dry-run  →  exit code 0
  2. Output MP4 exists in output/
  3. Output MP4 size > 100 KB
  4. No row was inserted into SQLite (dry-run must skip DB write)

Exit 0 if all checks pass. Exit 1 if any fail.
"""

import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Resolve project root (parent of this file's directory)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
MAIN_SCRIPT  = PROJECT_ROOT / "main.py"


def _find_latest_mp4(output_dir: Path) -> "Path | None":
    """Return the most recently modified .mp4 in output_dir, or None."""
    mp4s = sorted(output_dir.glob("episode_*.mp4"), key=lambda p: p.stat().st_mtime)
    return mp4s[-1] if mp4s else None


def check_exit_code(result: subprocess.CompletedProcess) -> bool:
    if result.returncode != 0:
        print(f"[Check 1] FAILED — exit code {result.returncode}")
        print("--- stdout ---")
        print(result.stdout[-2000:] if result.stdout else "(empty)")
        print("--- stderr ---")
        print(result.stderr[-2000:] if result.stderr else "(empty)")
        return False
    print("[Check 1] PASSED — exit code 0")
    return True


def check_mp4_exists(output_dir: Path, run_start: float) -> "tuple[bool, Path | None]":
    mp4 = _find_latest_mp4(output_dir)
    if mp4 is None:
        print("[Check 2] FAILED — no episode_*.mp4 found in output/")
        return False, None
    # Verify it was created after this run started
    if mp4.stat().st_mtime < run_start:
        print(f"[Check 2] FAILED — newest MP4 ({mp4.name}) pre-dates this run.")
        return False, None
    print(f"[Check 2] PASSED — {mp4.name} exists")
    return True, mp4


def check_mp4_size(mp4: Path) -> bool:
    size = mp4.stat().st_size
    if size <= 100 * 1024:
        print(f"[Check 3] FAILED — MP4 size {size:,} bytes is not > 100 KB")
        return False
    print(f"[Check 3] PASSED — {size:,} bytes")
    return True


def check_no_db_row(db_path: Path, run_start: float) -> bool:
    """
    Verify that dry-run did NOT insert any row into the SQLite DB.
    We check whether any row has a created_at timestamp after run_start.
    """
    if not db_path.exists():
        # DB file was never created — that's fine; no insert happened.
        print("[Check 4] PASSED — DB file not created (no insert)")
        return True

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        # Count rows added at or after the run started
        # SQLite CURRENT_TIMESTAMP stores UTC without timezone
        import datetime
        cutoff = datetime.datetime.utcfromtimestamp(run_start).strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.execute(
            "SELECT COUNT(*) as cnt FROM memory_log WHERE created_at >= ?", (cutoff,)
        )
        row_count = cur.fetchone()["cnt"]
        conn.close()

        if row_count > 0:
            print(
                f"[Check 4] FAILED — {row_count} row(s) were inserted during dry-run "
                "(DB write should be skipped)."
            )
            return False
        print("[Check 4] PASSED — no rows inserted during dry-run")
        return True

    except Exception as exc:
        print(f"[Check 4] ERROR — could not query DB: {exc}")
        return False


def main():
    print("=" * 60)
    print("AI Radio Echo — Integration Test Suite")
    print("Command: python main.py --env local --dry-run")
    print("=" * 60)

    # Run the pipeline inside a temp working directory so it doesn't
    # pollute the project tree with test artifacts.
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path    = Path(tmpdir)
        output_dir  = tmp_path / "output"
        assets_dir  = tmp_path / "assets"
        db_path     = tmp_path / "ai_radio_dev.db"

        # Copy required project files into temp dir
        required_files = [
            "main.py",
            "db_client.py",
            "news_fetcher.py",
            "ai_client.py",
            "tts_generator.py",
            "publisher.py",
            "sync_config.py",
            "schema.sql",
        ]
        for fname in required_files:
            src = PROJECT_ROOT / fname
            if not src.exists():
                print(f"[Setup] FAILED — required file not found: {src}")
                sys.exit(1)
            import shutil
            shutil.copy(str(src), str(tmp_path / fname))

        run_start = time.time()

        cmd = [
            sys.executable,
            str(tmp_path / "main.py"),
            "--env", "local",
            "--dry-run",
        ]

        print(f"\nRunning: {' '.join(cmd)}\n")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        )

        print("--- Pipeline output ---")
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("[stderr]", result.stderr[-1000:])
        print("--- End output ---\n")

        # --- Run all checks independently ---
        c1 = check_exit_code(result)
        c2, mp4_path = check_mp4_exists(tmp_path / "output", run_start)
        c3 = check_mp4_size(mp4_path) if mp4_path else False
        c4 = check_no_db_row(db_path, run_start)

        print("\n" + "=" * 60)
        print("RESULTS SUMMARY")
        print("=" * 60)
        checks = {
            "Exit code 0":          c1,
            "MP4 exists":           c2,
            "MP4 size > 100 KB":    c3,
            "No DB row (dry-run)":  c4,
        }
        all_passed = True
        for name, passed in checks.items():
            status = "PASS" if passed else "FAIL"
            print(f"  {status}  {name}")
            if not passed:
                all_passed = False

        if all_passed:
            print("\nAll integration checks passed.")
            sys.exit(0)
        else:
            print("\nOne or more integration checks failed.")
            sys.exit(1)


if __name__ == "__main__":
    main()
