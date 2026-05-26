# AI Radio — Echo (Instructional Context)

# ⚠️ CORE MANDATES — READ BEFORE ACTING
1.  **STRICT NO REFACTORING:** NEVER refactor, rewrite, or "clean up" existing code.
2.  **PRESERVE LOGIC & STRUCTURE:** Do not change variable names, function signatures, class structures, or the existing logic flow unless it is the DIRECT cause of a functional bug.
3.  **SURGICAL EDITS ONLY:** Every change MUST be minimal, targeted, and strictly relevant to the immediate task or fix.
4.  **RESPECT ARCHITECTURE:** Adhere to the existing architectural patterns (Multi-Environment, Hybrid Player, Groq TTS) without modification.
5.  **NO "CLEAN CODE" BYPASS:** "Clean code" is NOT an excuse to bypass these mandates. Stability and predictability are the highest priorities.
6.  **NO OVERWRITING:** NEVER use `write_file` on an existing file. Always use the `replace` tool to ensure transparency and prevent accidental refactoring.
7.  **ADDITION-ONLY BIAS:** When adding features, insert them as isolated blocks. Do not touch, "harmonize," or beautify the surrounding established code.
8.  **MANDATE CHECKPOINT:** Re-read these mandates before every single tool call. Structural stability and token efficiency are the absolute priority.

## Project Overview
**AI Radio — Echo** is an autonomous news commentary pipeline hosted by an AI persona named **Echo**. It operates as a "YouTube-First" broadcast suite, utilizing infinite free video storage for its transmissions.

### 📜 Architectural Evolution & Intent (MUST PRESERVE)
The project evolved from a "Short News Clip" generator to a **High-Quality Satirical Podcast Suite**. All future work must respect the following pillars:
1.  **Mono-Topic Deep Dive:** The show shifted from jumping between 7 topics to spending ~10 minutes tearing apart **ONE** specific, absurd news item. This provides depth and a "Jon Stewart" feel.
2.  **The Echo & Glitch Dynamic:** Echo (Host/Anchor) and Glitch (Correspondent) are established personas with an intellectual vs. chaotic dynamic. They must use names, argue, and use aggressive punctuation for rhythm.
3.  **Quota-Saver Strategy:** Cloud TTS (Groq) is for **Production only**. Local/Staging must always use standard TTS (Edge) to preserve the strict 3.6k daily token limit.
4.  **Hybrid Playback:** The dashboard is custom-built to switch between local file playback (Offline/Dev) and YouTube embeds (Production).
5.  **Smart Deduplication:** Uses keyword-overlap (threshold: 2) to ensure Echo never covers the same story twice, even with different headlines.

The system features a highly isolated multi-environment architecture:
1.  **Ingestion:** Scrapes news via RSS and HackerNews. Uses a **Keyword Overlap** algorithm to prevent duplicate coverage of the same story.
2.  **Analysis:** Processes news and historical memory using **Llama 3.3 70B** (via Groq) or **Gemini 3.5 Flash** (via Google). Explicitly avoids repetition.
3.  **Synthesis:** Converts scripts into audio (**Groq Cloud TTS**) and compiles MP4 videos (`ffmpeg`).
4.  **Distribution:** Uploads videos to **YouTube** and posts to **Bluesky**.
5.  **Exhibition:** A "neon-glass" web frontend featuring a **Hybrid Player** that intelligently switches between YouTube embeds and local HTML5 video playback.

## Technical Stack
-   **Language:** Python 3.x (Backend), Vanilla JS (Frontend).
-   **AI Brain:** Llama 3.3 (Primary), Gemini 3.5 Flash (Fallback).
-   **Visual Arts:** **Flux Model** (via Pollinations.ai). Generates unique, HD satirical art for every broadcast background.
-   **Speech Synthesis:** **Groq Cloud TTS** (canopylabs/orpheus-v1-english). Supports inline emotional tags and advanced prosody.
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

### AI Persona: "Echo & Glitch"
The broadcast is a dynamic, high-performance satirical duo:
-   **Echo (Host):** Intellectual, rhythmic, Jon Stewart-style. Voice: `daniel`.
-   **Glitch (Correspondent):** High-energy, chaotic data-stream. Voice: `hannah`.
-   **Speech Tags:** The system uses Groq's inline tags (e.g., `[sarcastic]`, `[angry]`, `<break />`) to create a theatrical, melodic performance.
-   **Prosody Control:** Every segment features dynamic `speed`, `stability`, `clarity`, and `style_exaggeration` parameters.

### FFmpeg & Environment
-   **Resiliency:** The system includes a proactive fallback for FFmpeg at `C:\ffmpeg\bin\ffmpeg.exe`.
-   **Rhythm:** Audio is rendered per-segment with custom pitch/rate/style and merged via FFmpeg concat.
-   **Portability:** No hardcoded local user paths are permitted.

### Data Integrity & Deduplication
-   **Keyword Overlap:** Headlines sharing 2+ significant words are automatically skipped to avoid covering the same event twice.
-   **AI Memory:** Echo receives a summary of the last 20 posts to ensure new takes are fresh and referenceable.

### Frontend Portability
-   **Hardcoding Keys:** For static deployment (Netlify/GH Pages), hardcode `SUPABASE_URL` and `SUPABASE_ANON_KEY` in `app.js` to ensure the dashboard initializes instantly.
-   **Visualizer:** Uses procedural animation for YouTube playback and Web Audio API for local playback (where possible).

### Self-Maintenance
-   **Rolling Window:** The system automatically deletes database records and Supabase storage files older than 7 days to stay within free tier limits.
