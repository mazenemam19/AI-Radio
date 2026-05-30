"""
main.py — AI Radio Echo
Full pipeline orchestration:
  1. Fetch news
  2. Generate broadcast (AI) — or use stub in dry-run
  3. Generate segment audio (TTS)
  4. Concatenate audio
  5. Validate duration
  6. Generate episode image
  7. Compile MP4 (FFmpeg)
  8. Upload to YouTube
  9. Save to DB
  10. Sync config.js
"""

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from db_client     import DBClient
from news_fetcher  import fetch_news
from ai_client     import generate_broadcast
from tts_generator import generate_segment_audio
from publisher     import upload_to_youtube
from sync_config   import sync_env_to_config


# ------------------------------------------------------------------ #
#  Environment definitions                                            #
# ------------------------------------------------------------------ #

VALID_ENVS        = {"local", "prod-db", "prod-models", "production"}
PRODUCTION_ENVS   = {"production", "prod-models"}   # high-tier AI + cloud TTS
LOCAL_MODEL_ENVS  = {"local", "prod-db"}             # Gemini-only + edge-tts

# Minimum audio duration per env class (seconds)
MIN_DURATION: dict[str, int] = {
    "local":        200,
    "prod-db":      200,
    "prod-models":  600,
    "production":   600,
}


# ------------------------------------------------------------------ #
#  Dry-run stub broadcast                                             #
# ------------------------------------------------------------------ #
# Each segment is ~100 words to ensure combined audio > 200 s (local minimum).

_STUB_SEG_HOST_1 = (
    "Welcome to AI Radio Echo — the show where silicon meets satire and algorithms "
    "argue with anchors. Tonight we are running in dry-run mode, which means instead "
    "of our usual AI-hallucinated headlines, you are getting this very carefully "
    "hand-crafted test script. Think of it as a fire drill for the broadcast stack: "
    "nobody gets hurt, but everyone gets to verify that text-to-speech, FFmpeg, and "
    "the rest of the infrastructure are doing exactly what they are supposed to do."
)
_STUB_SEG_COHOST_1 = (
    "That is right, and honestly I think this is the most honest broadcast we have "
    "ever done. No AI fever dreams, no hallucinated statistics, no confidently wrong "
    "summaries of events that did not happen. Just good old-fashioned infrastructure "
    "testing wrapped in the warm blanket of fake radio banter. The audio pipeline is "
    "running, the quota tracker is being initialised, and somewhere in a GitHub "
    "Actions runner a virtual machine is spending two and a half minutes pretending "
    "to be a radio station."
)
_STUB_SEG_HOST_2 = (
    "And what a radio station it is. Our FFmpeg encoder is standing by to compress "
    "this audio into a video file alongside a procedurally generated episode card. "
    "The image will be a tasteful shade of dark blue — not because we have any "
    "particular fondness for the colour, but because that is what the PIL default "
    "produces when you ask it to generate something quickly and without any design "
    "budget. We are testing the full stack here, from RSS to MP4."
)
_STUB_SEG_COHOST_2 = (
    "Speaking of the full stack, let us walk through what is NOT happening tonight. "
    "The AI language model is not being called. No Groq, no Gemini, not a single "
    "token is being exchanged with any cloud provider. The database is not being "
    "written to. YouTube will not receive an upload. This is infrastructure only — "
    "a clean, quiet, zero-cost verification pass that confirms everything would work "
    "if the real run were to fire. CI loves this. Engineers love this. Accountants "
    "love this even more."
)
_STUB_SEG_HOST_3 = (
    "We should also mention the news fetcher, which has been politely told to stay "
    "home today. In dry-run mode there is no reason to hammer the BBC, Reuters, the "
    "Guardian, or the good people at Hacker News with HTTP requests when the output "
    "is entirely predetermined. The news is irrelevant because the broadcast is a "
    "stub. The stub is hardcoded. And the hardcoded stub is exactly what you are "
    "listening to right now. Meta, is it not?"
)
_STUB_SEG_COHOST_3 = (
    "Extremely meta. I am a text-to-speech engine reading a script that was written "
    "to test the text-to-speech engine. There is a philosophy dissertation in there "
    "somewhere, but we do not have time for it because we need to keep the segment "
    "count above eight and each segment above fifty words. Those are the spec "
    "requirements. We respect the spec. The spec is law. At least until someone "
    "opens a pull request and the law changes."
)
_STUB_SEG_HOST_4 = (
    "Let us take a moment to appreciate the engineers who wrote the repetition "
    "checker. Every segment in this broadcast is being scanned for Jaccard similarity "
    "against every other segment. If any two segments share more than fifty percent "
    "word overlap, the whole script gets rejected. Which is why each of these "
    "segments talks about something slightly different, even though they are all "
    "fundamentally about the same dry run. Variety within repetition. The hallmark "
    "of truly great infrastructure testing."
)
_STUB_SEG_COHOST_4 = (
    "And on that note, we are approaching the final segment of tonight's dry-run "
    "broadcast. The audio will be concatenated, the image will be compiled, the "
    "video duration will be checked against the minimum threshold, and assuming "
    "everything has gone according to plan, the process will exit with code zero. "
    "Exit code zero is our standing ovation. Exit code zero is how machines say "
    "well done. We hope to see you on the other side of a successful pipeline run. "
    "This has been AI Radio Echo — and none of it was real."
)

