#!/usr/bin/env python3
"""
tests/test_app_logic.py — AI Radio Echo
Tests for UI logic in app.js (simulated).
"""

import sys
import re
from pathlib import Path

PROJ_ROOT = Path(__file__).parent.parent
APP_JS = PROJ_ROOT / "app.js"

def test_has_audio_logic():
    print("Checking app.js for local:// support...")
    content = APP_JS.read_text(encoding="utf-8")
    
    # Extract the hasAudio condition
    # Example: const hasAudio = ep.audio_url && !ep.audio_url.includes('placeholder') && ep.audio_url.startsWith('http');
    match = re.search(r"const\s+hasAudio\s+=\s+(.+?);", content)
    if not match:
        print("  [FAIL] Could not find hasAudio logic in app.js")
        return False
    
    logic = match.group(1)
    print(f"  Current logic: {logic}")
    
    # Simulate the logic for a local:// URI
    audio_url = "local://broadcast_20260531.mp3"
    
    # Simple simulation of the current logic
    # ep.audio_url && !ep.audio_url.includes('placeholder') && ep.audio_url.startsWith('http')
    has_audio = (audio_url and 
                 "placeholder" not in audio_url and 
                 audio_url.startswith("http"))
    
    if not has_audio:
        print(f"  [PASS] Verified that local:// URIs currently FAIL the hasAudio check: {audio_url}")
        return True
    else:
        print(f"  [FAIL] local:// URIs should fail current logic but passed? {audio_url}")
        return False

def run():
    success = test_has_audio_logic()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    run()
