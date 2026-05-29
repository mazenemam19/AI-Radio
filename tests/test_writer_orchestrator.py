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
        
        with patch.object(self.client, 'call_groq') as mock_groq, \
             patch.object(self.client, 'call_gemini') as mock_gemini:
            
            # Setup responses
            # First call: thin script (2 segments)
            # Second call: good script (10 segments, 200 words each)
            mock_groq.side_effect = [
                json.dumps({
                    "segments": [{"speaker": "ECHO", "text": "Short.", "speed": 1.0}] * 2
                }),
                json.dumps({
                    "segments": [{"speaker": "ECHO", "text": "Very long detailed satire text. " * 100, "speed": 1.0}] * 10
                })
            ]
            
            news = [{"headline": f"H{i}", "source": "S"} for i in range(15)]
            mem = []
            
            # Execute
            res = self.client.generate_broadcast(news, mem, "ts", is_cloud=True)
            
            # Assertions
            self.assertIsNotNone(res)
            
            # Verify first call (Attempt 1) was with 15 news items
            first_call_input = json.loads(mock_groq.call_args_list[0].kwargs['user_input_json'])
            self.assertEqual(len(first_call_input["news_items"]), 15)
            
            # Verify second call (Attempt 2) was with 8 news items (noise reduction)
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
