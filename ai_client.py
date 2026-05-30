"""
ai_client.py — AI Radio Echo
Two callers: call_gemini(), call_groq()
One orchestrator: generate_broadcast(news, memory, env)
Includes heal_truncated_json and full validation per spec.
"""

import json
import os
import re

# ---------------------------------------------------------------------------
# Model queues per spec
# ---------------------------------------------------------------------------

_QUEUE_PROD = [
    ("groq",   "llama-3.3-70b-versatile"),
    ("gemini", "gemini-3.5-flash"),
    ("gemini", "gemini-3.1-flash-lite"),
]

_QUEUE_LOCAL = [
    ("gemini", "gemini-3.5-flash"),
]

_PROD_ENVS = {"production", "prod-models"}

# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are the head writer for "Echo," a satirical AI radio station that covers world events
with wit and irreverence. Your scripts blend genuine insight with sharp absurdist humour.

Return ONLY valid JSON. No markdown, no code fences, no explanation — ONLY the raw JSON object.

Required format exactly:
{
  "title": "Catchy episode title (max 80 chars)",
  "headline": "Main story headline",
  "confidence": "high",
  "segments": [
    {"speaker": "HOST", "text": "Full spoken text, minimum 50 words..."},
    ...
  ]
}

Strict rules:
- Minimum 10 segments, maximum 15.
- Each segment text MUST be at least 50 words — count carefully before finishing.
- Valid speakers: HOST, REPORTER, ANALYST, WEATHERBOT, COMMENTATOR.
- HOST opens the broadcast and closes it. Alternate other speakers naturally.
- Satirical, fact-based. Exaggerate real trends. Do NOT invent fictional statistics.
- No segment may repeat ideas from another segment (>50% word overlap forbidden).
- confidence must be "high", "medium", or "low".
"""


def _build_prompt(news: list[dict], memory: list[dict], max_news: int = 15) -> str:
    news_block_items = []
    for item in news[:max_news]:
        src = item.get("source", "Unknown")
        headline = item.get("headline", "")
        summary = item.get("summary", "")
        news_block_items.append(f"  [{src}] {headline}: {summary[:300]}")
    news_block = "\n".join(news_block_items) or "  (no news items available)"

    memory_block_items = [m.get("headline", "") for m in memory[:5] if m.get("headline")]
    memory_block = "\n".join(f"  - {h}" for h in memory_block_items) or "  (no prior episodes)"

    return (
        _SYSTEM_PROMPT
        + "\n\nTODAY'S NEWS ITEMS:\n"
        + news_block
        + "\n\nRECENT EPISODE HEADLINES (avoid repetition):\n"
        + memory_block
        + "\n\nWrite the complete broadcast JSON now:"
    )


# ---------------------------------------------------------------------------
# Raw API callers
# ---------------------------------------------------------------------------

def call_gemini(prompt: str, model: str) -> str | None:
    """Call Google Gemini. Returns raw text or None on any failure."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("[AI] GEMINI_API_KEY not set.")
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model_obj = genai.GenerativeModel(model)
        response = model_obj.generate_content(
            prompt,
            generation_config={"temperature": 0.9, "max_output_tokens": 8192},
        )
        return response.text
    except Exception as exc:
        print(f"[AI] Gemini error ({model}): {exc}")
        return None


def call_groq(prompt: str, model: str) -> str | None:
    """Call Groq. Returns raw text or None on any failure."""
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        print("[AI] GROQ_API_KEY not set.")
        return None
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=8000,
        )
        return response.choices[0].message.content
    except Exception as exc:
        print(f"[AI] Groq error ({model}): {exc}")
        return None


# ---------------------------------------------------------------------------
# JSON healing
# ---------------------------------------------------------------------------

