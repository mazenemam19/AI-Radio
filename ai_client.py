"""
ai_client.py — AI Radio Echo
LLM orchestration for satirical radio broadcast generation.

Model queues (set by --env, never inferred):
  Set A (prod-models, production): llama-3.3-70b-versatile → gemini-3.5-flash → gemini-3.1-flash-lite
  Set B (local, prod-db):          gemini-3.5-flash only

Step-down: first attempt uses 15 news items; each subsequent model drops to 8.
JSON healing attempted once on parse failure — no regex repair ever.
Validation failure is terminal; retries are the caller's responsibility.
"""

import json
import os
import re
from typing import Optional

# ── Model constants (exact strings — do not alter) ────────────────────────────

GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_PRIMARY = "gemini-3.5-flash"
GEMINI_FALLBACK = "gemini-3.1-flash-lite"

MODEL_SET_A: list[str] = [GROQ_MODEL, GEMINI_PRIMARY, GEMINI_FALLBACK]
MODEL_SET_B: list[str] = [GEMINI_PRIMARY]

_PRODUCTION_ENVS: frozenset[str] = frozenset({"production", "prod-models"})

# ── JSON Healer ───────────────────────────────────────────────────────────────

def heal_truncated_json(raw: str) -> Optional[dict]:
    """
    Attempt to salvage a truncated JSON object from an LLM response.

    Strategy (no regex content patching — only structural token appending):
      1. Try appending common closing sequences to the raw string.
      2. Walk the raw string character-by-character to find the last properly
         closed segment object (brace depth returns to 1), then truncate there
         and close the array + outer object.

    Returns a parsed dict or None if healing is impossible.
    """
    candidate = raw.strip()

    # Pass 1: simple closing token append
    for suffix in ("]}", "\n]}", "]\n}", " ]}"):
        try:
            result = json.loads(candidate + suffix)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    # Pass 2: walk to last complete segment, then close
    last_valid_end = -1
    brace_depth = 0
    in_string = False
    escape_next = False

    for i, ch in enumerate(candidate):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if not in_string:
            if ch == "{":
                brace_depth += 1
            elif ch == "}":
                brace_depth -= 1
                # depth 1 means we just closed a segment (still inside the array)
                if brace_depth == 1:
                    last_valid_end = i

    if last_valid_end > 0:
        truncated = candidate[: last_valid_end + 1]
        for suffix in ("]}", "\n]\n}", "\n]}"):
            try:
                result = json.loads(truncated + suffix)
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass

    return None


# ── LLM callers ───────────────────────────────────────────────────────────────

def call_groq(prompt: str, model: str) -> Optional[str]:
    """
    Call the Groq chat completions API.
    Returns the response text or None on any error (logged, not re-raised).
    """
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        print("[AI] GROQ_API_KEY is not set — cannot call Groq.")
        return None

    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=8192,
        )
        return response.choices[0].message.content
    except Exception as exc:
        print(f"[AI] Groq call failed (model={model}): {exc}")
        return None


def call_gemini(prompt: str, model: str) -> Optional[str]:
    """
    Call the Gemini API via google-generativeai.
    Returns the response text or None on any error (logged, not re-raised).
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[AI] GEMINI_API_KEY is not set — cannot call Gemini.")
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        gemini_model = genai.GenerativeModel(model)
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as exc:
        print(f"[AI] Gemini call failed (model={model}): {exc}")
        return None


# ── Broadcast prompt ──────────────────────────────────────────────────────────

def _build_prompt(news: list[dict], memory: list[dict], news_limit: int) -> str:
    """Construct the LLM prompt for a full satirical radio broadcast."""
    news_block = "\n".join(
        f"  [{item.get('source', '?')}] {item['headline']} — {item.get('summary', '')}"
        for item in news[:news_limit]
    ) or "  (No news items available today.)"

    memory_block = "\n".join(
        f"  ID: {m.get('id', '?')} | {m.get('headline', '?')} (tags: {m.get('topic_tags', [])})"
        for m in memory[:5]
    ) or "  No recent episodes on file."

    return f"""You are the head writer for "Echo FM" — a satirical AI-powered radio station
covering tech, AI, and the general absurdity of modern civilisation.

RECENT EPISODES (do NOT repeat these topics; use these IDs for 'related_ids'):
{memory_block}

TODAY'S NEWS FEED:
{news_block}

Write a COMPLETE live radio broadcast script. Return ONLY a single valid JSON object
with this EXACT structure — no markdown fences, no preamble, no commentary:

{{{{
  "title": "Episode title (punchy, satirical, max 10 words)",
  "topic_tags": ["tag1", "tag2", "tag3"],
  "confidence": "high/medium/low based on news factual density",
  "related_ids": [list of IDs from RECENT EPISODES that share themes],
  "my_take": "One punchy editorial sentence summarising the AI's read on today's news.",
  "post_text": "A social-media-ready 280-character teaser for this episode.",
  "segments": [
    {{{{
      "speaker": "ANCHOR",
      "text": "At least 100 words of satirical radio copy. No exceptions."
    }}}}
  ]
}}}}

