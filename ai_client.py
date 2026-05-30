"""
ai_client.py — AI Radio Echo
Handles LLM calls to Groq and Gemini.
Orchestrates model queues, JSON healing, and broadcast validation.
"""

import os
import json

from google import genai as google_genai
from groq import Groq


# ------------------------------------------------------------------ #
#  Model constants                                                    #
# ------------------------------------------------------------------ #

GROQ_MODEL       = "llama-3.3-70b-versatile"
GEMINI_PRIMARY   = "gemini-3.5-flash"
GEMINI_FALLBACK  = "gemini-3.1-flash-lite"

# Set A: production / prod-models
MODEL_SET_A: list[str] = [GROQ_MODEL, GEMINI_PRIMARY, GEMINI_FALLBACK]

# Set B: local / prod-db
MODEL_SET_B: list[str] = [GEMINI_PRIMARY]

PRODUCTION_ENVS = {"production", "prod-models"}


# ------------------------------------------------------------------ #
#  Low-level callers                                                  #
# ------------------------------------------------------------------ #

def call_groq(prompt: str, model: str) -> str | None:
    """
    Call the Groq chat completion API.
    Returns raw text response, or None on any failure.
    Never raises — every exception is caught and printed.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print(f"[AI] GROQ_API_KEY not set — cannot call {model}.")
        return None
    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[AI] Groq call failed ({model}): {e}")
        return None


def call_gemini(prompt: str, model: str) -> str | None:
    """
    Call the Gemini generative API via the google-genai SDK.
    Returns raw text response, or None on any failure.
    Never raises — every exception is caught and printed.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(f"[AI] GEMINI_API_KEY not set — cannot call {model}.")
        return None
    try:
        client = google_genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model, contents=prompt)
        return response.text
    except Exception as e:
        print(f"[AI] Gemini call failed ({model}): {e}")
        return None


# ------------------------------------------------------------------ #
#  JSON healing                                                       #
# ------------------------------------------------------------------ #

def heal_truncated_json(raw: str) -> dict | None:
    """
    Attempt to repair a truncated JSON string by closing open brackets/braces.
    Never tries regex repair — only structural bracket balancing.
    Returns parsed dict on success, None on failure.
    """
    text = raw.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop first line (```json or ```) and last line if it's a closing fence
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end]).strip()

    # Remove trailing comma before closing (common truncation artifact)
    text = text.rstrip()
    if text.endswith(","):
        text = text[:-1]

    # Count unmatched brackets
    open_braces   = text.count("{") - text.count("}")
    open_brackets = text.count("[") - text.count("]")

    # Close open arrays before closing objects (inner before outer)
    repaired = text
    if open_brackets > 0:
        repaired += "]" * open_brackets
    if open_braces > 0:
        repaired += "}" * open_braces

    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None


# ------------------------------------------------------------------ #
#  Broadcast validation                                               #
# ------------------------------------------------------------------ #

def _jaccard(a: str, b: str) -> float:
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    union = wa | wb
    if not union:
        return 0.0
    return len(wa & wb) / len(union)


def validate_broadcast(data: dict) -> bool:
    """
    Validates the structure of an AI-generated broadcast dict.
    Rules (all from spec):
      - Must have 'segments' key.
      - segments must be a list of >= 8 items.
      - Each segment must have 'speaker' and 'text' keys.
      - Each segment text must be >= 50 words.
      - No two segments may have Jaccard word overlap > 0.5.
    Returns True if valid, False otherwise (prints reason).
    """
    if "segments" not in data:
        print("[AI] Validation failed: missing 'segments' key.")
        return False

    segments = data["segments"]
    if not isinstance(segments, list):
        print(f"[AI] Validation failed: 'segments' is not a list (got {type(segments)}).")
        return False
    if len(segments) < 8:
        print(f"[AI] Validation failed: need >= 8 segments, got {len(segments)}.")
        return False

    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            print(f"[AI] Validation failed: segment {i} is not a dict.")
            return False
        if "speaker" not in seg:
            print(f"[AI] Validation failed: segment {i} missing 'speaker'.")
            return False
        if "text" not in seg:
            print(f"[AI] Validation failed: segment {i} missing 'text'.")
            return False
        word_count = len(str(seg["text"]).split())
        if word_count < 50:
            print(
                f"[AI] Validation failed: segment {i} has {word_count} words "
                f"(minimum 50)."
            )
            return False

    # Repetition check — Jaccard similarity between every pair
    texts = [str(seg["text"]) for seg in segments]
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            sim = _jaccard(texts[i], texts[j])
            if sim > 0.5:
                print(
                    f"[AI] Repetition rule violated: segments {i} and {j} "
                    f"have {sim:.1%} word overlap (> 50%)."
                )
                return False

    return True


