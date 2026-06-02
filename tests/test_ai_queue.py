import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJ_ROOT = Path(__file__).parent.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

import ai_client
import tts_generator
import inspect

class TestGoldStandard(unittest.TestCase):
    """
    Gold Standard Contract Test.
    Locks the AI Writing Models and TTS Audio Engines to prevent logic drift.
    """

    def test_ai_writer_models(self):
        """Verify the exact strings for AI Writing Model sets."""
        # Set A: Gold Standard Production Queue
        expected_a = [
            "gemini-3.5-flash",
            "gemini-2.5-pro",
            "gemini-3-flash-preview",
            "gemini-2.5-flash",
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash-lite"
        ]
        self.assertEqual(ai_client.MODEL_SET_A, expected_a, "AI MODEL_SET_A has drifted!")

        # Set B: Local / Development Queue
        expected_b = [
            "gemini-2.5-flash-lite-preview-09-2025",
            "gemma-4-31b-it",
            "openai/gpt-oss-120b",
            "groq/compound",
            "llama-3.3-70b-versatile",
            "groq/compound-mini",
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "qwen/qwen3-32b",
            "openai/gpt-oss-20b",
            "llama-3.1-8b-instant"
        ]
        self.assertEqual(ai_client.MODEL_SET_B, expected_b, "AI MODEL_SET_B has drifted!")

    def test_audio_production_tier(self):
        """Verify the priority order of high-fidelity TTS engines for production."""
        source = inspect.getsource(tts_generator.generate_segment_audio)
        
        # Verify the priority order: Cartesia -> Kokoro -> Edge-TTS
        # We search for the presence and order of these calls in the cloud block.
        self.assertIn("_run_cartesia_tts", source, "Production audio missing Cartesia tier.")
        self.assertIn("_run_kokoro_tts", source, "Production audio missing Kokoro tier.")
        
        # Check that Cartesia is attempted before Kokoro
        idx_cartesia = source.find("_run_cartesia_tts")
        idx_kokoro = source.find("_run_kokoro_tts")
        
        self.assertTrue(idx_cartesia < idx_kokoro, "Production TTS priority order has drifted!")

    def test_audio_non_production_tier(self):
        """Verify that local/non-production runs use only edge-tts or silent fallback."""
        source = inspect.getsource(tts_generator.generate_segment_audio)
        
        # Ensure that if not use_cloud, we eventually call edge-tts or the fallback.
        self.assertIn("_run_edge_tts(text, voice, path)", source, "Local audio logic missing edge-tts call.")
        self.assertIn("_generate_ffmpeg_audio_fallback(text, path)", source, "Local audio logic missing silent fallback.")

if __name__ == "__main__":
    unittest.main()
