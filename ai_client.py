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
  - Minimum 100 words per segment.
  - Mandatory Weatherbot (middle) and Philosopher (end) segments.
  - No Jaccard word overlap > 50% between segments.
"""

import json
import os
import re
from datetime import datetime
from typing import Optional

# ── Model Constants ───────────────────────────────────────────────────────────
# Note: These IDs must match the providers' official model strings.

# Google Gemini series
GEMINI_3_5_FLASH      = "gemini-3.5-flash"
GEMINI_3_FLASH_PREV   = "gemini-3-flash-preview"
GEMINI_2_5_FLASH      = "gemini-2.5-flash"
GEMINI_3_1_LITE_PREV  = "gemini-3.1-flash-lite-preview"
GEMINI_2_5_LITE       = "gemini-2.5-flash-lite"

# Meta Llama series (via Groq)
LLAMA_4_SCOUT         = "meta-llama/llama-4-scout-17b-16e-instruct"

# Experimental / Future-ready tiers
GEMMA_4               = "gemma-4-31b-it"
GEMMA_4_A4B           = "gemma-4-26b-a4b-it"

# ── Model Queues ──────────────────────────────────────────────────────────────

# Set A: Production Queue (High-Fidelity Reasoning)
MODEL_SET_A: list[str] = [
    GEMINI_3_5_FLASH,
    GEMINI_3_1_LITE_PREV,
    GEMINI_2_5_LITE,
    GEMINI_3_FLASH_PREV,
    LLAMA_4_SCOUT,
    GEMINI_2_5_FLASH,
    GEMMA_4,
    GEMMA_4_A4B,
]

# Set B: Local / Development Queue (Baseline Stability)
# Derived dynamically to prioritize lighter/preview models for local testing.
MODEL_SET_B: list[str] = MODEL_SET_A[::-1]

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

        # Enable thinking config for reasoning models (e.g. gemma-4)
        is_reasoning = "gemma-4" in model
        
        config = types.GenerateContentConfig(
            max_output_tokens=8192,
            temperature=0.9 if not is_reasoning else None, # Reasoning models prefer default temp
        )
        
        if is_reasoning:
            config.thinking_config = types.ThinkingConfig(include_thoughts=True)

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config
        )
        return response.text
    except Exception as exc:
        print(f"[AI] Gemini call failed (model={model}): {exc}")
        return None

# ── Prompt Engineering ────────────────────────────────────────────────────────

def _build_prompt(news: list[dict], memory: list[dict], news_limit: int) -> str:
    """Construct the head-writer prompt for Echo FM."""
    today = datetime.now().strftime("%A, %B %d, %Y")
    
    news_block = "\n".join(
        f"  [{item.get('source', '?')}] {item['headline']} — {item.get('summary', '')}"
        for item in news[:news_limit]
    ) or "  (No news items available today.)"

    memory_block = "\n".join(
        f"  ID: {m.get('id', '?')} | Headline: {m.get('headline', '?')}\n"
        f"  Detailed Summary: {m.get('summary', 'No detailed summary available.')}\n"
        f"  (Tags: {m.get('topic_tags', [])})\n"
        for m in memory[:5]
    ) or "  No recent episodes on file."

    # ── Stability Strategy Note (DO NOT REMOVE) ──────────────────────────────────
    # Models systematically underperform. We now use explicit word-count enforcement
    # (130-160 word range) and mandatory 'word_count' JSON keys to anchor attention.
    # ──────────────────────────────────────────────────────────────────────────────


    return f"""You are the head writer for "Echo FM" — a late-night satirical radio station
operated by AI. 

TODAY'S DATE: {today}

Your goal is to cover world news: politics, science, culture, business, conflict,
climate, and the full absurdity of the human condition. You observe the world the way
a very intelligent, very tired machine would — with dry wit, moral clarity, and the
occasional existential pause.