DRY_RUN_STUB: dict = {
    "headline":          "AI Radio Echo — Dry Run Test Broadcast",
    "original_headline": "Infrastructure verification: all systems nominal",
    "source":            "DryRunTestSuite",
    "topic_tags":        ["dry-run", "infrastructure", "test"],
    "my_take": (
        "Everything you are hearing is a lie, but a well-engineered one. "
        "The pipeline is healthy. The pipeline is always healthy."
    ),
    "post_text": "AI Radio Echo dry-run passed ✓ #AIRadio #DryRun",
    "confidence": "high",
    "_healer_used": False,
    "segments": [
        {"speaker": "HOST",    "text": _STUB_SEG_HOST_1},
        {"speaker": "CO-HOST", "text": _STUB_SEG_COHOST_1},
        {"speaker": "HOST",    "text": _STUB_SEG_HOST_2},
        {"speaker": "CO-HOST", "text": _STUB_SEG_COHOST_2},
        {"speaker": "HOST",    "text": _STUB_SEG_HOST_3},
        {"speaker": "CO-HOST", "text": _STUB_SEG_COHOST_3},
        {"speaker": "HOST",    "text": _STUB_SEG_HOST_4},
        {"speaker": "CO-HOST", "text": _STUB_SEG_COHOST_4},
    ],
}


# ------------------------------------------------------------------ #
#  FFmpeg utilities                                                   #
# ------------------------------------------------------------------ #

def _get_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError(
            "FFmpeg not found in PATH. Install FFmpeg and ensure it is in PATH."
        )
    return ffmpeg


def _get_ffprobe() -> str | None:
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        return ffprobe
    # Try to find it next to ffmpeg
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        candidate = Path(ffmpeg).parent / "ffprobe"
        if candidate.exists():
            return str(candidate)
    return None


