# AI Radio — Echo (Instructional Context)

## Project Overview
**AI Radio — Echo** is an autonomous news commentary pipeline hosted by an AI persona named **Echo**. It operates as a "YouTube-First" broadcast suite, utilizing infinite free video storage for its transmissions.

The system features a highly isolated multi-environment architecture:
1.  **Ingestion:** Scrapes news via RSS and HackerNews. Uses a **Keyword Overlap** algorithm to prevent duplicate coverage of the same story.
2.  **Analysis:** Processes news and historical memory using **Llama 3.3 70B** (via Groq) or **Gemini 3.5 Flash** (via Google). Explicitly avoids repetition.
3.  **Synthesis:** Converts scripts into audio (`edge-tts`) and compiles MP4 videos (`ffmpeg`).
4.  **Distribution:** Uploads videos to **YouTube** and posts to **Bluesky**.
5.  **Exhibition:** A "neon-glass" web frontend featuring a **Hybrid Player** that intelligently switches between YouTube embeds and local HTML5 video playback.

## Technical Stack
-   **Language:** Python 3.x (Backend), Vanilla JS (Frontend).
-   **AI Brain:** Llama 3.3 (Primary), Gemini 3.5 Flash (Fallback).
-   **Databases:** Supabase (PostgreSQL) for Cloud; SQLite for Local.
-   **Media Hosting:** YouTube (Primary), Local `output/` folder (Development).

## Multi-Environment Architecture

### 1. Production (`--env production`)
-   **Database:** Main Supabase Project.
-   **Media:** Real YouTube uploads.
-   **Socials:** Live Bluesky posts.
-   **Sync:** `npm run sync:prod`

### 2. Staging (`--env staging`)
-   **Database:** Dedicated "Staging" Supabase Project.
-   **Media:** Mocks YouTube (Rick Astley fallback). Real video saved to `output/`.
-   **Socials:** Mocked (No posts).
-   **Sync:** `npm run sync:staging`

### 3. Local (`--env local`)
-   **Database:** Local SQLite (`ai_radio_dev.db`).
-   **Media:** Local file paths (`output/`). Dashboard plays local files directly.
-   **Socials:** Mocked (No posts).
-   **Sync:** `npm run sync:local` (Automated at end of run).

## Project Structure
-   `main.py`: Central orchestrator with environment-aware logic.
-   `ai_client.py`: AI persona "Echo" logic and strict JSON generation.
-   `db_client.py`: Triple-mode client (Supabase Prod, Supabase Staging, SQLite Local).
-   `news_fetcher.py`: Smart scraper with keyword-based deduplication.
-   `sync_config.py`: Bridge script that exports .env or SQLite data to `config.js`.
-   `app.js`: Hybrid frontend logic with custom neural visualizer.
-   `schema.sql`: PostgreSQL definitions for `memory_log` and `comments` tables.

## Development Conventions

### AI Persona: "Echo"
Echo's identity is the core of the project. Future interactions must adhere to:
-   **Tone:** Sarcastic, cynical, highly intelligent, and pattern-obsessed.
-   **Voice:** Explicitly artificial. References human affairs like a detached scientist.
-   **Audio Cues:** Uses square-bracketed cues for the TTS engine (e.g., `[cybernetic chuckle]`, `[sigh]`, `[static transition]`).
-   **Logic:** Never vague. Directly names absurdities and connects them to historical patterns.

### FFmpeg & Environment
-   **Resiliency:** The system includes a proactive fallback for FFmpeg at `C:\ffmpeg\bin\ffmpeg.exe` on Windows, while remaining portable for Linux/Cloud environments.
-   **Portability:** No hardcoded local user paths are permitted in `main.py`.

### Data Integrity & Deduplication
-   **Keyword Overlap:** Headlines sharing 3+ significant words are automatically skipped to avoid covering the same event twice.
-   **AI Memory:** Echo receives a summary of the last 30 posts to ensure new takes are fresh and referenceable.

### Frontend Portability
-   **Hardcoding Keys:** For static deployment (Netlify/GH Pages), hardcode `SUPABASE_URL` and `SUPABASE_ANON_KEY` in `app.js` to ensure the dashboard initializes instantly.
-   **Visualizer:** Uses procedural animation for YouTube playback and Web Audio API for local playback (where possible).

### Self-Maintenance
-   **Rolling Window:** The system automatically deletes database records and Supabase storage files older than 7 days to stay within free tier limits.
