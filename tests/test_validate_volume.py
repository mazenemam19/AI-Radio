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
            "topic_tags": ["test"],
            "confidence": "high",
            "my_take": "Test editorial.",
            "post_text": "Test post.",
            "related_ids": [],
            "segments": [
                {"speaker": "ALISTAIR", "text": "Word " * 140, "voice_style": "normal", "sfx_pre": None, "sfx_post": None} 
                for _ in range(8)
            ]
        }

    def test_minimum_segments_fail(self):
        """Should fail if less than 8 segments are provided."""
        words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet"]
        for count in range(1, 8):
            with self.subTest(count=count):
                data = self.base_data.copy()
                data["segments"] = [
                    {"speaker": "ALISTAIR", "text": f"{words[i%len(words)]} " * 140, "voice_style": "normal", "sfx_pre": None, "sfx_post": None} 
                    for i in range(count)
                ]
                valid, reason = validate_broadcast(data, "local")
                self.assertFalse(valid, f"Should have failed for {count} segments: {reason}")

    def test_minimum_segments_pass(self):
        """Should pass if 8 or more segments are provided."""
        words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet"]
        for count in range(8, 11):
            with self.subTest(count=count):
                data = self.base_data.copy()
                data["segments"] = [
                    {"speaker": "ALISTAIR", "text": f"{words[i%len(words)]} " * 140, "voice_style": "normal", "sfx_pre": None, "sfx_post": None} 
                    for i in range(count)
                ]
                # Ensure mandatory segments are present to satisfy validation
                data["segments"][len(data["segments"])//2]["speaker"] = "CASPER"
                data["segments"][-1]["speaker"] = "MARCUS"
                
                valid, reason = validate_broadcast(data, "local")
                self.assertTrue(valid, f"Should have passed for {count} segments: {reason}")

if __name__ == "__main__":
    unittest.main()
