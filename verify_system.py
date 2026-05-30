"""
verify_system.py — AI Radio Echo
Fast local verification: import check, TTS, FFmpeg, SQLite DB.
No API calls. Should complete in < 15 seconds.
Each test is independent — failure of one does not affect others.
Exit 0 if all pass, exit 1 if any fail.
"""

import os
import shutil
import sqlite3
import struct
import subprocess
import sys
import zlib
from pathlib import Path


# ------------------------------------------------------------------ #
#  Helpers shared across tests                                        #
# ------------------------------------------------------------------ #

def _ensure_output_dir() -> Path:
    p = Path("output")
    p.mkdir(exist_ok=True)
    return p


def _create_test_image(out_path: str) -> bool:
    """
    Create a minimal valid PNG for FFmpeg tests.
    Tries PIL first; falls back to stdlib-only approach.
    Returns True on success, False on failure.
    """
    try:
        from PIL import Image
        img = Image.new("RGB", (640, 360), color=(15, 15, 35))
        img.save(out_path)
        return True
    except ImportError:
        pass
    except Exception as e:
        print(f"  PIL image creation failed: {e}")

    # stdlib-only minimal PNG
    try:
        width, height = 640, 360

        def _chunk(ctype: bytes, data: bytes) -> bytes:
            crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
            return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc)

        sig  = b"\x89PNG\r\n\x1a\n"
        ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        raw  = (b"\x00" + bytes([15, 15, 35]) * width) * height
        idat = _chunk(b"IDAT", zlib.compress(raw, 1))
        iend = _chunk(b"IEND", b"")

        with open(out_path, "wb") as fh:
            fh.write(sig + ihdr + idat + iend)
        return True
    except Exception as e:
        print(f"  Stdlib PNG creation failed: {e}")
        return False


# ------------------------------------------------------------------ #
#  Test 1 — Import check                                              #
# ------------------------------------------------------------------ #

def test_imports() -> bool:
    print("\n[Test 1] Import check — all modules must load without error")
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
    for name in modules:
        try:
            __import__(name)
            print(f"  ✓ {name}")
        except Exception as exc:
            print(f"  ✗ {name}: {exc}")
            failed.append(name)

    if failed:
        print(f"[Test 1] FAIL — {len(failed)} module(s) failed to import.")
        return False

    print("[Test 1] PASS")
    return True


# ------------------------------------------------------------------ #
#  Test 2 — TTS synthesis (edge-tts only, no cloud)                  #
# ------------------------------------------------------------------ #

def test_tts() -> bool:
    print("\n[Test 2] TTS synthesis — generate a short audio file with edge-tts")
    out_dir = _ensure_output_dir()
    out_path = str(out_dir / "verify_tts.mp3")

    try:
        from tts_generator import generate_segment_audio
        text = (
            "This is a verification test for AI Radio Echo. "
            "The text-to-speech system is working correctly."
        )
        ok = generate_segment_audio(
            text=text,
            voice="HOST",
            path=out_path,
            use_cloud=False,   # always edge-tts for this test
        )
        if not ok:
            print("[Test 2] FAIL — generate_segment_audio returned False.")
            return False

        p = Path(out_path)
        if not p.exists() or p.stat().st_size == 0:
            print("[Test 2] FAIL — audio file missing or empty.")
            return False

        print(f"[Test 2] PASS — audio file: {out_path} ({p.stat().st_size:,} bytes)")
        return True

    except Exception as exc:
        print(f"[Test 2] FAIL — exception: {exc}")
        return False


# ------------------------------------------------------------------ #
#  Test 3 — FFmpeg compile (image + audio → MP4)                     #
# ------------------------------------------------------------------ #

