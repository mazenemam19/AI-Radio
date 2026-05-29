import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import asyncio

# Ensure we can import tts_generator
sys.path.append(os.getcwd())

class TestNarratorOrchestrator(unittest.TestCase):
    def setUp(self):
        from tts_generator import TTSRadioGenerator
        self.gen = TTSRadioGenerator(use_cloud=True)

    @patch("tts_generator.requests.post")
    def test_narrator_switches_to_google_on_groq_failure(self, mock_post):
        """Verify fallback from Groq to Google Cloud TTS in production."""
        # Setup mock: Groq fails with 429, Google succeeds
        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        mock_resp_429.headers = {"retry-after": "70"} # Triggers immediate fallback
        
        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.json.return_value = {"audioContent": "YmFzZTY0ZGF0YQ=="} # 'base64data'
        
        mock_post.side_effect = [mock_resp_429, mock_resp_200]
        
        # We need to mock ffmpeg and other subprocess calls
        with patch("tts_generator.subprocess.run") as mock_run, \
             patch("tts_generator.time.sleep"), \
             patch("tts_generator.shutil.which", return_value="ffmpeg"), \
             patch("builtins.open", unittest.mock.mock_open()), \
             patch("os.remove"), \
             patch("os.path.abspath", return_value="abs_path"):
            
            # Execute
            # Note: We need a Google Key for the check to not skip it
            self.gen.google_key = "fake_key"
            res = self.gen.generate_segment_audio("Hello", "daniel", "test.mp3")
            
            self.assertTrue(res)
            # Verify two POST calls: 1 to Groq, 1 to Google
            self.assertEqual(mock_post.call_count, 2)
            # First call was Groq
            self.assertIn("api.groq.com", mock_post.call_args_list[0].args[0])
            # Second call was Google
            self.assertIn("texttospeech.googleapis.com", mock_post.call_args_list[1].args[0])

    def test_narrator_isolation_test_mode(self):
        """Verify that in test mode, Groq is physically unreachable."""
        from tts_generator import TTSRadioGenerator
        test_gen = TTSRadioGenerator(use_cloud=False)
        
        with patch("tts_generator.requests.post") as mock_post:
            # If we call generate_segment_audio in local mode, it should use edge_tts
            # and NEVER call requests.post (which is used for Groq/Google)
            with patch("tts_generator.asyncio.run") as mock_run:
                test_gen.generate_segment_audio("Hello", "daniel", "path.mp3")
                self.assertFalse(mock_post.called)

if __name__ == "__main__":
    unittest.main()
