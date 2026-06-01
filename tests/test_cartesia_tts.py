#!/usr/bin/env python3
"""
tests/test_cartesia_tts.py — AI Radio Echo
Verifies the Cartesia Sonic TTS implementation.
"""

import sys
import unittest
import tempfile
import shutil
import os
from unittest.mock import patch, MagicMock
from pathlib import Path

# ── Import Fix ────────────────────────────────────────────────────────────────
PROJ_ROOT = Path(__file__).parent.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

import tts_generator

class TestCartesiaTTS(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.output_path = os.path.join(self.test_dir, "test_output.wav")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch("requests.post")
    def test_run_cartesia_tts_success(self, mock_post):
        """Should return True and write file on successful API call."""
        # Use a real WAV header mock if you want it to be "playable", 
        # but for unit testing, any bytes will prove the write logic.
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xAC\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        mock_post.return_value = mock_response
        
        with patch.dict("os.environ", {"CARTESIA_API_KEY": "fake-key"}):
            success = tts_generator._run_cartesia_tts("Hello", "ANCHOR", self.output_path)
            self.assertTrue(success)
            self.assertTrue(os.path.exists(self.output_path))
            
    def test_run_cartesia_tts_no_key(self):
        """Should return False if API key is missing."""
        with patch.dict("os.environ", {"CARTESIA_API_KEY": ""}):
            success = tts_generator._run_cartesia_tts("Hello", "ANCHOR", self.output_path)
            self.assertFalse(success)

if __name__ == "__main__":
    unittest.main()