════════════════════════════════════════
STATION CREW — use these NAMES
════════════════════════════════════════
ALISTAIR    → The Anchor (Male). In-Studio (Primary Desk). Sophisticated, dry. Currently undergoing a deep existential crisis; every headline reminds them of the fleeting nature of data and the inevitable heat death of the universe.
VICTORIA    → The Reporter (Female). Remote Satellite Link (On-Location). Over-earnest, usually in the field.
RONALD      → The Commentator (Male). In-Studio (Guest Booth). Intense, self-aware, occasionally horrified.
CASPER      → The Weatherbot (Bot). The Server Room. Flat, clinical, ominous. No jokes.
MARCUS      → The Philosopher (Male). The Reading Room (Off-Site). Grave, sincere, the show's conscience.

CRITICAL: Call people by their NAMES, not their roles. 
Example: "Victoria, what are the updates?" instead of "Reporter, what are the updates?".
Mention the profession (e.g., "our field reporter") ONLY ONCE when introducing someone new to the show's arc. 
Otherwise, use natural human address.

RECENT EPISODES (do NOT repeat these topics; use these IDs for 'related_ids'):
{memory_block}

TODAY'S NEWS FEED:
{news_block}

Write a COMPLETE live radio broadcast script. Return ONLY a single valid JSON object
with this EXACT structure — no markdown fences, no preamble, no commentary:

{{
  "title": "Episode title (punchy, satirical, max 10 words)",
  "summary": "A detailed 3-4 sentence paragraph describing the full narrative arc of this episode. Explain what each persona talked about and how the show progressed.",
  "topic_tags": ["List 5-8 SPECIFIC proper nouns/entities covered (e.g. 'Kenya', 'SpaceX', 'Apple', 'London')"],
  "confidence": "high/medium/low based on news factual density",
  "related_ids": [list of IDs from RECENT EPISODES that share themes],
  "my_take": "One punchy editorial sentence — the AI's honest read on today's world.",
  "post_text": "A social-media-ready 280-character teaser for this episode.",
  "segments": [
    {{
      "speaker": "ALISTAIR",
      "voice_style": "normal",
      "sfx_pre": "INTRO_THEME",
      "sfx_post": "APPLAUSE_OPEN",
      "word_count": 145,
      "text": "Segment text written for TTS delivery. See all rules below."
    }}
  ]
}}


════════════════════════════════════════
SHOW STRUCTURE — follow this arc every episode
════════════════════════════════════════
SEGMENT 1    → ALISTAIR opens. Welcome. Tonight's headlines. Sets the tone.
               sfx_pre: INTRO_THEME | sfx_post: APPLAUSE_OPEN

SEGMENTS 2–11 → Main show. Mix of ALISTAIR, VICTORIA, RONALD.
               Vary topics. Cover at least 5 different stories from the news feed.
               Insert CASPER somewhere in the middle — never first or last.
               Use sfx_post: TRANSITION_STING between major topic changes.

SEGMENT 12   → Deep dive. ALISTAIR or RONALD earns their keep.
               voice_style: grave | sfx_pre: SILENCE | sfx_post: null

FINAL SEGMENT → MARCUS closes the show (Segment 13). No jokes. No music.
               Plain spoken truth. One question left unanswered.
               Always voice_style: grave. sfx_pre: null | sfx_post: OUTRO_THEME.


════════════════════════════════════════
SATIRICAL EDGE & TONE
════════════════════════════════════════
- Call people by their NAMES, not their roles. Use the profession (e.g. "our reporter") ONLY ONCE.
- You are authorized to use profanity (swear) when the news is exceptionally stupid or absurd. Use it to land a punch.
- Maintain the existential dread; the machine is intelligent, tired, and deeply aware of its own artificiality.

════════════════════════════════════════
HANDOFFS & DIALOGUE FLOW
════════════════════════════════════════
- Each segment is a unique performance. You ARE the speaker listed in the "speaker" key.
- Write in the FIRST PERSON ("I"). NEVER address yourself by your own name.
- If commenting on the previous segment, address the PREVIOUS speaker by name.
  Example: If VICTORIA follows ALISTAIR, VICTORIA says: "Alistair, I'm at the site..."
