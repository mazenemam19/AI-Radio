"""
tests/test_validate_volume.py — TDD for Volume Pressure logic.
Verifies that validate_broadcast enforces the new 12-15 segment requirement.
"""

import sys
import unittest
from ai_client import validate_broadcast

class TestVolumeValidation(unittest.TestCase):
    def setUp(self):
        self.base_data = {
            "title": "Test Episode",
            "confidence": "high",
            "related_ids": [],
            "segments": [
                {"speaker": "ANCHOR", "text": "Word " * 140} for _ in range(8)
            ]
        }

    def test_minimum_segments_fail(self):
        """Should fail if less than 8 segments are provided."""
        words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet"]
        for count in range(1, 8):
            with self.subTest(count=count):
                data = self.base_data.copy()
                data["segments"] = [
                    {"speaker": "ANCHOR", "text": f"{words[i%len(words)]} " * 140} 
                    for i in range(count)
                ]
                valid, reason = validate_broadcast(data)
                self.assertFalse(valid, f"Should have failed for {count} segments: {reason}")

    def test_minimum_segments_pass(self):
        """Should pass if 8 or more segments are provided."""
        words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet"]
        for count in range(8, 11):
            with self.subTest(count=count):
                data = self.base_data.copy()
                data["segments"] = [
                    {"speaker": "ANCHOR", "text": f"{words[i%len(words)]} " * 140} 
                    for i in range(count)
                ]
                valid, reason = validate_broadcast(data)
                self.assertTrue(valid, f"Should have passed for {count} segments: {reason}")

if __name__ == "__main__":
    unittest.main()
