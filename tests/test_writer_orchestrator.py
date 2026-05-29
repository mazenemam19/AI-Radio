import unittest
import json
from unittest.mock import patch, MagicMock
import os
import sys

# Ensure we can import ai_client
sys.path.append(os.getcwd())

class TestWriterOrchestrator(unittest.TestCase):
    def setUp(self):
        from ai_client import AIRadioAIClient
        self.client = AIRadioAIClient()

    @patch("ai_client.requests.post")
    def test_orchestrator_retries_and_trims_context(self, mock_post):
        """
        Verify that the orchestrator tries the second model in the queue
        with trimmed context (8 items) if the first one returns a thin script.
        """
        from ai_client import PROD_WRITER_QUEUE
        
        # Setup mock to return a thin script for the first call and a good one for the second
        # First call (Groq 70B): 2 segments (insufficient)
        thin_resp = MagicMock()
        thin_resp.status_code = 200
        thin_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "segments": [{"speaker": "ECHO", "text": "Short.", "speed": 1.0}] * 2
            })}}]
        }
        
        # Second call (Gemini Pro - mocked here via requests to different URL): 14 segments (sufficient)
        # Wait, the fallback is Gemini which uses a different URL.
        # Let's mock the internal call methods instead for cleaner test.
        
        with patch.object(self.client, 'call_groq') as mock_groq, \
             patch.object(self.client, 'call_gemini') as mock_gemini:
            
            # Setup responses
            # First call (Groq 70B): thin script
            # Second call (Mistral): good script
            mock_groq.side_effect = [
                json.dumps({
                    "segments": [{"speaker": "ECHO", "text": "Short.", "speed": 1.0}] * 2
                }),
                json.dumps({
                    "segments": [{"speaker": "ECHO", "text": "Long script text. " * 50, "speed": 1.0}] * 14
                })
            ]
            
            news = [{"headline": f"H{i}", "source": "S"} for i in range(15)]
            mem = []
            
            # Execute
            res = self.client.generate_broadcast(news, mem, "ts", is_cloud=True)
            
            # Assertions
            self.assertIsNotNone(res)
            
            # Verify first call (Groq 70B) was with 15 news items
            first_call_input = json.loads(mock_groq.call_args_list[0].kwargs['user_input_json'])
            self.assertEqual(len(first_call_input["news_items"]), 15)
            
            # Verify second call (Mistral) was with 8 news items (noise reduction)
            second_call_input = json.loads(mock_groq.call_args_list[1].kwargs['user_input_json'])
            self.assertEqual(len(second_call_input["news_items"]), 8)

    def test_orchestrator_returns_none_on_total_failure(self):
        """Verify return None if all models fail."""
        with patch.object(self.client, 'call_gemini') as mock_gemini:
            mock_gemini.return_value = None
            
            news = [{"headline": "H", "source": "S"}]
            mem = []
            
            res = self.client.generate_broadcast(news, mem, "ts", is_cloud=False)
            self.assertIsNone(res)

if __name__ == "__main__":
    unittest.main()
