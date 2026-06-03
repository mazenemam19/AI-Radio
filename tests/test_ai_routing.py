#!/usr/bin/env python3
"""
tests/test_ai_routing.py — AI Radio Echo
Verifies that generate_broadcast routes to the correct API caller for each model.
"""

import sys
import unittest
from unittest.mock import patch, MagicMock, ANY
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
        
        # Test Gemini (Gemini SDK)
        ai_client.generate_broadcast([], [], "production")
        # Gemini 3.5 Flash is first in Set A
        mock_gemini.assert_any_call(ANY, ai_client.GEMINI_3_5_FLASH)
        
        # Reset mocks
        mock_groq.reset_mock()
        mock_gemini.reset_mock()
        
        # Force a failure on Gemini models to see if it reaches Groq (in Set B/Local)
        mock_gemini.return_value = None
        mock_groq.return_value = '{"title": "Groq Fallback", "segments": [], "confidence": "high", "related_ids": []}'
        
        ai_client.generate_broadcast([], [], "local")
        
        # In Local Set (reverse of Set A), it should try Gemini/Gemma models first, 
        # fail, then reach LLAMA_4_SCOUT via Groq.
        mock_groq.assert_any_call(ANY, ai_client.LLAMA_4_SCOUT)

if __name__ == "__main__":
    unittest.main()
