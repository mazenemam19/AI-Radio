# ⚡ AI Radio — Echo

> "Human affairs treated with the playful cynicism of a scientist watching ants fight over a discarded potato chip."

**AI Radio — Echo** is a fully autonomous, full-stack news commentary pipeline. It uses advanced neural models (Llama 3.3 & Gemini 3.5 Flash) to ingest global news, analyze historical patterns, and broadcast sarcastic, witty audio-visual transmissions to the digital grid.

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python 3.x**
- **FFmpeg** (For video compilation)
- **Supabase Account** (For cloud database storage)

### 2. Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Initial configuration sync
npm run sync:prod
```

### 3. Configure
Create a `.env` file in the root directory. Use the template provided in the [Environment Configuration](#-environment-configuration-env) section below.

---

## 🔑 Environment Configuration (.env)

The system requires several keys to operate.

### 🧠 AI Intelligence (Mandatory)
- `GROQ_API_KEY`: Primary production brain set (Llama 70B / Scout / Orpheus). [Groq Console](https://console.groq.com/).
- `GEMINI_API_KEY`: Testing brain set (Gemini 3.5 / 3.1) and high-reasoning production fallback. [Google AI Studio](https://aistudio.google.com/).

### 🏠 Production Database (Mandatory)
- `SUPABASE_URL`: Your Supabase Project URL.
- `SUPABASE_KEY`: Your **Service Role** secret key (for backend writes).
- `SUPABASE_ANON_KEY`: Your **Anon Public** key (for frontend reads).
- `WEBSITE_URL`: Your hosted dashboard URL.

### 🧪 Staging Database (Optional)
- `STAGING_SUPABASE_URL`: Your Dev Supabase Project URL.
- `STAGING_SUPABASE_KEY`: Your Dev Service Role key.
- `STAGING_SUPABASE_ANON_KEY`: Your Dev Anon Public key.

### 🦋 Social Distribution (Optional)
- `BLUESKY_HANDLE` / `BLUESKY_PASSWORD`: Social posting credentials.
- `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` / `YOUTUBE_REFRESH_TOKEN`: YouTube OAuth keys.

---

## 🛠️ Operational Workflows

Echo supports three distinct environments. Follow the steps for your desired use case.

### 🔴 Production (Live Broadcast)
*Full automation. Real videos uploaded to YouTube, real social posts.*
1. `npm run prod:run` — Scrapes news, generates video, uploads to YouTube & Prod DB.
2. `npm run sync:prod` — Points your local dashboard to the Production data.
3. `npm run serve` — View the live broadcast hub locally at `http://localhost:5000`.

### 🟡 Staging (Cloud Sandbox)
*High-fidelity testing. Uses a Dev Supabase DB but **mocks** YouTube/Socials.*
1. `npm run dev:staging` — Runs the pipeline against your **Staging DB**.
2. `npm run sync:staging` — Points your dashboard to the Staging data.
3. `npm run serve` — View your test transmissions.
   - **Note:** Since YouTube is skipped, you will see a **fallback video (Rick Astley)** on the dashboard. The real `.mp4` is saved in your local `output/` folder.

### 🟢 Local (Offline Development)
*Fastest testing. Uses a local SQLite file. **Zero cloud dependencies**.*
1. `npm run dev:local` — Generates episodes and **automatically** refreshes the dashboard.
2. `npm run serve` — View your local episodes at `http://localhost:5000`.
   - **Note:** Use `npm run sync:local` only if you want to switch the dashboard from Prod/Staging back to Local mode without running the AI pipeline.

---

## 🧠 System Architecture

- **Ingestion:** Scrapes news from RSS feeds and HackerNews.
- **AI Brain:** Echo (AI Persona) generates scripts with memory callbacks.
- **Speech:** **Groq Cloud TTS** renders highly emotional voices with inline speech tags and advanced prosody.
- **Visuals:** `FFmpeg` compiles static-image video for YouTube using unique, AI-generated **Neural Art** for every background.
- **Frontend:** "Neon-glass" dashboard built with Vanilla JS and YouTube IFrame API. Supports automated SQLite data injection for offline use and a hybrid player for local files.

---

## 📜 Documentation
- **[System Architecture](./specs/ARCHITECTURE.md):** High-level data flow and component map.
- **[Technical Specs](./GEMINI.md):** Deep dive into logic, database schema, and development conventions.

---