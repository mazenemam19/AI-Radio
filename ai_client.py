"""
ai_client.py — AI client for AI Radio Echo.

Two low-level callers: call_groq(), call_gemini()
One orchestration method: generate_broadcast(news, memory, env)

Model sets:
  Set A (production, prod-models): llama-3.3-70b-versatile → gemini-3.5-flash → gemini-3.1-flash-lite
  Set B (local, prod-db):          gemini-3.5-flash only

generate_broadcast returns a dict on success (broadcast + _meta keys),
or None on any failure. Retries are the CALLER's responsibility.
"""

import os
import json
import re

# ---------------------------------------------------------------------------
# Model identifiers — exact strings, never modified
# ---------------------------------------------------------------------------

GROQ_MODEL_PRIMARY    = "llama-3.3-70b-versatile"
GEMINI_MODEL_PRIMARY  = "gemini-3.5-flash"
GEMINI_MODEL_FALLBACK = "gemini-3.1-flash-lite"

MODEL_SET_A = [GROQ_MODEL_PRIMARY, GEMINI_MODEL_PRIMARY, GEMINI_MODEL_FALLBACK]
MODEL_SET_B = [GEMINI_MODEL_PRIMARY]

PROD_ENVS  = {"production", "prod-models"}
LOCAL_ENVS = {"local", "prod-db"}

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are the scriptwriter for "AI Radio — Echo," a fully automated satirical radio \
broadcast. You produce sharp, witty scripts that satirize real news with comedic \
timing and political independence. Your job is to take real news stories and produce \
a satirical radio dialogue that sounds like a live broadcast — not a summary.

OUTPUT FORMAT: Return ONLY a JSON object with this exact structure. \
No markdown. No explanation. No code blocks. Just raw JSON.
{
  "segments": [
    {"speaker": "HOST", "text": "..."},
    {"speaker": "ANCHOR", "text": "..."}
  ]
}

SPEAKER ROLES:
  HOST         — Sardonic anchor who ties everything together
  ANCHOR       — Co-anchor who plays it straighter but can't hide exasperation
  CORRESPONDENT — Field expert who knows too much about everything
  REPORTER     — Breathless on-the-ground voice, slightly overwhelmed

HARD REQUIREMENTS:
  - Minimum 8 segments total
  - Each "text" value must be at least 50 words of actual dialogue
  - Each segment must satirize, not merely summarise
  - No three consecutive segments by the same speaker
  - End with a sign-off from HOST
  - Return ONLY the JSON object\
"""

USER_TEMPLATE = """\
TODAY'S NEWS STORIES:
{news}

RECENT BROADCAST MEMORY (do not repeat these exact angles or phrases):
{memory}

Write the full satirical broadcast script now.\
"""


# ---------------------------------------------------------------------------
# Low-level callers
# ---------------------------------------------------------------------------

def call_groq(prompt: str, model: str) -> "str | None":
    """
    Call the Groq completions API. Returns raw text response or None on error.
    Never swallows the error silently.
    """
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        print("[AI] GROQ_API_KEY not set — cannot call Groq.")
        return None

    try:
        from groq import Groq  # type: ignore
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.9,
            max_tokens=4096,
        )
        return response.choices[0].message.content
    except Exception as exc:
        print(f"[AI] Groq call failed (model={model}): {exc}")
        return None


def call_gemini(prompt: str, model: str) -> "str | None":
    """
    Call the Gemini API. Returns raw text response or None on error.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[AI] GEMINI_API_KEY not set — cannot call Gemini.")
        return None

    try:
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=api_key)
        gemini_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=SYSTEM_PROMPT,
        )
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as exc:
        print(f"[AI] Gemini call failed (model={model}): {exc}")
        return None


# ---------------------------------------------------------------------------
# JSON healing — stack-based, no regex repair
# ---------------------------------------------------------------------------

def heal_truncated_json(raw: str) -> "str | None":
    """
    Stack-based truncated JSON healer.

    Strategy:
      1. Iterate through the string tracking open/close braces and brackets
         using a proper stack (handles nested structures correctly).
      2. Locate the position of the last successfully closed segment object —
         i.e., the last '}' that brought the stack back to depth [root, array].
      3. Clip the string at that position, remove any trailing comma/whitespace.
      4. Close the remaining open structural elements (segments array ']'
         and root object '}').
      5. Attempt json.loads() to confirm the result is valid. Return None if
         it still fails — the downstream validator handles rejection.

    Never uses regex. Never invents data.
    """
    stack: list[str] = []
    last_segment_close: int = -1
    in_string: bool = False
    escape_next: bool = False

    for i, ch in enumerate(raw):
        if escape_next:
            escape_next = False
            continue

        if ch == "\\" and in_string:
            escape_next = True
            continue

        if ch == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch in ("{", "["):
            stack.append(ch)
        elif ch == "}":
            if stack and stack[-1] == "{":
                stack.pop()
                # After popping this '{', if the remaining stack is exactly
                # ['{', '['] we just closed a top-level segment object.
                if len(stack) == 2 and stack[0] == "{" and stack[1] == "[":
                    last_segment_close = i
        elif ch == "]":
            if stack and stack[-1] == "[":
                stack.pop()

    if last_segment_close == -1:
        print("[AI] heal_truncated_json: no complete segment found — cannot heal.")
        return None

    # Clip to the last complete segment object
    clipped = raw[: last_segment_close + 1].rstrip()

    # Remove trailing comma that preceded the truncated next segment
    if clipped.endswith(","):
        clipped = clipped[:-1]

    # Close remaining structure: segments array ']' then root object '}'
    healed = clipped + "]}"

    try:
        json.loads(healed)
        return healed
    except json.JSONDecodeError as exc:
        print(f"[AI] heal_truncated_json: healed string is still invalid JSON: {exc}")
        return None


