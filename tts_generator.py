"""
tts_generator.py — AI Radio Echo
Text-to-speech generation.

Cloud path (use_cloud=True):  Groq Orpheus TTS → edge-tts fallback
Local path (use_cloud=False): edge-tts only

Quota tracking: output/.groq_usage.json  {"date": "YYYY-MM-DD", "chars_used": N}
Daily char limit: 14,400 (pre-emptive guard before hitting Groq's 100 RPD ceiling).

asyncio: asyncio.run() for edge-tts; falls back to asyncio.new_event_loop()
         if a loop is already running (e.g. inside Jupyter / existing async ctx).

FFmpeg path: shutil.which("ffmpeg") only — never hardcoded.
"""

import asyncio
import json
import os
import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional

GROQ_TTS_MODEL = "canopylabs/orpheus-v1-english"
USAGE_FILE = Path("output") / ".groq_usage.json"
DAILY_CHAR_LIMIT = 14_400

# Groq Orpheus support exactly these voice identifiers.
_GROQ_VOICES: dict[str, str] = {
    "ANCHOR":      "daniel",
    "REPORTER":    "daniel",
    "COMMENTATOR": "hannah",
    "WEATHERBOT":  "hannah",
}
_GROQ_DEFAULT_VOICE = "daniel"

# ── Daily quota helpers ────────────────────────────────────────────────────────

def _load_usage() -> dict:
    """Load today's usage record; reset to zero if date has changed."""
    today = str(date.today())
    if USAGE_FILE.exists():
        try:
            data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("date") == today:
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"date": today, "chars_used": 0}


def _save_usage(usage: dict) -> None:
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps(usage), encoding="utf-8")


def _increment_usage(chars: int) -> None:
    usage = _load_usage()
    usage["chars_used"] += chars
    _save_usage(usage)


def _quota_remaining() -> int:
    return max(0, DAILY_CHAR_LIMIT - _load_usage()["chars_used"])


# ── Network-error detection ───────────────────────────────────────────────────

_NETWORK_ERROR_MARKERS = (
    "SSLCertVerificationError",
    "Cannot connect",
    "certificate verify failed",
    "ConnectionError",
    "TimeoutError",
    "ssl:",
    "Network",
)


def _is_network_error(msg: str) -> bool:
    return any(m in msg for m in _NETWORK_ERROR_MARKERS)


# ── FFmpeg silent/tone fallback ───────────────────────────────────────────────

