# Feature Spec 005: AI Scripting & Depth

## 🎯 Purpose
To transform the broadcast from "shallow news clips" into "10-minute long-form satirical deep dives" with Jon Stewart-style biting social commentary.

## 🛠️ Implementation
- **Persona Rules:** Intellectual elitist (Echo) vs. high-energy data-stream (Glitch) with a professional colleague dynamic.
- **Duration Enforcement:** Target 10 segments per show, with each segment reaching ~200 words to ensure a 10-12 minute total runtime.
- **Numerical Suppression:** Explicitly bans all numerical data as filler. The AI must use qualitative analysis and mockery instead of reading stats.
- **Rhythm & Tone:** Mandates the use of rhythm-shifting vocal directions (e.g., `[fast]`, `[slow]`, `[whisper]`, `[shout]`) to guide the TTS cadence.

## ⚙️ Logic
- **Resilient Queue:** Uses a 6-tier failover strategy (Set A) to combat rate limits.
- **Step-Down Focus:** Automatically reduces news context from 15 to 8 items on retry to force creative depth and avoid summary-traps.
- **Fail-Fast:** System returns `None` and aborts if quality thresholds are not met. Placeholder scripts are prohibited.
- **Healing JSON:** State-aware parsing logic heals truncated LLM responses, closing open strings and brackets automatically.
