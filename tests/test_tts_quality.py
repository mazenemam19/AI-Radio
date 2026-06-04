#!/usr/bin/env python3
"""
tests/test_tts_quality.py — AI Radio Echo
Directly tests the TTS Quality Guard logic (WPM check).
"""

import sys
import unittest
import tempfile
import shutil
import os
from unittest.mock import patch
from pathlib import Path

# ── Import Fix ────────────────────────────────────────────────────────────────
PROJ_ROOT = Path(__file__).parent.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

import tts_generator # noqa: E402

class TestTTSQualityGuard(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.fake_path = os.path.join(self.test_dir, "quality_test.wav")
        # Write a dummy file so exists() and size checks pass
        with open(self.fake_path, "wb") as f:
            f.write(b"RIFF" + b"X" * 200) # dummy wav content

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch("tts_generator._get_audio_duration")
    def test_audio_valid_normal_speed(self, mock_duration):
        """130 words in 60s (~130 WPM) should be VALID."""
        mock_duration.return_value = 60.0
        is_valid = tts_generator._is_audio_valid(self.fake_path, 130)
        self.assertTrue(is_valid)

    @patch("tts_generator._get_audio_duration")
    def test_audio_invalid_too_fast(self, mock_duration):
        """130 words in 10s (~780 WPM) should be INVALID."""
        mock_duration.return_value = 10.0
        is_valid = tts_generator._is_audio_valid(self.fake_path, 130)
        self.assertFalse(is_valid)

    @patch("tts_generator._get_audio_duration")
    def test_audio_valid_borderline(self, mock_duration):
        """300 WPM exactly should be VALID (threshold is > 300)."""
        # 100 words in 20s = 300 WPM
        mock_duration.return_value = 20.0
        is_valid = tts_generator._is_audio_valid(self.fake_path, 100)
        self.assertTrue(is_valid)

    def test_audio_invalid_missing_file(self):
        """Missing file should be INVALID."""
        is_valid = tts_generator._is_audio_valid("non_existent.wav", 130)
        self.assertFalse(is_valid)

    def test_audio_invalid_zero_byte(self):
        """Zero-byte file should be INVALID."""
        zero_path = os.path.join(self.test_dir, "zero.wav")
        with open(zero_path, "wb") as _:
            pass
        is_valid = tts_generator._is_audio_valid(zero_path, 130)
        self.assertFalse(is_valid)

if __name__ == "__main__":
    unittest.main()
