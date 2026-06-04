#!/usr/bin/env python3
"""
tests/test_audio_engine.py — AI Radio Echo
Verifies voice style processing and SFX mixing logic.
"""

import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# ── Import Fix ────────────────────────────────────────────────────────────────
PROJ_ROOT = Path(__file__).parent.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

# We expect an ImportError if pydub is not installed yet
try:
    from pydub import AudioSegment
except ImportError:
    AudioSegment = None


class TestAudioEngine(unittest.TestCase):
    def setUp(self):
        if AudioSegment is None:
            self.skipTest("pydub not installed.")

    @patch("tts_generator.AudioSegment")
    def test_whisper_processing(self, mock_as):
        """Should apply -8dB gain and reverb to whisper style (Functional Req 1)."""
        mock_audio = MagicMock()
        mock_as.from_file.return_value = mock_audio
        
        # Simulate gain reduction
        mock_audio.__sub__.return_value = mock_audio 
        
        from tts_generator import _apply_audio_processing
        # We assume the function signature based on the spec
        success = _apply_audio_processing("dummy.mp3", "whisper", None, None)
        
        self.assertTrue(success)
        # Verify gain reduction called (-8dB)
        mock_audio.__sub__.assert_called_with(8)
        # Verify reverb overlay (simulated reverb)
        mock_audio.overlay.assert_called()

    @patch("tts_generator.AudioSegment")
    @patch("tts_generator.Path.exists")
    def test_ambient_looping(self, mock_exists, mock_as):
        """Should loop STREET_AMBIENT for the full duration of speech (Functional Req 2)."""
        # Ensure the mixer looks for the right path: sfx/STREET_AMBIENT.mp3
        mock_exists.side_effect = lambda p: "sfx/STREET_AMBIENT.mp3" in str(p).replace("\\", "/")
        
        mock_speech = MagicMock()
        mock_ambient = MagicMock()
        
        mock_speech.__len__.return_value = 10000 # 10s
        mock_ambient.__len__.return_value = 2000  # 2s
        
        # Mocking the * (loop) operator
        mock_loop = MagicMock()
        mock_ambient.__mul__.return_value = mock_loop
        mock_loop.__getitem__.return_value = mock_loop
        
        mock_as.from_file.side_effect = [mock_speech, mock_ambient]
        
        from tts_generator import _apply_audio_processing
        _apply_audio_processing("dummy.mp3", "normal", None, None)
        
        # Verify ambient was looped (multiplied)
        mock_ambient.__mul__.assert_called()
        # Verify ambient was overlaid on speech (or speech on ambient)
        mock_loop.overlay.assert_called()

    @patch("tts_generator.AudioSegment")
    def test_sfx_pre_post(self, mock_as):
        """Should prepend sfx_pre and append sfx_post (Functional Req 2)."""
        mock_speech = MagicMock()
        mock_sfx = MagicMock()
        
        # mock_as.from_file will be called for speech, then potentially SFX
        mock_as.from_file.side_effect = [mock_speech, mock_sfx, mock_sfx]
        
        # Mocking addition (concatenation)
        mock_speech.__add__.return_value = mock_speech
        mock_speech.__radd__.return_value = mock_speech
        
        from tts_generator import _apply_audio_processing
        _apply_audio_processing("dummy.mp3", "normal", "INTRO_THEME", "APPLAUSE_OPEN")
        
        # Verify concatenation was called
        self.assertTrue(mock_speech.__add__.called or mock_speech.__radd__.called)

if __name__ == "__main__":
    unittest.main()