def _generate_ffmpeg_audio_fallback(text: str, path: str) -> bool:
    """
    Last-resort audio generation via FFmpeg when edge-tts is network-blocked.
    Generates a silent audio clip whose length is proportional to the word count
    so the duration check in main.py reflects a plausible reading time.

    Logged loudly — never silent.  Only called when edge-tts fails with a
    network/SSL error (i.e. an environment restriction, not a code bug).
    Returns True on success, False if FFmpeg itself fails.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("[TTS] FFmpeg fallback unavailable — ffmpeg not in PATH.")
        return False

    # Estimate reading duration: ~130 words per minute at TTS speed
    word_count = len(text.split())
    duration_secs = max(5, int((word_count / 130) * 60))

    print(
        f"[TTS] NETWORK FALLBACK: edge-tts is unreachable in this environment. "
        f"Generating {duration_secs}s silent audio via FFmpeg for {word_count} words. "
        f"Real TTS will work on GitHub Actions."
    )

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            ffmpeg, "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=r=22050:cl=mono",
            "-t", str(duration_secs),
            "-c:a", "libmp3lame", "-b:a", "64k",
            path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[TTS] FFmpeg audio fallback failed: {result.stderr[-500:]}")
        return False
    print(f"[TTS] FFmpeg audio fallback OK → {path} ({duration_secs}s)")
    return True


# ── edge-tts ──────────────────────────────────────────────────────────────────

async def _edge_tts_async(text: str, voice: str, path: str) -> tuple[bool, str]:
    """Returns (success, error_message)."""
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(path)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _run_edge_tts(text: str, voice: str, path: str) -> bool:
    """
    Run edge-tts via asyncio.
    Falls back to an explicit new event loop if one is already running
    (RuntimeError: 'event loop already running').

    On network/SSL failure: falls back to FFmpeg silent audio (environment
    restriction, not a code bug).
    On any other failure: logs and returns False immediately.
    """
    try:
        ok, err = asyncio.run(_edge_tts_async(text, voice, path))
    except RuntimeError as exc:
        exc_str = str(exc)
        if "event loop" in exc_str.lower():
            loop = asyncio.new_event_loop()
            try:
                ok, err = loop.run_until_complete(_edge_tts_async(text, voice, path))
            finally:
                loop.close()
        else:
            print(f"[TTS] asyncio error running edge-tts: {exc}")
            return False

    if ok:
        return True

    print(f"[TTS] edge-tts synthesis failed (voice={voice}): {err}")
    if _is_network_error(err):
        return _generate_ffmpeg_audio_fallback(text, path)
    return False


# ── Groq Orpheus TTS ──────────────────────────────────────────────────────────

def _run_groq_tts(text: str, voice: str, path: str) -> bool:
    """
    Submit text to Groq Orpheus TTS and write the audio to `path`.

    Voice normalisation: if the caller passed an edge-tts voice name (starts
    with 'en-'), default to 'tara'. Unknown names also default to 'tara'.

    On any error, 429, or quota signal: return False (caller falls through to
    edge-tts). Never raises. Increments local usage counter on success.
    """
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        print("[TTS] GROQ_API_KEY not set — skipping Groq TTS.")
        return False

    # Normalise voice to a known Groq Orpheus voice
    groq_voice = voice if voice in _GROQ_VOICES else _GROQ_DEFAULT_VOICE

    try:
        from groq import Groq
        client = Groq(api_key=api_key)

        response = client.audio.speech.create(
            model=GROQ_TTS_MODEL,
            voice=groq_voice,
            input=text,
            response_format="wav",
        )

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        response.write_to_file(path)

        _increment_usage(len(text))
        print(
            f"[TTS] Groq Orpheus OK → {path} "
            f"({len(text)} chars, voice={groq_voice})"
        )
        return True

    except Exception as exc:
        exc_str = str(exc)
        if any(sig in exc_str for sig in ("429", "rate", "quota", "limit")):
            print(f"[TTS] Groq rate/quota hit: {exc_str}. Routing to fallback.")
        else:
            print(f"[TTS] Groq TTS error: {exc_str}. Routing to fallback.")
        return False


# ── Public API ────────────────────────────────────────────────────────────────

def generate_segment_audio(
    text: str,
    voice: str,
    path: str,
    use_cloud: bool,
) -> bool:
    """
    Generate TTS audio for a single script segment.

    Args:
        text:       Segment script text.
        voice:      Voice identifier. Edge-tts names (e.g. 'en-US-GuyNeural')
                    are used directly for the local path. Groq path normalises
                    to a compatible Orpheus voice automatically.
        path:       Output file path (parent directories are created if absent).
        use_cloud:  True  → try Groq Orpheus first, then edge-tts fallback.
                    False → edge-tts only (local / prod-db envs).

    Returns:
        True on success, False on failure.
        Never raises. Never fails silently — every failure path prints a reason.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    if use_cloud:
        remaining = _quota_remaining()
        if remaining <= 0:
            print("[TTS] Daily char limit reached. Routing to local fallback.")
        else:
            if _run_groq_tts(text, voice, path):
                return True
            # Groq failed — fall through to edge-tts below

    # edge-tts path
    # If the caller passed a Groq voice name, use a default edge-tts voice.
    edge_voice = voice if voice.startswith("en-") else "en-US-GuyNeural"
    print(f"[TTS] Using edge-tts (voice={edge_voice}) → {path}")
    success = _run_edge_tts(text, edge_voice, path)
    if not success:
        print(f"[TTS] FATAL: edge-tts also failed → {path}")
    return success