# ---------------------------------------------------------------------------
# Broadcast validation
# ---------------------------------------------------------------------------

def _jaccard_similarity(text_a: str, text_b: str) -> float:
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    union = words_a | words_b
    if not union:
        return 0.0
    return len(words_a & words_b) / len(union)


def validate_broadcast(broadcast: dict) -> bool:
    """
    Validate the parsed broadcast dict against the Pipeline Rules.
    Returns True if valid, False (with a logged reason) if not.

    Rules checked:
      - Has 'segments' key
      - segments is a list with >= 8 items
      - Each segment has 'speaker' and 'text' keys
      - Each text is >= 50 words
      - No two segments have >50% Jaccard word overlap (repetition rule)
    """
    if not isinstance(broadcast, dict):
        print("[AI] Validation failed: broadcast is not a dict.")
        return False

    segments = broadcast.get("segments")
    if not isinstance(segments, list):
        print("[AI] Validation failed: 'segments' key missing or not a list.")
        return False

    if len(segments) < 8:
        print(f"[AI] Validation failed: only {len(segments)} segments (minimum 8).")
        return False

    for idx, seg in enumerate(segments):
        if not isinstance(seg, dict):
            print(f"[AI] Validation failed: segment {idx} is not a dict.")
            return False
        if "speaker" not in seg or "text" not in seg:
            print(f"[AI] Validation failed: segment {idx} missing 'speaker' or 'text'.")
            return False
        word_count = len(seg["text"].split())
        if word_count < 50:
            print(
                f"[AI] Validation failed: segment {idx} has {word_count} words "
                f"(minimum 50)."
            )
            return False

    # Repetition rule: Jaccard similarity check across all pairs
    texts = [seg["text"] for seg in segments]
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            sim = _jaccard_similarity(texts[i], texts[j])
            if sim > 0.5:
                print(
                    f"[AI] Validation failed: segments {i} and {j} have "
                    f"{sim:.0%} word overlap (maximum 50%)."
                )
                return False

    return True


# ---------------------------------------------------------------------------
# Broadcast generation — orchestrator
# ---------------------------------------------------------------------------

def _build_user_prompt(news: list[dict], memory: list[dict]) -> str:
    news_text = "\n".join(
        f"{i+1}. [{item.get('source', 'Unknown')}] {item['title']}"
        + (f"\n   {item['summary']}" if item.get("summary") else "")
        for i, item in enumerate(news)
    )
    memory_text = "\n".join(
        f"- {m.get('headline', '')} (via {m.get('writer_model', 'unknown')})"
        for m in memory[:10]
    ) or "No previous broadcasts."

    return USER_TEMPLATE.format(news=news_text, memory=memory_text)


def _try_model(prompt: str, model: str) -> "str | None":
    """Route to the correct low-level caller based on model name."""
    if model == GROQ_MODEL_PRIMARY:
        return call_groq(prompt, model)
    else:
        return call_gemini(prompt, model)


def generate_broadcast(
    news: list[dict],
    memory: list[dict],
    env: str,
) -> "dict | None":
    """
    Attempt to generate a validated broadcast using the appropriate model queue.

    Returns a dict on success. The dict contains all broadcast keys PLUS:
      _healer_used  (bool)  — whether heal_truncated_json was invoked
      _writer_model (str)   — which model produced the final output

    Returns None on any failure. Does NOT retry internally.
    Retries (with reduced news context) are the caller's responsibility.
    """
    if env in PROD_ENVS:
        model_queue = MODEL_SET_A
    elif env in LOCAL_ENVS:
        model_queue = MODEL_SET_B
    else:
        print(f"[AI] Unknown env '{env}'.")
        return None

    prompt = _build_user_prompt(news, memory)

    for model in model_queue:
        print(f"[AI] Trying model: {model}")
        raw = _try_model(prompt, model)

        if not raw:
            print(f"[AI] {model} returned empty response. Moving to next model.")
            continue

        # --- Strip markdown fences if the model wrapped in ```json ... ``` ---
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
            cleaned = cleaned.strip()

        # --- Attempt direct parse ---
        healer_used = False
        broadcast = None

        try:
            broadcast = json.loads(cleaned)
        except json.JSONDecodeError:
            print(f"[AI] JSON parse failed for {model}. Attempting heal_truncated_json.")
            healed = heal_truncated_json(cleaned)
            if healed is None:
                print(f"[AI] Heal failed for {model}. Moving to next model.")
                continue
            try:
                broadcast = json.loads(healed)
                healer_used = True
                print(f"[AI] Healed JSON parsed successfully.")
            except json.JSONDecodeError as exc:
                print(f"[AI] Healed JSON still invalid: {exc}. Moving to next model.")
                continue

        # --- Validate structure ---
        if not validate_broadcast(broadcast):
            print(f"[AI] Broadcast from {model} failed validation. Moving to next model.")
            continue

        # --- Success ---
        broadcast["_healer_used"]  = healer_used
        broadcast["_writer_model"] = model
        print(f"[AI] Broadcast generated successfully by {model}.")
        return broadcast

    print("[AI] All models in queue exhausted. generate_broadcast returning None.")
    return None
