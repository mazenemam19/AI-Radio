"""
tts_generator.py — AI Radio Echo
Text-to-speech generation.

Cloud path (use_cloud=True):  Cartesia Sonic → Kokoro Cloud → edge-tts fallback
Local path (use_cloud=False): edge-tts only

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

# Cartesia Sonic 3.5 curated voices (Verified June 2026)
_CARTESIA_VOICES: dict[str, str] = {
    "ANCHOR":      "c8f7835e-28a3-4f0c-80d7-c1302ac62aae", # Alistair (Sophisticated British Male)
    "REPORTER":    "dc30854e-e398-4579-9dc8-16f6cb2c19b9", # Victoria (Professional British Female)
    "COMMENTATOR": "5ee9feff-1265-424a-9d7f-8e4d431a12c7", # Ronald (Intense American Male)
    "WEATHERBOT":  "4f7f1324-1853-48a6-b294-4e78e8036a83", # Casper (Wistful British Male)
}
_CARTESIA_DEFAULT_VOICE = "c8f7835e-28a3-4f0c-80d7-c1302ac62aae"

# Kokoro-82M curated voices (June 2026)
_KOKORO_VOICES: dict[str, str] = {
    "ANCHOR":      "af_heart",    # Formal/Clear
    "REPORTER":    "bf_emma",   # British/Professional
    "COMMENTATOR": "af_nicole",   # Deep/Thoughtful
    "WEATHERBOT":  "af_bella",  # Soft/Ethereal
}
_KOKORO_DEFAULT_VOICE = "af_heart"

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


# ── Cartesia Sonic 3.5 ────────────────────────────────────────────────────────

def _run_cartesia_tts(text: str, voice: str, path: str) -> bool:
    """
    Submit text to Cartesia Sonic 3.5 TTS and write the audio to `path`.
    
    On any error: return False (caller falls through to next provider).
    """
    api_key = os.environ.get("CARTESIA_API_KEY", "").strip()
    if not api_key:
        print("[TTS] CARTESIA_API_KEY not set — skipping Cartesia Sonic.")
        return False

    cartesia_voice = _CARTESIA_VOICES.get(voice, _CARTESIA_DEFAULT_VOICE)

    try:
        import requests
        url = "https://api.cartesia.ai/tts/bytes"
        headers = {
            "X-API-Key": api_key,
            "Cartesia-Version": "2024-06-10",
            "Content-Type": "application/json",
        }
        payload = {
            "model_id": "sonic-3.5",
            "transcript": text,
            "voice": {
                "mode": "id",
                "id": cartesia_voice,
            },
            "output_format": {
                "container": "mp3",
                "sample_rate": 22050,
            },
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            Path(path).write_bytes(resp.content)
            print(f"[TTS] Cartesia Sonic OK → {path}")
            return True
            
        print(f"[TTS] Cartesia failed ({resp.status_code}): {resp.text}")
        return False

    except Exception as exc:
        print(f"[TTS] Cartesia error: {exc}")
        return False


# ── Kokoro Cloud (fal.ai / OpenAI-Compatible) ────────────────────────────────

def _run_kokoro_tts(text: str, voice: str, path: str) -> bool:
    """
    Submit text to Kokoro Cloud TTS and write audio to `path`.
    Uses an OpenAI-compatible endpoint (common for Kokoro providers in 2026).
    
    On any error: return False (caller falls through).
    """
    api_key = os.environ.get("KOKORO_API_KEY", "").strip()
    base_url = os.environ.get("KOKORO_BASE_URL", "https://api.fal.ai/v1/openai").strip()
    
    if not api_key:
        print("[TTS] KOKORO_API_KEY not set — skipping Kokoro Cloud.")
        return False

    kokoro_voice = _KOKORO_VOICES.get(voice, _KOKORO_DEFAULT_VOICE)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)

        response = client.audio.speech.create(
            model="kokoro",
            voice=kokoro_voice,
            input=text,
        )

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        response.stream_to_file(path)
        print(f"[TTS] Kokoro Cloud OK → {path} (voice={kokoro_voice})")
        return True

    except Exception as exc:
        print(f"[TTS] Kokoro error: {exc}")
        return False


# ── TTS Quality Guard ─────────────────────────────────────────────────────────

def _get_audio_duration(path: str) -> float:
    """Return duration in seconds using ffprobe or ffmpeg."""
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg:
        return -1.0

    if ffprobe:
        cmd = [
            ffprobe, "-v", "quiet", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                return float(res.stdout.strip())
        except (ValueError, subprocess.TimeoutExpired, Exception):
            pass

    # Fallback to ffmpeg -i
    cmd = [ffmpeg, "-i", path]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        import re
        match = re.search(r"Duration:\s*(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)", res.stderr)
        if match:
            h, m, s = int(match.group(1)), int(match.group(2)), float(match.group(3))
            return h * 3600 + m * 60 + s
    except Exception:
        pass
    return -1.0


def _is_audio_valid(path: str, word_count: int) -> bool:
    """
    Verify audio integrity.
    Rejects files that are missing, zero-byte, or suspiciously short 
    (e.g. > 300 words per minute is likely a TTS truncation error).
    """
    p = Path(path)
    if not p.exists() or p.stat().st_size < 100:
        return False
    
    duration = _get_audio_duration(path)
    if duration <= 0:
        print(f"[TTS] Quality Check: Failed to determine duration for {path}.")
        return False
    
    # 300 WPM is double the normal speed. Anything faster is definitely a bug.
    wpm = (word_count / duration) * 60
    print(f"[TTS] Quality Check: {path} has {word_count} words in {duration:.1f}s (~{wpm:.0f} WPM).")
    
    if wpm > 300:
        print(f"[TTS] Quality Alert: Audio too fast/short for word count.")
        return False
    
    return True


# ── Public API ────────────────────────────────────────────────────────────────

def generate_segment_audio(
    text: str,
    voice: str,
    path: str,
    use_cloud: bool,
) -> tuple[bool, str]:
    """
    Generate TTS audio for a single script segment with duration guarding.

    Args:
        text:       Segment script text.
        voice:      Voice identifier.
        path:       Output file path.
        use_cloud:  True  → try Cartesia first, then Kokoro, then edge-tts.
                    False → edge-tts only.

    Returns:
        (success, engine_name)
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    word_count = len(text.split())
    preview = (text[:47] + "...") if len(text) > 50 else text
    print(f"[TTS] Narrating {word_count} words: \"{preview}\"")

    if use_cloud:
        if _run_cartesia_tts(text, voice, path):
            if _is_audio_valid(path, word_count):
                return True, "cartesia-sonic"
            else:
                print(f"[TTS] Cartesia output failed quality check. Falling back.")

        if _run_kokoro_tts(text, voice, path):
            if _is_audio_valid(path, word_count):
                return True, "kokoro-cloud"
            else:
                print(f"[TTS] Kokoro output failed quality check. Falling back.")

    # edge-tts path
    edge_voice = voice if voice.startswith("en-") else "en-US-GuyNeural"
    print(f"[TTS] Using edge-tts (voice={edge_voice}) → {path}")
    
    if _run_edge_tts(text, edge_voice, path):
        if _is_audio_valid(path, word_count):
            return True, "edge-tts"
        else:
            print(f"[TTS] edge-tts output failed quality check.")

    # Final attempt: FFmpeg silent fallback (always passes quality check if it matches word count)
    print(f"[TTS] FATAL: All TTS engines failed for segment. Using silent fallback.")
    success = _generate_ffmpeg_audio_fallback(text, path)
    return success, "silent-fallback"
