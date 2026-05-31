"""
tests/measure_baseline.py — Measure current performance metrics from the database.
Calculates average duration, segment count, and words-per-segment over recent runs.
"""

import sys
import json
from pathlib import Path

# ── Import Fix ────────────────────────────────────────────────────────────────
PROJ_ROOT = Path(__file__).parent.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

from db_client import DBClient

def measure(limit: int = 10):
    print(f"\n[MEASURE] Auditing last {limit} episodes...")
    db = DBClient("local")
    episodes = db.fetch_recent_memory(limit=limit)
    
    if not episodes:
        print("[MEASURE] No data found.")
        return

    total_dur = 0
    total_segs = 0
    total_words = 0
    valid_count = 0

    for ep in episodes:
        # Skip dry-run stubs or failed entries
        if ep.get("broadcast_duration", 0) == 0:
            continue
        
        script = ep.get("audio_script")
        if not script:
            continue
            
        try:
            segments = json.loads(script)
        except:
            continue

        valid_count += 1
        total_dur += ep["broadcast_duration"]
        total_segs += len(segments)
        
        for s in segments:
            # Handle list of strings or list of dicts
            text = s["text"] if isinstance(s, dict) else s
            total_words += len(text.split())

    if valid_count == 0:
        print("[MEASURE] No valid production episodes found to measure.")
        return

    avg_dur = total_dur / valid_count
    avg_segs = total_segs / valid_count
    avg_words_per_seg = total_words / total_segs
    avg_words_per_ep = total_words / valid_count

    print(f"\n[RESULTS] Based on {valid_count} recent run(s):")
    print(f"  - Avg Duration:         {avg_dur:.1f}s")
    print(f"  - Avg Segments:         {avg_segs:.1f}")
    print(f"  - Avg Words/Segment:    {avg_words_per_seg:.1f}")
    print(f"  - Avg Total Words:      {avg_words_per_ep:.1f}")
    
    # Target for 600s
    words_needed = 1500
    deficit = max(0, words_needed - avg_words_per_ep)
    print(f"\n[TARGET] Goal: 600s (~{words_needed} words)")
    print(f"  - Current Deficit:      {deficit:.1f} words (~{deficit/avg_words_per_seg:.1f} segments)")

if __name__ == "__main__":
    measure()