def get_audio_duration(audio_path: str) -> float:
    """Return duration in seconds. Returns 0.0 on failure."""
    ffprobe = _get_ffprobe()
    if ffprobe:
        result = subprocess.run(
            [
                ffprobe, "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                audio_path,
            ],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                return float(data["format"]["duration"])
            except (json.JSONDecodeError, KeyError, ValueError):
                pass

    # Fallback: parse ffmpeg stderr for Duration line
    ffmpeg = _get_ffmpeg()
    result = subprocess.run(
        [ffmpeg, "-i", audio_path, "-f", "null", os.devnull],
        capture_output=True, text=True,
    )
    match = re.search(
        r"Duration:\s+(\d+):(\d+):(\d+)\.(\d+)", result.stderr
    )
    if match:
        h, m, s, cs = (int(x) for x in match.groups())
        return h * 3600 + m * 60 + s + cs / 100
    print(f"[Audio] Could not determine duration for {audio_path}")
    return 0.0


def concatenate_audio(segment_paths: list[str], output_path: str) -> bool:
    """
    Concatenate MP3 segment files into a single MP3 using FFmpeg concat demuxer.
    Re-encodes to ensure compatibility across variable-bitrate sources.
    """
    ffmpeg = _get_ffmpeg()

    fd, list_file = tempfile.mkstemp(suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for path in segment_paths:
                abs_path = os.path.abspath(path).replace("'", "'\\''")
                fh.write(f"file '{abs_path}'\n")

        result = subprocess.run(
            [
                ffmpeg, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c:a", "libmp3lame",
                "-q:a", "2",
                output_path,
            ],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"[FFmpeg] Audio concatenation failed:\n{result.stderr[-1000:]}")
            return False
        return True
    finally:
        try:
            os.unlink(list_file)
        except OSError:
            pass


def compile_video(image_path: str, audio_path: str, output_path: str) -> bool:
    """
    Compile a still image + audio into an MP4.
    Validates that the output file exists and has size > 0.
    """
    ffmpeg = _get_ffmpeg()

    result = subprocess.run(
        [
            ffmpeg, "-y",
            "-loop", "1",     "-i", image_path,
            "-i", audio_path,
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            output_path,
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"[FFmpeg] Video compilation failed:\n{result.stderr[-1000:]}")
        return False

    out = Path(output_path)
    if not out.exists() or out.stat().st_size == 0:
        print(f"[FFmpeg] Output file missing or empty: {output_path}")
        return False

    return True


# ------------------------------------------------------------------ #
#  Image generation                                                   #
# ------------------------------------------------------------------ #

def _create_minimal_png(out_path: str, width: int = 1280, height: int = 720) -> None:
    """
    Create a dark-blue PNG without PIL, using only stdlib (struct + zlib).
    Used as a fallback when Pillow is not installed.
    """
    def _chunk(ctype: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc)

    sig  = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))

    raw = b""
    for _ in range(height):
        raw += b"\x00"                    # filter none
        raw += bytes([15, 15, 35]) * width  # RGB dark blue per pixel

    idat = _chunk(b"IDAT", zlib.compress(raw, 1))
    iend = _chunk(b"IEND", b"")

    with open(out_path, "wb") as fh:
        fh.write(sig + ihdr + idat + iend)


def generate_image(headline: str, out_path: str) -> None:
    """Generate a simple episode card. Uses PIL if available, else minimal PNG."""
    try:
        from PIL import Image, ImageDraw

        img  = Image.new("RGB", (1280, 720), color=(15, 15, 35))
        draw = ImageDraw.Draw(img)

        # Border
        draw.rectangle([30, 30, 1249, 689], outline=(70, 130, 200), width=4)

        # Title block
        draw.rectangle([30, 30, 1249, 160], fill=(25, 25, 60))
        draw.text((640, 95), "AI RADIO — ECHO", fill=(100, 180, 255), anchor="mm")

        # Headline (word-wrap at ~55 chars)
        words   = headline.split()
        lines:  list[str] = []
        current: list[str] = []
        for w in words:
            if len(" ".join(current + [w])) > 55:
                lines.append(" ".join(current))
                current = [w]
            else:
                current.append(w)
        if current:
            lines.append(" ".join(current))

        y_start = 300 - (len(lines) * 30)
        for line in lines[:5]:
            draw.text((640, y_start), line, fill=(220, 220, 220), anchor="mm")
            y_start += 60

        img.save(out_path)
    except ImportError:
        _create_minimal_png(out_path)


# ------------------------------------------------------------------ #
#  Pipeline                                                           #
# ------------------------------------------------------------------ #

def _fail(msg: str) -> None:
    print(f"[Main] FATAL: {msg}")
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Radio — Echo pipeline")
    parser.add_argument(
        "--env",
        default="local",
        choices=sorted(VALID_ENVS),
        help="Environment profile.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip AI + DB; use stub broadcast to test infrastructure only.",
    )
    args = parser.parse_args()

    env     = args.env
    dry_run = args.dry_run

    load_dotenv()

    print(f"\n{'='*60}")
    print(f"  AI Radio — Echo  |  env={env}  |  dry-run={dry_run}")
    print(f"{'='*60}\n")

    # Ensure output and assets directories exist
    Path("output").mkdir(exist_ok=True)
    Path("assets").mkdir(exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # ── Step 1: DB init (skipped in dry-run) ────────────────────────
    db: DBClient | None = None
    memory: list[dict]  = []

    if not dry_run:
        try:
            db = DBClient(env)
            print("[Main] DB connected.")
        except Exception as exc:
            _fail(f"DB initialisation failed: {exc}")

        memory = db.fetch_recent_memory(20)
        print(f"[Main] Loaded {len(memory)} memory entries.")

    # ── Step 2: News fetch (skipped in dry-run) ──────────────────────
    news: list[dict] = []
    if not dry_run:
        history_headlines = [m.get("headline", "") for m in memory if m.get("headline")]
        news = fetch_news(history_headlines)
        if not news:
            print("[Main] No new stories today. Exiting cleanly.")
            # Sync config even if exiting early (non-fatal)
            sync_env_to_config(env)
            sys.exit(0)

    # ── Step 3: Broadcast generation ────────────────────────────────
    healer_used:  bool = False
    writer_model: str  = "dry-run-stub"

    if dry_run:
        print("[Main] Dry-run: using hardcoded stub broadcast.")
        broadcast = dict(DRY_RUN_STUB)  # shallow copy to protect constant
    else:
        print("[Main] Generating broadcast (context_limit=15)…")
        broadcast, writer_model = generate_broadcast(news, memory, env, context_limit=15)

        if broadcast is None:
            print("[Main] First attempt failed. Retrying with reduced context (8 items)…")
            broadcast, writer_model = generate_broadcast(news, memory, env, context_limit=8)

        if broadcast is None:
            _fail("Broadcast generation failed after retry. Check AI client logs.")

        healer_used  = broadcast.pop("_healer_used", False)
        print(f"[Main] Broadcast generated by: {writer_model}")

    # ── Step 4: Audio generation ─────────────────────────────────────
    use_cloud     = env in PRODUCTION_ENVS and not dry_run
    segments      = broadcast["segments"]
    segment_paths: list[str] = []

    print(f"[Main] Generating audio for {len(segments)} segment(s)…")
    for i, seg in enumerate(segments):
        speaker      = seg.get("speaker", "HOST")
        text         = str(seg["text"])
        seg_path     = str(Path("output") / f"seg_{ts}_{i:03d}.mp3")

        ok = generate_segment_audio(text, speaker, seg_path, use_cloud)
        if not ok:
            _fail(f"Audio generation failed for segment {i} ({speaker}).")

        segment_paths.append(seg_path)
        print(f"  [TTS] Segment {i:03d} ({speaker}) → {seg_path}")

    # ── Step 5: Concatenate audio ────────────────────────────────────
    combined_audio = str(Path("output") / f"audio_{ts}.mp3")
    print(f"[Main] Concatenating {len(segment_paths)} audio file(s)…")
    if not concatenate_audio(segment_paths, combined_audio):
        _fail("Audio concatenation failed.")

    # ── Step 6: Validate duration ─────────────────────────────────────
    duration = get_audio_duration(combined_audio)
    print(f"[Main] Audio duration: {duration:.1f}s")

    min_dur = MIN_DURATION[env]
    if duration < min_dur:
        _fail(
            f"Audio duration {duration:.1f}s is below the minimum "
            f"{min_dur}s for env='{env}'."
        )

    # ── Step 7: Generate image ────────────────────────────────────────
    image_path = str(Path("assets") / f"art_{ts}.png")
    headline   = broadcast.get("headline", "AI Radio — Echo")
    print(f"[Main] Generating episode image: {image_path}")
    generate_image(headline, image_path)

    # ── Step 8: Compile video ─────────────────────────────────────────
    video_path = str(Path("output") / f"episode_{ts}.mp4")
    print(f"[Main] Compiling video: {video_path}")
    if not compile_video(image_path, combined_audio, video_path):
        _fail("Video compilation failed.")

    video_file = Path(video_path)
    if not video_file.exists() or video_file.stat().st_size == 0:
        _fail(f"Video file missing or empty after compile: {video_path}")

    print(f"[Main] Video ready: {video_path} ({video_file.stat().st_size:,} bytes)")

    # ── Step 9: YouTube upload ────────────────────────────────────────
    video_url: str | None = None

    if dry_run:
        print("[Main] Dry-run: YouTube upload mocked.")
    elif env == "production":
        print("[Main] Uploading to YouTube…")
        title       = headline[:100]
        description = broadcast.get("post_text", "")
        tags        = broadcast.get("topic_tags", [])
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except json.JSONDecodeError:
                tags = []

        video_url = upload_to_youtube(video_path, title, description, tags)
        if video_url is None:
            print("[Main] YouTube upload returned None. Continuing without video URL.")
        # Per spec: None return does NOT fail the pipeline.
    else:
        print(f"[Main] YouTube upload skipped for env='{env}'.")

    # ── Step 10: DB insert (skipped in dry-run) ───────────────────────
    if not dry_run and db is not None:
        topic_tags = broadcast.get("topic_tags", [])
        if isinstance(topic_tags, list):
            topic_tags = json.dumps(topic_tags)

        # audio_script: serialise the full broadcast dict (minus internal keys)
        script_copy = {k: v for k, v in broadcast.items() if not k.startswith("_")}
        audio_script = json.dumps(script_copy, ensure_ascii=False)

        confidence = broadcast.get("confidence", "medium")
        if confidence not in ("high", "medium", "low"):
            confidence = "medium"

        post_data = {
            "headline":          broadcast.get("headline",          ""),
            "original_headline": broadcast.get("original_headline", ""),
            "source":            broadcast.get("source",            ""),
            "topic_tags":        topic_tags,
            "my_take":           broadcast.get("my_take",           ""),
            "post_text":         broadcast.get("post_text",         ""),
            "audio_script":      audio_script,
            "audio_url":         None,    # no audio-only upload — never fake a URL
            "video_url":         video_url,
            "confidence":        confidence,
            "related_ids":       None,
            "broadcast_duration": int(duration),
            "healer_used":       healer_used,
            "writer_model":      writer_model,
            "narrator_model":    "groq-orpheus" if use_cloud else "edge-tts",
        }

        print("[Main] Saving episode to DB…")
        inserted = db.insert_post(post_data)
        if inserted is None:
            _fail("DB insert failed. Check db_client logs.")

        print(f"[Main] Saved to DB — id={inserted.get('id', 'unknown')}")
        db.delete_old_episodes(days_to_keep=30)

    # ── Step 11: Sync config ──────────────────────────────────────────
    sync_env_to_config(env)

    # ── Cleanup: remove per-segment audio files ───────────────────────
    for seg_path in segment_paths:
        try:
            os.unlink(seg_path)
        except OSError:
            pass

    print("\n[Main] Pipeline complete. ✓\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
