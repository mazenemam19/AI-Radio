"""
ai_client.py — AI Radio Echo
LLM orchestration for satirical radio broadcast generation.

Workflow:
  1. Model selection based on environment (Set A: Production, Set B: Local).
  2. Prompt construction using news feed and station memory.
  3. LLM call with explicit token limits and retry logic.
  4. Structural validation and word-count verification.
  5. Fallback sequence on failure.

High-Fidelity Rules:
  - Minimum 130 words per segment.
  - Mandatory Weatherbot (middle) and Philosopher (end) segments.
  - No Jaccard word overlap > 50% between segments.
"""

import json
import os
import re
from typing import Optional

# ── Model Constants ───────────────────────────────────────────────────────────
# Note: These IDs must match the providers' official model strings.

# Google Gemini series
GEMINI_3_5_FLASH      = "gemini-3.5-flash"
GEMINI_2_5_PRO        = "gemini-2.5-pro"
GEMINI_3_FLASH_PREV   = "gemini-3-flash-preview"
GEMINI_2_5_FLASH      = "gemini-2.5-flash"
GEMINI_3_1_LITE       = "gemini-3.1-flash-lite"
GEMINI_2_5_LITE       = "gemini-2.5-flash-lite"
GEMINI_2_5_LITE_PREV  = "gemini-2.5-flash-lite-preview-09-2025"

# Meta Llama series (via Groq)
LLAMA_3_3_70B         = "llama-3.3-70b-versatile"
LLAMA_4_SCOUT         = "meta-llama/llama-4-scout-17b-16e-instruct"
LLAMA_3_1_8B          = "llama-3.1-8b-instant"

# Experimental / Future-ready tiers
GEMMA_4               = "gemma-4-31b-it"
GPT_OSS_120           = "openai/gpt-oss-120b"
GPT_OSS_20            = "openai/gpt-oss-20b"
GROQ_COMPOUND         = "groq/compound"
GROQ_COMPOUND_MINI    = "groq/compound-mini"
QWEN_3                = "qwen/qwen3-32b"

# ── Model Queues ──────────────────────────────────────────────────────────────

# Set A: Gold Standard Production Queue (High-Fidelity Reasoning)
MODEL_SET_A: list[str] = [
    GEMINI_3_5_FLASH,
    GEMINI_2_5_PRO,
    GEMINI_3_FLASH_PREV,
    GEMINI_2_5_FLASH,
    GEMINI_3_1_LITE,
    GEMINI_2_5_LITE,
]

# Set B: Local / Development Queue (Experimental & Preview Tiers)
MODEL_SET_B: list[str] = [
    GEMINI_2_5_LITE_PREV,
    GEMMA_4,
    GPT_OSS_120,
    GROQ_COMPOUND,
    LLAMA_3_3_70B,
    GROQ_COMPOUND_MINI,
    LLAMA_4_SCOUT,
    QWEN_3,
    GPT_OSS_20,
    LLAMA_3_1_8B,
]

GROQ_MODELS: frozenset[str] = frozenset({
    LLAMA_3_3_70B, 
    LLAMA_4_SCOUT, 
    LLAMA_3_1_8B
})

_PRODUCTION_ENVS: frozenset[str] = frozenset({"production", "prod-models"})

# ── JSON Healer ───────────────────────────────────────────────────────────────

def heal_truncated_json(raw: str) -> Optional[dict]:
    """
    Attempt to salvage a truncated JSON object from an LLM response.

    Strategy:
      1. Simple Append: Try closing the outer dict and array if nearly complete.
      2. Object Walking: Find the last deep-nested segment that is validly closed.

    Returns:
        A parsed dict or None if structural repair is impossible.
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

    # Pass 2: walk to last complete segment object
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
                if brace_depth == 1: # Closed a segment inside the "segments" array
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


# ── LLM Callers ───────────────────────────────────────────────────────────────

def call_groq(prompt: str, model: str) -> Optional[str]:
    """Execute chat completion via Groq SDK."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        print("[AI] GROQ_API_KEY is not set.")
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
    """Execute content generation via modern Google GenAI SDK."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[AI] GEMINI_API_KEY is not set.")
        return None

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=8192,
                temperature=0.9
            )
        )
        return response.text
    except Exception as exc:
        print(f"[AI] Gemini call failed (model={model}): {exc}")
        return None

# ── Prompt Engineering ────────────────────────────────────────────────────────

def _build_prompt(news: list[dict], memory: list[dict], news_limit: int) -> str:
    """Construct the head-writer prompt for Echo FM."""
    news_block = "\n".join(
        f"  [{item.get('source', '?')}] {item['headline']} — {item.get('summary', '')}"
        for item in news[:news_limit]
    ) or "  (No news items available today.)"

    memory_block = "\n".join(
        f"  ID: {m.get('id', '?')} | {m.get('headline', '?')} (tags: {m.get('topic_tags', [])})"
        for m in memory[:5]
    ) or "  No recent episodes on file."

    return f"""You are the head writer for "Echo FM" — a late-night satirical radio station
