# Feature Spec 003: Satirical Performance Logic

## 🎯 Purpose
To transform monotonous text into a rhythmic, "Late Night" satirical performance with multiple voices and emotional cues.

## 👥 Personas
- **Echo (Host):** Intellectual elitist. Voice: `daniel` (Groq) or `guy` (Edge). Pitched down -10Hz.
- **Glitch (Correspondent):** Chaotic internet-minded. Voice: `hannah` (Groq) or `jenny` (Edge). Pitched up +15Hz.

## 🎙️ Synthesis (TTS)
- **Tiered Fallback:** 
    1. **Groq Cloud (Orpheus v1):** Primary high-fidelity engine.
    2. **Google Cloud (Neural2):** Secondary fallback.
    3. **Edge-TTS:** Final local resiliency tier.
- **Inline Tags:** Uses bracketed emotion tags `[sarcastic]`, `[angry]`, etc.
- **Rhythm Shifts:** Mandates `[fast]`, `[slow]`, `[whisper]`, `[shout]` tags to guide TTS cadence.
- **Pacing:** Standardized 8-second delay between chunks for RPM safety.
- **RPD Shield:** Hard 80-request daily limit for Groq to protect free tier tokens.
- **Punctuation:** AI is instructed to use "Universal Spirit" rules (AGGRESSIVE PUNCTUATION!!!) to steer the rhythm of standard fallback voices.

## 🎭 Comedic Beats
- **Style:** Jon Stewart / Stephen Colbert "Late Night" satire.
- **No Numerical Filler:** Ban all statistics and numbers; replace with qualitative mockery.
- **Duo Persona:** Mandatory conflict between Echo and Glitch (professional colleague dynamic).
- **Naming Rule:** Echo and Glitch must name each other and argue; professional titles are banned.
- **Content Expansion:** Requirement to expand on ideas (~200 words per segment).
