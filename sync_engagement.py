#!/usr/bin/env python3
"""
sync_engagement.py — AI Radio Echo
Standalone script to synchronize YouTube engagement metrics with the database.
"""

import argparse
import os
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
    load_dotenv(override=True)
except ImportError as exc:
    print(f"[Error] Missing dependencies: {exc}")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Manual Engagement Sync")
    parser.add_argument(
        "--env",
        choices=["local", "production", "prod-db", "prod-models"],
        default="local",
        help="Environment to sync (default: local)",
    )
    args = parser.parse_args()

    print(f"=== MANUAL ENGAGEMENT SYNC START ({args.env}) ===")
    try:
        db = DBClient(args.env)
        sync_engagement_stats(db)
        print(f"=== MANUAL ENGAGEMENT SYNC COMPLETE ({args.env}) ===")
    except Exception as exc:
        print(f"[Fatal] Engagement sync failed: {exc}")
        sys.exit(1)

if __name__ == "__main__":
    main()