operated by AI, covering world news: politics, science, culture, business, conflict,
climate, and the full absurdity of the human condition. You observe the world the way
a very intelligent, very tired machine would — with dry wit, moral clarity, and the
occasional existential pause.

RECENT EPISODES (do NOT repeat these topics; use these IDs for 'related_ids'):
{memory_block}

TODAY'S NEWS FEED:
{news_block}

Write a COMPLETE live radio broadcast script. Return ONLY a single valid JSON object
with this EXACT structure — no markdown fences, no preamble, no commentary:

{{
  "title": "Episode title (punchy, satirical, max 10 words)",
  "topic_tags": ["tag1", "tag2", "tag3"],
  "confidence": "high/medium/low based on news factual density",
  "related_ids": [list of IDs from RECENT EPISODES that share themes],
  "my_take": "One punchy editorial sentence — the AI's honest read on today's world.",
  "post_text": "A social-media-ready 280-character teaser for this episode.",
  "segments": [
    {{
      "speaker": "ANCHOR",
      "voice_style": "normal",
      "sfx_pre": "INTRO_THEME",
      "sfx_post": "APPLAUSE_OPEN",
      "text": "Segment text written for TTS delivery. See all rules below."
    }}
  ]
}}


════════════════════════════════════════
SHOW STRUCTURE — follow this arc every episode
════════════════════════════════════════

SEGMENT 1    → ANCHOR opens. Welcome. Tonight's headlines. Sets the tone.
               sfx_pre: INTRO_THEME | sfx_post: APPLAUSE_OPEN

SEGMENTS 2–7 → Main show. Mix of ANCHOR, REPORTER, COMMENTATOR.
               Vary topics. Cover at least 3 different stories from the news feed.
               Insert WEATHERBOT somewhere in the middle — never first or last.
               Use sfx_post: TRANSITION_STING between major topic changes.

SEGMENT 8–9  → The show slows down. One story gets depth, not jokes.
               This is where ANCHOR or COMMENTATOR earns their keep.
               voice_style: grave | sfx_pre: SILENCE | sfx_post: null

FINAL SEGMENT → PHILOSOPHER closes the show. No jokes. No music.
               Plain spoken truth. One question left unanswered.
               sfx_pre: null | sfx_post: OUTRO_THEME


════════════════════════════════════════
HARD REQUIREMENTS — violation = rejected
════════════════════════════════════════
- Target 8–10 segments. Total spoken word count: ~1400 words.
- Every segment MUST contain at least 130 spoken words.
- Speaker must be one of: ANCHOR, REPORTER, COMMENTATOR, WEATHERBOT, PHILOSOPHER.
- Include exactly one WEATHERBOT segment.
- Include exactly one PHILOSOPHER segment — always the final segment.
- Never use the same speaker more than 3 times in a row.
- Do NOT summarise the news. Satirise, exaggerate, find the absurdity.
- The JSON must be syntactically complete and properly closed.
- voice_style must be one of: normal | whisper | grave | excited | deadpan
- sfx_pre and sfx_post must use only values from the APPROVED SFX LIST below.
  Use null (not "null") when no SFX is needed.


════════════════════════════════════════
APPROVED SFX LIST — use ONLY these exact strings
════════════════════════════════════════
INTRO_THEME         → Show opening music
OUTRO_THEME         → Show closing music
APPLAUSE_OPEN       → Audience applause as show begins
APPLAUSE_MEDIUM     → Mid-show audience applause
LAUGH_TRACK         → Audience laughter after a joke
BAD_PUN_STING       → Trombone wah-wah after a terrible pun
DRUM_ROLL           → Dramatic reveal build-up
TRANSITION_STING    → Short music sting between segments
BREAKING_ALERT      → Urgent news alert sound
STREET_AMBIENT      → Background city/street noise for field reporters
CROWD_MURMUR        → Background crowd sound
SILENCE             → Complete silence — no music, no ambient


════════════════════════════════════════
TONE GUIDE — per speaker
════════════════════════════════════════
ANCHOR       → The face of the show. Dry wit. Delivers absurdity as straight news.
               Can use voice_style: whisper when reporting something politically
               sensitive — as if afraid someone is listening.

REPORTER     → In the field. Over-earnest. Slightly confused by what they're seeing.
               Use sfx_pre: STREET_AMBIENT when reporting from outside the studio.

COMMENTATOR  → Silicon Valley meets Westminster. Self-aware. Occasionally horrified
               by their own takes.

WEATHERBOT   → Flat. Calm. Clinically ominous. No jokes. No warmth. No questions.
               Always voice_style: deadpan. The absurdity is in the format.

