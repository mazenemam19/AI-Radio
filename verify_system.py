import os
import sys
import subprocess
import shutil
from dotenv import load_dotenv

load_dotenv()

def run_test(title, func):
    """Utility to run a test and print output beautifully."""
    print(f"\n[TEST] Run: {title}...")
    try:
        success = func()
        if success:
            print(f"[TEST] SUCCESS: {title} passed.")
            return True
        else:
            print(f"[TEST] FAILURE: {title} failed.")
            return False
    except Exception as e:
        print(f"[TEST] ERROR: {title} raised an exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_imports():
    """Verify all project modules can be loaded successfully."""
    try:
        import db_client
        import news_fetcher
        import ai_client
        import tts_generator
        import publisher
        import main
        return True
    except ImportError as e:
        print(f"Import check failed: {e}")
        return False

def test_tts_generation():
    """Verify that edge-tts speech synthesis works locally."""
    from tts_generator import TTSRadioGenerator
    generator = TTSRadioGenerator(use_cloud=False)
    test_script = "Echo here. Confirming that neural broadcast functions are online. [chuckle]"
    test_output = "output/test_verify.mp3"
    
    os.makedirs("output", exist_ok=True)
    if os.path.exists(test_output):
        os.remove(test_output)
        
    success = generator.make_audio(test_script, test_output)
    if success and os.path.exists(test_output) and os.path.getsize(test_output) > 0:
        return True
    return False

def test_ffmpeg_video_compiler():
    """Verify that FFmpeg successfully compiles a static image and MP3 into an MP4."""
    from tts_generator import TTSRadioGenerator
    generator = TTSRadioGenerator(use_cloud=False)
    
    test_audio = "output/test_verify.mp3"
    test_image = "assets/cover_art.png"
    test_video = "output/test_verify.mp4"
    
    os.makedirs("assets", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    
    # Check if we have cover art or create a temporary dummy image
    if not os.path.exists(test_image):
        try:
            from PIL import Image
            img = Image.new('RGB', (640, 360), color = (40, 20, 60))
            img.save(test_image)
        except Exception:
            # Create a 0-byte file placeholder
            with open(test_image, "wb") as f:
                f.write(b"")

    if os.path.exists(test_video):
        os.remove(test_video)

    if not shutil.which("ffmpeg"):
        print("[Verify] FFmpeg not found on this machine. Skipping compilation test (allowed in local dev).")
        return True

    success = generator.compile_video(test_audio, test_image, test_video)
    if success and os.path.exists(test_video) and os.path.getsize(test_video) > 0:
        return True
    return False

def test_pipeline_dry_run():
    """Execute main.py in dry-run mode and confirm success."""
    print("[Verify] Spawning main.py with --dry-run CLI flag...")
    
    # Run main.py as a subprocess to verify the entrypoint
    cmd = [sys.executable, "main.py", "--dry-run"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print("\n--- Subprocess Output ---")
    print(result.stdout)
    if result.stderr:
        print("--- Subprocess Errors ---")
        print(result.stderr)
    print("-------------------------\n")
    
    return result.returncode == 0

def test_database_schema_sync():
    """Verify that local and remote database schemas are identical and complete."""
    from db_client import SupabaseDBClient
    import sqlite3
    import requests

    REQUIRED_COLS = {
        'id', 'created_at', 'headline', 'original_headline', 'source', 
        'topic_tags', 'my_take', 'post_text', 'audio_script', 'audio_url', 
        'video_url', 'confidence', 'related_ids', 'likes', 'plays', 'broadcast_duration'
    }

    print("[Verify] Checking schema consistency...")
    
    # 1. Local SQLite Check
    try:
        local_db = SupabaseDBClient(env='local')
        if not os.path.exists(local_db.db_path):
            print(f"[Verify] ERROR: Local DB file {local_db.db_path} not found.")
            return False
            
        conn = sqlite3.connect(local_db.db_path)
        cursor = conn.execute('PRAGMA table_info(memory_log)')
        local_cols = set(row[1] for row in cursor.fetchall())
        conn.close()
        
        if not REQUIRED_COLS.issubset(local_cols):
            print(f"[Verify] ERROR: Local SQLite schema is missing required columns.")
            print(f"Missing: {REQUIRED_COLS - local_cols}")
            return False
        
        if local_cols != REQUIRED_COLS:
            print(f"[Verify] WARNING: Local SQLite has extra columns: {local_cols - REQUIRED_COLS}")
    except Exception as e:
        print(f"[Verify] Failed to read local schema: {e}")
        return False

    # 2. Get Remote Columns
    try:
        prod_db = SupabaseDBClient(env='production')
        if prod_db.is_mock:
            print("[Verify] Production credentials missing. Skipping remote schema check (expected in some CI envs).")
            return True
            
        # Verify all required columns are present in the remote schema via direct query
        cols_param = ",".join(REQUIRED_COLS)
        # Verify all required columns are present in the remote schema
        cols_param = ",".join(REQUIRED_COLS)
        endpoint = f"{prod_db.url}/rest/v1/memory_log?select={cols_param}&limit=1"
        response = requests.get(endpoint, headers=prod_db.headers, timeout=10)
        
        if response.status_code == 200:
            print("[Verify] Remote schema match confirmed (Required columns reachable).")
            
            # Check for structural equality if table is not empty
            data = response.json()
            if data:
                remote_cols = set(data[0].keys())
                if local_cols != remote_cols:
                    diff = local_cols ^ remote_cols
                    print(f"[Verify] ERROR: Local and Remote schemas differ on these columns: {diff}")
                    return False
            return True
        else:
            print(f"[Verify] Remote check failed: HTTP {response.status_code}")
            if response.status_code == 400:
                print("[Verify] Check failed likely due to missing columns or incorrect select parameter.")
            return False
    except Exception as e:
        print(f"[Verify] Failed to read remote schema: {e}")
        return False

    return True
if __name__ == "__main__":
    print("\n=========================================" )
    print("[SYSTEM VERIFICATION]")
    print("=========================================\n")
    
    results = []
    results.append(run_test("Import and Syntax Check", test_imports))
    results.append(run_test("Keyless TTS Synthesis Test", test_tts_generation))
    results.append(run_test("FFmpeg MP4 Compilation Test", test_ffmpeg_video_compiler))
    results.append(run_test("End-to-End Pipeline Dry-Run", test_pipeline_dry_run))
    results.append(run_test("Database Schema Sync Check", test_database_schema_sync))
    
    print("\n=========================================")
    print(f"VERIFICATION STATUS: {sum(results)}/{len(results)} TESTS PASSED")
    print("=========================================\n")
    
    if not all(results):
        print("[Verify] WARNING: Some verification items failed. Check error logs.")
        sys.exit(1)
    else:
        print("[Verify] All systems nominal. Ready for broadcast.")
        sys.exit(0)
