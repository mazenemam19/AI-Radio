"""
verify_system.py — Fast system verification. No API calls. Target: < 15 seconds.

Tests (each independent — failure of one does not halt others):
  1. Import check:     import all pipeline modules.
  2. TTS synthesis:    generate a 2-sentence audio file with edge-tts.
  3. FFmpeg compile:   compile audio + generated test image into an MP4.
  4. DB local:         create a SQLite DB, insert a row, fetch it back, verify fields.

Exit 0 if all pass. Exit 1 if any fail.
"""

import shutil
import sys
import os
import tempfile
import time
from pathlib import Path

# Ensure the project root is in the path regardless of CWD
sys.path.insert(0, str(Path(__file__).parent))

results: dict[str, bool] = {}


# ---------------------------------------------------------------------------
# Test 1: Import check
# ---------------------------------------------------------------------------

def test_imports() -> bool:
    print("\n[Test 1] Import check...")
    modules = [
        "db_client",
        "news_fetcher",
        "ai_client",
        "tts_generator",
        "publisher",
        "sync_config",
        "main",
    ]
    failed = []
    for mod in modules:
        try:
            __import__(mod)
            print(f"  ✓ {mod}")
        except Exception as exc:
            print(f"  ✗ {mod}: {exc}")
            failed.append(mod)

    if failed:
        print(f"[Test 1] FAILED — could not import: {failed}")
        return False
    print("[Test 1] PASSED")
    return True


# ---------------------------------------------------------------------------
# Test 2: TTS synthesis with edge-tts
# ---------------------------------------------------------------------------

def test_tts() -> bool:
    print("\n[Test 2] TTS synthesis (edge-tts)...")
    try:
        import asyncio
        import edge_tts  # type: ignore
    except ImportError as exc:
        print(f"[Test 2] FAILED — edge-tts not installed: {exc}")
        return False

    text  = (
        "This is a system verification test for AI Radio Echo. "
        "The edge-tts engine is confirming that local audio synthesis is fully operational."
    )
    voice = "en-US-GuyNeural"

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "verify_tts.mp3")
        try:
            async def _synth():
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(out_path)

            try:
                asyncio.run(_synth())
            except RuntimeError as exc:
                if "event loop already running" in str(exc):
                    loop = asyncio.new_event_loop()
                    try:
                        loop.run_until_complete(_synth())
                    finally:
                        loop.close()
                else:
                    raise

            if not os.path.exists(out_path):
                print("[Test 2] FAILED — output file not created.")
                return False
            size = os.path.getsize(out_path)
            if size == 0:
                print("[Test 2] FAILED — output file is empty.")
                return False
            print(f"[Test 2] PASSED — {out_path} ({size:,} bytes)")
            return True

        except Exception as exc:
            print(f"[Test 2] FAILED — TTS exception: {exc}")
            return False


# ---------------------------------------------------------------------------
# Test 3: FFmpeg compile (audio + generated image → MP4)
# ---------------------------------------------------------------------------

def _generate_test_image(path: str):
    """Generate a minimal 1280×720 test PNG without any network calls."""
    try:
        from PIL import Image, ImageDraw  # type: ignore
        img  = Image.new("RGB", (1280, 720), color=(20, 20, 40))
        draw = ImageDraw.Draw(img)
        draw.rectangle([100, 300, 1180, 420], fill=(50, 50, 80))
        draw.text((640, 360), "AI Radio Echo — Verify", fill=(200, 200, 255))
        img.save(path)
    except ImportError:
        # Pillow not available: write minimal PNG bytes
        import struct
        import zlib

        width, height = 320, 180  # smaller fallback
        raw = (b"\x00" + b"\x00\x20\x20" * width) * height
        compressed = zlib.compress(raw)

        def _chunk(name, data):
            c = name + data
            return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

        png = (
            b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + _chunk(b"IDAT", compressed)
            + _chunk(b"IEND", b"")
        )
        Path(path).write_bytes(png)


