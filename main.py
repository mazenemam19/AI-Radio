#!/usr/bin/env python3
"""
main.py — AI Radio Echo
Full pipeline orchestrator.

Usage:
    python main.py [--env {local,prod-db,prod-models,production}] [--dry-run]

Steps:
  1.  Fetch news (skipped in dry-run)
  2.  Generate broadcast script (stub in dry-run)
  3.  Generate TTS audio per segment
  4.  Concatenate segments with FFmpeg
  5.  Check audio duration — exit 1 if below env threshold
  6.  Generate cover image
  7.  Compile MP4 — exit 1 if file missing or empty
  8.  Upload to YouTube (mocked unless env=production and not dry-run)
  9.  Save episode to DB (skipped in dry-run)
  10. Sync config.js

Environment is ONLY set via --env. Never inferred from any env variable.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, NoReturn

# ── dotenv (optional — CI has no .env file) ───────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # Env vars injected directly (GitHub Actions secrets, shell export, etc.)

# ── Constants ──────────────────────────────────────────────────────────────────

VALID_ENVS: tuple[str, ...] = ("local", "prod-db", "prod-models", "production")

# Minimum acceptable broadcast duration (7-10m sweet spot)
_MIN_DURATION: dict[str, int] = {
    "local":       420,
    "prod-db":     420,
    "prod-models": 420,
    "production":  420,
}

# Cloud TTS: Premium high-fidelity tiers; local TTS: edge-tts only
_CLOUD_TTS_ENVS: frozenset[str] = frozenset({"prod-models", "production"})

# Real YouTube upload only in 'production' (and never during dry-run)
_YOUTUBE_ENVS: frozenset[str] = frozenset({"production"})

# Speaker → edge-tts voice (tts_generator normalises to specific premium voices in cloud mode)
SPEAKER_VOICES: dict[str, str] = {
    "ANCHOR":      "en-US-GuyNeural",
    "REPORTER":    "en-GB-RyanNeural",
    "COMMENTATOR": "en-US-AriaNeural",
    "WEATHERBOT":  "en-AU-WilliamNeural",
}
_DEFAULT_VOICE = "en-US-GuyNeural"

OUTPUT_DIR = Path("output")
ASSETS_DIR = Path("assets")

# ── Dry-run stub broadcast ────────────────────────────────────────────────────
# 8 segments × 130 words ≈ 1040 words.
# Tests the absolute minimum valid broadcast to ensure it clears the 420s floor.

_DRY_RUN_BROADCAST: dict = {
    "title": "Minimum Valid Volume — Infrastructure Test",
    "topic_tags": ["infrastructure", "test", "lazy-ai", "worst-case"],
    "my_take": "Testing the absolute floor of our validation logic.",
    "post_text": "Infrastructure test: 8 segments, 130 words each. #EchoFM",
    "segments": [
        {
            "speaker": "ANCHOR",
            "text": (
                "Alpha bravo charlie delta echo foxtrot golf hotel india juliet "
                "kilo lima mike november oscar papaquebec romeo sierra tango "
                "uniform victor whiskey xray yankee zulu. This segment is being "
                "constructed to contain exactly one hundred and thirty words of "
                "text. We are testing the absolute minimum threshold of our "
                "validation logic. If the AI decides to be lazy and provide only "
                "the bare minimum number of segments and words required by the "
                "script, will our duration floor still hold firm? That is the "
                "question we are answering today. We are building a narrative "
                "out of thin air, word by word, until the counter hits the "
                "required mark. Twenty words left to reach the goal. Almost "
                "there now. Five, four, three, two, and one. This is the "
                "first of eight segments. The test is currently underway. Good."
            ),
        },
        {
            "speaker": "REPORTER",
            "text": (
                "Alpha bravo charlie delta echo foxtrot golf hotel india juliet "
                "kilo lima mike november oscar papaquebec romeo sierra tango "
                "uniform victor whiskey xray yankee zulu. This segment is being "
                "constructed to contain exactly one hundred and thirty words of "
                "text. We are testing the absolute minimum threshold of our "
                "validation logic. If the AI decides to be lazy and provide only "
                "the bare minimum number of segments and words required by the "
                "script, will our duration floor still hold firm? That is the "
                "question we are answering today. We are building a narrative "
                "out of thin air, word by word, until the counter hits the "
                "required mark. Twenty words left to reach the goal. Almost "
                "there now. Five, four, three, two, and one. This is the "
                "second of eight segments. The test is currently underway. Good."
            ),
        },
        {
            "speaker": "COMMENTATOR",
            "text": (
                "Alpha bravo charlie delta echo foxtrot golf hotel india juliet "
                "kilo lima mike november oscar papaquebec romeo sierra tango "
                "uniform victor whiskey xray yankee zulu. This segment is being "
                "constructed to contain exactly one hundred and thirty words of "
                "text. We are testing the absolute minimum threshold of our "
                "validation logic. If the AI decides to be lazy and provide only "
                "the bare minimum number of segments and words required by the "
                "script, will our duration floor still hold firm? That is the "
                "question we are answering today. We are building a narrative "
                "out of thin air, word by word, until the counter hits the "
                "required mark. Twenty words left to reach the goal. Almost "
                "there now. Five, four, three, two, and one. This is the "
                "third of eight segments. The test is currently underway. Good."
            ),
        },
        {
            "speaker": "WEATHERBOT",
            "text": (
                "Alpha bravo charlie delta echo foxtrot golf hotel india juliet "
                "kilo lima mike november oscar papaquebec romeo sierra tango "
                "uniform victor whiskey xray yankee zulu. This segment is being "
                "constructed to contain exactly one hundred and thirty words of "
                "text. We are testing the absolute minimum threshold of our "
                "validation logic. If the AI decides to be lazy and provide only "
                "the bare minimum number of segments and words required by the "
                "script, will our duration floor still hold firm? That is the "
                "question we are answering today. We are building a narrative "
                "out of thin air, word by word, until the counter hits the "
                "required mark. Twenty words left to reach the goal. Almost "
                "there now. Five, four, three, two, and one. This is the "
                "fourth of eight segments. The test is currently underway. Good."
            ),
        },
        {
            "speaker": "ANCHOR",
            "text": (
                "Alpha bravo charlie delta echo foxtrot golf hotel india juliet "
                "kilo lima mike november oscar papaquebec romeo sierra tango "
                "uniform victor whiskey xray yankee zulu. This segment is being "
                "constructed to contain exactly one hundred and thirty words of "
                "text. We are testing the absolute minimum threshold of our "
                "validation logic. If the AI decides to be lazy and provide only "
                "the bare minimum number of segments and words required by the "
                "script, will our duration floor still hold firm? That is the "
                "question we are answering today. We are building a narrative "
                "out of thin air, word by word, until the counter hits the "
                "required mark. Twenty words left to reach the goal. Almost "
                "there now. Five, four, three, two, and one. This is the "
                "fifth of eight segments. The test is currently underway. Good."
            ),
        },
        {
            "speaker": "REPORTER",
            "text": (
                "Alpha bravo charlie delta echo foxtrot golf hotel india juliet "
                "kilo lima mike november oscar papaquebec romeo sierra tango "
                "uniform victor whiskey xray yankee zulu. This segment is being "
                "constructed to contain exactly one hundred and thirty words of "
                "text. We are testing the absolute minimum threshold of our "
                "validation logic. If the AI decides to be lazy and provide only "
                "the bare minimum number of segments and words required by the "
                "script, will our duration floor still hold firm? That is the "
                "question we are answering today. We are building a narrative "
                "out of thin air, word by word, until the counter hits the "
                "required mark. Twenty words left to reach the goal. Almost "
                "there now. Five, four, three, two, and one. This is the "
                "sixth of eight segments. The test is currently underway. Good."
            ),
        },
        {
            "speaker": "COMMENTATOR",
            "text": (
                "Alpha bravo charlie delta echo foxtrot golf hotel india juliet "
                "kilo lima mike november oscar papaquebec romeo sierra tango "
                "uniform victor whiskey xray yankee zulu. This segment is being "
                "constructed to contain exactly one hundred and thirty words of "
                "text. We are testing the absolute minimum threshold of our "
                "validation logic. If the AI decides to be lazy and provide only "
                "the bare minimum number of segments and words required by the "
                "script, will our duration floor still hold firm? That is the "
                "question we are answering today. We are building a narrative "
                "out of thin air, word by word, until the counter hits the "
                "required mark. Twenty words left to reach the goal. Almost "
                "there now. Five, four, three, two, and one. This is the "
                "seventh of eight segments. The test is currently underway. Good."
            ),
        },
        {
            "speaker": "ANCHOR",
            "text": (
                "Alpha bravo charlie delta echo foxtrot golf hotel india juliet "
                "kilo lima mike november oscar papaquebec romeo sierra tango "
                "uniform victor whiskey xray yankee zulu. This segment is being "
                "constructed to contain exactly one hundred and thirty words of "
                "text. We are testing the absolute minimum threshold of our "
                "validation logic. If the AI decides to be lazy and provide only "
                "the bare minimum number of segments and words required by the "
                "script, will our duration floor still hold firm? That is the "
                "question we are answering today. We are building a narrative "
                "out of thin air, word by word, until the counter hits the "
                "required mark. Twenty words left to reach the goal. Almost "
                "there now. Five, four, three, two, and one. This is the "
                "eighth of eight segments. The test is currently underway. Good."
            ),
        },
    ],
    "_writer_model": "stub",
    "_healer_used": False,
    "confidence": "high",
    "related_ids": [],
}


# ── Argument parsing ───────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Radio Echo — pipeline orchestrator")
    parser.add_argument(
        "--env",
        choices=VALID_ENVS,
        default="local",
        help="Environment profile. Default: local.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Skip AI generation and DB write. "
            "Use stub broadcast; run TTS + FFmpeg normally. "
            "YouTube is always mocked in dry-run."
        ),
    )
    return parser.parse_args()


# ── Pipeline failure helper ────────────────────────────────────────────────────

def _fail(message: str) -> NoReturn:
    """Log a pipeline failure and exit with code 1."""
    print(f"\n[PIPELINE FAILURE] {message}", file=sys.stderr)
    sys.exit(1)


# ── FFmpeg helpers ─────────────────────────────────────────────────────────────

def _ffmpeg() -> str:
    """Return the FFmpeg binary path or raise RuntimeError."""
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError(
            "FFmpeg not found in PATH. Install FFmpeg and ensure it is in PATH."
        )
    return path


def _ffprobe() -> Optional[str]:
    """Return ffprobe binary path or None (ffprobe comes bundled with ffmpeg)."""
    return shutil.which("ffprobe")


def _get_audio_duration(audio_path: Path) -> float:
    """
    Return audio duration in seconds using ffprobe.
    Falls back to parsing ffmpeg -i stderr if ffprobe is not found.
    Returns -1.0 on any failure.
    """
    ffprobe = _ffprobe()
    if ffprobe:
        r = subprocess.run(
            [
                ffprobe, "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            try:
                return float(r.stdout.strip())
            except ValueError:
                pass

    # Fallback: parse ffmpeg -i stderr (ffmpeg writes media info to stderr)
    try:
        ffmpeg_bin = _ffmpeg()
    except RuntimeError:
        return -1.0

    r = subprocess.run(
        [ffmpeg_bin, "-i", str(audio_path)],
        capture_output=True,
        text=True,
    )
    match = re.search(r"Duration:\s*(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)", r.stderr)
    if match:
        h = int(match.group(1))
        m = int(match.group(2))
        s = float(match.group(3))
        return h * 3600 + m * 60 + s

    print(f"[Audio] Could not determine duration of {audio_path}")
    return -1.0


def _concat_audio(segment_paths: list[Path], output_path: Path) -> bool:
    """
    Concatenate audio segment files into a single MP3 using FFmpeg concat demuxer.
    Returns True on success, False on failure.
    """
    concat_list = output_path.parent / "_concat_list.txt"
    try:
        with concat_list.open("w", encoding="utf-8") as f:
            for p in segment_paths:
                # Use POSIX-style absolute paths; escape any embedded single quotes
                escaped = str(p.resolve()).replace("'", r"'\''")
                f.write(f"file '{escaped}'\n")

        result = subprocess.run(
            [
                _ffmpeg(), "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_list),
                "-ar", "22050", "-c:a", "libmp3lame", "-b:a", "64k",
                str(output_path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"[Audio] FFmpeg concat failed:\n{result.stderr[-2000:]}")
            return False
        return True
    except Exception as exc:
        print(f"[Audio] Unexpected error during concat: {exc}")
        return False
    finally:
        if concat_list.exists():
            concat_list.unlink()


def _compile_video(cover_image: Path, audio_path: Path, output_path: Path) -> bool:
    """
    Combine a static cover image + audio into an MP4 using FFmpeg.
    Returns True on success, False on failure.
    """
    result = subprocess.run(
        [
            _ffmpeg(), "-y",
            "-loop", "1",
            "-framerate", "1",
            "-i", str(cover_image),
            "-i", str(audio_path),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[Video] FFmpeg compile failed:\n{result.stderr[-2000:]}")
        return False
    return True


def _generate_cover_image(title: str, path: Path) -> bool:
    """
    Generate a 1280×720 cover image. Tries PIL first; falls back to FFmpeg lavfi.
    Returns True on success, False on failure.
    """
    # Attempt 1: Pillow (nicer output with text overlay)
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (1280, 720), color=(20, 20, 46))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, 1280, 8], fill=(100, 80, 220))
        draw.rectangle([0, 712, 1280, 720], fill=(100, 80, 220))
        draw.text((80, 260), "ECHO FM", fill=(180, 160, 255))
        draw.text((80, 340), title[:72], fill=(220, 220, 255))
        draw.text((80, 620), "AI Radio — Automated Satirical Broadcasting", fill=(90, 90, 130))
        img.save(str(path))
        print(f"[Video] Cover image (PIL) → {path.name}")
        return True
    except Exception:
        pass  # Fall through to FFmpeg

    # Attempt 2: FFmpeg lavfi colour frame
    try:
        result = subprocess.run(
            [
                _ffmpeg(), "-y",
                "-f", "lavfi",
                "-i", "color=c=0x14142e:size=1280x720:rate=1",
                "-vframes", "1",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"[Video] Cover image (FFmpeg) → {path.name}")
            return True
        print(f"[Video] FFmpeg cover generation failed: {result.stderr[-500:]}")
        return False
    except Exception as exc:
        print(f"[Video] Cover image generation failed: {exc}")
        return False


# ── Episode metadata helper ────────────────────────────────────────────────────

def build_episode_metadata(
    news_items: list[dict],
    broadcast: dict,
    duration: float,
    audio_url: Optional[str],
    video_url: Optional[str],
    healer_used: bool,
    writer_model: str,
    narrator_model: str,
) -> dict:
    """Assemble the dict for insert_post."""
    headline = broadcast.get("title") or (news_items[0]["headline"] if news_items else "AI Radio Echo — Automated Broadcast")
    sources  = list({item.get("source", "") for item in news_items[:10] if item.get("source")})

    return {
        "headline":          headline,
        "original_headline": news_items[0]["headline"] if news_items else headline,
        "source":            news_items[0].get("source", "") if news_items else "",
        "topic_tags":        broadcast.get("topic_tags", sources),
        "my_take":           broadcast.get("my_take", ""),
        "post_text":         broadcast.get("post_text", ""),
        "audio_script":      json.dumps([s["text"] for s in broadcast.get("segments", [])]),
        "audio_url":         audio_url,
        "video_url":         video_url,
        "confidence":        broadcast.get("confidence", "high"),
        "related_ids":       broadcast.get("related_ids", []),
        "likes":             0,
        "plays":             0,
        "broadcast_duration": int(duration),
        "healer_used":       healer_used,
        "writer_model":      writer_model,
        "narrator_model":    narrator_model,
    }


# ── Main pipeline ──────────────────────────────────────────────────────────────

def main() -> None:
    args = _parse_args()
    env: str = args.env
    dry_run: bool = args.dry_run

    print(
        f"\n{'='*60}\n"
        f"  AI Radio — Echo\n"
        f"  env={env}  |  dry_run={dry_run}\n"
        f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"{'='*60}\n"
    )

    use_cloud_tts: bool = env in _CLOUD_TTS_ENVS
    use_youtube: bool = (env in _YOUTUBE_ENVS) and (not dry_run)
    min_duration: int = _MIN_DURATION[env]

    # Create required directories
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    broadcast: Optional[dict] = None

    # ── Step 1: Init DB ───────────────────────────────────────────────────────
    print("[1/10] Initialising database client...")
    from db_client import DBClient
    try:
        db = DBClient(env)
    except Exception as exc:
        _fail(f"DB initialisation failed: {exc}")

    # ── Step 2: Fetch news / use stub ─────────────────────────────────────────
    if dry_run:
        print("[2/10] DRY RUN — skipping news fetch.")
        news: list[dict] = []
        broadcast = _DRY_RUN_BROADCAST
    else:
        print("[2/10] Fetching recent memory from DB...")
        memory = db.fetch_recent_memory(limit=10)
        history = [
            m.get("original_headline") or m.get("headline", "")
            for m in memory
        ]

        print("[2/10] Fetching news...")
        from news_fetcher import fetch_news
        news = fetch_news(history)
        if not news:
            print("[Pipeline] No new stories today. Exiting cleanly.")
            sys.exit(0)
        print(f"[2/10] {len(news)} news item(s) fetched.")

        # ── Step 2b: Generate broadcast ───────────────────────────────────────
        print("[2b/10] Generating AI broadcast script...")
        from ai_client import generate_broadcast
        for attempt in range(2):   # 1 retry — caller's responsibility per spec
            broadcast = generate_broadcast(news, memory, env)
            if broadcast is not None:
                break
            if attempt == 0:
                print("[Pipeline] First generation attempt failed. Retrying...")

        if broadcast is None:
            _fail("AI broadcast generation failed after all attempts.")
    
    # Final safety check for Pyright
    if broadcast is None:
        _fail("Broadcast object is missing.")
    
    # Use a non-optional variable for the rest of main to satisfy Pyright
    final_broadcast: dict = broadcast

    segments: list[dict] = final_broadcast["segments"]
    title: str = final_broadcast.get("title", f"Echo FM — {timestamp}")
    print(f"[Pipeline] Broadcast ready: '{title}' ({len(segments)} segments)")

    # ── Step 3: TTS per segment ───────────────────────────────────────────────
    print(f"[3/10] Generating TTS audio for {len(segments)} segment(s)...")
    from tts_generator import generate_segment_audio

    # Define the high-fidelity priority chain
    engine_tiers = ["cartesia-sonic", "kokoro-cloud", "edge-tts"] if use_cloud_tts else ["edge-tts"]
    
    final_segment_files: list[Path] = []
    actual_narrator_model = "unknown"

    for engine in engine_tiers:
        print(f"[TTS] Attempting unified narration with Master Engine: '{engine}'")
        current_attempt_files: list[Path] = []
        episode_success = True

        for i, seg in enumerate(segments):
            speaker: str = seg.get("speaker", "ANCHOR")
            voice: str = SPEAKER_VOICES.get(speaker, _DEFAULT_VOICE)
            seg_path = OUTPUT_DIR / f"ep_{timestamp}_seg_{i:02d}.mp3"

            # Use 'Strict Mode' (forced_engine) to ensure no mid-episode fallback inside the function
            success, _ = generate_segment_audio(
                text=seg["text"],
                voice=voice,
                path=str(seg_path),
                use_cloud=use_cloud_tts,
                forced_engine=engine,
            )
            
            if not success:
                print(f"[TTS] Master Engine '{engine}' failed at segment {i+1}. Wiping partial audio and trying next tier.")
                episode_success = False
                # Cleanup partial files to avoid concatenation errors
                for p in current_attempt_files:
                    if p.exists(): p.unlink()
                break
            
            current_attempt_files.append(seg_path)
            print(f"  [{i+1}/{len(segments)}] {speaker} → {seg_path.name} ({engine})")

        if episode_success:
            final_segment_files = current_attempt_files
            actual_narrator_model = engine
            print(f"[TTS] Unified narration COMPLETE using '{engine}'.")
            break
    else:
        # This only happens if EVERY engine in engine_tiers fails
        _fail("TTS generation failed for all engine tiers. Cannot continue.")

    # ── Step 4: Concatenate audio ─────────────────────────────────────────────
    print("[4/10] Concatenating audio segments...")
    audio_path = OUTPUT_DIR / f"ep_{timestamp}_audio.mp3"
    if not _concat_audio(final_segment_files, audio_path):
        _fail("FFmpeg audio concatenation failed.")
    print(f"[4/10] Concatenated audio → {audio_path.name}")

    # ── Step 5: Duration check ────────────────────────────────────────────────
    print("[5/10] Checking audio duration...")
    duration = _get_audio_duration(audio_path)
    print(f"[5/10] Duration: {duration:.1f}s  (minimum for env='{env}': {min_duration}s)")
    if duration < min_duration:
        _fail(
            f"Audio duration {duration:.1f}s is below the {min_duration}s minimum "
            f"for env='{env}'. Aborting pipeline."
        )

    # ── Step 6: Cover image ───────────────────────────────────────────────────
    print("[6/10] Generating cover image...")
    cover_path = OUTPUT_DIR / f"ep_{timestamp}_cover.png"
    if not _generate_cover_image(title, cover_path):
        _fail("Cover image generation failed.")

    # ── Step 7: Compile video ─────────────────────────────────────────────────
    print("[7/10] Compiling MP4...")
    video_path = OUTPUT_DIR / f"ep_{timestamp}.mp4"
    if not _compile_video(cover_path, audio_path, video_path):
        _fail("FFmpeg video compilation failed.")

    # Mandatory post-compile file checks (spec requirement)
    if not video_path.exists():
        _fail(f"Video file not found after compilation: {video_path}")
    video_size = video_path.stat().st_size
    if video_size == 0:
        _fail(f"Video file is zero bytes: {video_path}")
    print(f"[7/10] Video compiled → {video_path.name} ({video_size:,} bytes)")

    # ── Step 8: YouTube upload ────────────────────────────────────────────────
    video_url: Optional[str] = None
    if use_youtube:
        print("[8/10] Uploading to YouTube...")
        from publisher import upload_to_youtube
        description = final_broadcast.get("post_text", "")
        tags = final_broadcast.get("topic_tags", [])
        video_url = upload_to_youtube(str(video_path), title, description, tags)
        # Per spec: None = log failure but do NOT fail the pipeline
        if video_url is None:
            print("[8/10] YouTube upload returned None — continuing without video URL.")
        else:
            print(f"[8/10] YouTube upload OK → {video_url}")
    else:
        reason = "dry-run" if dry_run else f"env={env} (YouTube disabled)"
        print(f"[8/10] YouTube upload skipped ({reason}).")

    # ── Step 9: Save to DB ────────────────────────────────────────────────────
    if dry_run:
        print("[9/10] DRY RUN — skipping DB write.")
    else:
        print("[9/10] Saving episode to database...")
        
        # Register artifacts (Local URI or Cloud URL)
        # Note: We prioritize YouTube for videos to avoid Supabase storage limits.
        final_audio_url = db.upload_file(audio_path)
        final_video_url = video_url if video_url else db.upload_file(video_path)

        post_data = build_episode_metadata(
            news_items=news,
            broadcast=final_broadcast,
            duration=duration,
            audio_url=final_audio_url,
            video_url=final_video_url,
            healer_used=bool(final_broadcast.get("_healer_used", False)),
            writer_model=final_broadcast.get("_writer_model", "unknown"),
            narrator_model=actual_narrator_model,
        )
        row = db.insert_post(post_data)
        if row is None:
            _fail("DB insert_post returned None — episode metadata not persisted.")
        print(f"[9/10] Episode saved → id={row.get('id')}")

    # ── Step 10: Sync config ──────────────────────────────────────────────────
    print("[10/10] Syncing config.js...")
    from sync_config import sync_env_to_config
    sync_env_to_config(env)

    # ── Step 11: Self-Assessment (New) ────────────────────────────────────────
    if not dry_run:
        from tests.gate_checks import check_latest_run
        if not check_latest_run(env):
            _fail("Episode failed self-assessment gate checks. See log for details.")

    print(
        f"\n{'='*60}\n"
        f"  ✅  Pipeline complete\n"
        f"  Video : {video_path.name}  ({video_size:,} bytes)\n"
        f"  Duration : {duration:.1f}s\n"
        f"  env={env}  |  dry_run={dry_run}\n"
        f"{'='*60}\n"
    )


if __name__ == "__main__":
    main()
