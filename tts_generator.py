"""
tts_generator.py — AI Radio Echo
Segment-level TTS: Groq Orpheus (cloud) with edge-tts fallback (local).
  - Pre-emptive daily char quota tracked in output/.groq_usage.json
  - generate_segment_audio(text, voice, path, use_cloud) -> bool
  - Voice map: speaker name -> (edge_tts_voice, orpheus_voice)
"""

import asyncio
import json
import os
from datetime import datetime

# ---------------------------------------------------------------------------
# Voice maps
# ---------------------------------------------------------------------------

# speaker -> (edge_tts_voice, groq_orpheus_voice)
_VOICE_MAP: dict[str, tuple[str, str]] = {
    "HOST":        ("en-US-GuyNeural",         "leo"),
    "REPORTER":    ("en-US-JennyNeural",        "leah"),
    "ANALYST":     ("en-US-AriaNeural",         "jess"),
    "WEATHERBOT":  ("en-US-EricNeural",         "dan"),
    "COMMENTATOR": ("en-US-ChristopherNeural",  "zac"),
}

_DEFAULT_EDGE_VOICE    = "en-US-GuyNeural"
_DEFAULT_ORPHEUS_VOICE = "leo"

_GROQ_USAGE_PATH   = os.path.join("output", ".groq_usage.json")
_GROQ_DAILY_LIMIT  = 14400       # characters
_GROQ_CHUNK_CHARS  = 500         # max chars per API call
_GROQ_TTS_MODEL    = "canopylabs/orpheus-v1-english"
_GROQ_TTS_ENDPOINT = "https://api.groq.com/openai/v1/audio/speech"
_REQUEST_TIMEOUT   = 120         # seconds

# Module-level tracking of which TTS model was last successfully used
_narrator_model: str = "edge-tts"


def get_narrator_model() -> str:
    """Return the TTS model string used for the most recent batch."""
    return _narrator_model


def _set_narrator_model(model: str):
    global _narrator_model
    _narrator_model = model


# ---------------------------------------------------------------------------
# Groq quota helpers
# ---------------------------------------------------------------------------

def _load_groq_usage() -> dict:
    """Load today's Groq TTS usage. Returns fresh dict if file is missing or stale."""
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(_GROQ_USAGE_PATH, "r") as fh:
            data = json.load(fh)
        if data.get("date") == today:
            return data
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass
    return {"date": today, "chars_used": 0}


def _save_groq_usage(usage: dict):
    """Persist Groq TTS usage to file."""
    os.makedirs(os.path.dirname(_GROQ_USAGE_PATH), exist_ok=True)
    with open(_GROQ_USAGE_PATH, "w") as fh:
        json.dump(usage, fh)


def _groq_chars_remaining() -> int:
    usage = _load_groq_usage()
    return max(0, _GROQ_DAILY_LIMIT - usage["chars_used"])


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------

def _split_into_chunks(text: str, max_chars: int = _GROQ_CHUNK_CHARS) -> list[str]:
    """Split text on sentence/word boundaries, respecting max_chars."""
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    words = text.split()
    current: list[str] = []
    current_len = 0

    for word in words:
        word_len = len(word) + 1  # +1 for space
        if current_len + word_len > max_chars and current:
            chunks.append(" ".join(current))
            current = [word]
            current_len = word_len
        else:
            current.append(word)
            current_len += word_len

    if current:
        chunks.append(" ".join(current))

    return chunks


# ---------------------------------------------------------------------------
# Groq Orpheus TTS
# ---------------------------------------------------------------------------

