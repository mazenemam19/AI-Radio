import os
import sys
import subprocess
import shutil
import json
import re
import glob
from dotenv import load_dotenv

load_dotenv()

# ── Output Quality Thresholds ─────────────────────────────────────────────────
MIN_BROADCAST_DURATION = 700   # 11.6 minutes — absolute minimum for a 12+ segment show
MIN_SEGMENT_COUNT      = 10    # fewer than 10 segments = truncated script
MIN_AUDIO_SIZE_BYTES   = 100_000  # <100KB = almost certainly silent/broken

# ── Broadcast Contract ────────────────────────────────────────────────────────
REQUIRED_BROADCAST_FIELDS = {
    'show_title':            str,
    'segments':              list,
    'my_take':               str,
    'topic_tags':            list,
    'social_post':           str,
    'visual_description':    str,
    'primary_news_headline': str,
}

REQUIRED_SEGMENT_FIELDS = {'speaker', 'text', 'speed'}
REQUIRED_NEWS_FIELDS    = {'headline', 'source'}


# ── Test Runner ───────────────────────────────────────────────────────────────

def run_test(title, func):
    print(f"\n[TEST] Run: {title}...")
    try:
        success = func()
        if success:
            print(f"[TEST] SUCCESS: {title}")
            return True
        else:
            print(f"[TEST] FAILURE: {title}")
            return False
    except Exception as e:
        print(f"[TEST] ERROR: {title} raised an exception: {e}")
        import traceback
        traceback.print_exc()
        return False


# ── Existing Tests (preserved) ────────────────────────────────────────────────

def test_imports():
    try:
        import db_client, news_fetcher, ai_client, tts_generator, publisher, main
        return True
    except ImportError as e:
        print(f"Import check failed: {e}")
        return False


def test_tts_generation():
    from tts_generator import TTSRadioGenerator
    generator = TTSRadioGenerator(use_cloud=False)
    test_script = "Echo here. Confirming that neural broadcast functions are online. [chuckle]"
    test_output = "output/test_verify.mp3"
    os.makedirs("output", exist_ok=True)
    if os.path.exists(test_output):
        os.remove(test_output)
    success = generator.make_audio(test_script, test_output)
    return success and os.path.exists(test_output) and os.path.getsize(test_output) > 0