HARD REQUIREMENTS — violation will cause the episode to be rejected:
- Target 12–15 segments. Total script volume must be ~1500 words.
- Speaker must be one of: ANCHOR, REPORTER, COMMENTATOR, WEATHERBOT.
- Every segment text MUST contain at least 100 words.
- Include exactly one WEATHERBOT segment: a surreal forecast for the AI economy.

- Do NOT summarise the news. Satirise, exaggerate, find the absurdity.
- Vary speakers. Do not use the same speaker more than 3 times in a row.
- Tone: dry wit, British-radio gravitas meets Silicon Valley anxiety.
- The JSON must be syntactically complete and properly closed.
"""


# ── Validation ────────────────────────────────────────────────────────────────

def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _word_set(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z]+", text.lower()))


def validate_broadcast(data: dict) -> tuple[bool, str]:
    """
    Validate the parsed broadcast JSON against all spec rules.

    Checks (in order):
      1. data is a dict with required keys.
      2. segments is a list with ≥ 8 items.
      3. Each segment has 'speaker' and 'text' keys.
      4. Each segment text has ≥ 50 words.
      5. No segment has > 50% Jaccard word overlap with any prior segment.

    Returns (is_valid: bool, reason: str).
    """
    if not isinstance(data, dict):
        return False, "Response is not a dict"
    
    required_keys = ["title", "segments", "confidence", "related_ids"]
    for k in required_keys:
        if k not in data:
            return False, f"Missing '{k}' key"

    if data["confidence"] not in ("high", "medium", "low"):
        return False, f"Invalid confidence value: {data['confidence']}"

    segments = data["segments"]
    if not isinstance(segments, list):
        return False, "'segments' is not a list"
    if len(segments) < 12:
        return False, f"Only {len(segments)} segment(s) — need ≥ 12"

    seen_word_sets: list[set] = []

    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            return False, f"Segment {i} is not a dict"
        if "speaker" not in seg:
            return False, f"Segment {i} missing 'speaker'"
        if "text" not in seg:
            return False, f"Segment {i} missing 'text'"

        word_count = len(seg["text"].split())
        if word_count < 100:
            return False, (
                f"Segment {i} ({seg['speaker']}) has only {word_count} word(s) — need ≥ 100"
            )

        # Repetition / Jaccard similarity check
        seg_words = _word_set(seg["text"])
        for j, prev_words in enumerate(seen_word_sets):
            similarity = _jaccard(seg_words, prev_words)
            if similarity > 0.5:
                return False, (
                    f"Segment {i} has {similarity:.0%} Jaccard overlap with "
                    f"segment {j} — exceeds 50% threshold"
                )
        seen_word_sets.append(seg_words)

    return True, "OK"


# ── Orchestrator ──────────────────────────────────────────────────────────────

def generate_broadcast(
    news: list[dict],
    memory: list[dict],
    env: str,
) -> Optional[dict]:
    """
    Generate and validate a satirical broadcast script.

    Model selection (controlled entirely by env):
      - prod-models / production → Set A (Groq → Gemini primary → Gemini fallback)
      - local / prod-db          → Set B (Gemini primary only)

    Step-down: first model gets 15 news items; each subsequent gets 8.
    JSON healing runs once on parse failure; no regex repair ever.
    Validation failure returns None immediately — caller is responsible for retries.
    Returns validated dict with '_writer_model' and '_healer_used' metadata keys,
    or None on total failure.
    """
    model_queue = MODEL_SET_A if env in _PRODUCTION_ENVS else MODEL_SET_B

    for attempt, model in enumerate(model_queue):
        news_limit = 15 if attempt == 0 else 8
        prompt = _build_prompt(news, memory, news_limit)
        is_groq = model == GROQ_MODEL

        print(
            f"[AI] Attempt {attempt + 1}/{len(model_queue)}: {model} "
            f"({'Groq' if is_groq else 'Gemini'}), news_limit={news_limit}"
        )

        raw = call_groq(prompt, model) if is_groq else call_gemini(prompt, model)
        if raw is None:
            print(f"[AI] {model} returned None — trying next model.")
            continue

        # Strip accidental markdown fences the model might add
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            raw = raw.strip()

        # Parse JSON
        data: Optional[dict] = None
        healer_used = False
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"[AI] JSON parse failed ({exc}). Attempting heal.")
            data = heal_truncated_json(raw)
            if data is None:
                print(f"[AI] Heal failed — model {model} unusable. Trying next.")
                continue
            healer_used = True
            print("[AI] JSON healed successfully.")

        # Validate structure + repetition
        valid, reason = validate_broadcast(data)
        if not valid:
            print(f"[AI] Validation failed: {reason}. Returning None (caller retries).")
            return None

        # Attach pipeline metadata
        data["_writer_model"] = model
        data["_healer_used"] = healer_used
        print(
            f"[AI] Broadcast validated — {len(data['segments'])} segments, "
            f"model={model}, healer={healer_used}"
        )
        return data

    print("[AI] All models exhausted — generate_broadcast returning None.")
    return None
