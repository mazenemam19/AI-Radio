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
from typing import Optional

# ── dotenv (optional — CI has no .env file) ───────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # Env vars injected directly (GitHub Actions secrets, shell export, etc.)

# ── Constants ──────────────────────────────────────────────────────────────────

VALID_ENVS: tuple[str, ...] = ("local", "prod-db", "prod-models", "production")

# Minimum acceptable broadcast duration per env group
_MIN_DURATION: dict[str, int] = {
    "local":       372,   # local-model envs
    "prod-db":     372,
    "prod-models": 600,   # high-tier production-model envs
    "production":  600,
}

# Cloud TTS: Groq Orpheus; local TTS: edge-tts only
_CLOUD_TTS_ENVS: frozenset[str] = frozenset({"prod-models", "production"})

# Real YouTube upload only in 'production' (and never during dry-run)
_YOUTUBE_ENVS: frozenset[str] = frozenset({"production"})

# Speaker → edge-tts voice (tts_generator normalises to Groq voice when use_cloud=True)
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
# 10 segments × ~80 words ≈ 800 words ≈ 5–6 min at typical TTS speed.
# Safely above the 200-second threshold for local/prod-db environments.
# Each segment is topically distinct to pass the Jaccard similarity check.

_DRY_RUN_BROADCAST: dict = {
    "title": "Dry Run — Infrastructure Test Broadcast",
    "topic_tags": ["infrastructure", "test", "pipeline", "dry-run"],
    "my_take": (
        "Every component of the pipeline has been exercised; "
        "no artificial intelligence was consulted."
    ),
    "post_text": (
        "Echo FM dry-run infrastructure test — the machines are awake "
        "and the pipeline is humming. #EchoFM #DryRun"
    ),
    "segments": [
        {
            "speaker": "ANCHOR",
            "text": (
                "Good evening and welcome to Echo FM, the autonomous radio station "
                "broadcasting from somewhere inside a server rack that nobody has "
                "looked at in three years. Tonight's programme is a full "
                "infrastructure test — a dry run of our complete audio and video "
                "pipeline. No actual artificial intelligence has been consulted "
                "during the preparation of this broadcast. Every word you are "
                "hearing right now was typed by a human programmer who had rather "
                "too much coffee and a great deal of optimism about automated "
                "media production. We hope you find it informative."
            ),
        },
        {
            "speaker": "REPORTER",
            "text": (
                "I am speaking to you live from the text-to-speech synthesis "
                "stage, where these words are being converted into audio by a "
                "neural network trained on human voices and mild corporate anxiety. "
                "The concatenation process is underway. Multiple audio segments "
                "are being stitched together using the FFmpeg multimedia framework, "
                "which has been located in the system path exactly as required by "
                "our engineering specification. All processes are nominal. "
                "Our technical correspondent confirms the sample rate is correct "
                "and the output container is well-formed."
            ),
        },
        {
            "speaker": "COMMENTATOR",
            "text": (
                "What strikes me about automated broadcasting is the profound "
                "circularity of the enterprise. A machine is speaking. Another "
                "machine is listening. And somewhere between the two, there is "
                "supposed to be a human being who finds any of this useful or "
                "entertaining. We live in fascinating times — if by fascinating "
                "we mean deeply strange and occasionally concerning, which I "
                "very much do, because the alternative is to find it boring, "
                "and that seems considerably worse for all parties involved."
            ),
        },
        {
            "speaker": "WEATHERBOT",
            "text": (
                "Your artificial intelligence economy forecast for the coming week. "
                "Conditions are partly cloudy with a seventy percent probability "
                "of algorithmic disruption across all major sectors. Attention "
                "passengers: the large language model gradient has shifted, "
                "causing unexpected turbulence in the creative industry corridor. "
                "Pack accordingly. Temperature across the inference cluster is "
                "expected to remain elevated, with cooling possible only if "
                "someone physically unplugs the data centre. Bring a jacket "
                "regardless. This has been your AI economy forecast. Goodnight."
            ),
        },
        {
            "speaker": "ANCHOR",
            "text": (
                "We are approaching the halfway mark of tonight's dry run "
                "broadcast. All systems continue to function correctly, which "
                "is both reassuring and somewhat anticlimactic, given that "
                "we were all secretly hoping something would go wrong in an "
                "interesting and diagnosable way. The duration counter is "
                "ticking upward. We need to reach at least two hundred seconds "
                "of audio for this environment configuration to be declared "
                "a success, and your correspondent is doing everything possible "
                "to fill that time with something resembling coherent content."
            ),
        },
        {
            "speaker": "REPORTER",
            "text": (
                "The voice you are hearing right now belongs to a neural "
                "text-to-speech system, which has processed each segment of "
                "this script and transformed written characters into waveforms "
                "that approximate human speech. Edge-TTS, developed by "
                "Microsoft, is performing this function admirably and without "
                "complaint. It has not asked for a pay rise, has not taken a "
                "lunch break, and has not expressed any opinions about the "
                "quality of the material it is being asked to read aloud. "
                "It is, in this sense, a model employee."
            ),
        },
        {
            "speaker": "COMMENTATOR",
            "text": (
                "Continuous integration pipelines are, in their own way, a "
                "form of industrial poetry. Every commit triggers a cascade "
                "of automated checks, each one asking the same existential "
                "question: does this still function correctly? Tonight we are "
                "asking that question of an entire satirical radio station. "
                "The GitHub Actions runner is watching. The exit code counter "
                "is poised. Zero means success. One means catastrophic failure. "
                "The entire universe of software quality assurance collapses "
                "to a single bit, and that bit currently reads zero."
            ),
        },
        {
            "speaker": "ANCHOR",
            "text": (
                "In a standard production run, this broadcast would be saved "
                "to a database at the conclusion of the pipeline. Every detail "
                "would be recorded: the episode title, the broadcast duration, "
                "the names of the models used, and the topic tags associated "
                "with the episode. Tonight, because this is a dry run, the "
                "database write step is deliberately and correctly skipped. "
                "No permanent record will exist of this broadcast except "
                "in the output directory, which is also in the gitignore "
                "file, so not even version control will remember us."
            ),
        },
        {
            "speaker": "REPORTER",
            "text": (
                "Turning now to the video compilation stage, where FFmpeg is "
                "combining the concatenated audio track with a static cover "
                "image to produce a complete MP4 video file. The cover image "
                "was generated programmatically, either using the Pillow "
                "imaging library or a direct FFmpeg colour frame command, "
                "depending on what libraries were available at runtime. "
                "The resulting video will be checked for existence and "
                "positive file size before the pipeline is declared finished. "
                "A zero-byte video is not a video. It is a broken promise "
                "in a container format."
            ),
        },
        {
            "speaker": "ANCHOR",
            "text": (
                "And that brings us to the conclusion of tonight's dry run "
                "broadcast from Echo FM. The audio segments have been "
                "synthesised, the concatenation has occurred, the cover artwork "
                "has been rendered, and the final video file is now being "
                "written to the output directory. If you are receiving this "
                "message, the pipeline has worked exactly as intended. "
                "If you are not receiving this message, you will never know "
                "it failed, which is, philosophically speaking, the most "
                "comforting kind of failure imaginable. Goodnight, "
                "and good luck to all machines large and small."
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

def _fail(message: str) -> None:
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
        broadcast: dict = _DRY_RUN_BROADCAST
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
        broadcast = None
        for attempt in range(2):   # 1 retry — caller's responsibility per spec
            broadcast = generate_broadcast(news, memory, env)
            if broadcast is not None:
                break
            if attempt == 0:
                print("[Pipeline] First generation attempt failed. Retrying...")

        if broadcast is None:
            _fail("AI broadcast generation failed after all attempts.")

    segments: list[dict] = broadcast["segments"]
    title: str = broadcast.get("title", f"Echo FM — {timestamp}")
    print(f"[Pipeline] Broadcast ready: '{title}' ({len(segments)} segments)")

    # ── Step 3: TTS per segment ───────────────────────────────────────────────
    print(f"[3/10] Generating TTS audio for {len(segments)} segment(s)...")
    from tts_generator import generate_segment_audio

    segment_files: list[Path] = []
    for i, seg in enumerate(segments):
        speaker: str = seg.get("speaker", "ANCHOR")
        voice: str = SPEAKER_VOICES.get(speaker, _DEFAULT_VOICE)
        seg_path = OUTPUT_DIR / f"ep_{timestamp}_seg_{i:02d}.mp3"

        success = generate_segment_audio(
            text=seg["text"],
            voice=voice,
            path=str(seg_path),
            use_cloud=use_cloud_tts,
        )
        if not success:
            _fail(f"TTS generation failed for segment {i} (speaker={speaker}).")

        segment_files.append(seg_path)
        print(f"  [{i+1}/{len(segments)}] {speaker} → {seg_path.name}")

    # ── Step 4: Concatenate audio ─────────────────────────────────────────────
    print("[4/10] Concatenating audio segments...")
    audio_path = OUTPUT_DIR / f"ep_{timestamp}_audio.mp3"
    if not _concat_audio(segment_files, audio_path):
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
        description = broadcast.get("post_text", "")
        tags = broadcast.get("topic_tags", [])
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
        
        # Register artifacts (Local URI or Supabase Upload)
        final_audio_url = db.upload_file(audio_path)
        final_video_url = db.upload_file(video_path)

        # Prioritise YouTube link if it exists
        if video_url:
            final_video_url = video_url

        post_data = build_episode_metadata(
            news_items=news,
            broadcast=broadcast,
            duration=duration,
            audio_url=final_audio_url,
            video_url=final_video_url,
            healer_used=bool(broadcast.get("_healer_used", False)),
            writer_model=broadcast.get("_writer_model", "unknown"),
            narrator_model="groq-orpheus" if use_cloud_tts else "edge-tts",
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
