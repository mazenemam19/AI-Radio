# Feature Spec 007: Environment Branching & Parity

## 🎯 Purpose
To codify the specific behavioral differences between Local, Staging, and Production environments to ensure system stability and quota protection.

## 🛠️ Logic Branching Table

| Component | Logic | Local (Offline) | Staging (Sandbox) | Production (Live) |
| :--- | :--- | :--- | :--- | :--- |
| **AI Brain** | Routing | Gemini 3.5 Flash | Gemini 3.5 Flash | Llama 3.3 70B |
| **AI Brain** | Payload | 3 News / 1 Mem | 3 News / 1 Mem | 15 News / 10 Mem |
| **Speech** | Engine | Edge-TTS (Local) | Edge-TTS (Local) | Groq Cloud (Orpheus) |
| **Speech** | Fallback | N/A | N/A | Switches to Edge on 429 |
| **Database** | Type | SQLite | Supabase (Dev) | Supabase (Prod) |
| **Media** | URL | `local://...` | `local://...` | `https://supabase...` |
| **Dashboard** | Data | `config.js` | Supabase SDK | Supabase SDK |
| **Socials** | Action | Console Mock | Console Mock | Bluesky / YouTube Live |

## ⚙️ Key Mechanisms

### 1. The GitHub Actions Trigger
The choice of "Premium" AI logic (Llama 70B + Large Context) is tied to the `GITHUB_ACTIONS` environment variable. If `False`, the system assumes a "Quota-Saver" mode.

### 2. TTS Quota Shield
The system implements a **Fast Exit** protocol. If the Groq API returns a rate limit (`429`) with a wait time exceeding 60 seconds, the mastering engine immediately aborts the cloud request and completes the remaining segments using the local `edge-tts` fallback.

### 3. Frontend Path Translation
To support the `local://` protocol across different OS environments, `app.js` performs real-time path translation:
-   `local://` strings are regex-replaced with the relative `output/` directory.
-   YouTube placeholders (dQw4w9WgXcQ) are translated to local `.mp4` equivalents if the source is detected as local.

### 4. Duration Gate
All environments share a strict **700-second duration gate**. If FFmpeg's final output (probed via `ffprobe`) is shorter than 700s, the broadcast is aborted and no database entry is created.
