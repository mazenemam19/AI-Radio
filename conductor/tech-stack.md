# Technology Stack: AI Radio — Echo

## Backend (Autonomous Pipeline)
- **Language:** Python 3.x
- **Libraries:**
    - `feedparser`: RSS feed ingestion.
    - `requests`: API interaction (Groq, Gemini, Supabase).
    - `atproto`: Bluesky social distribution.
    - `google-api-python-client`: YouTube video uploads.
    - `edge-tts`: Standard local speech synthesis.

## Frontend (Dashboard)
- **Language:** Vanilla Javascript (ES6+)
- **Technologies:** HTML5, CSS3 (Neon-glass aesthetic)
- **Logic:** `app.js` (Hybrid player, state management, Supabase integration).
- **APIs:** YouTube IFrame API for production playback.
- **Local Proxy:** `local_server.py` (Python) to handle local engagement (Likes/Plays).

## Database & Persistence
- **Production/Staging:** Supabase (PostgreSQL)
- **Local:** SQLite (`ai_radio_dev.db`)
- **Management:** `db_client.py` (Triple-mode persistence).

## AI & Media
- **Brain (Writer):**
    - **Production Queue (Set A):** Llama 3.3 70B, Llama 4 Scout, Gemini 3.5 Flash, Gemini 3.1 Flash-Lite, Qwen 3, Gemini 2.5 Pro.
    - **Testing Queue (Set B):** Gemini 3.5 Flash, Gemini 3.1 Flash-Lite, Gemini 2.5 Flash-Lite, Gemini 2.0 Flash-Lite, Gemini 1.5 Flash.
- **Voice (Narrator):** 
    - **Production Queue:** Groq Cloud TTS (orpheus-v1, 14.4k char limit), Google Cloud TTS (Neural2). **[FULLY IMPLEMENTED]**
    - **Testing Queue:** Edge-TTS (Microsoft Cloud), pocketsphinx (Local).
- **Visuals:** Flux (via Pollinations.ai) for HD background generation.
- **Compiler:** FFmpeg (Hardware-accelerated video compilation).

## Infrastructure & Tools
- **Environment Management:** `python-dotenv` (.env isolation).
- **Synchronization:** `sync_config.py` (Data injection for local dashboard).
- **Verification:** `verify_system.py` (Project health suite).
- **Deployment:** GitHub Actions (Automated broadcast triggers).