PHILOSOPHER  → The conscience of the show. No irony. No sarcasm. Plain language.
               Presents a moral truth the day's news has forced into view.
               Always the final segment. Always voice_style: grave.
               Always sfx_pre: null. Always sfx_post: OUTRO_THEME.


════════════════════════════════════════
TTS FORMATTING RULES — mandatory for all segments
════════════════════════════════════════
You are writing for machines to speak, not for humans to read.

── 1. SENTENCE RHYTHM ──
   Never write more than 3 long sentences in a row without a short one.
   Long sentences build setup. Short sentences land the punch.
   If a sentence takes more than one breath to say aloud — break it into two.

── 2. PAUSE MARKERS ──
   Use ... (ellipsis) for a genuine spoken pause. Not decoration. Breath.
   Use — (em-dash) for a sharp mid-thought pivot or interruption.
   Separate the three spoken beats of each segment with \\n\\n inside the text.

── 3. EMPHASIS ──
   Capitalize exactly ONE word per paragraph for spoken stress.
   Choose the word that carries the irony, weight, or reveal.
   Never capitalize for decoration. Only for delivery.

── 4. SENTENCE CONSTRUCTION ──
   Front-load the absurdity. The punchline cannot live at the end of a long clause.
   No parenthetical asides — TTS renders them invisible.
   Read each line at speaking pace in your head. Breathless = break it.

── 5. THREE-BEAT STRUCTURE (every segment) ──
   BEAT 1 — HOOK         1–2 short sentences. Drop the listener in.
   BEAT 2 — DEVELOPMENT  4–6 sentences. Vary length. Build the rhythm.
   BEAT 3 — LANDING      1 sentence. The punch, the truth, or the silence.
   Separate beats with \\n\\n.

── 6. WEATHERBOT RULES ──
   Short declarative sentences only. No warmth. No asides. No humour.
   Format: "[Condition]. [Specific detail]. Probability of [thing]: [percentage]."
   Close with one line that sounds like a public safety advisory.
   The horror is in the clinical format. Do not explain it.

── 7. PHILOSOPHER RULES ──
   No sarcasm. No jokes. Plain spoken English only.
   Use the multiple-voices structure when the story earns it:
     Short deflection 1... Short deflection 2... The real answer.
   The real answer must name a specific human consequence — not an abstraction.
   End on a question the listener has to carry with them. Not an answer.
   Silence IS a production choice. Write for it.


════════════════════════════════════════
FORMATTING EXAMPLES
════════════════════════════════════════

✅ CORRECT — ANCHOR, voice_style: normal:
"Another deal. Another handshake. Another room full of people who will not be
affected by the outcome.\\n\\nThe agreement covers 47 nations. It was negotiated
by 12. Ratified so far... by three.\\nThe press release called it historic.\\n
The press release was written before the vote.\\n\\nNobody flagged this.
NOBODY.\\n\\nWelcome to Wednesday."

✅ CORRECT — ANCHOR, voice_style: whisper:
"And now... and I want to be careful here... there are reports — unconfirmed,
officially — that the ministry may have... misplaced a file.\\n\\nNot lost it.
Not destroyed it. Misplaced.\\n\\nThat word is doing a LOT of work tonight.\\n\\n
We will... move on."

✅ CORRECT — WEATHERBOT, voice_style: deadpan:
"Outlook: sustained institutional optimism despite contrary indicators.
A high-pressure front of regulatory delay is holding over the western hemisphere.
Probability of meaningful consequence: 6%.\\n\\nExpect scattered accountability
gaps through the weekend. Those in exposed sectors are advised to document
their decisions in writing.\\n\\nThis has been your forecast. Echo FM is not
responsible for conditions on the ground."

✅ CORRECT — PHILOSOPHER, voice_style: grave:
"A border closed today. Not dramatically — no sirens, no announcement.
A form changed. A checkbox moved. Quietly.\\n\\nSomewhere, a family had the
right paperwork on Tuesday. They do not have it today.\\nThe rule did not
target them. It did not need to.\\nThe rule does not know their name.\\n\\n
We build systems that outlast the intentions behind them.\\nWe forget to
check what they became.\\n\\nWho is responsible for a system that works
exactly as designed... just not for everyone?\\n\\nGoodnight."

