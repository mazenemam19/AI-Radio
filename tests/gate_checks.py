"""
tests/gate_checks.py — Automated Self-Assessment Gates for AI Radio Echo.

This script compares the latest database entry against the Run 74 baseline.
Exit code 0: All gates passed.
Exit code 1: Regression detected.

Special handling: On first run with empty database, gates are skipped gracefully.
"""

import sys
from pathlib import Path

# ── Import Fix ────────────────────────────────────────────────────────────────
PROJ_ROOT = Path(__file__).parent.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

from db_client import DBClient  # noqa: E402

# ── Baseline Constants ────────────────────────────────────────────────────────
BASELINE_DURATION = 420
REQUIRED_METADATA_FIELDS = [
    "confidence",
    "summary",
    "my_take",
    "post_text",
    "topic_tags",
    "audio_url",
    "video_url",
    "writer_model",
    "narrator_model",
]


def check_latest_run(env: str = "local"):
    print(f"\n[GATE] Starting self-assessment (env={env})...")

    try:
        db = DBClient(env)
    except Exception as e:
        print(f"[GATE] FAILURE: Could not initialise DB: {e}")
        return False

    recent = db.fetch_recent_memory(limit=1)
    if not recent:
        print("[GATE] SKIP: Database is empty. First run detected — gates skipped.")
        return True

    run = recent[0]
    run_id = run.get("id", "?")
    print(f"[GATE] Checking Run ID: {run_id} ('{run.get('headline', 'Untitled')}')")

    errors = []

    # 1. Duration Gate
    duration = run.get("broadcast_duration", 0)
    if duration < BASELINE_DURATION:
        errors.append(
            f"Duration regression: {duration}s (Baseline: {BASELINE_DURATION}s)"
        )

    # 2. Metadata Integrity Gate
    for field in REQUIRED_METADATA_FIELDS:
        val = run.get(field)

        # Standard Null/Empty check
        is_empty = val is None or val == "" or val == [] or val == "[]"

        # Exception: 'related_ids' can be empty in a fresh or small database.
        if field == "related_ids" and is_empty:
            continue

        if is_empty:
            errors.append(f"Metadata missing: '{field}' is empty or NULL.")

        # Specific check for dynamic values (not just defaults)
        if field == "confidence" and val not in ("high", "medium", "low"):
            errors.append(f"Metadata invalid: 'confidence' has weird value: {val}")

    # 3. Report Results
    if errors:
        print(f"\n[GATE] ❌ REGRESSION DETECTED in Run {run_id}:")
        for err in errors:
            print(f"  - {err}")
        return False

    print(f"[GATE] ✅ SUCCESS: Run {run_id} passed all baseline checks.")
    return True


if __name__ == "__main__":
    # Default to local unless env provided
    env = sys.argv[1] if len(sys.argv) > 1 else "local"
    success = check_latest_run(env)
    sys.exit(0 if success else 1)
