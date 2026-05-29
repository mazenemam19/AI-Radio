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
The choice of "Premium" AI logic (Llama 70B / Groq TTS) is strictly gated by the `is_real_run` boolean in `main.py`. This boolean is only `True` if `env == 'production'`, `dry_run == False`, and `GITHUB_ACTIONS == True`.

### 2. Hard Fail-Fast (Anti-Zombie)
The system no longer produces placeholder broadcasts ("The Silent Treatment"). If all AI tiers in a set fail to return a quality script, the system returns `None` and the orchestrator exits with code 1. This prevents burning tokens on broken shows.

### 3. Step-Down Focus
On Attempt 2 (Fallback), the system automatically reduces input noise by trimming news items from 15 down to 8. This ensures the backup model has enough "cognitive space" to be verbose and avoid summary-traps.

### 4. Zero-Leak Tests
Set B (Testing) contains zero references to Groq or Mistral. It is physically impossible for a test run or local development session to consume your production quotas.
