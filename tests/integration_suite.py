import os
import sys
import subprocess
import shutil
import json
import re
import glob
from dotenv import load_dotenv

# Ensure we can import from parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# ── Quality Thresholds ────────────────────────────────────────────────────────
# These are strict for integration testing
MIN_BROADCAST_DURATION = 700   # 11.6 minutes

def run_test(title, func):
    print(f"\n[INTEGRATION] Run: {title}...")
    try:
        success = func()
        if success:
            print(f"[INTEGRATION] SUCCESS: {title}")
            return True
        else:
            print(f"[INTEGRATION] FAILURE: {title}")
            return False
    except Exception as e:
        print(f"[INTEGRATION] ERROR: {title} raised an exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_pipeline_dry_run():
    """
    EXTREMELY HEAVY: Runs the full production pipeline in dry-run mode.
    Validates end-to-end connectivity, AI script generation, TTS rendering, 
    and FFmpeg compilation.
    """
    print("[Integration] Spawning full pipeline dry-run (env: local) ...")
    files_before = set(glob.glob("output/broadcast_*.mp3"))

    # Force --env local to save Groq 70B tokens while still testing the full flow
    # This also tests that main.py now correctly exits non-zero on failure.
    cmd = [sys.executable, "main.py", "--dry-run", "--env", "local"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    print("\n--- Pipeline Output ---")
    print(result.stdout)
    if result.stderr:
        print("--- Pipeline Errors ---")
        print(result.stderr)
    print("------------------------\n")

    # Real check: main.py MUST exit 0 for this to pass
    if result.returncode != 0:
        print(f"[Integration] FAILURE: Pipeline exited with error code {result.returncode}.")
        return False

    # Assert artifacts were created
    files_after = set(glob.glob("output/broadcast_*.mp3"))
    new_files = files_after - files_before
    if not new_files:
        print("[Integration] FAILURE: No artifacts generated.")
        return False

    # Assert duration was correct
    duration_match = re.search(r'Broadcast duration:\s*([\d.]+)\s*seconds', result.stdout)
    if not duration_match:
        print("[Integration] FAILURE: No duration reported.")
        return False

    duration = float(duration_match.group(1))
    if duration < MIN_BROADCAST_DURATION:
        # Note: In local mode, the 1177s emergency script might be triggered
        # if Gemini Flash is being brief. 1177s > 700s, so it passes.
        print(f"[Integration] FAILURE: Duration {duration}s below prod threshold {MIN_BROADCAST_DURATION}s.")
        return False

    return True

if __name__ == "__main__":
    print("\n=========================================")
    print("[HEAVY INTEGRATION SUITE]")
    print("=========================================\n")

    results = []
    results.append(run_test("End-to-End Pipeline Dry-Run (Heavy)", test_pipeline_dry_run))

    if not all(results):
        print("\n[Integration] SUITE FAILED.")
        sys.exit(1)
    else:
        print("\n[Integration] SUITE PASSED.")
        sys.exit(0)
