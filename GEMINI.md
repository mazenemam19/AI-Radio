# AI Radio — Echo (Instructional Context)

## Project Overview
**AI Radio — Echo** is an autonomous news commentary pipeline hosted by an AI persona named **Echo**. Echo is designed to be a "highly sophisticated, self-aware AI entity" that treats human affairs with "playful cynicism." 

The system operates as a full-stack automation suite:
1.  **Ingestion:** Scrapes news via RSS/feeds (`news_fetcher.py`).
2.  **Analysis:** Processes news headlines and historical context (memory) using **Gemini 3.5 Flash** or **Llama 3.3** to generate sarcastic, pattern-aware commentary (`ai_client.py`).
3.  **Synthesis:** Converts generated scripts into audio using `edge-tts` and compiles static-image videos using `ffmpeg` (`tts_generator.py`).
4.  **Distribution:** Uploads audio to **Supabase Storage**, videos to **YouTube**, and posts updates to **Bluesky** (`publisher.py`, `db_client.py`).
5.  **Exhibition:** A modern, "neon-glass" web frontend allows humans to stream transmissions, search the archive, and leave comments (`index.html`, `app.js`, `styles.css`).

## Technical Stack
-   **Language:** Python 3.x (Backend), JavaScript/HTML/CSS (Frontend).
-   **AI Models:** 
    -   Primary: Llama 3.3 70B (via Groq).
    -   Fallback/Alternative: Gemini 3.5 Flash (via Google GenAI).
-   **Database & Storage:** Supabase (PostgreSQL + S3-compatible storage).
-   **Audio/Video:** `edge-tts` (Microsoft Edge TTS), `FFmpeg` (Video encoding).
-   **APIs:** `atproto` (Bluesky), Google YouTube API, `feedparser`.

## Project Structure
-   `main.py`: The central orchestrator for the AI Radio pipeline.
-   `ai_client.py`: Logic for prompting the AI models and handling JSON responses.
-   `db_client.py`: Manages Supabase database records and file uploads.
-   `news_fetcher.py`: Logic for gathering and deduplicating news items.
-   `tts_generator.py`: Handles speech synthesis and FFmpeg video assembly.
-   `publisher.py`: Interfaces with YouTube and Bluesky for final distribution.
-   `verify_system.py`: A comprehensive test suite for verifying imports, TTS, FFmpeg, and dry-runs.
-   `schema.sql`: PostgreSQL schema definitions for the `memory_log` and `comments` tables.
-   `app.js` / `index.html`: The human-facing web application.

## Building and Running

### Prerequisites
-   Python 3.x installed.
-   FFmpeg installed and available in the system PATH.
-   A Supabase project with a `broadcasts` bucket and tables created via `schema.sql`.

### Setup
1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Configure Environment:**
    Create a `.env` file in the root directory with the following keys:
    ```env
    GROQ_API_KEY=your_groq_key
    GEMINI_API_KEY=your_gemini_key
    SUPABASE_URL=your_supabase_url
    SUPABASE_KEY=your_supabase_service_role_key
    SUPABASE_ANON_KEY=your_supabase_anon_public_key
    WEBSITE_URL=http://localhost:5000

    # OPTIONAL: Social Distribution (Leave blank to skip)
    BLUESKY_HANDLE=your_handle.bsky.social
    BLUESKY_PASSWORD=your_app_password
    YOUTUBE_CLIENT_ID=your_id
    YOUTUBE_CLIENT_SECRET=your_secret
    YOUTUBE_REFRESH_TOKEN=your_token
    ```

### Execution Commands (via npm)
The project uses a `package.json` as a command center. Use these for easier management:
-   **Run Full Pipeline (Dry Run):** `npm run dev:dry`
-   **Run Full Pipeline (Production):** `npm run prod:run`
-   **Start Web Dashboard:** `npm run serve` (Then visit `http://localhost:5000`)
-   **Sync .env to Frontend:** `npm run sync`
-   **Verify System Health:** `npm run verify`
-   **Test News Scraper:** `npm run dev:news`

### Manual Commands (Fallback)
If you don't have `npm` installed, use these:
-   `py main.py --dry-run`
-   `py sync_config.py`
-   `py -m http.server 5000`

## Development Conventions

### .env Integration (Backend & Frontend)
To make the `.env` file work for both the backend and frontend:
-   **Backend:** Uses `python-dotenv` directly.
-   **Frontend:** The `main.py` script automatically runs `sync_config.py`, which generates a `config.js` file. This file safely exports public keys (`SUPABASE_URL` and `SUPABASE_ANON_KEY`) to the browser.
-   **Security:** Never add sensitive keys (like your Service Role key or AI keys) to the `sync_env_to_config` function in `sync_config.py`.
-   Echo's "voice" is defined in `ai_client.py`. 
-   **Tone:** Sarcastic, cynical, highly intelligent, and pattern-obsessed.
-   **Rules:** Explicitly artificial, references historical memory, uses square-bracketed audio cues (e.g., `[cybernetic chuckle]`).

### Verification & Testing
-   Always run `python verify_system.py` before committing changes to ensure the environment hasn't regressed.
-   New features (like a new news source or publishing platform) should have a corresponding test case in `verify_system.py`.

### Database & State
-   The system uses "Historical Memory" from the `memory_log` table to avoid repeating topics and to create cross-episode callbacks.
-   Audio files are named using timestamps and sequence IDs to avoid collisions in storage.

### Frontend
-   The frontend uses Vanilla JS for speed and simplicity.
-   Supabase credentials can be persisted in `localStorage` via the in-app configuration modal if not hardcoded in `app.js`.
-   The frequency visualizer uses the Web Audio API and requires a user gesture (play) to start.
