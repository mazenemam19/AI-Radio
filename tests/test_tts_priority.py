#!/usr/bin/env python3
"""
tests/test_tts_priority.py — AI Radio Echo
Verifies the TTS engine priority: Cartesia -> Kokoro -> Edge-TTS.
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

    @patch("tts_generator._run_cartesia_tts")
    @patch("tts_generator._run_kokoro_tts")
    @patch("tts_generator._run_edge_tts")
    @patch("tts_generator._is_audio_valid")
    def test_priority_fallthrough(self, mock_valid, mock_edge, mock_kokoro, mock_cartesia):
        """Should try Cartesia, then Kokoro, then Edge-TTS."""
        # Scenario: Cartesia fails, Kokoro succeeds
        mock_cartesia.return_value = False
        mock_kokoro.return_value = True
        mock_valid.return_value = True
        
        success, engine = tts_generator.generate_segment_audio("Test", "ANCHOR", self.output_path, use_cloud=True)
        
        self.assertTrue(success)
        self.assertEqual(engine, "kokoro-cloud")
        mock_cartesia.assert_called_once()
        mock_kokoro.assert_called_once()
        mock_edge.assert_not_called()

    @patch("tts_generator._run_cartesia_tts")
    @patch("tts_generator._run_kokoro_tts")
    @patch("tts_generator._run_edge_tts")
    @patch("tts_generator._is_audio_valid")
    def test_full_fallback(self, mock_valid, mock_edge, mock_kokoro, mock_cartesia):
        """Should fall all the way to Edge-TTS if premium fails."""
        mock_cartesia.return_value = False
        mock_kokoro.return_value = False
        mock_edge.return_value = True
        mock_valid.return_value = True
        
        success, engine = tts_generator.generate_segment_audio("Test", "ANCHOR", self.output_path, use_cloud=True)
        
        self.assertTrue(success)
        self.assertEqual(engine, "edge-tts")
        mock_cartesia.assert_called_once()
        mock_kokoro.assert_called_once()
        mock_edge.assert_called_once()

    @patch("tts_generator._run_cartesia_tts")
    @patch("tts_generator._run_kokoro_tts")
    @patch("tts_generator._run_edge_tts")
    @patch("tts_generator._is_audio_valid")
    def test_quality_failure_triggers_fallback(self, mock_valid, mock_edge, mock_kokoro, mock_cartesia):
        """Should fallback if an engine succeeds but its output is invalid (too short)."""
        # Scenario: Cartesia succeeds writing a file, but Quality Guard REJECTS it.
        mock_cartesia.return_value = True
        mock_valid.side_effect = [False, True] # False for Cartesia, True for Kokoro
        mock_kokoro.return_value = True
        
        success, engine = tts_generator.generate_segment_audio("Test words", "ANCHOR", self.output_path, use_cloud=True)
        
        self.assertTrue(success)
        self.assertEqual(engine, "kokoro-cloud") # Should have moved past Cartesia
        mock_cartesia.assert_called_once()
        mock_kokoro.assert_called_once()

if __name__ == "__main__":
    unittest.main()
