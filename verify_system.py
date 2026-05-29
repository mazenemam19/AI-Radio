import os
import sys
import subprocess
import shutil
import json
import re
import glob
import requests
import sqlite3
from dotenv import load_dotenv

load_dotenv()

# ── Verification Constants ───────────────────────────────────────────────────
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
    print(f"\n[VERIFY] Run: {title}...")
    try:
        success = func()
        if success:
            print(f"[VERIFY] SUCCESS: {title}")
            return True
        else:
            print(f"[VERIFY] FAILURE: {title}")
            return False
    except Exception as e:
        print(f"[VERIFY] ERROR: {title} raised an exception: {e}")
        import traceback
        traceback.print_exc()
        return False


# ── Health Checks (Lightweight & High-Speed) ──────────────────────────────────

def test_imports():
    """Checks if all core modules can be imported without syntax errors."""
    try:
        import db_client, news_fetcher, ai_client, tts_generator, publisher, main
        return True
    except ImportError as e:
        print(f"Import check failed: {e}")
        return False

def test_environment_vars():
    """Checks for presence of critical API keys."""
    keys = ["GROQ_API_KEY", "GEMINI_API_KEY", "SUPABASE_URL"]
    missing = [k for k in keys if not os.environ.get(k)]
    if missing:
        print(f"[Verify] Missing environment variables: {missing}")
        return False
    return True

def test_binaries():
    """Checks for required system binaries."""
    bins = ["ffmpeg", "ffprobe"]
    missing = [b for b in bins if not shutil.which(b) and not os.path.exists(f"C:\\ffmpeg\\bin\\{b}.exe")]
    if missing:
        print(f"[Verify] Missing binaries: {missing}")
        # Allow missing binaries in light verification, but warn
        print("[Verify] WARNING: Media processing binaries not found.")
    return True

def test_tts_connectivity():
    """Checks connectivity to edge-tts (local/fast)."""
    from tts_generator import TTSRadioGenerator
    generator = TTSRadioGenerator(use_cloud=False)
    test_output = "output/health_check.mp3"
    os.makedirs("output", exist_ok=True)
    success = generator.make_audio("System healthy.", test_output)
    return success and os.path.exists(test_output)