# ------------------------------------------------------------------ #
#  Prompt builder                                                     #
# ------------------------------------------------------------------ #

def _build_prompt(news: list[dict], memory: list[dict], context_limit: int = 15) -> str:
    news_lines = "\n".join(
        f"- [{item['source']}] {item['headline']}: "
        f"{str(item.get('summary', ''))[:200]}"
        for item in news[:context_limit]
    )

    memory_block = ""
    if memory:
        prev_headlines = "\n".join(
            f"  - {m.get('headline', '')}" for m in memory[:5]
        )
        memory_block = f"\nRecent episodes (DO NOT repeat these topics):\n{prev_headlines}\n"

    return f"""You are the head writer of AI Radio — Echo, a satirical tech and world-news radio show.
Generate a complete broadcast script as a single JSON object.

Today's headlines:
{news_lines}
{memory_block}
Return ONLY a valid JSON object — no markdown fences, no explanation, nothing else.
The JSON must follow this exact structure:

{{
  "headline": "Catchy, satirical episode headline",
  "original_headline": "The primary source headline being covered",
  "source": "Primary news source name",
  "topic_tags": ["tag1", "tag2", "tag3"],
  "my_take": "The show's satirical editorial commentary (2-3 punchy sentences)",
  "post_text": "Social media post for this episode (max 280 characters)",
  "confidence": "high",
  "segments": [
    {{
      "speaker": "HOST",
      "text": "At least fifty words of spoken radio content here. Make it satirical, witty, and entertaining. Vary the sentence rhythm. Do not use bullet points or lists — this is spoken audio."
    }},
    {{
      "speaker": "CO-HOST",
      "text": "At least fifty words of spoken radio content here. Respond to the host, add analysis, make jokes, push back a little. Keep it natural and conversational."
    }}
  ]
}}

Hard requirements:
- MINIMUM 8 segments (alternating HOST / CO-HOST is preferred but not required)
- EVERY segment text must be at least 50 words
- No two segments may repeat the same points or language
- Cover multiple headlines from the list above
- confidence must be exactly one of: "high", "medium", "low"
- Return ONLY the JSON — any text before or after will break parsing"""


# ------------------------------------------------------------------ #
#  Main orchestration                                                 #
# ------------------------------------------------------------------ #

def generate_broadcast(
    news: list[dict],
    memory: list[dict],
    env: str,
    context_limit: int = 15,
) -> tuple[dict | None, str | None]:
    """
    Attempt to generate a validated broadcast dict.

    Model queue:
      - production / prod-models → Set A: Groq → Gemini Primary → Gemini Fallback
      - local / prod-db          → Set B: Gemini Primary only

    Per the spec:
      - If JSON parse fails → run heal_truncated_json → if still fails, try next model
      - If validation fails → return (None, None) immediately (no retry here)
      - Retries with reduced context are the CALLER's responsibility

    Returns:
        (broadcast_dict, model_name) on success
        (None, None) on failure
    """
    model_queue = MODEL_SET_A if env in PRODUCTION_ENVS else MODEL_SET_B
    prompt = _build_prompt(news, memory, context_limit)

    for model in model_queue:
        print(f"[AI] Trying model: {model} (context_limit={context_limit})")

        # --- Call the right backend ---
        if model == GROQ_MODEL:
            raw = call_groq(prompt, model)
        else:
            raw = call_gemini(prompt, model)

        if raw is None:
            print(f"[AI] {model} returned no output. Trying next model.")
            continue

        # --- Parse JSON ---
        healer_used = False
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            print(f"[AI] JSON parse failed for {model}. Attempting heal.")
            data = heal_truncated_json(raw)
            if data is None:
                print(f"[AI] Heal failed for {model}. Trying next model.")
                continue  # try next model in queue
            healer_used = True
            print(f"[AI] JSON healed successfully for {model}.")

        if not isinstance(data, dict):
            print(f"[AI] Parsed value is not a dict (got {type(data)}). Trying next model.")
            continue

        # --- Validate structure — hard stop on failure ---
        if not validate_broadcast(data):
            print("[AI] Validation failed. Returning None (caller handles retry).")
            return None, None

        data["_healer_used"] = healer_used
        print(f"[AI] Broadcast validated. Writer: {model}")
        return data, model

    print("[AI] All models exhausted without producing parseable output.")
    return None, None
