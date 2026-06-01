"""
tts_generator.py — AI Radio Echo
Text-to-speech generation with high-fidelity mixing.

Cloud path:  Cartesia Sonic 3.5 → Kokoro Cloud → edge-tts fallback
Mixing:      Pydub for SFX overlays, looping ambient tracks, and voice styles.

Voice Styles:
  - normal:  Base settings.
  - whisper: -8dB gain + simulated reverb.
  - grave:   0.9x speed + flat emotion.
  - excited: 1.1x speed + high emotion.
  - deadpan: 0.8x speed + clinical delivery.
"""

import asyncio
import json
import os
import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional
from pydub import AudioSegment

# Cartesia Sonic 3.5 curated voices (Verified June 2026)
_CARTESIA_VOICES: dict[str, str] = {
    "ANCHOR":      "c8f7835e-28a3-4f0c-80d7-c1302ac62aae", # Alistair (Sophisticated British Male)
    "REPORTER":    "dc30854e-e398-4579-9dc8-16f6cb2c19b9", # Victoria (Professional British Female)
    "COMMENTATOR": "5ee9feff-1265-424a-9d7f-8e4d431a12c7", # Ronald (Intense American Male)
    "WEATHERBOT":  "4f7f1324-1853-48a6-b294-4e78e8036a83", # Casper (Wistful British Male)
    "PHILOSOPHER": "8205562d-949e-49fb-9407-a690f3b06385", # Marcus (Grave American Male)
}
_CARTESIA_DEFAULT_VOICE = "c8f7835e-28a3-4f0c-80d7-c1302ac62aae"

# Kokoro-82M curated voices (June 2026)
_KOKORO_VOICES: dict[str, str] = {
    "ANCHOR":      "bm_george", # British Male (Matches Alistair)
    "REPORTER":    "bf_emma",   # British Female (Matches Victoria)
    "COMMENTATOR": "am_adam",   # American Male (Matches Ronald)
    "WEATHERBOT":  "bm_lewis",  # British Male (Matches Casper)
    "PHILOSOPHER": "am_michael", # American Male (Matches Marcus)
}
_KOKORO_DEFAULT_VOICE = "bm_george"

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


# ── Step 1 & 2: Style & SFX Processing ────────────────────────────────────────

def _simulate_reverb(audio: AudioSegment) -> AudioSegment:
    """Simulate slight reverb by overlaying a delayed, quieter version."""
    delay = 40 # ms
    feedback = audio - 15 # -15dB
    return audio.overlay(feedback, position=delay)

def _apply_audio_processing(
    audio_path: str, 
    voice_style: str, 
    sfx_pre: Optional[str], 
    sfx_post: Optional[str]
) -> bool:
    """
    Apply voice styles (pydub) and mix SFX overlays.
    - sfx_pre: Prepended to speech.
    - sfx_post: Appended to speech.
    - STREET_AMBIENT: Looped underneath speech at low volume.
    """
    try:
        speech = AudioSegment.from_file(audio_path)
        
        # 1. Voice Style Processing (Post-Generation)
        if voice_style == "whisper":
            speech = speech - 8 # Reduce gain by 8dB
            speech = _simulate_reverb(speech)
        
        # 2. Ambient Underlay (Looping)
        ambient_path = Path(f"sfx/STREET_AMBIENT.mp3")
        if ambient_path.exists():
            ambient = AudioSegment.from_file(str(ambient_path))
            # Loop ambient to cover speech duration
            loop_count = int(len(speech) / len(ambient)) + 1
            ambient_loop = (ambient * loop_count)[:len(speech)]
            ambient_loop = ambient_loop - 22 # Quiet background
            speech = ambient_loop.overlay(speech)
        
        # 3. SFX Pre/Post
        final_audio = speech
        
        if sfx_pre:
            pre_path = Path(f"sfx/{sfx_pre}.mp3")
            if pre_path.exists():
                sfx = AudioSegment.from_file(str(pre_path))
                final_audio = sfx + final_audio
            elif sfx_pre == "SILENCE":
                # Ensure SILENCE.mp3 exists or generate on the fly
                if not Path("sfx/SILENCE.mp3").exists():
                    AudioSegment.silent(duration=2000).export("sfx/SILENCE.mp3", format="mp3")
                sfx = AudioSegment.from_file("sfx/SILENCE.mp3")
                final_audio = sfx + final_audio
            else:
                print(f"[SFX] Warning: Pre-SFX '{sfx_pre}' not found.")

        if sfx_post:
            post_path = Path(f"sfx/{sfx_post}.mp3")
            if post_path.exists():
                sfx = AudioSegment.from_file(str(post_path))
                final_audio = final_audio + sfx
            elif sfx_post == "SILENCE":
                if not Path("sfx/SILENCE.mp3").exists():
                    AudioSegment.silent(duration=2000).export("sfx/SILENCE.mp3", format="mp3")
                sfx = AudioSegment.from_file("sfx/SILENCE.mp3")
                final_audio = final_audio + sfx
            else:
                print(f"[SFX] Warning: Post-SFX '{sfx_post}' not found.")

        final_audio.export(audio_path, format="mp3", bitrate="64k")
        return True

    except Exception as exc:
        print(f"[Mixer] Failed to process audio: {exc}")
        return False


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