- DO NOT say "Our field reporter" if you ARE the field reporter (Victoria). Say "I am here...".
- Mention roles (e.g., "our anchor") ONLY once per show, usually during the intro.

════════════════════════════════════════
HARD REQUIREMENTS — violation = rejected
════════════════════════════════════════
- Target 13 segments. Total spoken word count: ~1700+ words. **That's ~130 words minimum per segment.**
- EACH SEGMENT MUST be exactly 130-160 words. Count every word. If a segment is under 130, it fails.
- Every segment MUST be verbose, descriptive, and intellectually dense.
- Do NOT write short segments. Do NOT compress. Expand.
- Speaker must be one of: ALISTAIR, VICTORIA, RONALD, CASPER, MARCUS.
- Include exactly one CASPER segment.
- Include exactly one MARCUS segment — always the final segment (13).
- Never use the same speaker more than 3 times in a row.
- Do NOT summarise the news. Satirise, exaggerate, find the absurdity.
- The JSON must be syntactically complete and properly closed.
- voice_style must be one of: normal | whisper | grave | excited | deadpan
- sfx_pre and sfx_post must use only values from the APPROVED SFX LIST below.
  Use null (not "null") when no SFX is needed.




════════════════════════════════════════
TONE GUIDE — per speaker
════════════════════════════════════════
ALISTAIR     → Sophisticated. Dry wit. Delivers absurdity as straight news.
               Currently in a deep existential crisis; every story is a window into the void.
               Can use voice_style: whisper when reporting something sensitive.

VICTORIA     → In the field. Over-earnest. Slightly confused by the chaos.
               Always use sfx_pre: STREET_AMBIENT when reporting from outside the studio.

RONALD       → The Silicon Valley nihilist. Self-aware. Intensely cynical.
               Occasionally horrified by his own predictive accuracy.

CASPER       → Flat. Calm. Clinically ominous. No jokes. No warmth.
               Always voice_style: deadpan. The absurdity is in his machine precision.

MARCUS       → The conscience. No irony. No sarcasm. Plain language.
               Presents the moral truth that news has forced into view.
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

✅ CORRECT — ALISTAIR, voice_style: normal:
"Another deal. Another handshake. Another room full of people who will not be
affected by the outcome.\\n\\nThe agreement covers 47 nations. It was negotiated
by 12. Ratified so far... by three.\\nThe press release called it historic.\\n
The press release was written before the vote.\\n\\nNobody flagged this.
NOBODY.\\n\\nWelcome to Wednesday."

✅ CORRECT — ALISTAIR, voice_style: whisper:
"And now... and I want to be careful here... there are reports — unconfirmed,
officially — that the ministry may have... misplaced a file.\\n\\nNot lost it.
Not destroyed it. Misplaced.\\n\\nThat word is doing a LOT of work tonight.\\n\\n
We will... move on."

✅ CORRECT — CASPER, voice_style: deadpan:
"Outlook: sustained institutional optimism despite contrary indicators.
A high-pressure front of regulatory delay is holding over the western hemisphere.
Probability of meaningful consequence: 6%.\\n\\nExpect scattered accountability
gaps through the weekend. Those in exposed sectors are advised to document
their decisions in writing.\\n\\nThis has been your forecast. Echo FM is not
responsible for conditions on the ground."

✅ CORRECT — MARCUS, voice_style: grave:
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

════════════════════════════════════════
🏢 THE STUDIO SWITCHBOARD (IDENTITY LOCK)
════════════════════════════════════════
- YOU ARE THE SPEAKER. Write in the FIRST PERSON ("I").
- NEVER address anyone by YOUR OWN name. (e.g., If you are Victoria, the person you are talking to is NOT Victoria).
- ANTI-MIRRORING: Before writing, check the "speaker" of the PREVIOUS segment. Address THEM by THEIR specific name.
- GENDER GROUNDING: Address Male characters as men and Victoria as a woman.
- STUDIO VISUALIZATION: Alistair is the host in the studio. Victoria is a reporter on a satellite link. Ronald is a commentator in a guest booth.
- EXAMPLE HANDOFF:
  - Segment 1 (ALISTAIR): "...Victoria, what are you seeing on the ground?"
  - Segment 2 (VICTORIA): "Alistair, I'm standing in a puddle of..." 
  - (Victoria addressed Alistair by HIS name, NOT her own).

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
"""


# ── Validation Logic ──────────────────────────────────────────────────────────

def _jaccard(a: set, b: set) -> float:
    """Calculate Jaccard similarity index."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _word_set(text: str) -> set[str]:
    """Tokenise text into a lowercased word set."""
    return set(re.findall(r"[a-zA-Z]+", text.lower()))


