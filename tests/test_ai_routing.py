#!/usr/bin/env python3
"""
tests/test_ai_routing.py — AI Radio Echo
Verifies that generate_broadcast routes to the correct API caller for each model.
"""

import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# ── Import Fix ────────────────────────────────────────────────────────────────
PROJ_ROOT = Path(__file__).parent.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

import ai_client

class TestAIRouting(unittest.TestCase):
    @patch("ai_client.call_groq")
    @patch("ai_client.call_gemini")
    @patch("ai_client.validate_broadcast")
    def test_routing_logic(self, mock_validate, mock_gemini, mock_groq):
        """Should call the correct provider based on model prefix or constant."""
        mock_validate.return_value = (True, "OK")
        mock_groq.return_value = '{"title": "Test", "segments": [], "confidence": "high", "related_ids": []}'
        mock_gemini.return_value = mock_groq.return_value
        
        # Test DeepSeek (Groq)
        ai_client.generate_broadcast([], [], "production")
        # DeepSeek is first in Set A
        mock_groq.assert_any_call(unittest.mock.ANY, ai_client.DEEPSEEK_MODEL)
        
        # Reset mocks
        mock_groq.reset_mock()
        mock_gemini.reset_mock()
        
        # Force a failure on Groq models to see if it reaches Gemini
        mock_groq.return_value = None
        ai_client.generate_broadcast([], [], "production")
        
        # Should have tried all 3 Groq models then moved to Gemini
        mock_gemini.assert_any_call(unittest.mock.ANY, ai_client.GEMINI_PRIMARY)

if __name__ == "__main__":
    unittest.main()