def test_ffmpeg() -> bool:
    print("\n[Test 3] FFmpeg compile (audio + image → MP4)...")

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        print("[Test 3] FAILED — ffmpeg not found in PATH.")
        return False

    # We need an audio file — re-synthesise a short one with edge-tts
    import asyncio
    try:
        import edge_tts  # type: ignore
    except ImportError as exc:
        print(f"[Test 3] SKIPPED — edge-tts unavailable, cannot create test audio: {exc}")
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "test_audio.mp3")
        image_path = os.path.join(tmpdir, "test_image.png")
        video_path = os.path.join(tmpdir, "test_output.mp4")

        # Generate audio
        try:
            async def _synth():
                com = edge_tts.Communicate("FFmpeg compilation test.", "en-US-GuyNeural")
                await com.save(audio_path)

            try:
                asyncio.run(_synth())
            except RuntimeError as exc:
                if "event loop already running" in str(exc):
                    loop = asyncio.new_event_loop()
                    try:
                        loop.run_until_complete(_synth())
                    finally:
                        loop.close()
                else:
                    raise
        except Exception as exc:
            print(f"[Test 3] FAILED — could not generate test audio: {exc}")
            return False

        # Generate image
        _generate_test_image(image_path)

        # Compile video
        import subprocess
        cmd = [
            ffmpeg,
            "-loop", "1",
            "-i", image_path,
            "-i", audio_path,
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            "-y",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[Test 3] FAILED — FFmpeg error:\n{result.stderr[-500:]}")
            return False

        if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
            print("[Test 3] FAILED — output MP4 missing or empty.")
            return False

        size = os.path.getsize(video_path)
        print(f"[Test 3] PASSED — {video_path} ({size:,} bytes)")
        return True


# ---------------------------------------------------------------------------
# Test 4: SQLite DB — insert + fetch + verify
# ---------------------------------------------------------------------------

def test_db() -> bool:
    print("\n[Test 4] SQLite DB (insert / fetch / verify)...")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Temporarily override the working directory so DBClient creates its
        # sqlite file inside the temp dir without polluting the project root.
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            # Copy schema.sql into the temp dir
            schema_src = Path(original_cwd) / "schema.sql"
            if not schema_src.exists():
                # Try relative to this script's location
                schema_src = Path(__file__).parent / "schema.sql"
            if not schema_src.exists():
                print("[Test 4] FAILED — schema.sql not found.")
                return False

            import shutil as _shutil
            _shutil.copy(str(schema_src), os.path.join(tmpdir, "schema.sql"))

            from db_client import DBClient  # type: ignore

            db = DBClient("local")

            test_row = {
                "headline":          "Verify System Test Headline",
                "original_headline": "Verify System Test Headline",
                "source":            "verify_system.py",
                "topic_tags":        '["test"]',
                "audio_script":      '{"segments":[]}',
                "audio_url":         None,
                "video_url":         None,
                "confidence":        "high",
                "broadcast_duration": 42,
                "healer_used":       False,
                "writer_model":      "stub",
                "narrator_model":    "edge-tts",
            }

            inserted = db.insert_post(test_row)
            if inserted is None:
                print("[Test 4] FAILED — insert_post returned None.")
                return False

            rows = db.fetch_recent_memory(5)
            if not rows:
                print("[Test 4] FAILED — fetch_recent_memory returned empty list.")
                return False

            row = rows[0]
            assert row["headline"] == test_row["headline"], \
                f"headline mismatch: {row['headline']!r}"
            assert row["writer_model"] == "stub", \
                f"writer_model mismatch: {row['writer_model']!r}"
            assert row["broadcast_duration"] == 42, \
                f"broadcast_duration mismatch: {row['broadcast_duration']!r}"

            print("[Test 4] PASSED")
            return True

        except AssertionError as exc:
            print(f"[Test 4] FAILED — field verification error: {exc}")
            return False
        except Exception as exc:
            print(f"[Test 4] FAILED — exception: {exc}")
            return False
        finally:
            os.chdir(original_cwd)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("AI Radio Echo — System Verification")
    print("=" * 60)

    results["imports"] = test_imports()
    results["tts"]     = test_tts()
    results["ffmpeg"]  = test_ffmpeg()
    results["db"]      = test_db()

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    all_passed = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {status}  {name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\nAll checks passed.")
        sys.exit(0)
    else:
        print("\nOne or more checks failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