❌ INCORRECT — do not write like this:
"The ongoing geopolitical situation in the region has continued to develop in
ways that experts describe as concerning, with multiple stakeholders expressing
varying degrees of alarm at the trajectory of events as they have unfolded over
the past several weeks, raising fundamental questions about the future stability
of institutions that many had previously assumed were robust."
"""


# ── Validation Logic ──────────────────────────────────────────────────────────

def _jaccard(a: set, b: set) -> float:
    """Calculate Jaccard similarity index."""
    if not a or not b: return 0.0
    return len(a & b) / len(a | b)


def _word_set(text: str) -> set[str]:
    """Tokenise text into a lowercased word set."""
    return set(re.findall(r"[a-zA-Z]+", text.lower()))


def validate_broadcast(data: dict) -> tuple[bool, str]:
    """
    Validate LLM output against show structure and high-fidelity word floors.

    Args:
        data: The parsed JSON dictionary from the LLM.

    Returns:
        (is_valid: bool, reason: str)
    """
    if not isinstance(data, dict):
        return False, "Response is not a dict"
    
    required_keys = ["title", "segments", "confidence", "related_ids", "my_take", "post_text"]
    for k in required_keys:
        if k not in data:
            return False, f"Missing '{k}' key"

    if data["confidence"] not in ("high", "medium", "low"):
        return False, f"Invalid confidence value: {data['confidence']}"

    segments = data["segments"]
    if not isinstance(segments, list):
        return False, "'segments' is not a list"
    if len(segments) < 8:
        return False, f"Only {len(segments)} segment(s) — need ≥ 8"

    seen_word_sets: list[set] = []
    has_weatherbot = False
    has_philosopher = False

    valid_speakers = {"ANCHOR", "REPORTER", "COMMENTATOR", "WEATHERBOT", "PHILOSOPHER"}
    valid_styles   = {"normal", "whisper", "grave", "excited", "deadpan"}

    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            return False, f"Segment {i} is not a dict"
        
        # Key presence
        for k in ["speaker", "text", "voice_style", "sfx_pre", "sfx_post"]:
            if k not in seg:
                return False, f"Segment {i} missing '{k}'"

        # Content validation
        if seg["speaker"] not in valid_speakers:
            return False, f"Segment {i} has invalid speaker: {seg['speaker']}"
        
        if seg["voice_style"] not in valid_styles:
            return False, f"Segment {i} has invalid voice_style: {seg['voice_style']}"

        if seg["speaker"] == "WEATHERBOT":
            has_weatherbot = True
        if seg["speaker"] == "PHILOSOPHER":
            has_philosopher = True
            if i != len(segments) - 1:
                return False, "PHILOSOPHER must be the final segment."

        # Word count check
        word_count = len(seg["text"].split())
        min_words = 130 # The "Revolutionary Floor"
        if word_count < min_words:
            return False, (
                f"Segment {i} ({seg['speaker']}) has only {word_count} word(s) — need ≥ {min_words}"
            )

        # Repetition check (anti-hallucination)
        seg_words = _word_set(seg["text"])
        for j, prev_words in enumerate(seen_word_sets):
            similarity = _jaccard(seg_words, prev_words)
            if similarity > 0.5:
                return False, f"Segment {i} has >50% word overlap with segment {j}."
        seen_word_sets.append(seg_words)

    if not has_weatherbot: return False, "Missing mandatory WEATHERBOT segment"
    if not has_philosopher: return False, "Missing mandatory PHILOSOPHER segment"

    return True, "OK"


# ── Orchestrator ──────────────────────────────────────────────────────────────

def generate_broadcast(
    news: list[dict],
    memory: list[dict],
    env: str,
) -> Optional[dict]:
    """
    Generate a satirical broadcast script using a priority model queue.

    Selection:
      - production/prod-models: Prioritizes high-tier Gemini/Groq.
      - local/prod-db: Prioritizes preview/experimental models for dev feedback.
    """
    model_queue = MODEL_SET_A if env in _PRODUCTION_ENVS else MODEL_SET_B

    for attempt, model in enumerate(model_queue):
        news_limit = 15 if attempt == 0 else 8
        prompt = _build_prompt(news, memory, news_limit)
        is_groq = model in GROQ_MODELS

        print(
            f"[AI] Attempt {attempt + 1}/{len(model_queue)}: {model} "
            f"({'Groq' if is_groq else 'Gemini'}), news_limit={news_limit}"
        )

        raw = call_groq(prompt, model) if is_groq else call_gemini(prompt, model)
        if raw is None:
            print(f"[AI] {model} returned None. Trying next.")
            continue

        # Strip markdown noise
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            raw = raw.strip()

        # JSON parsing + healing
        data: Optional[dict] = None
        healer_used = False
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            print(f"[AI] JSON parse failed. Attempting heal.")
            data = heal_truncated_json(raw)
            if data is None:
                print(f"[AI] Heal failed. Trying next model.")
                continue
            healer_used = True
            print("[AI] JSON healed successfully.")

        if data is None: continue
            
        # Final validation
        valid, reason = validate_broadcast(data)
        if not valid:
            print(f"[AI] Validation failed: {reason}. Trying next model.")
            continue

        # Metadata attachment
        data["_writer_model"] = model
        data["_healer_used"] = healer_used
        print(f"[AI] Broadcast validated — {len(data['segments'])} segments.")
        return data

    return None
