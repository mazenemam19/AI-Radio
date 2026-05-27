# Feature Spec 005: AI Scripting & Depth

## 🎯 Purpose
To transform the broadcast from "shallow news clips" into "10-minute long-form satirical deep dives" with Jon Stewart-style biting social commentary.

## 🛠️ Implementation
- **Persona Rules:** Intellectual elitist (Echo) vs. high-energy data-stream (Glitch) with a professional colleague dynamic.
- **Duration Enforcement:** Target 12 segments per show, with each segment reaching 250-350 words to ensure a 10-12 minute total runtime.
- **Numerical Suppression:** Explicitly bans all numerical data as filler. The AI must use qualitative analysis and mockery instead of reading stats.
- **Rhythm & Tone:** Mandates the use of rhythm-shifting vocal directions (e.g., `[fast]`, `[slow]`, `[whisper]`, `[shout]`) to guide the TTS cadence.

## ⚙️ Logic
- **Full Memory Context:** AI receives the complete JSON script of past episodes to prevent repeating jokes or satirical angles.
- **Emergency Protocol:** A hardcoded "Technical Difficulties" script is triggered if all AI engines (Groq/Gemini) hit quota limits, ensuring the pipeline completes.
- **Healing JSON:** State-aware parsing logic heals truncated LLM responses, closing open strings and brackets automatically to prevent pipeline crashes.
