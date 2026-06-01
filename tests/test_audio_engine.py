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

import tts_generator

class TestAudioEngine(unittest.TestCase):
    def setUp(self):
        if AudioSegment is None:
            self.skipTest("pydub not installed.")

    @patch("tts_generator.AudioSegment")
    def test_whisper_processing(self, mock_as):
        """Should apply -8dB gain and reverb to whisper style (Functional Req 1)."""
        mock_audio = MagicMock()
        mock_as.from_file.return_value = mock_audio
        
        # pydub gain adjustment is __sub__
        mock_audio.__sub__.return_value = mock_audio 
        
        from tts_generator import _apply_audio_processing
        _apply_audio_processing("dummy.mp3", "whisper", None, None)
        
        # Verify gain reduction called (-8dB)
        # It's called as speech - 8
        mock_audio.__sub__.assert_any_call(8)

    @patch("tts_generator.AudioSegment")
    @patch("tts_generator.Path.exists")
    def test_ambient_looping(self, mock_exists, mock_as):
        """Should loop STREET_AMBIENT for the full duration of speech (Functional Req 2)."""
        # Ensure it finds the ambient file
        mock_exists.return_value = True
        
        mock_speech = MagicMock()
        mock_ambient = MagicMock()
        
        # AudioSegment works in milliseconds
        mock_speech.__len__.return_value = 10000 
        mock_ambient.__len__.return_value = 2000  
        
        # pydub operators return new segments
        mock_loop = MagicMock()
        mock_ambient.__mul__.return_value = mock_loop
        mock_loop.__getitem__.return_value = mock_loop
        mock_loop.__sub__.return_value = mock_loop
        mock_loop.overlay.return_value = mock_loop
        
        mock_as.from_file.side_effect = [mock_speech, mock_ambient]
        
        from tts_generator import _apply_audio_processing
        _apply_audio_processing("dummy.mp3", "normal", None, None)
        
        # Verify ambient was looped
        mock_ambient.__mul__.assert_called()
        # Verify ambient was overlaid
        mock_loop.overlay.assert_called()

    @patch("tts_generator.AudioSegment")
    @patch("tts_generator.Path.exists")
    def test_sfx_pre_post(self, mock_exists, mock_as):
        """Should prepend sfx_pre and append sfx_post (Functional Req 2)."""
        # Ensure it finds all files
        mock_exists.return_value = True
        
        mock_speech = MagicMock()
        mock_ambient = MagicMock()
        mock_sfx_pre = MagicMock()
        mock_sfx_post = MagicMock()
        
        # from_file sequence: speech, ambient, sfx_pre, sfx_post
        mock_as.from_file.side_effect = [mock_speech, mock_ambient, mock_sfx_pre, mock_sfx_post]
        
        # AudioSegment works in milliseconds
        mock_speech.__len__.return_value = 1000 
        mock_ambient.__len__.return_value = 1000
        
        # Ambient overlay setup
        mock_ambient.__mul__.return_value = mock_ambient
        mock_ambient.__getitem__.return_value = mock_ambient
        mock_ambient.__sub__.return_value = mock_ambient
        mock_ambient.overlay.return_value = mock_ambient # Final speech is mock_ambient
        
        # Concatenation setup
        mock_after_pre = MagicMock()
        mock_sfx_pre.__add__.return_value = mock_after_pre
        
        mock_final = MagicMock()
        mock_after_pre.__add__.return_value = mock_final
        
        from tts_generator import _apply_audio_processing
        _apply_audio_processing("dummy.mp3", "normal", "INTRO_THEME", "APPLAUSE_OPEN")
        
        # Prepend: sfx_pre + ambient_speech
        mock_sfx_pre.__add__.assert_called_with(mock_ambient)
        # Append: after_pre + sfx_post
        mock_after_pre.__add__.assert_called_with(mock_sfx_post)

if __name__ == "__main__":
    unittest.main()