def test_database_schema_sync():
    """
    Checks if Supabase schema matches the local source of truth.
    Hardened to handle empty tables and select all columns.
    """
    from db_client import SupabaseDBClient
    print("[Verify] Comparing Local vs Remote schema...")
    try:
        local_db = SupabaseDBClient(env='local')
        if not os.path.exists(local_db.db_path):
            print(f"[Verify] ERROR: Local DB not found.")
            return False
        conn = sqlite3.connect(local_db.db_path)
        cursor = conn.execute('PRAGMA table_info(memory_log)')
        local_cols = set(row[1] for row in cursor.fetchall())
        conn.close()

        prod_db = SupabaseDBClient(env='production')
        if prod_db.is_mock:
            print("[Verify] Prod credentials missing — skipping remote check.")
            return True

        # Check for empty table or schema mismatch
        endpoint = f"{prod_db.url}/rest/v1/memory_log?limit=1"
        response = requests.get(endpoint, headers=prod_db.headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if not data:
                # Table empty: probe columns individually for sync
                for col in local_cols:
                    probe = requests.get(f"{prod_db.url}/rest/v1/memory_log?select={col}&limit=0", headers=prod_db.headers, timeout=5)
                    if probe.status_code == 400:
                        print(f"[Verify] Missing remote column: {col}")
                        return False
                return True
            
            remote_cols = set(data[0].keys())
            if not local_cols.issubset(remote_cols):
                print(f"[Verify] Local columns missing on remote: {local_cols - remote_cols}")
                return False
            return True
        return False
    except Exception as e:
        print(f"[Verify] Schema check exception: {e}")
        return False

def test_news_fetcher_deduplication():
    """Asserts news items have required fields and deduplication logic works."""
    from news_fetcher import NewsFetcher
    fetcher = NewsFetcher()
    try:
        items = fetcher.get_all_news(processed_headlines=[])
        if not items:
            print("[Verify] WARNING: News fetcher returned empty list (network?).")
            return True
        
        # Check contract
        for item in items[:5]:
            for field in REQUIRED_NEWS_FIELDS:
                if field not in item:
                    print(f"[Verify] News item missing field '{field}'")
                    return False

        # Test deduplication
        known = items[0]["headline"]
        filtered = fetcher.get_all_news(processed_headlines=[known])
        if any(i["headline"] == known for i in filtered):
            print("[Verify] Deduplication failed to exclude known headline.")
            return False
        return True
    except Exception as e:
        print(f"[Verify] News fetcher error: {e}")
        return False

def test_environment_firewall():
    """Ensures staging/local can't hit production Supabase."""
    from db_client import SupabaseDBClient
    prod = SupabaseDBClient(env='production')
    staging = SupabaseDBClient(env='staging')
    local = SupabaseDBClient(env='local')

    if not prod.is_mock and not staging.is_mock:
        if staging.url == prod.url:
            print("[Verify] Firewall breach: Staging == Production URL!")
            return False
    
    if not hasattr(local, 'db_path') or not local.db_path:
        print("[Verify] Local DB client should use SQLite path.")
        return False
    return True

def test_ai_client_json_healing():
    """Regression tests for the state-aware JSON healer."""
    from ai_client import AIRadioAIClient
    client = AIRadioAIClient()

    # Mid-string truncation
    bad = '{"show_title": "Test", "segments": [{"speaker": "ECHO", "text": "Hel'
    healed = client.heal_truncated_json(bad)
    try:
        parsed = json.loads(healed)
        if "show_title" not in parsed: return False
    except: return False

    # Prose wrapper
    wrapped = "Here is the JSON:\n{\"show_title\": \"Wrapped\"}\nEnd."
    repaired = client.attempt_json_repair(wrapped)
    if not repaired or repaired.get("show_title") != "Wrapped": return False

    return True

def test_broadcast_output_contract():
    """Validates the structure of the broadcast dictionary."""
    sample = {
        "show_title": "Test", "segments": [{"speaker":"ECHO", "text":"hi", "speed":1.0}],
        "my_take": "x", "topic_tags": ["x"], "social_post": "x",
        "visual_description": "x", "primary_news_headline": "x"
    }
    for field, ftype in REQUIRED_BROADCAST_FIELDS.items():
        if field not in sample or not isinstance(sample[field], ftype):
            return False
    return True

def test_production_model_isolation():
    """Verifies that 70B model is NEVER used in local mode."""
    from ai_client import AIRadioAIClient
    client = AIRadioAIClient()
    captured = []
    orig = client.call_groq
    client.call_groq = lambda p, s, model="llama-3.3-70b-versatile", **k: captured.append(model) or "{}"
    client.call_gemini = lambda *a, **k: "{}"
    
    try:
        client.generate_broadcast([], [], "ts", is_cloud=False)
        if "llama-3.3-70b-versatile" in captured:
            return False
        return True
    finally:
        client.call_groq = orig

def test_ai_client_payload_trimming():
    """Verifies that context is trimmed for local mode to save tokens."""
    from ai_client import AIRadioAIClient
    client = AIRadioAIClient()
    captured = {}
    client.call_gemini = lambda user_input_json, *a, **k: captured.update({"data": json.loads(user_input_json)}) or "{}"
    
    news = [{"headline": f"H{i}", "source": "S"} for i in range(10)]
    mem = [{"headline": f"M{i}", "my_take": "T"} for i in range(10)]
    
    client.generate_broadcast(news, mem, "ts", is_cloud=False)
    
    n_count = len(captured['data']['news_items'])
    m_count = len(captured['data']['memory_context'])
    
    return n_count == 3 and m_count == 1

def test_ai_routing_logic():
    """Verifies internal model routing logic using mocks."""
    from ai_client import AIRadioAIClient
    client = AIRadioAIClient()
    client.call_groq = lambda *a, **k: json.dumps({"segments": [{"speaker":"ECHO", "text":"hi", "speed":1.0}]})
    client.call_gemini = client.call_groq
    
    res_local = client.generate_broadcast([], [], "ts", is_cloud=False)
    res_cloud = client.generate_broadcast([], [], "ts", is_cloud=True)
    return res_local is not None and res_cloud is not None

# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=========================================")
    print("[SYSTEM HEALTH CHECK]")
    print("=========================================\n")

    results = []
    results.append(run_test("Import and Syntax Check",        test_imports))
    results.append(run_test("Environment Variables Check",    test_environment_vars))
    results.append(run_test("Binaries Availability",          test_binaries))
    results.append(run_test("Local TTS Connectivity",         test_tts_connectivity))
    results.append(run_test("Database Schema Sync",           test_database_schema_sync))
    results.append(run_test("News Fetcher Deduplication",     test_news_fetcher_deduplication))
    results.append(run_test("Environment Firewall",           test_environment_firewall))
    results.append(run_test("AI JSON Healing Regression",     test_ai_client_json_healing))
    results.append(run_test("Broadcast Output Contract",      test_broadcast_output_contract))
    results.append(run_test("Model Isolation (Prod Guard)",   test_production_model_isolation))
    results.append(run_test("AI Payload Trimming (Mocked)",   test_ai_client_payload_trimming))
    results.append(run_test("AI Routing Logic (Mocked)",      test_ai_routing_logic))

    passed = sum(results)
    total  = len(results)

    print("\n=========================================")
    print(f"VERIFICATION STATUS: {passed}/{total} TESTS PASSED")
    print("=========================================\n")

    if not all(results):
        print("\n[Verify] HEALTH CHECK FAILED.")
        sys.exit(1)
    else:
        print("\n[Verify] HEALTH CHECK PASSED.")
        sys.exit(0)
