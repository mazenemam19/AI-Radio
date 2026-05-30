# Track Specification: Model Tier Manager & Fail-Fast Logic

## 🎯 Purpose
To implement a resilient, multi-tiered AI model queue that strictly separates Production and Testing environments, eliminates "zombie broadcasts," and protects expensive Groq quotas.

## 📋 Requirements

### 1. Provider Isolation (No-Overlap v3.1)
- **Production Set (Premium):** 6-Tier Resilient Queue (Llama 70B, Scout, Gemini 3.5, Flash-Lite, Qwen 3, Pro).
- **Testing Set (Shielded):** 5-Tier Fast Queue (Gemini 3.5, 3.1, 2.5, 2.0, 1.5).
- **Hard Gate:** Local/Test runs must be physically incapable of calling Groq/Mistral APIs.

### 2. Deep Observability
- Mandatory logging of raw model output lengths.
- Real-time quality metric logging (segment counts, average words).
- Explicit error code logging (429, 413, 404) for all tiers.

### 3. Fail-Fast Integrity
- Remove the "Silent Treatment" emergency placeholder.
- If all models in a queue fail (quality or availability), return `None`.
- `main.py` must catch `None` and exit with code 1.

### 4. Step-Down Focus
- Implement an automated context reduction on retry.
- If Attempt 1 (15 news items) fails, Attempt 2 should reduce input to 8 items to force creative depth and avoid "summary traps."

### 5. Efficient TTS Budgeting
- Increase TTS chunk size from 190 to 450 characters.
- Implement a 14,400 character daily pre-emptive limit (RPD Shield) in `tts_generator.py`.


## ⚙️ Logic & Integration
- **`ai_client.py`:** Central refactor to use a declarative strategy pattern for model queues.
- **`main.py`:** Update exit handling and intent calculation (`is_real_run`).
- **`verify_system.py`:** Add regression tests for schema stability and budget enforcement.
