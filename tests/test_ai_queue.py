#!/usr/bin/env python3
"""
tests/test_ai_queue.py — AI Radio Echo
Verifies the End-Game AI model queue configuration.
"""

import sys
import unittest
from pathlib import Path

# ── Import Fix ────────────────────────────────────────────────────────────────
PROJ_ROOT = Path(__file__).parent.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

import ai_client

class TestAIQueue(unittest.TestCase):
    def test_production_queue(self):
        """Set A should have the 5-tier end-game queue in correct order."""
        expected = [
            "deepseek-r1-distill-llama-70b",
            "llama-3.3-70b-versatile",
            "llama-4-scout-17b-instruct",
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite"
        ]
        self.assertEqual(ai_client.MODEL_SET_A, expected)

    def test_local_queue(self):
        """Set B should mirror the production fallback (Gemini 3.5 -> 3.1)."""
        expected = [
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite"
        ]
        self.assertEqual(ai_client.MODEL_SET_B, expected)

if __name__ == "__main__":
    unittest.main()
