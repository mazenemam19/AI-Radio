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

def run_pipeline(env="production"):
    is_github = os.environ.get("GITHUB_ACTIONS") == "true"
    print(f"--- [AI Radio Broadcast Start] --- Env: {env.upper()} ---")
    setup_directories(env=env)
    cover_image_path = copy_cover_art()

    db = SupabaseDBClient(env=env)
    fetcher = NewsFetcher()
    ai = AIRadioAIClient()
    tts = TTSRadioGenerator()
    publisher = DistributionPublisher(env=env)

    # 1. Memory
    history = db.fetch_recent_memory(limit=20)
    processed_headlines = [item["headline"] for item in history]
    memory_context = [{"id": i["id"], "headline": i["headline"]} for i in history]

    # 2. News
    print("[Main] Fetching news grid...")
    news_items = fetcher.get_all_news(processed_headlines=processed_headlines)
    if not news_items:
        print("[Main] No new stories. Staying off-air.")
        return

    # 3. AI SATIRICAL SCRIPT
    print("[Main] Invoking Echo for satirical script...")
    broadcast = ai.generate_broadcast(
        news_items=news_items[:15],
        memory_context=memory_context,
        timestamp=datetime.now(timezone.utc).isoformat(),
        is_cloud=is_github
    )

    if not broadcast or "segments" not in broadcast:
        print("[Main] Script generation failed.")
        return

    # 4. THE SHOW MUST GO ON (Performance)
    show_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    audio_path = f"output/broadcast_{show_id}.mp3"
    video_path = f"output/broadcast_{show_id}.mp4"

    # Render long-form audio with multiple voices
    if not tts.make_broadcast_audio(broadcast["segments"], audio_path):
        return

    # Compile video
    tts.compile_video(audio_path, cover_image_path, video_path)

    # 5. DISTRIBUTION
    video_url = None
    if env == "production":
        video_url = publisher.upload_to_youtube(
            video_path=video_path,
            title=broadcast["show_title"],
            description=f"{broadcast['my_take']}\n\nBroadcasted by Echo AI.",
            tags=broadcast["topic_tags"]
        )
        publisher.post_to_bluesky(broadcast["social_post"])
    else:
        video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # Rick Astley for Staging/Local

    # 6. SAVE TO DB
    db.insert_post(
        headline=broadcast["show_title"],
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
    args = parser.parse_args()
    run_pipeline(env=args.env)