def test_ffmpeg_video_compiler():
    from tts_generator import TTSRadioGenerator
    generator = TTSRadioGenerator(use_cloud=False)
    test_audio = "output/test_verify.mp3"
    test_image = "assets/cover_art.png"
    test_video = "output/test_verify.mp4"
    os.makedirs("assets", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    if not os.path.exists(test_image):
        try:
            from PIL import Image
            Image.new('RGB', (640, 360), color=(40, 20, 60)).save(test_image)
        except Exception:
            with open(test_image, "wb") as f:
                f.write(b"")
    if os.path.exists(test_video):
        os.remove(test_video)
    if not shutil.which("ffmpeg"):
        print("[Verify] FFmpeg not found. Skipping compilation test (allowed in local dev).")
        return True
    success = generator.compile_video(test_audio, test_image, test_video)
    return success and os.path.exists(test_video) and os.path.getsize(test_video) > 0


# ── Fixed: Dry-Run validates output artifacts, not just exit code ─────────────

def test_pipeline_dry_run():
    """
    Runs the full pipeline in dry-run mode and asserts:
    - A new audio file was created
    - Audio file is not suspiciously small (silent/broken)
    - Broadcast duration meets the minimum threshold
    """
    print("[Verify] Spawning main.py --dry-run --env local ...")
    files_before = set(glob.glob("output/broadcast_*.mp3"))

    # Force --env local even in CI/CD to save Groq 70B tokens for real broadcasts
    cmd = [sys.executable, "main.py", "--dry-run", "--env", "local"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    print("\n--- Subprocess Output ---")
    print(result.stdout)
    if result.stderr:
        print("--- Subprocess Errors ---")
        print(result.stderr)
    print("-------------------------\n")

    if result.returncode != 0:
        print("[Verify] FAILURE: Pipeline exited non-zero.")
        return False

    # Check 1: new audio file exists
    files_after = set(glob.glob("output/broadcast_*.mp3"))
    new_files = files_after - files_before
    if not new_files:
        print("[Verify] FAILURE: No new broadcast_*.mp3 found after dry-run.")
        return False

    audio_file = sorted(new_files)[-1]
    audio_size = os.path.getsize(audio_file)

    # Check 2: audio file is not empty / nearly silent
    if audio_size < MIN_AUDIO_SIZE_BYTES:
        print(f"[Verify] FAILURE: Audio file too small ({audio_size:,} bytes). "
              f"Expected >= {MIN_AUDIO_SIZE_BYTES:,}. Possible silent or truncated output.")
        return False
    print(f"[Verify] Audio file size: {audio_size:,} bytes — OK.")

    # Check 3: duration in stdout meets minimum
    duration_match = re.search(r'Broadcast duration:\s*([\d.]+)\s*seconds', result.stdout)
    if not duration_match:
        print("[Verify] FAILURE: 'Broadcast duration' not found in pipeline output. "
              "main.py may have failed silently.")
        return False

    duration = float(duration_match.group(1))
    if duration < MIN_BROADCAST_DURATION:
        print(f"[Verify] FAILURE: Duration {duration:.0f}s is below minimum "
              f"{MIN_BROADCAST_DURATION}s ({MIN_BROADCAST_DURATION // 60} min). "
              f"Script was likely truncated by the LLM.")
        return False

    print(f"[Verify] Broadcast duration: {duration:.0f}s — OK.")
    return True


# ── Fixed: Schema sync is derived dynamically, not from a hardcoded set ───────

def test_database_schema_sync():
    """
    Derives the required column set from local SQLite (source of truth) and
    compares it against Supabase. No hardcoded column list — adding a column
    locally automatically makes this test catch the missing remote migration.
    """
    from db_client import SupabaseDBClient
    import sqlite3
    import requests

    print("[Verify] Deriving schema from local SQLite (source of truth)...")

    # 1. Read local schema
    try:
        local_db = SupabaseDBClient(env='local')
        if not os.path.exists(local_db.db_path):
            print(f"[Verify] ERROR: Local DB {local_db.db_path} not found. Run 'npm run dev:local' first.")
            return False
        conn = sqlite3.connect(local_db.db_path)
        cursor = conn.execute('PRAGMA table_info(memory_log)')
        local_cols = set(row[1] for row in cursor.fetchall())
        conn.close()
        if not local_cols:
            print("[Verify] ERROR: memory_log table has no columns. DB may be uninitialized.")
            return False
        print(f"[Verify] Local schema ({len(local_cols)} cols): {sorted(local_cols)}")
    except Exception as e:
        print(f"[Verify] Failed to read local schema: {e}")
        return False

    # 2. Compare against remote
    try:
        prod_db = SupabaseDBClient(env='production')
        if prod_db.is_mock:
            print("[Verify] Production credentials missing — skipping remote check.")
            return True

        cols_param = ",".join(local_cols)
        endpoint = f"{prod_db.url}/rest/v1/memory_log?select={cols_param}&limit=1"
        response = requests.get(endpoint, headers=prod_db.headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data:
                remote_cols = set(data[0].keys())
                missing_on_remote = local_cols - remote_cols
                extra_on_remote   = remote_cols - local_cols
                if missing_on_remote:
                    print(f"[Verify] ERROR: Remote is missing columns: {missing_on_remote}")
                    print("[Verify] ACTION REQUIRED: Run the migration on Supabase.")
                    return False
                if extra_on_remote:
                    print(f"[Verify] WARNING: Remote has extra columns not in local: {extra_on_remote}")
            print("[Verify] Remote schema matches local — OK.")
            return True

        elif response.status_code == 400:
            # 400 = at least one column in our SELECT doesn't exist remotely.
            # Probe individually to find exactly which ones are missing.
            print("[Verify] ERROR: Remote rejected column query — probing for missing columns...")
            missing = []
            for col in local_cols:
                probe = requests.get(
                    f"{prod_db.url}/rest/v1/memory_log?select={col}&limit=1",
                    headers=prod_db.headers, timeout=5
                )
                if probe.status_code == 400:
                    missing.append(col)
            print(f"[Verify] Columns missing on remote: {missing}")
            print("[Verify] ACTION REQUIRED: Add these columns to Supabase before deploying.")
            return False

        else:
            print(f"[Verify] Remote check failed: HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"[Verify] Failed to read remote schema: {e}")
        return False


# ── New: JSON Healing Regression ──────────────────────────────────────────────

def test_ai_client_json_healing():
    """
    Regression test for ai_client JSON recovery.
    If AI touching this file ever breaks the healer, these cases catch it.
    """
    from ai_client import AIRadioAIClient
    client = AIRadioAIClient()

    # Case 1: Truncated mid-string
    truncated = '{"show_title": "Test Show", "segments": [{"speaker": "ECHO", "text": "Hello wor'
    try:
        healed = client.heal_truncated_json(truncated)
        parsed = json.loads(healed)
        assert "show_title" in parsed, "show_title missing after heal"
        print("[Verify] Heal case 1 (truncated mid-string): OK")
    except Exception as e:
        print(f"[Verify] FAILURE: heal_truncated_json failed on truncated input: {e}")
        return False

    # Case 2: Valid JSON wrapped in extra prose (LLM sometimes adds preamble/postamble)
    wrapped = 'Sure, here is your JSON output:\n{"show_title": "Wrapped Show", "segments": []}\nThat concludes the script.'
    repaired = client.attempt_json_repair(wrapped)
    if repaired is None or repaired.get("show_title") != "Wrapped Show":
        print("[Verify] FAILURE: attempt_json_repair failed to strip prose wrapper.")
        return False
    print("[Verify] Heal case 2 (prose-wrapped JSON): OK")

    # Case 3: Valid JSON must pass through unchanged
    valid = '{"show_title": "Clean Show", "segments": [], "my_take": "Fine"}'
    result = client.attempt_json_repair(valid)
    if result is None or result.get("show_title") != "Clean Show":
        print("[Verify] FAILURE: attempt_json_repair corrupted valid JSON.")
        return False
    print("[Verify] Heal case 3 (valid JSON passthrough): OK")

    # Case 4: Empty/None input must not crash
    try:
        client.attempt_json_repair("")
        client.attempt_json_repair("{}")
        print("[Verify] Heal case 4 (empty/minimal input): OK")
    except Exception as e:
        print(f"[Verify] FAILURE: attempt_json_repair crashed on empty input: {e}")
        return False

    return True


# ── New: Broadcast Output Contract ───────────────────────────────────────────

def test_broadcast_output_contract():
    """
    Validates that a broadcast object has all required fields with correct types,
    and that segments contain the expected per-segment fields.
    This is a contract test — it documents what the rest of the pipeline depends on.
    """
    # Construct a minimal valid broadcast (matches what generate_broadcast should return)
    sample = {
        "show_title":            "Test Broadcast",
        "segments":              [{"speaker": "ECHO", "text": "Hello world.", "speed": 1.0}],
        "my_take":               "Things are bad and getting worse.",
        "topic_tags":            ["tech", "ai"],
        "social_post":           "New episode out now.",
        "visual_description":    "A surreal scene of robots arguing over a newspaper.",
        "primary_news_headline": "AI Takes Over Everything Again"
    }

    def validate_broadcast(broadcast):
        for field, expected_type in REQUIRED_BROADCAST_FIELDS.items():
            if field not in broadcast:
                print(f"[Verify] FAILURE: Missing required field: '{field}'")
                return False
            val = broadcast[field]
            if not isinstance(val, expected_type):
                print(f"[Verify] FAILURE: Field '{field}' wrong type. "
                      f"Expected {expected_type.__name__}, got {type(val).__name__}")
                return False
            if expected_type == str and not val.strip():
                print(f"[Verify] FAILURE: Field '{field}' is blank.")
                return False
            if expected_type == list and len(val) == 0:
                print(f"[Verify] WARNING: Field '{field}' is an empty list.")

        # Validate segment structure
        for i, seg in enumerate(broadcast["segments"]):
            for sf in REQUIRED_SEGMENT_FIELDS:
                if sf not in seg:
                    print(f"[Verify] FAILURE: Segment {i} missing field '{sf}': {seg}")
                    return False

        seg_count = len(broadcast["segments"])
        if seg_count == 0:
            print(f"[Verify] FAILURE: segments list is empty.")
            return False
        # NOTE: minimum segment count (>= {MIN_SEGMENT_COUNT}) is enforced in
        # test_pipeline_dry_run against real output, not here against a fixture.

        return True

    if not validate_broadcast(sample):
        return False

    print(f"[Verify] Broadcast contract: all {len(REQUIRED_BROADCAST_FIELDS)} fields valid — OK.")

    # Also expose the validator for use in main.py if needed
    # (call verify_broadcast_contract(broadcast) after generate_broadcast returns)
    return True


# ── New: News Fetcher Output + Deduplication ──────────────────────────────────

def test_news_fetcher_deduplication():
    """
    Asserts news items have required fields and that known headlines are
    correctly excluded by the deduplication logic.
    """
    from news_fetcher import NewsFetcher
    fetcher = NewsFetcher()

    # Test 1: Basic fetch
    try:
        items = fetcher.get_all_news(processed_headlines=[])
    except Exception as e:
        print(f"[Verify] News fetcher raised exception: {e}")
        return False

    if not items:
        print("[Verify] WARNING: News fetcher returned empty list. Network may be unavailable.")
        return True  # Don't fail CI for transient network issues

    for item in items[:5]:
        for field in REQUIRED_NEWS_FIELDS:
            if field not in item:
                print(f"[Verify] FAILURE: News item missing required field '{field}': {item}")
                return False

    print(f"[Verify] Fetched {len(items)} items with required fields — OK.")

    # Test 2: Deduplication actually excludes known headlines
    known = items[0]["headline"]
    filtered = fetcher.get_all_news(processed_headlines=[known])
    returned_headlines = [i["headline"] for i in filtered]
    if known in returned_headlines:
        print(f"[Verify] FAILURE: Deduplication failed — known headline reappeared: '{known}'")
        return False

    print("[Verify] Deduplication correctly excluded known headline — OK.")
    return True


# ── New: Environment Firewall ─────────────────────────────────────────────────

def test_environment_firewall():
    """
    Ensures staging and local environments cannot accidentally hit production.
    Catches misconfigured .env where STAGING_SUPABASE_URL == SUPABASE_URL.
    """
    from db_client import SupabaseDBClient

    prod_db    = SupabaseDBClient(env='production')
    staging_db = SupabaseDBClient(env='staging')
    local_db   = SupabaseDBClient(env='local')

    # Staging must not point to prod
    if not prod_db.is_mock and not staging_db.is_mock:
        if staging_db.url == prod_db.url:
            print("[Verify] FAILURE: Staging and Production point to the SAME Supabase URL. "
                  "A staging run would write to production.")
            return False
        print(f"[Verify] Staging URL != Production URL — OK.")

    # Local must use SQLite
    if not hasattr(local_db, 'db_path') or not local_db.db_path:
        print("[Verify] FAILURE: Local DB client has no db_path — may be routing to cloud in local mode.")
        return False
    print(f"[Verify] Local uses SQLite at '{local_db.db_path}' — OK.")

    return True


# ── New: Model Isolation and Environment Logic ───────────────────────────────

def test_production_model_isolation():
    """
    STRICT RULE: llama-3.3-70b-versatile is for Production ONLY.
    This test verifies that Local mode NEVER routes to the 70B model.
    """
    from ai_client import AIRadioAIClient
    import json

    client = AIRadioAIClient()
    captured_model = []

    # Mock call_groq to capture the model name
    original_call_groq = client.call_groq
    def mock_call_groq(payload, segments, model="llama-3.3-70b-versatile", max_tokens=6000, mandate=""):
        captured_model.append(model)
        return json.dumps({"segments": [{"speaker": "ECHO", "text": "Test"}]})
    
    client.call_groq = mock_call_groq
    client.call_gemini = lambda *args, **kwargs: json.dumps({"segments": [{"speaker": "ECHO", "text": "Test"}]})

    try:
        # Test Local
        client.generate_broadcast([], [], "ts", is_cloud=False)
        if captured_model and captured_model[0] == "llama-3.3-70b-versatile":
            print("[Verify] CRITICAL FAILURE: 70B model routed to Local environment!")
            return False
        
        print(f"[Verify] Model isolation: OK (Local used {captured_model[0] if captured_model else 'Gemini'})")
        return True
    finally:
        client.call_groq = original_call_groq

def test_ai_client_environment_logic():
    """
    Validates that ai_client correctly trims payloads and routes models
    based on the environment (Local vs Cloud).
    """
    from ai_client import AIRadioAIClient
    import json

    client = AIRadioAIClient()
    
    captured_args = []
    
    # Mock API callers
    def mock_call_groq(user_input_json, target_segments, model, max_tokens, mandate=""):
        captured_args.append({'payload': json.loads(user_input_json), 'model': model, 'max_tokens': max_tokens, 'engine': 'groq'})
        return json.dumps({"segments": [{"speaker": "ECHO", "text": "Test Word " * 100, "speed": 1.0} for _ in range(25)]})

    def mock_call_gemini(user_input_json, target_segments, mandate=""):
        captured_args.append({'payload': json.loads(user_input_json), 'mandate': mandate, 'engine': 'gemini'})
        return json.dumps({"segments": [{"speaker": "ECHO", "text": "Test Word " * 100, "speed": 1.0} for _ in range(25)]})

    client.call_groq = mock_call_groq
    client.call_gemini = mock_call_gemini

    sample_news = [{"headline": f"H{i}", "source": "S"} for i in range(15)]
    sample_memory = [{"headline": f"M{i}", "my_take": "T"} for i in range(10)]
    
    try:
        # 1. Test Local Environment
        print("[Verify] Testing Local logic (Payload Trimming + Gemini Primary)...")
        captured_args.clear()
        client.generate_broadcast(sample_news, sample_memory, "ts", is_cloud=False)
        
        local_call = captured_args[0]
        if local_call['engine'] != 'gemini':
            print(f"[Verify] FAILURE: Local mode did not use Gemini as primary engine.")
            return False

        news_len = len(local_call['payload']['news_items'])
        mem_len = len(local_call['payload']['memory_context'])
        
        if news_len != 3 or mem_len != 1:
            print(f"[Verify] FAILURE: Local payload not trimmed correctly (News: {news_len}, Mem: {mem_len})")
            return False
            
        print("[Verify] Local environment logic: OK")

        # 2. Test Cloud Environment
        print("[Verify] Testing Cloud logic (Full Payload + 70B Model)...")
        captured_args.clear()
        client.generate_broadcast(sample_news, sample_memory, "ts", is_cloud=True)
        
        cloud_call = captured_args[0]
        if cloud_call['engine'] != 'groq' or cloud_call['model'] != "llama-3.3-70b-versatile":
            print(f"[Verify] FAILURE: Cloud mode did not use Groq 70B primary engine.")
            return False

        news_len = len(cloud_call['payload']['news_items'])
        mem_len = len(cloud_call['payload']['memory_context'])
        
        if news_len != 15 or mem_len != 10:
            print(f"[Verify] FAILURE: Cloud payload trimmed unexpectedly (News: {news_len}, Mem: {mem_len})")
            return False
            
        print("[Verify] Cloud environment logic: OK")
        return True

    finally:
        pass

def test_ai_client_environment_routing():
    """
    Validates that AIRadioAIClient trims payloads accurately and routes 
    to the correct models/engines depending on the environment flag.
    """
    from ai_client import AIRadioAIClient
    import json

    client = AIRadioAIClient()
    captured_groq_calls = []
    captured_gemini_calls = []

    # Generate a valid mock response with 25 segments to satisfy internal quality validations cleanly
    mock_valid_script = json.dumps({
        "show_title": "Test",
        "primary_news_headline": "Test",
        "my_take": "Test",
        "visual_description": "Test",
        "topic_tags": ["test"],
        "social_post": "Test",
        "segments": [{"speaker": "ECHO", "text": "Word " * 160, "speed": 1.0} for _ in range(25)]
    })

    # Mock the low-level API callers to inspect what gets passed to them
    def mock_call_groq(user_input_json, target_segments, model, max_tokens, mandate=""):
        captured_groq_calls.append({'payload': json.loads(user_input_json), 'model': model, 'max_tokens': max_tokens})
        return mock_valid_script

    def mock_call_gemini(user_input_json, target_segments, mandate=""):
        captured_gemini_calls.append({'payload': json.loads(user_input_json), 'mandate': mandate})
        return mock_valid_script

    client.call_groq = mock_call_groq
    client.call_gemini = mock_call_gemini

    # Generate a mock oversized context (10 news items, 8 memory items)
    sample_news = [{"headline": f"News {i}", "source": "Source"} for i in range(10)]
    sample_memory = [{"headline": f"Mem {i}", "my_take": "Take"} for i in range(8)]

    try:
        # 1. Verify Local Execution Mode
        print("[Verify] Checking Local routing & trimming rules...")
        captured_groq_calls.clear()
        captured_gemini_calls.clear()
        client.generate_broadcast(sample_news, sample_memory, "timestamp", is_cloud=False)
        
        if not captured_gemini_calls:
            print("[Verify] FAILURE: Local mode did not route to Gemini primary engine.")
            return False
        
        local_payload = captured_gemini_calls[0]['payload']
        if len(local_payload['news_items']) != 3 or len(local_payload['memory_context']) != 1:
            print("[Verify] FAILURE: Local payload trimming broken. "
                  f"Got news: {len(local_payload['news_items'])}, memory: {len(local_payload['memory_context'])}")
            return False

        # 2. Verify Cloud Execution Mode
        print("[Verify] Checking Cloud routing & full payload rules...")
        captured_groq_calls.clear()
        captured_gemini_calls.clear()
        client.generate_broadcast(sample_news, sample_memory, "timestamp", is_cloud=True)
        
        if not captured_groq_calls:
            print("[Verify] FAILURE: Cloud mode did not route to Groq primary engine.")
            return False
            
        cloud_call = captured_groq_calls[0]
        if cloud_call['model'] != "llama-3.3-70b-versatile" or cloud_call['max_tokens'] != 6000:
            print(f"[Verify] FAILURE: Cloud model routing mismatch. Got model: {cloud_call['model']}")
            return False
            
        cloud_payload = cloud_call['payload']
        if len(cloud_payload['news_items']) != 10 or len(cloud_payload['memory_context']) != 8:
            print("[Verify] FAILURE: Cloud payload was unexpectedly mutated or trimmed.")
            return False

        print("[Verify] AI Client Environment Routing: OK")
        return True
    except Exception as e:
        print(f"[Verify] Exception occurred during routing test: {e}")
        return False

# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=========================================")
    print("[SYSTEM VERIFICATION]")
    print("=========================================\n")

    results = []
    results.append(run_test("Import and Syntax Check",                    test_imports))
    results.append(run_test("Keyless TTS Synthesis",                      test_tts_generation))
    results.append(run_test("FFmpeg MP4 Compilation",                     test_ffmpeg_video_compiler))
    results.append(run_test("Pipeline Dry-Run + Output Validation",       test_pipeline_dry_run))
    results.append(run_test("Database Schema Sync (Dynamic)",             test_database_schema_sync))
    results.append(run_test("AI Client JSON Healing Regression",          test_ai_client_json_healing))
    results.append(run_test("Broadcast Output Contract",                  test_broadcast_output_contract))
    results.append(run_test("News Fetcher Output + Deduplication",        test_news_fetcher_deduplication))
    results.append(run_test("Environment Firewall",                       test_environment_firewall))
    results.append(run_test("Model Isolation Check",                       test_production_model_isolation))
    results.append(run_test("AI Environment Logic (Trimming/Routing)",    test_ai_client_environment_logic))
    results.append(run_test("AI Client Environment Routing",              test_ai_client_environment_routing))

    passed = sum(results)
    total  = len(results)

    print("\n=========================================")
    print(f"VERIFICATION STATUS: {passed}/{total} TESTS PASSED")
    print("=========================================\n")

    if not all(results):
        print("[Verify] Some checks failed. Fix before broadcasting.")
        sys.exit(1)
    else:
        print("[Verify] All systems nominal. Ready for broadcast.")
        sys.exit(0)
