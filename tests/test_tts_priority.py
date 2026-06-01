#!/usr/bin/env python3
"""
tests/test_tts_priority.py — AI Radio Echo
Verifies the TTS engine priority: Groq -> Cartesia -> Edge-TTS.
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

class TestTTSPriority(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.output_path = os.path.join(self.test_dir, "path.wav")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch("tts_generator._run_groq_tts")
    @patch("tts_generator._run_cartesia_tts")
    @patch("tts_generator._run_edge_tts")
    def test_priority_fallthrough(self, mock_edge, mock_cartesia, mock_groq):
        """Should try Groq, then Cartesia, then Edge-TTS."""
        # Scenario: Groq fails, Cartesia succeeds
        mock_groq.return_value = False
        mock_cartesia.return_value = True
        
        success, engine = tts_generator.generate_segment_audio("Test", "ANCHOR", self.output_path, use_cloud=True)
        
        self.assertTrue(success)
        self.assertEqual(engine, "cartesia-sonic")
        mock_groq.assert_called_once()
        mock_cartesia.assert_called_once()
        mock_edge.assert_not_called()

    @patch("tts_generator._run_groq_tts")
    @patch("tts_generator._run_cartesia_tts")
    @patch("tts_generator._run_edge_tts")
    def test_full_fallback(self, mock_edge, mock_cartesia, mock_groq):
        """Should fall all the way to Edge-TTS if premium fails."""
        mock_groq.return_value = False
        mock_cartesia.return_value = False
        mock_edge.return_value = True
        
        success, engine = tts_generator.generate_segment_audio("Test", "ANCHOR", self.output_path, use_cloud=True)
        
        self.assertTrue(success)
        self.assertEqual(engine, "edge-tts")
        mock_groq.assert_called_once()
        mock_cartesia.assert_called_once()
        mock_edge.assert_called_once()

if __name__ == "__main__":
    unittest.main()