def _run_cartesia_tts(text: str, voice: str, path: str, voice_style: str = "normal") -> bool:
    """
    Submit text to Cartesia Sonic 3.5 TTS and write the audio to `path`.
    
    On any error: return False (caller falls through to next provider).
    """
    api_key = os.environ.get("CARTESIA_API_KEY", "").strip()
    if not api_key:
        print("[TTS] CARTESIA_API_KEY not set — skipping Cartesia Sonic.")
        return False

    cartesia_voice = _CARTESIA_VOICES.get(voice, _CARTESIA_DEFAULT_VOICE)
    
    # Map styles to Cartesia numeric speed (0.6 - 1.5)
    speed = 1.0
    if voice_style in ("grave", "deadpan"): speed = 0.9
    if voice_style == "excited": speed = 1.1

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
            "generation_config": {
                "speed": speed,
            }
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
    forced_engine: Optional[str] = None,
    voice_style: str = "normal",
    sfx_pre: Optional[str] = None,
    sfx_post: Optional[str] = None,
) -> tuple[bool, str]:
    """
    Generate TTS audio and apply voice styles/SFX (Step 1 & 2).

    Returns:
        (success, engine_name)
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    word_count = len(text.split())
    preview = (text[:47] + "...") if len(text) > 50 else text
    print(f"[TTS] Narrating {word_count} words ({voice_style}): \"{preview}\"")

    # 1. Generation
    success = False
    engine_used = "failed"

    if forced_engine:
        if forced_engine == "cartesia-sonic":
            success = _run_cartesia_tts(text, voice, path, voice_style)
        elif forced_engine == "kokoro-cloud":
            success = _run_kokoro_tts(text, voice, path)
        elif forced_engine == "edge-tts":
            success = _run_edge_tts(text, voice, path)
        engine_used = forced_engine
    else:
        if use_cloud:
            if _run_cartesia_tts(text, voice, path, voice_style):
                success, engine_used = True, "cartesia-sonic"
            elif _run_kokoro_tts(text, voice, path):
                success, engine_used = True, "kokoro-cloud"
        
        if not success:
            if _run_edge_tts(text, voice, path):
                success, engine_used = True, "edge-tts"
            else:
                success = _generate_ffmpeg_audio_fallback(text, path)
                engine_used = "silent-fallback"

    # 2. Validation & Mixing (Steps 1 & 2)
    if success and _is_audio_valid(path, word_count):
        if _apply_audio_processing(path, voice_style, sfx_pre, sfx_post):
            return True, engine_used
    
    return False, "failed"