def test_ffmpeg() -> bool:
    print("\n[Test 3] FFmpeg compile — still image + audio → MP4")
    out_dir  = _ensure_output_dir()
    img_path = str(out_dir / "verify_image.png")
    aud_path = str(out_dir / "verify_tts.mp3")
    vid_path = str(out_dir / "verify_video.mp4")

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("[Test 3] FAIL — FFmpeg not found in PATH.")
        return False

    # Create test image
    if not _create_test_image(img_path):
        print("[Test 3] FAIL — could not create test image.")
        return False

    # Audio file should exist from Test 2; if not, create a short silence
    if not Path(aud_path).exists():
        print("  Audio from Test 2 not found; generating 1-second silence via FFmpeg.")
        silence_result = subprocess.run(
            [
                ffmpeg, "-y",
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                "-t", "1",
                "-q:a", "9",
                "-acodec", "libmp3lame",
                aud_path,
            ],
            capture_output=True, text=True,
        )
        if silence_result.returncode != 0:
            print(f"[Test 3] FAIL — could not create silent audio: {silence_result.stderr[-300:]}")
            return False

    try:
        result = subprocess.run(
            [
                ffmpeg, "-y",
                "-loop", "1",     "-i", img_path,
                "-i", aud_path,
                "-c:v", "libx264",
                "-tune", "stillimage",
                "-c:a", "aac",
                "-b:a", "128k",
                "-pix_fmt", "yuv420p",
                "-shortest",
                vid_path,
            ],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"[Test 3] FAIL — FFmpeg error:\n{result.stderr[-500:]}")
            return False

        p = Path(vid_path)
        if not p.exists() or p.stat().st_size == 0:
            print("[Test 3] FAIL — output MP4 missing or empty.")
            return False

        print(f"[Test 3] PASS — video: {vid_path} ({p.stat().st_size:,} bytes)")
        return True

    except Exception as exc:
        print(f"[Test 3] FAIL — exception: {exc}")
        return False


# ------------------------------------------------------------------ #
#  Test 4 — SQLite DB: insert, fetch, verify                         #
# ------------------------------------------------------------------ #

def test_db() -> bool:
    print("\n[Test 4] SQLite DB — create table, insert row, fetch and verify fields")
    test_db_path = "verify_test.db"

    try:
        schema_path = Path("schema.sql")
        if not schema_path.exists():
            print("[Test 4] FAIL — schema.sql not found.")
            return False

        conn = sqlite3.connect(test_db_path)
        conn.row_factory = sqlite3.Row
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()

        test_row = {
            "headline":           "Verify Test Headline",
            "original_headline":  "Original verify headline",
            "source":             "VerifyTestSuite",
            "topic_tags":         '["verify", "test"]',
            "my_take":            "This is a verification test take.",
            "post_text":          "Verification test post text.",
            "audio_script":       "{}",
            "audio_url":          None,
            "video_url":          None,
            "confidence":         "high",
            "related_ids":        None,
            "broadcast_duration": 300,
            "healer_used":        False,
            "writer_model":       "test-model",
            "narrator_model":     "edge-tts",
        }

        cols   = list(test_row.keys())
        vals   = [test_row[c] for c in cols]
        cursor = conn.execute(
            f"INSERT INTO memory_log ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            vals,
        )
        conn.commit()
        row_id = cursor.lastrowid

        row = conn.execute(
            "SELECT * FROM memory_log WHERE id = ?", (row_id,)
        ).fetchone()
        conn.close()

        if row is None:
            print("[Test 4] FAIL — row not found after insert.")
            return False

        d = dict(row)
        checks = {
            "headline":   "Verify Test Headline",
            "source":     "VerifyTestSuite",
            "confidence": "high",
        }
        for field, expected in checks.items():
            if d.get(field) != expected:
                print(
                    f"[Test 4] FAIL — field '{field}': "
                    f"expected {expected!r}, got {d.get(field)!r}"
                )
                return False

        print(f"[Test 4] PASS — inserted id={row_id}, all fields verified.")
        return True

    except Exception as exc:
        print(f"[Test 4] FAIL — exception: {exc}")
        return False
    finally:
        try:
            os.unlink(test_db_path)
        except OSError:
            pass


# ------------------------------------------------------------------ #
#  Runner                                                             #
# ------------------------------------------------------------------ #

def main() -> None:
    results = {
        "imports": test_imports(),
        "tts":     test_tts(),
        "ffmpeg":  test_ffmpeg(),
        "db":      test_db(),
    }

    print("\n" + "=" * 50)
    print("  verify_system.py — Summary")
    print("=" * 50)
    all_pass = True
    for name, ok in results.items():
        status = "PASS ✓" if ok else "FAIL ✗"
        print(f"  {name:<12} {status}")
        if not ok:
            all_pass = False

    print("=" * 50)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
