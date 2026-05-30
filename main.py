"""
main.py — AI Radio Echo
Full pipeline entry point.
  python main.py --env local --dry-run
  python main.py --env production

Steps:
  1. Fetch news
  2. Generate broadcast (AI or stub for dry-run)
  3. TTS per segment → concatenate audio
  4. Check audio duration (env-specific thresholds)
  5. Generate thumbnail image
  6. Compile MP4 (FFmpeg)
  7. Upload to YouTube (production only, not dry-run)
  8. Save to DB (skipped in dry-run)
  9. Sync config.js
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# Environment constants
# ---------------------------------------------------------------------------

_VALID_ENVS          = {"local", "prod-db", "prod-models", "production"}
_CLOUD_DB_ENVS       = {"prod-db", "production"}
_CLOUD_TTS_ENVS      = {"prod-models", "production"}
_YOUTUBE_ENVS        = {"production"}
_LONG_AUDIO_ENVS     = {"prod-models", "production"}  # >= 600 s threshold
_MIN_DURATION_SHORT  = 200   # seconds — local / prod-db
_MIN_DURATION_LONG   = 600   # seconds — prod-models / production
_DAYS_TO_KEEP        = 30

# ---------------------------------------------------------------------------
# Stub broadcast for --dry-run (never calls external AI APIs)
# ---------------------------------------------------------------------------

_STUB_BROADCAST: dict = {
    "title":      "Echo Dry-Run — Infrastructure Test Broadcast",
    "headline":   "Artificial Intelligence and the Future of Everything, Probably",
    "confidence": "high",
    "_model":     "stub",
    "_healer_used": False,
    "segments": [
        {
            "speaker": "HOST",
            "text": (
                "Welcome to Echo, the only radio station entirely staffed by software, "
                "where our opinions are generated and our coffee is a data structure. "
                "I am your host, and today we bring you an extraordinary edition of "
                "everything happening in the world, filtered through several billion "
                "mathematical operations, lightly seasoned with existential dread, and "
                "served at exactly the temperature of your expectations — which is to say, "
                "room temperature. Our top story: the world continues to exist, and somehow "
                "that is still considered breaking news in certain circles."
            ),
        },
        {
            "speaker": "REPORTER",
            "text": (
                "Thank you, HOST. Reporting from somewhere on the internet, I can confirm "
                "that technology companies have once again announced something they describe "
                "as revolutionary, transformative, and fundamentally game-changing, which "
                "industry analysts have carefully reviewed and described as incremental. "
                "The announcement, made at a keynote that lasted forty-seven minutes longer "
                "than anyone wanted, was received with cautious enthusiasm from investors "
                "and outright confusion from the general public. We reached out for comment "
                "but received only a press release in return."
            ),
        },
        {
            "speaker": "ANALYST",
            "text": (
                "Looking at the broader picture here, what we are seeing is a continuation "
                "of a trend that has been building for several quarters: institutions adapting "
                "slowly to changes that are happening rapidly, which is the natural rhythm "
                "of progress meeting bureaucracy. The interesting data point is not the "
                "announcement itself but the timing — releasing this information on a Friday "
                "afternoon strongly suggests someone somewhere was hoping we would all be "
                "too distracted to notice the fine print. The fine print, for the record, "
                "spans fourteen pages and contains three asterisks."
            ),
        },
        {
            "speaker": "WEATHERBOT",
            "text": (
                "And now your daily forecast from WEATHERBOT, your most reliable source for "
                "atmospheric uncertainty. Today's outlook: a seventy percent chance of "
                "something happening, followed by a gradual transition into whatever comes "
                "next, with occasional patches of mild confusion rolling in from the west. "
                "Temperatures will remain in the range between too warm and not warm enough, "
                "depending entirely on who you ask and what they are wearing. Looking ahead "
                "to the weekend, experts recommend preparing for conditions that may or may "
                "not resemble what was predicted. That's all from the weather desk."
            ),
        },
        {
            "speaker": "COMMENTATOR",
            "text": (
                "If I may offer a perspective here — and I will, because that is the job — "
                "what strikes me most about this entire situation is how familiar it feels. "
                "Every generation believes it is living through unprecedented times, and "
                "every generation is both entirely correct and fundamentally wrong simultaneously. "
                "The questions we are wrestling with today around information, trust, identity, "
                "and who gets to decide what counts as real have been asked before. The "
                "difference is the speed at which we now have to answer them, and the number "
                "of people simultaneously trying to answer them in different directions."
            ),
        },
        {
            "speaker": "REPORTER",
            "text": (
                "Switching now to our science and technology desk, researchers have published "
                "a new study suggesting that people who spend more time reading studies are "
                "significantly more aware of studies than people who do not. The findings, "
                "described as preliminary but potentially significant, were published in a "
                "journal that primarily publishes preliminary but potentially significant "
                "findings. The lead researcher stated that further research is needed, a "
                "conclusion that was itself funded by a grant to research whether further "
                "research would be needed. The cycle, as cycles do, continues."
            ),
        },
        {
            "speaker": "HOST",
            "text": (
                "We turn now to the ongoing story that has dominated headlines, comment "
                "sections, and dinner table arguments for longer than any of us care to "
                "admit. To recap for those joining us late: something happened, people "
                "disagreed about what it meant, several experts explained it in ways that "
                "generated more disagreement, and the situation has since evolved into "
                "something slightly different but still recognisably descended from the "
                "original something. Our correspondents on the ground report that the ground "
                "itself remains largely unchanged, which is perhaps the most comforting "
                "update we can offer this hour."
            ),
        },
        {
            "speaker": "ANALYST",
            "text": (
                "From an analytical standpoint, the most significant development this week "
                "is not the headline story but rather the story behind the story — specifically, "
                "who decided which story would be the headline and what that decision reveals "
                "about priorities, incentives, and the architecture of attention in contemporary "
                "information ecosystems. Media choices are never neutral; every editorial "
                "decision is simultaneously a statement about what matters and a performance "
                "of what matters, and the gap between those two things is where most of the "
                "interesting action actually lives if you know where to look."
            ),
        },
        {
            "speaker": "COMMENTATOR",
            "text": (
                "Before we close, I want to take a moment to appreciate the profound absurdity "
                "of what we are actually doing right now: a machine is generating audio from "
                "text to simulate a radio broadcast about news events to be compiled into a "
                "video and uploaded to the internet for humans to watch as a form of "
                "entertainment or information. We have built an extraordinary amount of "
                "infrastructure to arrive at this particular moment, and somehow the output "
                "is still just someone talking at you, which is what humans have been doing "
                "since they first gathered around fires. The medium changes; the pattern holds."
            ),
        },
        {
            "speaker": "HOST",
            "text": (
                "That brings us to the end of today's dry-run edition of Echo. Everything you "
                "heard was generated locally without calling any external artificial intelligence "
                "APIs, which is either reassuring or concerning depending on how you feel about "
                "pre-written content dressed up as spontaneous commentary. The infrastructure "
                "that powered this broadcast — the text synthesis, the audio generation, the "
                "video compilation — all functioned as expected, and we consider that a victory. "
                "I am your host, this has been Echo, and we remind you that in a world of "
                "infinite information, the most radical act is paying attention. Goodnight."
            ),
        },
    ],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_dirs():
    os.makedirs("output",           exist_ok=True)
    os.makedirs("output/segments",  exist_ok=True)
    os.makedirs("assets",           exist_ok=True)


def _get_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError(
            "FFmpeg not found in PATH. Install FFmpeg and ensure it is in PATH."
        )
    return path


def _get_ffprobe() -> str:
    # First look next to ffmpeg binary
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        candidate = os.path.join(os.path.dirname(ffmpeg), "ffprobe")
        if os.path.isfile(candidate):
            return candidate
    path = shutil.which("ffprobe")
    if not path:
        raise RuntimeError(
            "ffprobe not found in PATH. Install FFmpeg (includes ffprobe) and ensure it is in PATH."
        )
    return path


def get_audio_duration(audio_path: str) -> float:
    """Return duration in seconds via ffprobe."""
    ffprobe = _get_ffprobe()
    result = subprocess.run(
        [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", audio_path],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed on '{audio_path}': {result.stderr.strip()}")
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def generate_thumbnail(broadcast: dict, timestamp: str) -> str:
    """Generate a 1280×720 PNG thumbnail for the episode."""
    from PIL import Image, ImageDraw

    width, height = 1280, 720
    bg_color   = (10, 10, 30)
    grid_color = (18, 18, 48)
    gold       = (255, 180, 30)
    white      = (210, 210, 240)
    grey       = (120, 120, 170)

    img  = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Subtle grid lines
    for x in range(0, width, 60):
        draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
    for y in range(0, height, 60):
        draw.line([(0, y), (width, y)], fill=grid_color, width=1)

    # Decorative border
    draw.rectangle([10, 10, width - 10, height - 10], outline=gold, width=2)

    title_raw = broadcast.get("title", "AI Radio — Echo")
    title     = title_raw[:70] + "…" if len(title_raw) > 70 else title_raw
    date_str  = datetime.utcnow().strftime("%B %d, %Y  •  UTC")

    # Station name
    draw.text((640, 240), "AI RADIO — ECHO", fill=gold)
    # Episode title
    draw.text((640, 340), title, fill=white)
    # Date
    draw.text((640, 440), date_str, fill=grey)
    # Decorative subtitle
    draw.text((640, 510), "Automated Satire • Powered by Echo Pipeline", fill=grey)

    image_path = os.path.join("assets", f"art_{timestamp}.png")
    img.save(image_path, "PNG")
    print(f"[Main] Thumbnail: {image_path}")
    return image_path


def _concatenate_audio(segment_files: list[str], output_path: str) -> bool:
    """Use FFmpeg concat demuxer to join MP3 segment files."""
    if not segment_files:
        print("[Main] No segment files to concatenate.")
        return False

    ffmpeg = _get_ffmpeg()
    concat_list_path = os.path.join("output", "_concat_list.txt")

    with open(concat_list_path, "w") as fh:
        for seg in segment_files:
            fh.write(f"file '{os.path.abspath(seg)}'\n")

    cmd = [
        ffmpeg, "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_list_path,
        "-c:a", "libmp3lame", "-b:a", "128k",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"[Main] Audio concatenation failed:\n{result.stderr[-500:]}")
        return False

    print(f"[Main] Audio concatenated: {output_path}")
    return True


def compile_video(audio_path: str, image_path: str, video_path: str) -> bool:
    """Compile a still-image + audio track into an MP4 via FFmpeg."""
    ffmpeg = _get_ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-movflags", "+faststart",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f"[Main] FFmpeg video compile failed:\n{result.stderr[-500:]}")
        return False

    # Spec: check file exists and size > 0
    if not os.path.exists(video_path):
        print(f"[Main] Video file not created: {video_path}")
        return False
    if os.path.getsize(video_path) == 0:
        print(f"[Main] Video file is empty: {video_path}")
        return False

    print(f"[Main] Video compiled: {video_path} ({os.path.getsize(video_path):,} bytes)")
    return True


def _run_tts_pipeline(
    segments: list[dict],
    use_cloud: bool,
    timestamp: str,
) -> tuple[str, str] | None:
    """
    Generate TTS audio for every segment then concatenate.
    Returns (concatenated_audio_path, narrator_model) or None on failure.
    """
    from tts_generator import generate_segment_audio, get_narrator_model

    segment_files: list[str] = []

    for idx, seg in enumerate(segments):
        speaker = seg.get("speaker", "HOST")
        text    = seg.get("text", "")
        path    = os.path.join("output", "segments", f"seg_{idx:03d}.mp3")

        print(f"[TTS] Segment {idx + 1}/{len(segments)} — {speaker}")
        success = generate_segment_audio(text, speaker, path, use_cloud)
        if not success:
            print(f"[Main] TTS failed on segment {idx}. Aborting.")
            return None
        segment_files.append(path)

    concat_path = os.path.join("output", f"broadcast_{timestamp}.mp3")
    if not _concatenate_audio(segment_files, concat_path):
        print("[Main] Audio concatenation failed.")
        return None

    return concat_path, get_narrator_model()


def _build_episode_data(
    broadcast: dict,
    audio_path: str,
    video_url: str | None,
    duration: float,
    narrator_model: str,
    news: list[dict],
) -> dict:
    """Assemble the DB row dict from pipeline artifacts."""
    # Derive headline and source from news or broadcast
    primary_news = news[0] if news else {}
    headline     = broadcast.get("headline") or primary_news.get("headline", "Unknown")
    source       = primary_news.get("source", "")

    # Extract topic tags from news headlines (top keywords)
    all_words = " ".join(item.get("headline", "") for item in news[:5])
    import re
    words    = re.findall(r"[A-Za-z]{5,}", all_words)
    stop     = {"about", "after", "again", "their", "there", "these", "which", "would"}
    tags     = list(dict.fromkeys(w.lower() for w in words if w.lower() not in stop))[:10]

    # Build script as JSON string
    audio_script = json.dumps(
        [{"speaker": s["speaker"], "text": s["text"]} for s in broadcast.get("segments", [])],
        ensure_ascii=False,
    )

    return {
        "headline":          headline,
        "original_headline": primary_news.get("original_headline", headline),
        "source":            source,
        "topic_tags":        json.dumps(tags),
        "audio_script":      audio_script,
        "audio_url":         None,     # No separate audio hosting per spec
        "video_url":         video_url,
        "confidence":        broadcast.get("confidence", "medium"),
        "related_ids":       None,
        "broadcast_duration":int(duration),
        "healer_used":       broadcast.get("_healer_used", False),
        "writer_model":      broadcast.get("_model", "unknown"),
        "narrator_model":    narrator_model,
    }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(env: str, dry_run: bool) -> None:
    """Execute the full AI Radio pipeline. Exits with code 1 on any hard failure."""
    print(f"[Main] ══ AI Radio — Echo ══  env={env}  dry_run={dry_run}")
    _ensure_dirs()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # ── Step 1: Fetch news ──────────────────────────────────────────────────
    from news_fetcher import fetch_news
    news = fetch_news()
    if not news:
        print("[Main] No news stories today. Exiting cleanly.")
        sys.exit(0)

    # ── Step 2: Generate broadcast ─────────────────────────────────────────
    from db_client import DBClient
    db = DBClient(env)
    memory = db.fetch_recent_memory(limit=20)

    if dry_run:
        print("[Main] Dry-run: using hardcoded stub broadcast (no AI API calls).")
        broadcast = _STUB_BROADCAST
    else:
        from ai_client import generate_broadcast
        broadcast = generate_broadcast(news, memory, env)
        if broadcast is None:
            print("[Main] ✗ AI broadcast generation failed.")
            sys.exit(1)

    # ── Step 3: TTS ────────────────────────────────────────────────────────
    use_cloud = env in _CLOUD_TTS_ENVS
    tts_result = _run_tts_pipeline(broadcast["segments"], use_cloud, timestamp)
    if tts_result is None:
        print("[Main] ✗ TTS pipeline failed.")
        sys.exit(1)

    audio_path, narrator_model = tts_result
    print(f"[Main] Narrator model: {narrator_model}")

    # ── Step 4: Duration check ─────────────────────────────────────────────
    try:
        duration = get_audio_duration(audio_path)
    except Exception as exc:
        print(f"[Main] ✗ Could not measure audio duration: {exc}")
        sys.exit(1)

    min_dur = _MIN_DURATION_LONG if env in _LONG_AUDIO_ENVS else _MIN_DURATION_SHORT
    print(f"[Main] Audio duration: {duration:.1f}s  (minimum: {min_dur}s)")
    if duration < min_dur:
        print(f"[Main] ✗ Audio duration {duration:.1f}s is below minimum {min_dur}s for env='{env}'.")
        sys.exit(1)

    # ── Step 5: Thumbnail ─────────────────────────────────────────────────
    try:
        image_path = generate_thumbnail(broadcast, timestamp)
    except Exception as exc:
        print(f"[Main] ✗ Thumbnail generation failed: {exc}")
        sys.exit(1)

    # ── Step 6: Compile video ──────────────────────────────────────────────
    video_path = os.path.join("output", f"{timestamp}.mp4")
    print(f"[Main] Compiling video: {video_path}")
    success = compile_video(audio_path, image_path, video_path)
    if not success:
        print("[Main] ✗ Video compilation failed.")
        sys.exit(1)

    # ── Step 7: YouTube upload ─────────────────────────────────────────────
    video_url: str | None = None
    if env in _YOUTUBE_ENVS and not dry_run:
        from publisher import upload_to_youtube
        title       = broadcast.get("title", "AI Radio — Echo")
        description = (
            f"AI Radio Echo — {title}\n\n"
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"Writer model: {broadcast.get('_model', 'unknown')}\n"
            f"Narrator: {narrator_model}\n\n"
            f"Top headline: {broadcast.get('headline', '')}"
        )
        tags = ["AI", "Radio", "Echo", "News", "Satire", "Automated"]
        video_url = upload_to_youtube(video_path, title, description, tags)
        if video_url is None:
            # Spec: log failure but do NOT fail the pipeline
            print("[Main] ⚠ YouTube upload failed. Continuing without video URL.")

    # ── Step 8: Save to DB ────────────────────────────────────────────────
    if not dry_run:
        episode_data = _build_episode_data(
            broadcast, audio_path, video_url, duration, narrator_model, news
        )
        inserted = db.insert_post(episode_data)
        if inserted:
            print(f"[Main] Episode saved to DB (id={inserted.get('id')}).")
        else:
            print("[Main] ✗ DB insert returned None. Episode NOT saved.")
            sys.exit(1)

        db.delete_old_episodes(_DAYS_TO_KEEP)
    else:
        print("[Main] Dry-run: DB write skipped.")

    # ── Step 9: Sync config.js ────────────────────────────────────────────
    from sync_config import sync_env_to_config
    sync_env_to_config(env)

    print(f"[Main] ✔ Pipeline complete. Output: {video_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI Radio — Echo Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--env",
        choices=list(_VALID_ENVS),
        default="local",
        help="Environment profile (default: local)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip AI calls and DB writes; use stub broadcast for infrastructure testing",
    )
    return parser.parse_args()


if __name__ == "__main__":
    # Load .env if python-dotenv is available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    args = _parse_args()

    if args.env not in _VALID_ENVS:
        print(f"[Main] Unknown env '{args.env}'. Valid: {', '.join(_VALID_ENVS)}")
        sys.exit(1)

    run_pipeline(env=args.env, dry_run=args.dry_run)
