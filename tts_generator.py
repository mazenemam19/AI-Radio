"""
tts_generator.py — AI Radio Echo
Generates segment audio via Groq Orpheus TTS (cloud) or edge-tts (local fallback).
Maintains a daily character quota file at output/.groq_usage.json.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path


# ------------------------------------------------------------------ #
#  Constants & voice maps                                             #
# ------------------------------------------------------------------ #

_GROQ_USAGE_FILE  = Path("output") / ".groq_usage.json"
_GROQ_DAILY_LIMIT = 14_400          # characters per day
_GROQ_TTS_MODEL   = "canopylabs/orpheus-v1-english"

# edge-tts voices keyed by speaker name
_EDGE_VOICES: dict[str, str] = {
    "HOST":    "en-US-GuyNeural",
    "CO-HOST": "en-US-AriaNeural",
    "DEFAULT": "en-US-GuyNeural",
}

# Groq Orpheus voice IDs keyed by speaker name
_GROQ_VOICES: dict[str, str] = {
    "HOST":    "dan",
    "CO-HOST": "talia",
    "DEFAULT": "talia",
}


# ------------------------------------------------------------------ #
#  Quota helpers                                                      #
# ------------------------------------------------------------------ #

def _load_usage() -> dict:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if _GROQ_USAGE_FILE.exists():
        try:
            data = json.loads(_GROQ_USAGE_FILE.read_text(encoding="utf-8"))
            if data.get("date") == today:
                return data
        except Exception:
            pass
    return {"date": today, "chars_used": 0}


def _save_usage(data: dict) -> None:
    _GROQ_USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _GROQ_USAGE_FILE.write_text(json.dumps(data), encoding="utf-8")


def _quota_ok() -> bool:
    usage = _load_usage()
    if usage["chars_used"] >= _GROQ_DAILY_LIMIT:
        print("[TTS] Daily char limit reached. Routing to local fallback.")
        return False
    return True


def _increment_usage(chars: int) -> None:
    usage = _load_usage()
    usage["chars_used"] += chars
    _save_usage(usage)


# ------------------------------------------------------------------ #
#  Groq Orpheus TTS                                                   #
# ------------------------------------------------------------------ #

def _groq_tts(text: str, voice_id: str, out_path: str) -> bool:
    """
    Generate audio via Groq Orpheus TTS and save to out_path (.mp3).
    Tracks character usage per chunk after each successful API call.
    Returns True on success, False on any error or quota/rate issue.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("[TTS] GROQ_API_KEY not set.")
        return False

    try:
        from groq import Groq
        client = Groq(api_key=api_key)

        # Split into chunks so each chunk's char count is tracked individually
        chunk_size = 500
        chunks = [text[i: i + chunk_size] for i in range(0, len(text), chunk_size)]

        audio_parts: list[bytes] = []
        for chunk_text in chunks:
            resp = client.audio.speech.create(
                model=_GROQ_TTS_MODEL,
                voice=voice_id,
                input=chunk_text,
                response_format="mp3",
            )
            audio_parts.append(resp.read())
            _increment_usage(len(chunk_text))   # track after each successful chunk

        with open(out_path, "wb") as fh:
            for part in audio_parts:
                fh.write(part)

        return True

    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
            print(f"[TTS] Groq TTS rate-limited / quota hit: {e}")
        else:
            print(f"[TTS] Groq TTS error: {e}")
        return False


# ------------------------------------------------------------------ #
#  edge-tts (local fallback)                                         #
# ------------------------------------------------------------------ #

async def _edge_tts_coro(text: str, voice: str, out_path: str) -> bool:
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(out_path)
        return True
    except Exception as e:
        print(f"[TTS] edge-tts coroutine failed: {e}")
        return False


def _edge_tts(text: str, voice: str, out_path: str) -> bool:
    """
    Synchronous wrapper around edge-tts.
    Uses asyncio.run(); falls back to asyncio.new_event_loop() if a loop
    is already running (e.g. inside Jupyter or an async framework).
    """
    coro = _edge_tts_coro(text, voice, out_path)
    try:
        return asyncio.run(coro)
    except RuntimeError as exc:
        if "event loop" in str(exc).lower():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(_edge_tts_coro(text, voice, out_path))
            finally:
                loop.close()
                asyncio.set_event_loop(None)
        else:
            print(f"[TTS] Unexpected asyncio error: {exc}")
            return False


# ------------------------------------------------------------------ #
#  Public API                                                         #
# ------------------------------------------------------------------ #

def generate_segment_audio(
    text: str,
    voice: str,
    path: str,
    use_cloud: bool,
) -> bool:
    """
    Generate audio for a single broadcast segment.

    Args:
        text:       Spoken text for this segment.
        voice:      Speaker name key ("HOST", "CO-HOST", or any string).
        path:       Destination file path (should end in .mp3).
        use_cloud:  True for prod/prod-models envs; False for local/prod-db.

    Behaviour:
        - use_cloud=False  → edge-tts only (no Groq).
        - use_cloud=True   → try Groq Orpheus first; fall back to edge-tts.
        - Pre-emptive quota check: if chars_used >= 14 400 today, skip Groq.
        - On any Groq error (429, exception, quota) → fall back to edge-tts.
        - If edge-tts also fails → return False (never silent failure).

    Returns:
        True on success, False if both TTS engines failed.
    """
    if use_cloud and _quota_ok():
        groq_voice = _GROQ_VOICES.get(voice, _GROQ_VOICES["DEFAULT"])
        print(f"[TTS] Attempting Groq Orpheus (voice={groq_voice}) for '{voice}'")
        if _groq_tts(text, groq_voice, path):
            return True
        print("[TTS] Groq failed. Falling back to edge-tts.")

    edge_voice = _EDGE_VOICES.get(voice, _EDGE_VOICES["DEFAULT"])
    print(f"[TTS] Using edge-tts (voice={edge_voice}) for '{voice}'")
    success = _edge_tts(text, edge_voice, path)
    if not success:
        print(f"[TTS] edge-tts also failed for segment path={path}. Returning False.")
    return success