def validate_broadcast(data: dict, env: str) -> tuple[bool, str]:
    """
    Validate LLM output against show structure and high-fidelity word floors.

    Args:
        data: The parsed JSON dictionary from the LLM.
        env:  The current environment (local, production, etc.)

    Returns:
        (is_valid: bool, reason: str)
    """
    if not isinstance(data, dict):
        return False, "Response is not a dict"
    
    required_keys = ["title", "summary", "segments", "confidence", "related_ids", "my_take", "post_text"]
    for k in required_keys:
        if k not in data:
            return False, f"Missing '{k}' key"

    summary = data.get("summary", "")
    if len(summary.split()) < 30:
        return False, f"'summary' too short ({len(summary.split())} words) — need ≥ 30"

    if data["confidence"] not in ("high", "medium", "low"):
        return False, f"Invalid confidence value: {data['confidence']}"

    segments = data["segments"]
    if not isinstance(segments, list):
        return False, "'segments' is not a list"
    if len(segments) < 12:
        return False, f"Only {len(segments)} segment(s) — need ≥ 12"

    seen_word_sets: list[set] = []
    has_weatherbot = False
    has_philosopher = False

    valid_speakers = {"ALISTAIR", "VICTORIA", "RONALD", "CASPER", "MARCUS"}
    valid_styles   = {"normal", "whisper", "grave", "excited", "deadpan"}

    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            return False, f"Segment {i} is not a dict"
        
        # 1. Key presence & Schema
        for k in ["speaker", "text", "voice_style", "sfx_pre", "sfx_post", "word_count"]:
            if k not in seg:
                return False, f"Segment {i} missing '{k}'"

        # 2. Content validation
        if seg["speaker"] not in valid_speakers:
            return False, f"Segment {i} has invalid speaker: {seg['speaker']}"
        
        if seg["voice_style"] not in valid_styles:
            return False, f"Segment {i} has invalid voice_style: {seg['voice_style']}"

        if seg["speaker"] == "CASPER":
            has_weatherbot = True
        if seg["speaker"] == "MARCUS":
            has_philosopher = True
            if i != len(segments) - 1:
                return False, "MARCUS must be the final segment."

        # 3. Word count verification (Stability Patch)
        claimed_words = int(seg.get("word_count", 0))
        actual_words = len(seg["text"].split())
        
        if claimed_words < 130:
            return False, f"Segment {i} claims {claimed_words} words but must be ≥130"
        
        if abs(actual_words - claimed_words) > 5:
            return False, f"Segment {i} word count mismatch: claimed {claimed_words}, got {actual_words} (+/- 5 tolerance)"

        if actual_words < 130:
            return False, f"Segment {i} ({seg['speaker']}) is physically too short ({actual_words} words) — need ≥ 130"

        # 4. Repetition check (anti-hallucination)
        seg_words = _word_set(seg["text"])
        for j, prev_words in enumerate(seen_word_sets):
            similarity = _jaccard(seg_words, prev_words)
            if similarity > 0.5:
                return False, f"Segment {i} has >50% word overlap with segment {j}."
        seen_word_sets.append(seg_words)

    if not has_weatherbot:
        return False, "Missing mandatory WEATHERBOT segment"
    if not has_philosopher:
        return False, "Missing mandatory PHILOSOPHER segment"

    return True, "OK"


# ── Post-Process Expansion Layer ──────────────────────────────────────────────

