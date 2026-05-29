# Architecture Cleanup Plan: The Brain & Voice Queue (v3)

## 🎯 Objective
To eliminate all provider overlap between Testing and Production, ensuring that CI/CD runs and local development never touch production Groq/Mistral quotas.

## 🏗️ The Non-Overlapping Stack (2026)

| Role | Production (Premium) | Local / Testing (Shielded) |
| :--- | :--- | :--- |
| **Writer (LLM)** | Groq 70B -> Mistral Large | Gemini 3.5 Flash -> Gemini 3.1 Flash-Lite |
| **Narrator (TTS)** | Groq Orpheus -> Google Cloud | Edge-TTS -> pocketsphinx |

## 📋 Implementation Steps

### Phase 1: AI Client Refactor (`ai_client.py`)
- [x] **Define Static Queues:** Hardcode the `PROD_WRITER_QUEUE` and `TEST_WRITER_QUEUE`. 7353f90
- [x] **Implement `WriterOrchestrator`:** 5a25c9a
    - Iterate through the active queue.
    - If Attempt 1 fails, **reduce news context to 8 items** for Attempt 2.
    - If all fail, return `None`.
- [x] **Delete "Silent Treatment" logic:** Ensure no placeholder script is ever returned. 5a25c9a

### Phase 2: TTS Generator Refactor (`tts_generator.py`)
- [x] **Define Static Queues:** Hardcode the `PROD_VOICE_QUEUE` and `TEST_VOICE_QUEUE`. 774f2b4
- [x] **Implement `NarratorOrchestrator`:** 774f2b4
    - Explicitly check `is_real_run`. 
    - If `False`, the code path to `self.api_url` (Groq) must be physically unreachable.
- [x] **RPD Shield:** Maintain the 80-request hard ceiling for Groq. 774f2b4

### Phase 3: Orchestrator fail-fast (`main.py`)
- [x] **Hard Abort:** Ensure `main.py` returns `False` (exit 1) if either the Writer or Narrator fails. bf34335

### Phase 4: Verification & Integration
- [ ] **CI Protection:** Update `.github/workflows/radio.yml` to confirm it only uses the "Shielded" set for the integration test.
- [ ] **Update `ARCHITECTURE.md`:** Finalize the "Bible" with this dual-stack architecture.
