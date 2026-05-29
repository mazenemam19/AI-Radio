import os
import sys
import argparse
import shutil
import time
import random
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

from db_client import SupabaseDBClient
from news_fetcher import NewsFetcher
from ai_client import AIRadioAIClient
from tts_generator import TTSRadioGenerator
from publisher import DistributionPublisher
from sync_config import sync_env_to_config

load_dotenv()

def setup_directories(env="production"):
    os.makedirs("assets", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    sync_env_to_config(env=env)
    db = SupabaseDBClient(env=env)
    db.delete_old_episodes(days_to_keep=7)

def copy_cover_art():
    local_cover = "assets/cover_art.png"
    if os.path.exists(local_cover) and os.path.getsize(local_cover) > 0:
        return local_cover
    return local_cover

def generate_neural_art(description, save_path):
    """Generate a high-quality 'dreamed up' image based on Echo's description."""
    print(f"[Main] Dreaming up visuals: {description[:50]}...")
    import requests
    import random
    try:
        # We use a high-quality, free, unlimited generative AI endpoint
        prompt_encoded = requests.utils.quote(description)
        seed = random.randint(0, 999999)
        # 1280x720 for perfect YouTube/HD resolution
        url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=1280&height=720&nologo=true&seed={seed}&model=flux"
        
        r = requests.get(url, timeout=45)
        if r.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(r.content)
            print(f"[Main] Neural Art materialized: {save_path}")
            return True
        return False
    except Exception as e:
        print(f"[Main] Vision failure: {e}")
        return False

def run_pipeline(env="production", dry_run=False, force_premium=False):
    # 0. THE MASTER SWITCH: Determine if this is a final performance or just a test/dev run
    is_ci_env = os.environ.get("GITHUB_ACTIONS") == "true"
    is_real_run = (env == "production" and not dry_run and is_ci_env) or force_premium
    
    # QUOTA SAVER: Use Premium Cloud TTS only for real broadcasts.
    use_cloud_tts = is_real_run
    
    print(f"--- [AI Radio Broadcast Start] --- Env: {env.upper()} --- Real Run: {is_real_run} --- Dry Run: {dry_run} ---")
    setup_directories(env=env)
    cover_image_path = copy_cover_art()

    db = SupabaseDBClient(env=env)
    fetcher = NewsFetcher()
    ai = AIRadioAIClient()
    tts = TTSRadioGenerator(use_cloud=use_cloud_tts)
    publisher = DistributionPublisher(env=env)

    # 1. Memory
    history = db.fetch_recent_memory(limit=20)
    processed_headlines = [item["headline"] for item in history]
    memory_context = [{"id": i["id"], "headline": i["headline"], "my_take": i.get("my_take", "")} for i in history]

    # 2. News
    print("[Main] Fetching news grid...")
    news_items = fetcher.get_all_news(processed_headlines=processed_headlines)
    if not news_items:
        print("[Main] No new stories. Staying off-air.")
        return True # Not an error, just no work

    # 3. AI SCRIPT (Now with Voice-Awareness)
    print(f"[Main] Invoking Echo for satirical script...")
    broadcast = ai.generate_broadcast(
        news_items=news_items[:15],
        memory_context=memory_context,
        timestamp=datetime.now(timezone.utc).isoformat(),
        is_cloud=is_real_run
    )

    if not broadcast or "segments" not in broadcast:
        print("[Main] Script generation failed.")
        return False

    # Extract flags
    healer_used = broadcast.pop("_healer_used", False)

    # 4. THE SHOW MUST GO ON
    show_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    audio_path = f"output/broadcast_{show_id}.mp3"
    video_path = f"output/broadcast_{show_id}.mp4"

    # NEW: Dream up unique visuals for this specific broadcast
    episode_image = f"assets/art_{show_id}.png"
    if not generate_neural_art(broadcast.get("visual_description", "Surreal technology chaos"), episode_image):
        episode_image = copy_cover_art()
        if episode_image is None:
            print("[Main] No background image available. Aborting.")
            return False

    if not tts.make_broadcast_audio(broadcast["segments"], audio_path):
        return False

    # Use the 'dreamed up' image for the video compilation
    if not tts.compile_video(audio_path, episode_image, video_path):
        print("[Main] Video compilation failed. Aborting.")
        return False

    # Calculate exact duration
    duration = tts.get_audio_duration(audio_path)
    print(f"[Main] Broadcast duration: {duration} seconds.")

    # Duration Gate: Production requires 700s (~11.6m), Local/Test requires 250s
    MIN_BROADCAST_DURATION = 700 if is_real_run else 250
    if duration < MIN_BROADCAST_DURATION:
        print(f"[Main] ABORT: Duration {duration}s below minimum {MIN_BROADCAST_DURATION}s. Discarding episode.")
        return False

    # 5. DISTRIBUTION
    video_url = None
    if env == "production" and not dry_run:
        video_url = publisher.upload_to_youtube(
            video_path=video_path,
            title=broadcast["show_title"],
            description=f"{broadcast['my_take']}\n\nBroadcasted by Echo AI.",
            tags=broadcast["topic_tags"]
        )
        publisher.post_to_bluesky(broadcast["social_post"])
    else:
        video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    # 6. SAVE TO DB
    if not dry_run:
        # Save the show title to 'headline' (for dashboard) and original headline to 'original_headline' (for deduplication)
        full_script = json.dumps(broadcast["segments"])
        db.insert_post(
            headline=f"[{broadcast['show_title']}] {broadcast.get('primary_news_headline', 'Daily Broadcast')}",
            original_headline=broadcast.get('primary_news_headline', 'Daily Broadcast'),
            source="The Echo Broadcast",
            topic_tags=broadcast["topic_tags"],
            my_take=broadcast["my_take"],
            post_text=broadcast["social_post"],
            audio_script=full_script,
            audio_url=f"local://broadcast_{show_id}.mp3" if env != "production" else f"https://placeholder.com",
            video_url=video_url,
            confidence="high",
            broadcast_duration=duration,
            healer_used=healer_used
        )
    if env == "local": sync_env_to_config(env="local")
    print(f"\n--- [Broadcast Complete] --- Show: {broadcast['show_title']} ---")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", choices=["production", "staging", "local"], default=None)
    parser.add_argument("--dry-run", action="store_true", help="Run pipeline in dry-run mode without publishing")
    parser.add_argument("--premium", action="store_true", help="Force production AI/TTS models even in local mode")
    args = parser.parse_args()

    # Determine environment
    selected_env = args.env
    if not selected_env:
        selected_env = "local" if args.dry_run else "production"
    
    success = run_pipeline(env=selected_env, dry_run=args.dry_run, force_premium=args.premium)
    sys.exit(0 if success else 1)