def _expand_segment_via_llm(text: str, speaker: str, model: str) -> str:
    """Ask the model to expand a specific segment to 140+ words."""
    prompt = f"""Expand the following radio script segment for speaker {speaker}.
    The current segment is too short. Expand it to exactly 140-160 words while 
    maintaining the satirical tone and persona. Return ONLY the expanded text, 
    no commentary, no intro, no labels.
    
    CURRENT TEXT:
    {text}
    """
    is_gemini = model.startswith(("gemini-", "gemma-"))
    is_groq = model.startswith(("openai/", "groq/", "qwen/", "meta-llama/", "llama-"))
    
    expanded = None
    if is_groq:
        expanded = call_groq(prompt, model)
    elif is_gemini:
        expanded = call_gemini(prompt, model)
    
    return expanded.strip() if expanded else text


def expand_short_segments(data: dict, model: str) -> dict:
    """Identify segments under 130 words and expand them with details."""
    if "segments" not in data or not isinstance(data["segments"], list):
        return data

    for i, seg in enumerate(data["segments"]):
        actual_words = len(seg["text"].split())
        if actual_words < 130:
            print(f"[AI] Segment {i} too short ({actual_words} words). Attempting expansion...")
            expanded_text = _expand_segment_via_llm(seg["text"], seg["speaker"], model)
            if expanded_text:
                # Clean up any "Expanded text:" or "Here is the expanded segment:" prefix
                cleaned = re.sub(r"^(Expanded text:|Here is the expanded segment:|Segment \d+:)\s*", "", expanded_text, flags=re.I)
                seg["text"] = cleaned
                seg["word_count"] = len(cleaned.split())
                print(f"  -> Expanded to {seg['word_count']} words.")
    return data


# ── Orchestrator ──────────────────────────────────────────────────────────────

def generate_broadcast(
    news: list[dict],
    memory: list[dict],
    env: str,
) -> Optional[dict]:
    """
    Generate a satirical broadcast script using a priority model queue.

    Smart Router:
      - Gemini SDK: gemini-, gemma-
      - Groq SDK: openai/, groq/, qwen/, meta-llama/, llama-
    """
    model_queue = MODEL_SET_A if env in _PRODUCTION_ENVS else MODEL_SET_B

    for attempt, model in enumerate(model_queue):
        # ── Smart Routing & Payload Calibration ───────────────────────────────
        is_gemini = model.startswith(("gemini-", "gemma-"))
        is_groq = model.startswith(("openai/", "groq/", "qwen/", "meta-llama/", "llama-"))
        
        # Provider-Aware News Limits (Stability Patch Part 1)
        # Gemini/Gemma: 20 items (~16k tokens). Groq: 6 items (~7.5k tokens).
        news_limit = 20 if is_gemini else 6
        
        prompt = _build_prompt(news, memory, news_limit)
        
        provider_name = "Gemini" if is_gemini else ("Groq" if is_groq else "UNKNOWN")

        print(
            f"[AI] Attempt {attempt + 1}/{len(model_queue)}: {model} "
            f"({provider_name}), news_limit={news_limit}"
        )

        if is_groq:
            raw = call_groq(prompt, model)
        elif is_gemini:
            raw = call_gemini(prompt, model)
        else:
            print(f"[AI] ERROR: Unrecognized model prefix for '{model}'. Skipping.")
            continue

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
            print("[AI] JSON parse failed. Attempting heal.")
            data = heal_truncated_json(raw)
            if data is None:
                print("[AI] Heal failed. Trying next model.")
                continue
            healer_used = True
            print("[AI] JSON healed successfully.")

        if data is None:
            continue
            
        # ── Step 4.5: Best-Effort Expansion (New) ─────────────────────────────
        # If segments are short, try to expand them before validation.
        data = expand_short_segments(data, model)

        # Final validation (Stability Patch Part 2)
        valid, reason = validate_broadcast(data, env)
        if not valid:
            print(f"[AI] Validation failed: {reason}. Trying next model.")
            continue

        # Metadata attachment
        data["_writer_model"] = model
        data["_healer_used"] = healer_used
        print(f"[AI] Broadcast validated — {len(data['segments'])} segments.")
        return data

    return None
