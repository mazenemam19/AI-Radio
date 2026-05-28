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

## Database & Persistence
- **Production/Staging:** Supabase (PostgreSQL)
- **Local:** SQLite (`ai_radio_dev.db`)
- **Management:** `db_client.py` (Triple-mode persistence).

## AI & Media
- **Brain:** Llama 3.3 70B (Production), Llama 3.1 8B (Local), Gemini 3.5 Flash (Fallback).
- **Voice:** Groq Cloud TTS (canopylabs/orpheus-v1-english).
- **Visuals:** Flux (via Pollinations.ai) for HD background generation.
- **Compiler:** FFmpeg (Hardware-accelerated video compilation).

## Infrastructure & Tools
- **Environment Management:** `python-dotenv` (.env isolation).
- **Synchronization:** `sync_config.py` (Data injection for local dashboard).
- **Verification:** `verify_system.py` (Project health suite).
- **Deployment:** GitHub Actions (Automated broadcast triggers).
