import os
import sys
import argparse
import shutil
from datetime import datetime
from dotenv import load_dotenv

# Import our custom modules
from db_client import SupabaseDBClient
from news_fetcher import NewsFetcher
from ai_client import AIRadioAIClient
from tts_generator import TTSRadioGenerator
from publisher import DistributionPublisher
from sync_config import sync_env_to_config

load_dotenv()

def setup_directories():
    """Create local directories for assets and temporary output."""
    os.makedirs("assets", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    # Sync environment variables to frontend config
    sync_env_to_config()
    
    # Initialize DB and clean up old data to prevent hitting storage limits
    # (Keeps a rolling 7-day window of broadcasts)
    db = SupabaseDBClient()
    db.delete_old_episodes(days_to_keep=7)

def copy_cover_art():
    """Ensure a cover art image exists in the local assets folder."""
    local_cover = "assets/cover_art.png"
    if os.path.exists(local_cover) and os.path.getsize(local_cover) > 0:
        return local_cover

    # If no cover art exists, try to create a stylish placeholder
    print("[Main] Cover art not found in assets/cover_art.png. Creating a placeholder.")
    try:
        from PIL import Image, ImageDraw
        # Create a neon-glass themed placeholder
        img = Image.new('RGB', (1280, 720), color = (10, 5, 25))
        d = ImageDraw.Draw(img)
        # Add some simple "neon" lines for flair
        d.line([(0,0), (1280, 720)], fill=(175, 82, 255), width=2)
        d.line([(0,720), (1280, 0)], fill=(0, 240, 255), width=2)
        d.text((500, 340), "AI RADIO - ECHO", fill=(255, 255, 255))
        img.save(local_cover)
    except Exception as e:
        print(f"[Main] Could not generate placeholder image: {e}")
        # Create a zero-byte file just to let ffmpeg run without crashing
        with open(local_cover, "wb") as f:
            f.write(b"")
    return local_cover

def run_pipeline(dry_run=False):
    print(f"--- [AI Radio Pipeline Start] --- Dry Run? {dry_run} ---")
    setup_directories()
    cover_image_path = copy_cover_art()

    # Instantiate our clients
    db = SupabaseDBClient()
    fetcher = NewsFetcher()
    ai = AIRadioAIClient()
    tts = TTSRadioGenerator()
    publisher = DistributionPublisher()

    # Step 1: Query historical memory
    print("[Main] Fetching historical memory...")
    history = db.fetch_recent_memory(limit=30)
    processed_headlines = [item["headline"] for item in history]
    
    # Format memory context for the AI prompt
    memory_context = []
    for item in history:
        memory_context.append({
            "id": item["id"],
            "headline": item["headline"],
            "my_take": item.get("my_take", ""),
            "post_text": item.get("post_text", "")
        })

    # Step 2: Fetch and deduplicate news
    print("[Main] Fetching raw news...")
    news_items = fetcher.get_all_news(processed_headlines=processed_headlines)
    if not news_items:
        print("[Main] No new unique articles found to cover. Exiting.")
        return

    # Step 3: Run AI generation
    from datetime import timezone
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    print("[Main] Invoking Echo for commentary...")
    commentary = ai.generate_commentary(
        news_items=news_items[:10], # Top 10 items to prevent prompt overflow
        memory_context=memory_context,
        timestamp=timestamp
    )

    if not commentary or "posts" not in commentary or not commentary["posts"]:
        print("[Main] AI did not produce any valid commentary posts. Skipping distribution.")
        return

    posts = commentary["posts"]
    print(f"[Main] AI generated {len(posts)} commentaries.")
    
    # Log session notes
    session_note = commentary.get("session_note", "No session notes.")
    print(f"[Main] Session note: {session_note}")

    # Process and distribute each generated post
    for idx, post in enumerate(posts):
        headline = post.get("headline")
        source = post.get("source")
        my_take = post.get("my_take")
        post_text = post.get("post_text")
        audio_script = post.get("audio_script")
        confidence = post.get("confidence", "medium")
        topic_tags = post.get("topic_tags", ["general"])
        memory_callback = post.get("memory_callback")
        callback_note = post.get("callback_note")

        print(f"\n--- Processing Episode {idx + 1}: '{headline}' ---")

        # Create localized filenames
        timestamp_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_filename = f"episode_{timestamp_slug}_{idx}.mp3"
        video_filename = f"episode_{timestamp_slug}_{idx}.mp4"
        
        local_audio_path = os.path.join("output", audio_filename)
        local_video_path = os.path.join("output", video_filename)

        # 1. Render Speech Audio via edge-tts
        audio_success = tts.make_audio(audio_script, local_audio_path)
        if not audio_success:
            print(f"[Main] [ERROR] Audio generation failed for episode {idx}. Skipping.")
            continue

        # 2. Render MP4 Video via FFmpeg
        video_success = tts.compile_video(local_audio_path, cover_image_path, local_video_path)
        
        audio_url = None
        video_url = None

        if dry_run:
            print("[Main] [DRY RUN] Skipping cloud uploads and database insertion.")
            continue

        # --- PRODUCTION MODE (Real cloud writes) ---

        # 3. Skip Supabase audio upload (Hosted on YouTube for long-term scalability)
        audio_url = f"https://placeholder-audio.com/{audio_filename}"
        
        # 4. Upload MP4 to YouTube
        if video_success:
            yt_title = f"AI Radio: {headline}"
            yt_description = f"Broadcasted by Echo, AI Radio Host.\n\nEcho's Take: {my_take}\n\nListen on our site: {os.environ.get('WEBSITE_URL', 'http://localhost:5000')}"
            video_url = publisher.upload_to_youtube(
                video_path=local_video_path,
                title=yt_title,
                description=yt_description,
                tags=topic_tags
            )

        # 5. Insert Log record into Database and obtain dynamic ID
        db_record = db.insert_post(
            headline=headline,
            source=source,
            topic_tags=topic_tags,
            my_take=my_take,
            post_text=post_text,
            audio_script=audio_script,
            audio_url=audio_url,
            video_url=video_url,
            confidence=confidence,
            related_ids=[memory_callback] if memory_callback else []
        )
        
        episode_id = db_record.get("id")

        # 6. Compose Social Post Text (include direct site play-back link if configured)
        site_url = os.environ.get("WEBSITE_URL")
        final_post_text = post_text
        if site_url and episode_id:
            playback_link = f"{site_url}?id={episode_id}"
            # Ensure post stays under 280 chars even with link
            max_desc_len = 280 - len(playback_link) - 12
            if len(final_post_text) > max_desc_len:
                final_post_text = final_post_text[:max_desc_len] + "..."
            final_post_text = f"{final_post_text} Listen: {playback_link}"

        # 7. Post to Bluesky
        publisher.post_to_bluesky(final_post_text)

    print("\n--- [AI Radio Pipeline Complete] ---")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Radio - Echo Automation Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Runs pipeline locally without posting to cloud/socials.")
    parser.add_argument("--test-news", action="store_true", help="Queries and displays raw scraped news only.")
    args = parser.parse_args()

    if args.test_news:
        print("[Main] Fetching news for testing...")
        fetcher = NewsFetcher()
        news = fetcher.get_all_news()
        for idx, item in enumerate(news):
            print(f"{idx+1}. [{item['source']}] {item['headline']}\n   Summary: {item['summary']}\n")
        sys.exit(0)

    run_pipeline(dry_run=args.dry_run)
