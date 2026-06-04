"""
tests/test_healer_volume.py — Verify JSON Healer with large Volume Pressure outputs.
Tests if the healer can salvage a 15-segment JSON that is truncated mid-segment.
"""

import json
import unittest
from ai_client import heal_truncated_json

class TestHealerVolume(unittest.TestCase):
    def test_heal_large_truncated_json(self):
        """Should salvage valid segments from a 15-segment truncated response."""
        # Create a large valid JSON with 15 segments
        data = {
            "title": "Large Test",
            "confidence": "high",
            "related_ids": [],
            "segments": [
                {"speaker": "ANCHOR", "text": f"This is segment {i} with enough words to be realistic... " * 10}
                for i in range(15)
            ]
        }
        full_json = json.dumps(data)
        
        # Truncate mid-segment 12
        # Segment 12 starts around index... let's just cut at 80% length
        truncated_json = full_json[:int(len(full_json) * 0.8)]
        
        print(f"\n[HEAL] Full length: {len(full_json)}")
        print(f"[HEAL] Truncated length: {len(truncated_json)}")
        
        healed = heal_truncated_json(truncated_json)
        
        self.assertIsNotNone(healed, "Healer failed to salvage truncated JSON")
        self.assertIn("segments", healed)
        
        segs = healed["segments"]
        print(f"[HEAL] Salvaged {len(segs)} segments out of 15.")
        
        self.assertGreaterEqual(len(segs), 1, "Healer should have salvaged at least one segment")
        
        # Verify it's still valid JSON
        json.loads(json.dumps(healed))

if __name__ == "__main__":
    unittest.main()
