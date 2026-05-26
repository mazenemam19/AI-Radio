# Feature Spec 003: Satirical Performance Logic

## 🎯 Purpose
To transform monotonous text into a rhythmic, "Late Night" satirical performance with multiple voices and emotional cues.

## 👥 Personas
- **Echo (Host):** Intellectual elitist. Voice: `daniel` (Groq) or `guy` (Edge). Pitched down -10Hz.
- **Glitch (Correspondent):** Chaotic internet-minded. Voice: `hannah` (Groq) or `jenny` (Edge). Pitched up +15Hz.

## 🎙️ Synthesis (TTS)
- **Inline Tags:** Uses bracketed emotion tags `[sarcastic]`, `[angry]`, etc.
- **Pacing:** Standardized 8-second delay between chunks for RPM safety.
- **Retry Logic:** Parses `retry-after` headers and performs a "Fast Exit" to fallback voice if Groq wait > 60s.
- **Punctuation:** AI is instructed to use "Universal Spirit" rules (AGGRESSIVE PUNCTUATION!!!) to steer the rhythm of the standard fallback voice.

## 🎭 Comedic Beats
- Mandatory conflict between Echo and Glitch.
- Banned professional titles (Host/Correspondent).
- Requirement to expand on ideas (200-300 words per segment).
