# Feature Spec 007: Environment Branching & Parity

## 🎯 Purpose
To codify the specific behavioral differences between Local, Staging, and Production environments to ensure system stability and quota protection.

## 🛠️ Logic Branching Table (v3: No-Overlap Strategy)

| Component | Logic | Local (Offline) | Staging (Sandbox) | Production (Live) |
| :--- | :--- | :--- | :--- | :--- |
| **AI Brain** | Routing | Gemini 3.1 Flash-Lite | Gemini 3.1 Flash-Lite | Llama 3.3 70B |
| **AI Brain** | Fallback | Gemini 3 Flash | Gemini 3 Flash | Mistral Large |
| **AI Brain** | Payload | 3 News / 1 Mem | 3 News / 1 Mem | 15 News / 20 Mem |
| **Speech** | Engine | Edge-TTS (Cloud) | Edge-TTS (Cloud) | Groq (Orpheus v1) |
| **Speech** | Fallback | pocketsphinx (Local) | pocketsphinx (Local) | Google Cloud (Neural2) |
| **Database** | Type | SQLite | Supabase (Dev) | Supabase (Prod) |
| **Media** | URL | `local://...` | `local://...` | `https://supabase...` |
| **Socials** | Action | Console Mock | Console Mock | Bluesky / YouTube Live |

## ⚙️ Key Mechanisms

### 1. The "Real Run" Trigger
The choice of "Premium" AI logic (Llama 70B / Groq TTS) is strictly gated by the environment state (`env == "production"`). This ensures production model usage is isolated from local development.

### 2. Hard Fail-Fast (Anti-Zombie)
The system no longer produces placeholder broadcasts ("The Silent Treatment"). If all AI tiers in a set fail to return a quality script, the system returns `None` and the orchestrator exits with code 1. This prevents burning tokens on broken shows.

### 3. Duration Gate
All environments share a strict **600-second duration gate**. If the final audio duration (probed via `ffprobe`) is shorter than 600s, the broadcast is aborted immediately to ensure content quality.

### 4. Tiered Speech Fallback
Production speech follows a 3-tier resilient chain:
1. **Groq Cloud (Orpheus v1)**: Primary high-fidelity engine. Protected by a 14,400 char daily pre-emptive quota.
2. **Google Cloud (Neural2)**: Secondary high-fidelity fallback.
3. **Edge-TTS (Cloud)**: Tertiary local resiliency tier.
