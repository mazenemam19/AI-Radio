"""
tests/test_validate_volume.py — TDD for Volume Pressure logic.
Verifies that validate_broadcast enforces the new 12-14 segment requirement with 100-word floor.
"""

import unittest
import copy
from ai_client import validate_broadcast

class TestVolumeValidation(unittest.TestCase):
    def setUp(self):
        words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet", "kilo", "lima", "mike", "november"]
        self.base_data = {
            "title": "Test Episode",
            "summary": "This is a comprehensive summary of the test episode that meets the thirty word requirement for validation purposes in the high fidelity production pipeline of echo fm radio station. Extra words added here.",
            "topic_tags": ["test"],
            "confidence": "high",
            "my_take": "Test editorial.",
            "post_text": "Test post.",
            "related_ids": [],
            "segments": [
                {
                    "speaker": "ALISTAIR",
                    "text": f"{words[i]} " * 135,
                    "voice_style": "normal",
                    "sfx_pre": None,
                    "sfx_post": None,
                    "word_count": 135
                } 
                for i in range(13)
            ]
        }
        # Ensure mandatory segments are present to satisfy validation
        self.base_data["segments"][6]["speaker"] = "CASPER"
        self.base_data["segments"][-1]["speaker"] = "MARCUS"

    def test_minimum_segments_fail(self):
        """Should fail if less than 12 segments are provided."""
        for count in range(1, 12):
            with self.subTest(count=count):
                data = copy.deepcopy(self.base_data)
                data["segments"] = data["segments"][:count]
                valid, reason = validate_broadcast(data, "local")
                self.assertFalse(valid, f"Should have failed for {count} segments: {reason}")

    def test_minimum_segments_pass(self):
        """Should pass if 12 or more segments are provided."""
        for count in range(12, 14):
            with self.subTest(count=count):
                data = copy.deepcopy(self.base_data)
                data["segments"] = data["segments"][:count]
                # Re-assign Marcus to final slot
                for seg in data["segments"]:
                    if seg["speaker"] == "MARCUS":
                        seg["speaker"] = "ALISTAIR"
                data["segments"][-1]["speaker"] = "MARCUS"
                
                valid, reason = validate_broadcast(data, "local")
                self.assertTrue(valid, f"Should have passed for {count} segments: {reason}")

    def test_word_floor_fail(self):
        """Should fail if any segment is below 100 words."""
        data = copy.deepcopy(self.base_data)
        data["segments"][0]["text"] = "Too short"
        data["segments"][0]["word_count"] = 2
        valid, reason = validate_broadcast(data, "production")
        self.assertFalse(valid)
        self.assertIn("need ≥ 100", reason)

if __name__ == "__main__":
    unittest.main()
