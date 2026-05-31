# Track Specification: Volume Pressure Logic

## Objective
Increase the total duration of the satirical radio broadcast to hit production-grade targets (600s for Production, 200s for Local) by implementing "Volume Pressure" logic. This ensures the AI generates enough content to fill a 10-minute slot without sacrificing quality.

## Scope
- **Target:** `ai_client.py` and its interaction with LLMs.
- **Goal:** consistently hit ~1500 words across 12-15 segments.

## Functional Requirements
- **Increased Segment Target:** Update the orchestrator to request 12-15 segments instead of the current 8-10.
- **Prompt Pressure:** Hard-code word count expectations into the system prompt to force longer segment copy (target >100 words per segment where possible).
- **Validation Update:** Adjust the `validate_broadcast` function to enforce these new higher minimums.
- **Environment Awareness:** Ensure the system respects the 200s local gate vs the 600s production gate.

## Non-Functional Requirements
- **Token Efficiency:** Maintain high narrative density to avoid "filler" words that waste Groq/Gemini tokens.
- **Stability:** The parser must handle longer JSON outputs without truncation errors (utilize the existing JSON Healer).

## Technical Constraints
- Must remain compatible with existing `main.py` pipeline.
- Must not exceed Groq's token-per-minute (TPM) limits for the Orpheus model during TTS synthesis.

## Self-Assessment Gates (CRITICAL)
Every production run must be measured against **Run 74** (Baseline). The following conditions are mandatory for acceptance:
- **Duration Gate:** Total audio duration must be ≥ 372s (Baseline). Any run shorter than 372s is a regression.
- **Metadata Integrity:** Every column in the `memory_log` table must be populated. If `related_ids`, `confidence`, `my_take`, or `post_text` are missing or defaulted to static values, the implementation is failing.
- **Script Quality:**
    - Jaccard similarity between segments must remain < 50% (Anti-Repetition).
    - Narrative must maintain the "Late-Night Show" format established in Product Guidelines.
- **Resource Logic:** `likes` and `plays` must always initialize at 0 (never hallucinated).
