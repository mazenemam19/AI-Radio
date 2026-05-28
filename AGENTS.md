# AI AGENTS Operations Manual: Echo Broadcast Suite

This file is the authoritative operations manual for AI agents. Adherence to these architectural pillars is critical for system stability.

## 📜 ARCHITECTURAL EVOLUTION & INTENT (MUST PRESERVE)
The project evolved from a "Short News Clip" generator to a **High-Quality Satirical Podcast Suite**. All future work must respect the following pillars:
1.  **Mono-Topic Deep Dive:** The show spends ~10 minutes tearing apart **ONE** specific, absurd news item. This provides depth and a "Jon Stewart" feel.
2.  **The Echo & Glitch Dynamic:** Echo (Host) and Glitch (Correspondent) have an intellectual vs. chaotic dynamic. They must use names, argue, and use rhythmic punctuation.
3.  **Quota-Saver Strategy:** Cloud TTS (Groq) is for **Production only**. Local/Staging must always use standard TTS (Edge) to preserve the strict 3.6k daily token limit.
4.  **Hybrid Playback:** The dashboard is custom-built to switch between local file playback (Offline/Dev) and YouTube embeds (Production).
5.  **Smart Deduplication:** Uses keyword-overlap (threshold: 2) to ensure Echo never covers the same story twice, even with different headlines.

## 🛠️ AGENT WORKFLOW & COMMANDS
@./conductor/workflow.md

## 🎭 PERSONA: ECHO & GLITCH
The broadcast is a dynamic, high-performance satirical duo:
- **ECHO (Host):** Intellectual, rhythmic, Jon Stewart-style. Voice: `daniel`/`guy`.
- **GLITCH (Correspondent):** High-energy, chaotic data-stream. Voice: `hannah`/`jenny`.
- **Interaction:** They must call each other by name. **BANNED:** "Anchor", "Correspondent", "Host".
- **Melody:** AI uses aggressive punctuation (!!!, ???, ...) and ALL CAPS to steer the TTS engine.

## 📁 REPO MAP
- `main.py`: Orchestrator. Implements **Gentle Cloud** limits and **Quota-Saver** TTS logic.
- `ai_client.py`: Satirical script engine. Uses **Mono-Topic Deep Dive** (10-minute focus).
- `tts_generator.py`: Smart TTS engine. Implements 190-char chunking and header-aware rate-limiting.
- `db_client.py`: Triple-mode persistence (Supabase REST / SQLite).
- `app.js`: Hybrid frontend logic. Switches between YouTube and Local HTML5 player.
- `news_fetcher.py`: Smart scraper. Uses **Keyword Overlap (Threshold: 2)**.
- `sync_config.py`: Automation script for environment/data synchronization.
- `schema.sql`: PostgreSQL definitions for `memory_log` and `comments`.

## ⚖️ DEVELOPMENT CONVENTIONS
- **Deduplication:** Headlines sharing 2+ keywords with the history are automatically skipped.
- **Memory Context:** AI receives the `my_take` of recent episodes to ensure new angles are unique.
- **FFmpeg Resiliency:** Includes a fallback for `C:\ffmpeg\bin\ffmpeg.exe`. No hardcoded local user paths.
- **Self-Maintenance:** System deletes records and Supabase storage files older than 7 days per run.
- **Token Optimization:** Uses smart 190-character chunking and 8s pacing to handle Groq RPM/TPM limits.
- **Frontend Sync:** Use `npm run sync` commands to update `config.js`. Avoid hardcoding keys in `app.js`.