import os
import sys
import argparse
import shutil
import time
import random
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

def run_pipeline(env="production", dry_run=False):
    is_github = os.environ.get("GITHUB_ACTIONS") == "true"
    
    # QUOTA SAVER: Use Premium Cloud TTS only in Production. 
    # Use Standard Local TTS for Staging and Local.
    use_cloud_tts = (env == "production")
    
    print(f"--- [AI Radio Broadcast Start] --- Env: {env.upper()} --- Dry Run: {dry_run} ---")
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
        return

    # 3. AI SCRIPT (Now with Voice-Awareness)
    print(f"[Main] Invoking Echo for satirical script (Cloud Mode? {is_github})...")
    broadcast = ai.generate_broadcast(
        news_items=news_items[:15],
        memory_context=memory_context,
        timestamp=datetime.now(timezone.utc).isoformat(),
        is_cloud=is_github
    )

    if not broadcast or "segments" not in broadcast:
        print("[Main] Script generation failed.")
        return

    # 4. THE SHOW MUST GO ON
    show_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    audio_path = f"output/broadcast_{show_id}.mp3"
    video_path = f"output/broadcast_{show_id}.mp4"

    # NEW: Dream up unique visuals for this specific broadcast
    episode_image = f"assets/art_{show_id}.png"
    if not generate_neural_art(broadcast.get("visual_description", "Surreal technology chaos"), episode_image):
        episode_image = copy_cover_art()

    if not tts.make_broadcast_audio(broadcast["segments"], audio_path):
        return

    # Use the 'dreamed up' image for the video compilation
    tts.compile_video(audio_path, episode_image, video_path)

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
        display_headline = f"[{broadcast['show_title']}] {broadcast.get('primary_news_headline', 'Daily Broadcast')}"
        db.insert_post(
            headline=display_headline,
            source="The Echo Broadcast",
            topic_tags=broadcast["topic_tags"],
            my_take=broadcast["my_take"],
            post_text=broadcast["social_post"],
            audio_script="[Long Form Broadcast]",
            audio_url=f"local://broadcast_{show_id}.mp3" if env != "production" else f"https://placeholder.com",
            video_url=video_url,
            confidence="high"
        )

    if env == "local": sync_env_to_config(env="local")
    print(f"\n--- [Broadcast Complete] --- Show: {broadcast['show_title']} ---")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", choices=["production", "staging", "local"], default="production")
    parser.add_argument("--dry-run", action="store_true", help="Run pipeline in dry-run mode without publishing")
    args = parser.parse_args()
    run_pipeline(env=args.env, dry_run=args.dry_run)
