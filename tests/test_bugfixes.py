import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import json

# Ensure we can import modules
sys.path.append(os.getcwd())

# We'll import run_pipeline later inside tests to avoid immediate side effects
# from main.py top-level code if any.
# from main import run_pipeline 

class TestBugFixes(unittest.TestCase):
    
    @patch("main.TTSRadioGenerator.get_audio_duration")
    @patch("main.SupabaseDBClient")
    @patch("main.AIRadioAIClient.generate_broadcast")
    @patch("main.DistributionPublisher")
    @patch("main.NewsFetcher.get_all_news")
    def test_duration_gate_issue_1(self, mock_news, mock_pub, mock_gen_broadcast, mock_db, mock_duration):
        """ISSUE 1: Verify that episodes shorter than 600s are aborted."""
        from main import run_pipeline
        mock_duration.return_value = 500 # Too short
        mock_gen_broadcast.return_value = {"segments": [{"text": "test"}], "show_title": "T", "topic_tags": [], "my_take": "M", "social_post": "P"}
        mock_news.return_value = [{"headline": "H", "source": "S"}]
        # Mock the instance of SupabaseDBClient
        mock_db_instance = mock_db.return_value
        mock_db_instance.fetch_recent_memory.return_value = []
        
        # We need to mock generate_neural_art and compile_video too
        with patch("main.generate_neural_art", return_value=True), \
             patch("main.copy_cover_art", return_value="assets/cover_art.png"), \
             patch("main.TTSRadioGenerator.make_broadcast_audio", return_value="edge"), \
             patch("main.TTSRadioGenerator.compile_video", return_value=True):
            
            result = run_pipeline(env="local", dry_run=True)
            self.assertFalse(result)

    def test_quota_preemptive_check_issue_2(self):
        """ISSUE 2: Verify that Groq is skipped if char limit is reached."""
        from tts_generator import TTSRadioGenerator
        gen = TTSRadioGenerator(use_cloud=True)
        gen.daily_char_limit = 100
        
        # Mock usage to be over limit
        with patch.object(gen, "_get_groq_usage", return_value=150):
            with patch("tts_generator.requests.post") as mock_post:
                # Should skip Groq and go to next provider (Google or Edge)
                gen.generate_segment_audio("Hello world", "daniel", "test.mp3")
                
                # Check if Groq was called (it shouldn't be)
                for call in mock_post.call_args_list:
                    url = call.args[0] if call.args else call.kwargs.get('url', '')
                    self.assertNotIn("api.groq.com", str(url))

    def test_temp_file_cleanup_issue_7(self):
        """ISSUE 7: Verify that temp files are cleaned up in finally block."""
        from tts_generator import TTSRadioGenerator
        gen = TTSRadioGenerator(use_cloud=False)
        segments = [{"speaker": "ECHO", "text": "Test"}]
        
        # Mock generate_segment_audio to return a fake path and mock os.path.exists
        with patch.object(gen, "generate_segment_audio", return_value="edge"), \
             patch("tts_generator.subprocess.run", side_effect=Exception("FFmpeg Crash")), \
             patch("os.remove") as mock_remove, \
             patch("os.path.exists", return_value=True):
            
            gen.make_broadcast_audio(segments, "out.mp3")
            # Ensure os.remove was called for temp files even on crash
            self.assertTrue(mock_remove.called)

    def test_env_based_is_cloud_issue_4(self):
        """ISSUE 4: Verify is_cloud is based on env."""
        from main import run_pipeline
        with patch("main.AIRadioAIClient.generate_broadcast") as mock_gen_broadcast:
            with patch("main.SupabaseDBClient") as mock_db, \
                 patch("main.NewsFetcher.get_all_news", return_value=[{"headline": "H"}]):
                
                mock_db.return_value.fetch_recent_memory.return_value = []
                
                # Run with env="production"
                # Mock subsequent pipeline steps to avoid errors
                with patch("main.TTSRadioGenerator.make_broadcast_audio", return_value="edge"), \
                     patch("main.TTSRadioGenerator.get_audio_duration", return_value=700), \
                     patch("main.generate_neural_art", return_value=True):
                    
                    run_pipeline(env="production", dry_run=True)
                    # Check is_cloud argument in mock_gen
                    mock_gen_broadcast.assert_called_with(
                        news_items=unittest.mock.ANY,
                        memory_context=unittest.mock.ANY,
                        timestamp=unittest.mock.ANY,
                        is_cloud=True # env="production" -> is_cloud=True
                    )

                    # Run with env="local"
                    run_pipeline(env="local", dry_run=True)
                    mock_gen_broadcast.assert_called_with(
                        news_items=unittest.mock.ANY,
                        memory_context=unittest.mock.ANY,
                        timestamp=unittest.mock.ANY,
                        is_cloud=False # env="local" -> is_cloud=False
                    )

if __name__ == "__main__":
    unittest.main()
