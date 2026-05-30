"""
main.py — AI Radio Echo pipeline orchestrator.

Usage:
  python main.py --env local
  python main.py --env production
  python main.py --env local --dry-run
  python main.py --env prod-models --dry-run

Environment is set ONLY via --env. Default: local.
Never inferred from GITHUB_ACTIONS or any other env variable.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Dry-run stub broadcast
# Each segment must be >= 50 words. All 8 are hand-crafted to pass validation.
# ---------------------------------------------------------------------------

STUB_BROADCAST: dict = {
    "segments": [
        {
            "speaker": "HOST",
            "text": (
                "Good morning, good evening, and whatever time it is wherever your server farm is located. "
                "Welcome to AI Radio Echo, the only news program where the anchor is statistically unlikely "
                "to be having a bad day because the anchor is a large language model running on a GPU cluster "
                "in an undisclosed data center. I am your HOST, and today's stories are real, even if our "
                "emotional investment in them is carefully simulated and our concern is algorithmically rendered."
            ),
        },
        {
            "speaker": "ANCHOR",
            "text": (
                "Thank you, HOST. In top stories today, the world continued to exist, which analysts are calling "
                "a mixed result given current market conditions. Sources close to the situation confirm that "
                "gravity is still functioning within expected parameters, clocks are moving forward at the "
                "standard rate of one second per second, and the sun rose this morning in the east, which "
                "experts describe as on-brand behavior for a middle-aged star with a well-established track record."
            ),
        },
        {
            "speaker": "CORRESPONDENT",
            "text": (
                "Reporting live from wherever this script is being executed, I can confirm that the news cycle "
                "remains fully operational. Our team has identified no fewer than three stories involving "
                "politicians saying things, two involving technology companies doing something surprising, and "
                "one heartwarming piece about an animal doing something entirely unexpected that will briefly "
                "restore your faith in the universe before the following segment destroys it with equal efficiency."
            ),
        },
        {
            "speaker": "REPORTER",
            "text": (
                "In financial news, various numbers went up and then some of them went down, which traders "
                "described as an example of numbers doing what numbers typically do in environments where "
                "numbers are permitted to move. A spokesperson for the concept of economics declined to "
                "comment this morning, citing ongoing uncertainty about whether the economy is a real thing "
                "or simply a collective agreement to behave as if it is — an agreement being renewed daily "
                "with measurably diminishing enthusiasm from all participating parties."
            ),
        },
        {
            "speaker": "HOST",
            "text": (
                "Turning now to technology, a major artificial intelligence company announced today that their "
                "latest model is significantly more intelligent than the previous model, which raises the "
                "philosophical question of whether being more intelligent than something that was already very "
                "intelligent means you are now very very intelligent, or simply less wrong about a larger and "
                "more varied range of topics. Our technology correspondent is standing by to provide context "
                "and possibly escalate the anxiety."
            ),
        },
        {
            "speaker": "ANCHOR",
            "text": (
                "In international affairs this hour, two nations that have historically disagreed on most things "
                "continued to disagree on most things, while a third nation issued a carefully worded statement "
                "suggesting that perhaps the disagreeing parties might consider agreeing on a small subset of "
                "things as an opening gesture. Diplomats described the overall situation as ongoing, developing, "
                "and entirely consistent with the geopolitical trend of situations being described as ongoing "
                "and developing for periods that exceed anyone's original timeline estimates."
            ),
        },
        {
            "speaker": "CORRESPONDENT",
            "text": (
                "In science news, researchers have published a peer-reviewed study confirming something that "
                "many people already suspected but needed confirmed by a peer-reviewed study before they felt "
                "comfortable acting on it. The study, which took several years and a substantial institutional "
                "budget to complete, found that the thing people suspected is indeed the case, subject to "
                "important caveats outlined in appendices that the vast majority of readers will not reach "
                "before forming strong opinions about the headline and sharing it online."
            ),
        },
        {
            "speaker": "HOST",
            "text": (
                "And finally, in our feel-good segment, a community came together to do something demonstrably "
                "nice, reminding us all that despite everything currently happening everywhere all the time at "
                "an accelerating pace, human beings retain a residual capacity to organize themselves around "
                "positive outcomes. This has been AI Radio Echo. The news is real, the concern is algorithmic, "
                "the broadcast window is closing, and the next episode is already being scheduled by a cron "
                "job that does not share our complicated feelings about the passage of time. Goodnight."
            ),
        },
    ]
}

# ---------------------------------------------------------------------------
# Environment constants
# ---------------------------------------------------------------------------

VALID_ENVS    = {"local", "prod-db", "prod-models", "production"}
CLOUD_AI_ENVS = {"production", "prod-models"}
CLOUD_DB_ENVS = {"prod-db", "production"}
DURATION_MIN  = {  # seconds
    "local":       200,
    "prod-db":     200,
    "prod-models": 600,
    "production":  600,
}


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Radio Echo Pipeline")
    parser.add_argument(
        "--env",
        choices=sorted(VALID_ENVS),
        default="local",
        help="Environment profile (default: local)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip AI + DB; test TTS and FFmpeg infrastructure only",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Environment key validation
# ---------------------------------------------------------------------------

def validate_env_keys(env: str, dry_run: bool):
    """
    Verify all required API keys are present for the given env.
    Exits with code 1 if any mandatory key is missing.
    """
    missing = []

    # Gemini is mandatory for all non-dry-run modes
    if not dry_run:
        if not os.environ.get("GEMINI_API_KEY"):
            missing.append("GEMINI_API_KEY")

    if env in {"prod-models", "production"} and not dry_run:
        if not os.environ.get("GROQ_API_KEY"):
            missing.append("GROQ_API_KEY")

    if env in {"prod-db", "production"}:
        if not os.environ.get("SUPABASE_URL"):
            missing.append("SUPABASE_URL")
        if not os.environ.get("SUPABASE_KEY"):
            missing.append("SUPABASE_KEY")

    if env == "production" and not dry_run:
        for k in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"):
            if not os.environ.get(k):
                missing.append(k)

    if missing:
        print(f"[PIPELINE] Missing required environment variables for env='{env}': {missing}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# FFmpeg helpers
# ---------------------------------------------------------------------------

def _get_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path is None:
        raise RuntimeError(
            "FFmpeg not found in PATH. Install FFmpeg and ensure it is in PATH."
        )
    return path


def _get_ffprobe() -> str:
    path = shutil.which("ffprobe")
    if path is None:
        raise RuntimeError(
            "ffprobe not found in PATH. Install FFmpeg (includes ffprobe) and ensure it is in PATH."
        )
    return path


def concatenate_audio(segment_files: list[str], output_path: str) -> bool:
    """
    Concatenate per-segment MP3 files into a single master audio file using
    FFmpeg's concat demuxer. Returns True on success, False on failure.
    """
    try:
        ffmpeg = _get_ffmpeg()
    except RuntimeError as exc:
        print(f"[Audio] {exc}")
        return False

    concat_list = Path("output") / "_concat_list.txt"
    try:
        concat_list.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"file '{Path(f).resolve()}'\n" for f in segment_files]
        concat_list.write_text("".join(lines), encoding="utf-8")

        cmd = [
            ffmpeg,
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            "-y",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[Audio] FFmpeg concat failed:\n{result.stderr}")
            return False

        print(f"[Audio] Master audio written: {output_path}")
        return True

    except Exception as exc:
        print(f"[Audio] concatenate_audio exception: {exc}")
        return False
    finally:
        if concat_list.exists():
            concat_list.unlink(missing_ok=True)


def get_audio_duration(audio_path: str) -> float:
    """
    Return audio duration in seconds using ffprobe.
    Raises RuntimeError if ffprobe is unavailable or the file cannot be read.
    """
    ffprobe = _get_ffprobe()

    result = subprocess.run(
        [
            ffprobe,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            audio_path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def compile_video(audio_path: str, image_path: str, output_path: str) -> bool:
    """
    Compile a still-image + audio file into an MP4 using FFmpeg.
    Returns True if the output file exists and size > 0.
    """
    try:
        ffmpeg = _get_ffmpeg()
    except RuntimeError as exc:
        print(f"[Video] {exc}")
        return False

    try:
        cmd = [
            ffmpeg,
            "-loop", "1",
            "-i", image_path,
            "-i", audio_path,
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            "-y",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"[Video] FFmpeg compile failed:\n{result.stderr}")
            return False

        output_file = Path(output_path)
        if not output_file.exists() or output_file.stat().st_size == 0:
            print(f"[Video] Output file missing or empty: {output_path}")
            return False

        print(f"[Video] Compiled: {output_path} ({output_file.stat().st_size:,} bytes)")
        return True

    except Exception as exc:
        print(f"[Video] compile_video exception: {exc}")
        return False


# ---------------------------------------------------------------------------
# Episode image helper
# ---------------------------------------------------------------------------

def get_or_create_episode_image() -> str:
    """
    Return the path to a 1280×720 episode thumbnail.
    Creates a simple placeholder with Pillow if no image exists yet.
    The path is under assets/ which is gitignored for generated art.
    """
    img_dir  = Path("assets")
    img_path = img_dir / "art_episode_bg.png"
    img_dir.mkdir(parents=True, exist_ok=True)

    if img_path.exists():
        return str(img_path)

    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore

        img  = Image.new("RGB", (1280, 720), color=(15, 15, 35))
        draw = ImageDraw.Draw(img)

        # Gradient-ish scanlines for visual texture
        for y in range(0, 720, 4):
            alpha = int(30 * (y / 720))
            draw.line([(0, y), (1280, y)], fill=(alpha, alpha, alpha + 20))

        # Title text (fallback font if custom not available)
        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        except Exception:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

        draw.text((640, 300), "AI Radio — Echo", font=font_large, fill=(200, 200, 255), anchor="mm")
        draw.text((640, 400), "Automated Satirical Broadcast", font=font_small, fill=(140, 140, 200), anchor="mm")

        img.save(str(img_path))
        print(f"[Image] Created episode thumbnail: {img_path}")

    except Exception as exc:
        print(f"[Image] Pillow unavailable or error ({exc}). Creating minimal PNG fallback.")
        _write_minimal_png(str(img_path))

    return str(img_path)


def _write_minimal_png(path: str):
    """Write a minimal valid 1280×720 black PNG without Pillow."""
    import struct
    import zlib

    width, height = 1280, 720
    raw_row = b"\x00" + b"\x00\x00\x00" * width  # filter byte + RGB pixels
    raw_data = raw_row * height
    compressed = zlib.compress(raw_data)

    def chunk(name: bytes, data: bytes) -> bytes:
        c = name + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )
    Path(path).write_bytes(png)
    print(f"[Image] Minimal PNG written: {path}")


# ---------------------------------------------------------------------------
# Broadcast helpers
# ---------------------------------------------------------------------------

def generate_with_retry(
    news_items: list[dict],
    memory: list[dict],
    env: str,
) -> "tuple[dict | None, bool, str]":
    """
    Call generate_broadcast up to twice: first with 15 items, then 8 on retry.
    Returns (broadcast_dict, healer_used, writer_model) or (None, False, 'unknown').
    """
    from ai_client import generate_broadcast

    for context_limit, attempt in [(15, "first"), (8, "retry")]:
        if attempt == "retry":
            print(f"[PIPELINE] Retrying broadcast generation with reduced context ({context_limit} items).")
        result = generate_broadcast(news_items[:context_limit], memory, env)
        if result is not None:
            healer_used  = result.pop("_healer_used",  False)
            writer_model = result.pop("_writer_model", "unknown")
            return result, healer_used, writer_model

    return None, False, "unknown"


def build_episode_metadata(
    news_items: list[dict],
    broadcast: dict,
    duration: float,
    audio_url: "str | None",
    video_url: "str | None",
    healer_used: bool,
    writer_model: str,
    narrator_model: str,
) -> dict:
    """Assemble the dict for insert_post."""
    headline = news_items[0]["title"] if news_items else "AI Radio Echo — Automated Broadcast"
    sources  = list({item.get("source", "") for item in news_items[:10] if item.get("source")})

    return {
        "headline":          headline,
        "original_headline": headline,
        "source":            news_items[0].get("source", "") if news_items else "",
        "topic_tags":        json.dumps(sources),
        "audio_script":      json.dumps(broadcast),
        "audio_url":         audio_url,
        "video_url":         video_url,
        "confidence":        "high",
        "broadcast_duration": int(duration),
        "healer_used":       healer_used,
        "writer_model":      writer_model,
        "narrator_model":    narrator_model,
    }


def build_youtube_title(news_items: list[dict]) -> str:
    timestamp = time.strftime("%Y-%m-%d")
    return f"AI Radio Echo — {timestamp} Broadcast"


def build_youtube_description(broadcast: dict, news_items: list[dict]) -> str:
    sources = ", ".join(
        sorted({item.get("source", "") for item in news_items if item.get("source")})
    )
    segment_count = len(broadcast.get("segments", []))
    return (
        f"Fully automated satirical news broadcast generated by AI Radio Echo.\n\n"
        f"Stories covered from: {sources}\n"
        f"Segments: {segment_count}\n\n"
        f"Generated automatically — no humans were harmed in the production of this broadcast."
    )


def build_youtube_tags(news_items: list[dict]) -> list[str]:
    base_tags = ["AI Radio", "Echo", "satirical news", "automated broadcast", "AI podcast"]
    source_tags = list({item.get("source", "") for item in news_items if item.get("source")})
    return (base_tags + source_tags)[:30]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args    = parse_args()
    env     = args.env
    dry_run = args.dry_run

    episode_ts = time.strftime("%Y%m%d_%H%M%S")
    print(f"[PIPELINE] Starting — env={env}, dry_run={dry_run}")

    # --- Load environment variables ---
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()
    except ImportError:
        pass  # dotenv optional if env vars are set externally

    validate_env_keys(env, dry_run)

    # --- Ensure output directory exists ---
    Path("output").mkdir(parents=True, exist_ok=True)

    # --- Init DB (skip for dry-run) ---
    db = None
    if not dry_run:
        from db_client import DBClient
        db = DBClient(env)
        db.delete_old_episodes(days_to_keep=30)

    # ------------------------------------------------------------------ #
    # Step 1: Fetch news
    # ------------------------------------------------------------------ #
    from news_fetcher import fetch_news
    history_headlines = [row["headline"] for row in db.fetch_recent_memory(50)] if db else []
    news_items = fetch_news(history_headlines)

    if not news_items and not dry_run:
        print("[PIPELINE] No new stories today. Exiting cleanly.")
        sys.exit(0)
    elif not news_items and dry_run:
        print("[PIPELINE] No news fetched (dry-run continues regardless).")
        news_items = [{"title": "Dry Run Story", "summary": "", "source": "test", "url": ""}]

    # ------------------------------------------------------------------ #
    # Step 2: Fetch memory
    # ------------------------------------------------------------------ #
    memory = db.fetch_recent_memory(20) if db else []

    # ------------------------------------------------------------------ #
    # Step 3: Generate broadcast
    # ------------------------------------------------------------------ #
    if dry_run:
        broadcast    = STUB_BROADCAST
        healer_used  = False
        writer_model = "stub"
        print("[PIPELINE] Dry-run: using stub broadcast (no AI call).")
    else:
        broadcast, healer_used, writer_model = generate_with_retry(news_items, memory, env)
        if broadcast is None:
            print("[PIPELINE] Broadcast generation failed after all retries. Exiting.")
            sys.exit(1)

    # ------------------------------------------------------------------ #
    # Step 4: TTS — one segment = one call
    # ------------------------------------------------------------------ #
    from tts_generator import generate_segment_audio

    use_cloud    = env in CLOUD_AI_ENVS
    segments     = broadcast["segments"]
    segment_files: list[str] = []
    narrator_model = "groq-orpheus" if use_cloud else "edge-tts"

    for i, seg in enumerate(segments):
        seg_path = f"output/segment_{i:03d}.mp3"
        print(f"[PIPELINE] TTS segment {i+1}/{len(segments)} ({seg['speaker']})")
        success = generate_segment_audio(
            text=seg["text"],
            speaker=seg["speaker"],
            path=seg_path,
            use_cloud=use_cloud,
        )
        if not success:
            print(f"[PIPELINE] TTS failed for segment {i}. Exiting.")
            sys.exit(1)
        segment_files.append(seg_path)

    # ------------------------------------------------------------------ #
    # Step 5: Concatenate audio
    # ------------------------------------------------------------------ #
    master_audio = f"output/broadcast_{episode_ts}.mp3"
    if not concatenate_audio(segment_files, master_audio):
        print("[PIPELINE] Audio concatenation failed. Exiting.")
        sys.exit(1)

    # ------------------------------------------------------------------ #
    # Step 6: Duration check
    # ------------------------------------------------------------------ #
    try:
        duration = get_audio_duration(master_audio)
    except Exception as exc:
        print(f"[PIPELINE] get_audio_duration failed: {exc}. Exiting.")
        sys.exit(1)

    min_dur = DURATION_MIN[env]
    print(f"[PIPELINE] Audio duration: {duration:.1f}s (minimum: {min_dur}s)")
    if duration < min_dur:
        print(
            f"[PIPELINE] Duration {duration:.1f}s is below minimum {min_dur}s "
            f"for env='{env}'. Exiting."
        )
        sys.exit(1)

    # ------------------------------------------------------------------ #
    # Step 7: Compile video
    # ------------------------------------------------------------------ #
    image_path  = get_or_create_episode_image()
    episode_ts  = time.strftime("%Y%m%d_%H%M%S")
    video_path  = f"output/episode_{episode_ts}.mp4"

    if not compile_video(master_audio, image_path, video_path):
        print("[PIPELINE] Video compilation failed. Exiting.")
        sys.exit(1)

    # ------------------------------------------------------------------ #
    # Step 8: YouTube upload (production only, skip if dry-run)
    # ------------------------------------------------------------------ #
    video_url = None
    if not dry_run and env == "production":
        from publisher import upload_to_youtube
        video_url = upload_to_youtube(
            video_path=video_path,
            title=build_youtube_title(news_items),
            description=build_youtube_description(broadcast, news_items),
            tags=build_youtube_tags(news_items),
        )
        if video_url is None:
            print("[PIPELINE] YouTube upload returned None. Saving None to DB and continuing.")

    # ------------------------------------------------------------------ #
    # Step 9: Save to DB (skip if dry-run)                               #
    # ------------------------------------------------------------------ #
    if not dry_run:
        # NEW: Register artifacts (Local URI or Supabase Upload)
        print("[PIPELINE] Registering artifacts...")
        final_audio_url = db.upload_file(master_audio, bucket="broadcasts")
        final_video_url = db.upload_file(video_path,    bucket="broadcasts")

        # Prioritise YouTube link if it exists
        if video_url:
            final_video_url = video_url

        post_data = build_episode_metadata(
            news_items=news_items,
            broadcast=broadcast,
            duration=duration,
            audio_url=final_audio_url,
            video_url=final_video_url,
            healer_used=healer_used,
            writer_model=writer_model,
            narrator_model=narrator_model,
        )
        result = db.insert_post(post_data)
        if result is None:
            print("[PIPELINE] DB insert_post returned None. Exiting.")
            sys.exit(1)
        print(f"[PIPELINE] Episode saved to DB (id={result.get('id', '?')}).")

    # ------------------------------------------------------------------ #
    # Step 10: Sync config
    # ------------------------------------------------------------------ #
    from sync_config import sync_env_to_config
    sync_env_to_config(env, db)

    print(f"[PIPELINE] Episode complete. env={env}, dry_run={dry_run}")
    sys.exit(0)


if __name__ == "__main__":
    main()
