#!/usr/bin/env python3
"""
sync_engagement.py — AI Radio Echo
Standalone script to synchronize YouTube engagement metrics with Supabase.
Used by the manual GitHub Action trigger.
"""

import sys
from pathlib import Path

# Add project root to path
PROJ_ROOT = Path(__file__).parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

try:
    from db_client import DBClient
    from publisher import sync_engagement_stats
    from dotenv import load_dotenv
    load_dotenv()
except ImportError as exc:
    print(f"[Error] Missing dependencies: {exc}")
    sys.exit(1)

def main():
    print("=== MANUAL ENGAGEMENT SYNC START ===")
    try:
        # We always target production for the live dashboard stats
        db = DBClient("production")
        sync_engagement_stats(db)
        print("=== MANUAL ENGAGEMENT SYNC COMPLETE ===")
    except Exception as exc:
        print(f"[Fatal] Engagement sync failed: {exc}")
        sys.exit(1)

if __name__ == "__main__":
    main()
