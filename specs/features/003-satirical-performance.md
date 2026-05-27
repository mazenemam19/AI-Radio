# Feature Spec 003: Satirical Performance Logic

## 🎯 Purpose
To transform monotonous text into a rhythmic, "Late Night" satirical performance with multiple voices and emotional cues.

## 👥 Personas
- **Echo (Host):** Intellectual elitist. Voice: `daniel` (Groq) or `guy` (Edge). Pitched down -10Hz.
- **Glitch (Correspondent):** Chaotic internet-minded. Voice: `hannah` (Groq) or `jenny` (Edge). Pitched up +15Hz.

## 🎙️ Synthesis (TTS)
- **Inline Tags:** Uses bracketed emotion tags `[sarcastic]`, `[angry]`, etc.
- **Rhythm Shifts:** Mandates `[fast]`, `[slow]`, `[whisper]`, `[shout]` tags to guide TTS cadence.
- **Pacing:** Standardized 8-second delay between chunks for RPM safety.
- **Retry Logic:** Parses `retry-after` headers and performs a "Fast Exit" to fallback voice if Groq wait > 60s.
- **Punctuation:** AI is instructed to use "Universal Spirit" rules (AGGRESSIVE PUNCTUATION!!!) to steer the rhythm of the standard fallback voice.

## 🎭 Comedic Beats
- **Style:** Jon Stewart / Stephen Colbert "Late Night" satire.
- **No Numerical Filler:** Ban all statistics and numbers; replace with qualitative mockery.
- **Duo Persona:** Mandatory conflict between Echo and Glitch (professional colleague dynamic).
- **Naming Rule:** Echo and Glitch must name each other and argue; professional titles are banned.
- **Content Expansion:** Requirement to expand on ideas (250-350 words per segment).
