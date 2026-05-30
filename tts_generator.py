"""
tts_generator.py — TTS generation for AI Radio Echo.

Strategy:
  - use_cloud=False (local, prod-db): edge-tts only.
  - use_cloud=True  (production, prod-models): Groq Orpheus first, edge-tts on any error.

Quota guard:
  - Groq Orpheus daily character cap: 14,400 chars/day tracked in output/.groq_usage.json
  - If chars_used >= 14,400 today, skip Groq and use edge-tts immediately.

1 segment = 1 TTS API call (chunk boundary = JSON segment boundary).
"""

import asyncio
import json
import os
import shutil
from datetime import date
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GROQ_TTS_MODEL    = "canopylabs/orpheus-v1-english"
GROQ_TTS_ENDPOINT = "https://api.groq.com/openai/v1/audio/speech"
DAILY_CHAR_LIMIT  = 14_400
USAGE_FILE        = Path("output") / ".groq_usage.json"

# ---------------------------------------------------------------------------
# Speaker → voice mappings
# ---------------------------------------------------------------------------

# Groq Orpheus voices
GROQ_VOICES: dict[str, str] = {
    "HOST":         "leo",
    "ANCHOR":       "tara",
    "CORRESPONDENT":"dan",
    "REPORTER":     "mia",
}
GROQ_VOICE_DEFAULT = "leo"

# edge-tts voices (Microsoft Neural TTS)
EDGE_VOICES: dict[str, str] = {
    "HOST":         "en-US-GuyNeural",
    "ANCHOR":       "en-US-JennyNeural",
    "CORRESPONDENT":"en-GB-RyanNeural",
    "REPORTER":     "en-AU-NatashaNeural",
}
EDGE_VOICE_DEFAULT = "en-US-GuyNeural"


def get_groq_voice(speaker: str) -> str:
    return GROQ_VOICES.get(speaker.upper(), GROQ_VOICE_DEFAULT)


def get_edge_voice(speaker: str) -> str:
    return EDGE_VOICES.get(speaker.upper(), EDGE_VOICE_DEFAULT)


# ---------------------------------------------------------------------------
# Quota tracker
# ---------------------------------------------------------------------------

def _load_usage() -> dict:
    """Load today's Groq usage record from disk. Returns fresh record if missing/stale."""
    today = str(date.today())
    if USAGE_FILE.exists():
        try:
            data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
            if data.get("date") == today:
                return data
        except Exception:
            pass
    return {"date": today, "chars_used": 0}


def _save_usage(usage: dict):
    """Persist usage record to disk."""
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps(usage), encoding="utf-8")


def _increment_usage(chars: int):
    """Add `chars` to today's usage counter and persist."""
    usage = _load_usage()
    usage["chars_used"] += chars
    _save_usage(usage)


def _quota_remaining() -> int:
    """Return how many characters are still available today."""
    usage = _load_usage()
    return max(0, DAILY_CHAR_LIMIT - usage["chars_used"])


# ---------------------------------------------------------------------------
# edge-tts backend
# ---------------------------------------------------------------------------

async def _edge_tts_async(text: str, voice: str, path: str):
    import edge_tts  # type: ignore
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(path)


def _generate_edge_tts(text: str, voice: str, path: str) -> bool:
    """
    Run edge-tts synthesis. Handles 'event loop already running' via
    explicit new event loop as required by the spec.
    """
    try:
        asyncio.run(_edge_tts_async(text, voice, path))
        return True
    except RuntimeError as exc:
        if "event loop already running" in str(exc):
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_edge_tts_async(text, voice, path))
                return True
            except Exception as inner_exc:
                print(f"[TTS] edge-tts (new loop) failed: {inner_exc}")
                return False
            finally:
                loop.close()
        print(f"[TTS] edge-tts RuntimeError: {exc}")
        return False
    except Exception as exc:
        print(f"[TTS] edge-tts failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Groq Orpheus backend
# ---------------------------------------------------------------------------

def _generate_groq_tts(text: str, voice: str, path: str) -> bool:
    """
    Call Groq Orpheus TTS. Returns False on any error or quota hit (429).
    Increments the daily character counter on success.
    """
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        print("[TTS] GROQ_API_KEY not set — cannot call Groq TTS.")
        return False

    try:
        response = requests.post(
            GROQ_TTS_ENDPOINT,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_TTS_MODEL,
                "input": text,
                "voice": voice,
                "response_format": "mp3",
            },
            timeout=120,
        )

        if response.status_code == 200:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_bytes(response.content)
            _increment_usage(len(text))
            return True

        if response.status_code == 429:
            print("[TTS] Groq TTS: 429 rate limit hit. Routing to local fallback.")
            return False

        print(
            f"[TTS] Groq TTS error {response.status_code}: "
            f"{response.text[:300]}"
        )
        return False

    except Exception as exc:
        print(f"[TTS] Groq TTS exception: {exc}")
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_segment_audio(
    text: str,
    speaker: str,
    path: str,
    use_cloud: bool,
) -> bool:
    """
    Generate TTS audio for a single broadcast segment.

    Args:
        text:       The dialogue text to synthesise.
        speaker:    Speaker name (HOST, ANCHOR, etc.) for voice selection.
        path:       Output file path (e.g. output/segment_001.mp3).
        use_cloud:  True = try Groq Orpheus first; False = edge-tts only.

    Returns:
        True on success, False on total failure (both backends tried and failed).
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    if not use_cloud:
        # Local/prod-db: edge-tts only
        voice = get_edge_voice(speaker)
        success = _generate_edge_tts(text, voice, path)
        if not success:
            print(f"[TTS] edge-tts failed for speaker '{speaker}' at {path}.")
        return success

    # Cloud mode: Groq first, edge-tts as fallback

    # --- Pre-emptive quota check ---
    remaining = _quota_remaining()
    if remaining <= 0:
        print("[TTS] Daily char limit reached. Routing to local fallback.")
        voice = get_edge_voice(speaker)
        return _generate_edge_tts(text, voice, path)

    # --- Try Groq ---
    groq_voice = get_groq_voice(speaker)
    success = _generate_groq_tts(text, groq_voice, path)
    if success:
        return True

    # --- Fallback to edge-tts ---
    print(f"[TTS] Groq failed for speaker '{speaker}'. Falling back to edge-tts.")
    edge_voice = get_edge_voice(speaker)
    success = _generate_edge_tts(text, edge_voice, path)
    if not success:
        print(f"[TTS] edge-tts fallback also failed for speaker '{speaker}' at {path}.")
    return success