def heal_truncated_json(text: str) -> dict | None:
    """
    Attempt to close a truncated JSON object.
    No regex repairs — only bracket balancing and quote closing.
    Returns parsed dict or None.
    """
    if not text:
        return None

    raw = text.strip()

    # Strip markdown code fence if present
    if raw.startswith("```"):
        lines = raw.splitlines()
        # Remove opening fence line
        lines = lines[1:]
        # Remove closing fence if present
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    # Try to parse as-is first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Remove trailing commas before closing brackets (common LLM mistake)
    cleaned = re.sub(r",\s*([}\]])", r"\1", raw)

    # Count unclosed string — if odd number of unescaped quotes, close it
    # Walk character by character to avoid false positives
    in_string = False
    escaped = False
    for ch in cleaned:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string

    if in_string:
        cleaned += '"'

    # Balance brackets
    open_braces   = cleaned.count("{") - cleaned.count("}")
    open_brackets  = cleaned.count("[") - cleaned.count("]")

    cleaned += "]" * max(0, open_brackets)
    cleaned += "}" * max(0, open_braces)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        print(f"[AI] Heal failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _word_count(text: str) -> int:
    return len(text.split())


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def _check_repetition(segments: list[dict]) -> bool:
    """
    Returns True if any segment pair has >50% Jaccard similarity (word overlap).
    Spec: reject the entire script if detected.
    """
    texts = [seg.get("text", "") for seg in segments]
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if _jaccard_similarity(texts[i], texts[j]) > 0.50:
                print(
                    f"[AI] Repetition detected between segments {i} and {j} "
                    f"(Jaccard={_jaccard_similarity(texts[i], texts[j]):.2f})"
                )
                return True
    return False


def validate_broadcast(data: object) -> bool:
    """
    Full structural validation per spec:
    - has 'segments' key
    - segments is a list with >= 8 items
    - each segment has 'speaker' and 'text'
    - each text >= 50 words
    """
    if not isinstance(data, dict):
        print("[AI] Validation failed: response is not a dict.")
        return False

    segments = data.get("segments")
    if segments is None:
        print("[AI] Validation failed: missing 'segments' key.")
        return False
    if not isinstance(segments, list):
        print("[AI] Validation failed: 'segments' is not a list.")
        return False
    if len(segments) < 8:
        print(f"[AI] Validation failed: only {len(segments)} segments (need >= 8).")
        return False

    for idx, seg in enumerate(segments):
        if not isinstance(seg, dict):
            print(f"[AI] Validation failed: segment {idx} is not a dict.")
            return False
        if "speaker" not in seg:
            print(f"[AI] Validation failed: segment {idx} missing 'speaker'.")
            return False
        if "text" not in seg:
            print(f"[AI] Validation failed: segment {idx} missing 'text'.")
            return False
        wc = _word_count(seg["text"])
        if wc < 50:
            print(
                f"[AI] Validation failed: segment {idx} ({seg['speaker']}) "
                f"has only {wc} words (need >= 50)."
            )
            return False

    return True


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def generate_broadcast(news: list[dict], memory: list[dict], env: str) -> dict | None:
    """
    Generate a broadcast JSON via the configured model queue.
    Per spec:
      - production/prod-models: Set A queue (Groq -> Gemini fallbacks)
      - local/prod-db: Set B queue (Gemini only)
      - Parse failures trigger heal; heal failures advance to next model.
      - Validation failure returns None immediately (caller retries).
      - Step-down: try 15 news items first; if all parse/heal fail, retry with 8.
    """
    queue = _QUEUE_PROD if env in _PROD_ENVS else _QUEUE_LOCAL

    for context_size in [15, 8]:
        prompt = _build_prompt(news, memory, max_news=context_size)

        for api_type, model_name in queue:
            print(f"[AI] Trying {model_name} with {context_size} news items...")

            raw = call_groq(prompt, model_name) if api_type == "groq" else call_gemini(prompt, model_name)
            if raw is None:
                print(f"[AI] {model_name} returned None. Advancing queue.")
                continue

            # Strip markdown code fences before parsing
            candidate = raw.strip()
            if candidate.startswith("```"):
                lines = candidate.splitlines()
                lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                candidate = "\n".join(lines).strip()

            data: dict | None = None
            healer_used = False

            try:
                data = json.loads(candidate)
            except json.JSONDecodeError:
                print(f"[AI] JSON parse failed for {model_name}. Attempting heal...")
                data = heal_truncated_json(candidate)
                healer_used = True
                if data is None:
                    print(f"[AI] Heal failed for {model_name}. Advancing queue.")
                    continue

            # Structural validation
            if not validate_broadcast(data):
                print(f"[AI] Validation failed for {model_name} output. Returning None.")
                return None  # Per spec: do not retry within generate_broadcast

            # Repetition check
            if _check_repetition(data["segments"]):
                print(f"[AI] Repetition rule violated in {model_name} output. Returning None.")
                return None

            data["_model"] = model_name
            data["_healer_used"] = healer_used
            print(f"[AI] Broadcast generated successfully with {model_name} "
                  f"(healer={'yes' if healer_used else 'no'}).")
            return data

        print(f"[AI] All models exhausted at context_size={context_size}. "
              f"{'Stepping down.' if context_size == 15 else 'Giving up.'}")

    print("[AI] generate_broadcast failed: all models and context sizes exhausted.")
    return None
