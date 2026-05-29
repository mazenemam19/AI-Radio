import os
import sys
import subprocess
import shutil
import json
import re
import glob
from dotenv import load_dotenv

# Ensure we can import from parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# ── Quality Thresholds ────────────────────────────────────────────────────────
# These are strict for integration testing
MIN_BROADCAST_DURATION = 700   # 11.6 minutes
MIN_AUDIO_SIZE_BYTES   = 500_000 # Integration should produce a substantial file

def run_test(title, func):
    print(f"\n[INTEGRATION] Run: {title}...")
    try:
        success = func()
        if success:
            print(f"[INTEGRATION] SUCCESS: {title}")
            return True
        else:
            print(f"[INTEGRATION] FAILURE: {title}")
            return False
    except Exception as e:
        print(f"[INTEGRATION] ERROR: {title} raised an exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ffmpeg_video_compiler():
    """Heavy: Tests actual FFmpeg compilation with a real audio file."""
    from tts_generator import TTSRadioGenerator
    generator = TTSRadioGenerator(use_cloud=False)
    
    test_audio = "output/test_integration.mp3"
    # Ensure audio exists independently
    generator.make_audio("Echo here. Testing the integration compiler logic.", test_audio)
        
    test_image = "output/test_integration_cover.png"
    test_video = "output/test_integration.mp4"
    os.makedirs("output", exist_ok=True)
    
    # Create a dummy valid image if needed
    if not os.path.exists(test_image):
        try:
            from PIL import Image
            Image.new('RGB', (1280, 720), color=(20, 20, 40)).save(test_image)
        except Exception:
            with open(test_image, "wb") as f:
                f.write(b"dummy image data") 

    if os.path.exists(test_video):
        os.remove(test_video)
        
    if not shutil.which("ffmpeg"):
        print("[Integration] FFmpeg not found. Aborting test.")
        return False
        
    success = generator.compile_video(test_audio, test_image, test_video)
    return success and os.path.exists(test_video) and os.path.getsize(test_video) > 0

def test_pipeline_dry_run():
    """
    EXTREMELY HEAVY: Runs the full production pipeline in dry-run mode.
    Validates end-to-end connectivity, AI script generation, TTS rendering, 
    and FFmpeg compilation.
    """
    print("[Integration] Spawning full pipeline dry-run (env: local) ...")
    files_before = set(glob.glob("output/broadcast_*.mp3"))

    # Force --env local to save Groq 70B tokens while still testing the full flow
    cmd = [sys.executable, "main.py", "--dry-run", "--env", "local"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    print("\n--- Pipeline Output ---")
    print(result.stdout)
    if result.stderr:
        print("--- Pipeline Errors ---")
        print(result.stderr)
    print("------------------------\n")

    # Now that main.py exits non-zero, this is a real check
    if result.returncode != 0:
        print("[Integration] FAILURE: Pipeline exited with error code.")
        return False

    # Assert artifacts were created
    files_after = set(glob.glob("output/broadcast_*.mp3"))
    new_files = files_after - files_before
    if not new_files:
        print("[Integration] FAILURE: No artifacts generated.")
        return False

    # Assert duration was correct
    duration_match = re.search(r'Broadcast duration:\s*([\d.]+)\s*seconds', result.stdout)
    if not duration_match:
        print("[Integration] FAILURE: No duration reported.")
        return False

    duration = float(duration_match.group(1))
    if duration < MIN_BROADCAST_DURATION:
        print(f"[Integration] FAILURE: Duration {duration}s below prod threshold {MIN_BROADCAST_DURATION}s.")
        return False

    return True

if __name__ == "__main__":
    print("\n=========================================")
    print("[HEAVY INTEGRATION SUITE]")
    print("=========================================\n")

    results = []
    results.append(run_test("FFmpeg Video Compilation (Heavy)", test_ffmpeg_video_compiler))
    results.append(run_test("End-to-End Pipeline Dry-Run (Heavy)", test_pipeline_dry_run))

    if not all(results):
        print("\n[Integration] SUITE FAILED.")
        sys.exit(1)
    else:
        print("\n[Integration] SUITE PASSED.")
        sys.exit(0)
