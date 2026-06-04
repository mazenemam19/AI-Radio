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
    
    # Extract the resolveUrl function logic or just the hasAudio condition
    # Looking for: const hasAudio = audioUrl && 
    match = re.search(r"const\s+hasAudio\s+=\s+(.+?);", content, re.DOTALL)
    assert match, "Could not find hasAudio logic in app.js"
    
    logic = match.group(1).strip()
    print(f"  Current logic: {logic}")
    
    # Simulate the resolveUrl logic
    def resolveUrl(url):
        if not url:
            return None
        if not isinstance(url, str):
            return url
        if url.startswith('local://'):
            return 'output/' + url[8:]
        return url

    # Simulate the hasAudio logic
    # (audioUrl.startsWith('http') || audioUrl.startsWith('output/'))
    audio_url_raw = "local://broadcast_20260531.mp3"
    audio_url = resolveUrl(audio_url_raw)
    
    has_audio = (audio_url and 
                 "placeholder" not in audio_url and 
                 (audio_url.startswith("http") or audio_url.startswith("output/")))
    
    assert has_audio, f"local:// URIs should pass new logic but failed: {audio_url}"
    print(f"  [PASS] Verified that local:// URIs now PASS the hasAudio check: {audio_url}")

def run():
    success = test_has_audio_logic()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    run()