def _call_groq_tts(text: str, orpheus_voice: str, path: str) -> bool:
    """
    Call Groq Orpheus TTS. Returns False on any error (caller falls back to edge-tts).
    Tracks character usage in output/.groq_usage.json.
    """
    import requests

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        print("[TTS] GROQ_API_KEY not set. Routing to local fallback.")
        return False

    # Pre-emptive quota check
    usage = _load_groq_usage()
    if usage["chars_used"] >= _GROQ_DAILY_LIMIT:
        print("[TTS] Daily char limit reached. Routing to local fallback.")
        return False

    chunks = _split_into_chunks(text, max_chars=_GROQ_CHUNK_CHARS)
    audio_parts: list[bytes] = []

    for chunk_text in chunks:
        # Mid-generation quota check
        if usage["chars_used"] >= _GROQ_DAILY_LIMIT:
            print("[TTS] Daily char limit reached mid-generation. Routing to local fallback.")
            return False

        try:
            resp = requests.post(
                _GROQ_TTS_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _GROQ_TTS_MODEL,
                    "voice": orpheus_voice,
                    "input": chunk_text,
                    "response_format": "mp3",
                },
                timeout=_REQUEST_TIMEOUT,
            )
        except Exception as exc:
            print(f"[TTS] Groq request exception: {exc}")
            return False

        if resp.status_code == 429:
            print(f"[TTS] Groq 429 rate limit. Routing to local fallback.")
            return False
        if resp.status_code != 200:
            print(f"[TTS] Groq error {resp.status_code}: {resp.text[:200]}")
            return False

        audio_parts.append(resp.content)
        usage["chars_used"] += len(chunk_text)
        _save_groq_usage(usage)

    # Write combined audio
    try:
        with open(path, "wb") as fh:
            for part in audio_parts:
                fh.write(part)
    except OSError as exc:
        print(f"[TTS] Failed to write Groq audio file: {exc}")
        return False

    _set_narrator_model(_GROQ_TTS_MODEL)
    return True


# ---------------------------------------------------------------------------
# edge-tts (local fallback)
# ---------------------------------------------------------------------------

async def _edge_tts_async(text: str, voice: str, path: str):
    """Async edge-tts synthesis."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(path)


def _call_edge_tts(text: str, edge_voice: str, path: str) -> bool:
    """
    Run edge-tts. Handles event-loop conflicts per spec.
    Returns True on success, False on failure.
    """
    try:
        asyncio.run(_edge_tts_async(text, edge_voice, path))
        _set_narrator_model("edge-tts")
        return True
    except RuntimeError as exc:
        if "event loop is already running" in str(exc).lower():
            # Fallback: create a fresh event loop explicitly
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_edge_tts_async(text, edge_voice, path))
                _set_narrator_model("edge-tts")
                return True
            except Exception as inner_exc:
                print(f"[TTS] edge-tts inner loop error: {inner_exc}")
                return False
            finally:
                loop.close()
        print(f"[TTS] edge-tts RuntimeError: {exc}")
        return False
    except Exception as exc:
        print(f"[TTS] edge-tts error: {exc}")
        return False


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def generate_segment_audio(text: str, voice: str, path: str, use_cloud: bool) -> bool:
    """
    Generate TTS audio for one segment.

    Args:
        text:       Spoken text.
        voice:      Speaker name (e.g. 'HOST') — resolved via VOICE_MAP.
        path:       Output file path (.mp3).
        use_cloud:  If True (prod-models/production), try Groq Orpheus first.
                    If False (local/prod-db), use edge-tts only.

    Returns:
        True on success, False if both TTS methods fail.
    """
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)

    edge_voice, orpheus_voice = _VOICE_MAP.get(voice.upper(), (_DEFAULT_EDGE_VOICE, _DEFAULT_ORPHEUS_VOICE))

    if use_cloud:
        success = _call_groq_tts(text, orpheus_voice, path)
        if success:
            return True
        print(f"[TTS] Groq failed for speaker '{voice}'. Falling back to edge-tts.")

    # Local fallback (or primary when use_cloud=False)
    success = _call_edge_tts(text, edge_voice, path)
    if not success:
        print(f"[TTS] edge-tts also failed for speaker '{voice}'. Segment audio generation failed.")
        return False

    return True
