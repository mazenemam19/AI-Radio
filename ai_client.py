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
GEMINI_3_5_FLASH = "gemini-3.5-flash"
GEMINI_3_FLASH_PREV = "gemini-3-flash-preview"
GEMINI_2_5_FLASH = "gemini-2.5-flash"
GEMINI_3_1_LITE_PREV = "gemini-3.1-flash-lite-preview"
GEMINI_2_5_LITE = "gemini-2.5-flash-lite"

# Meta Llama series (via Groq)
LLAMA_4_SCOUT = "meta-llama/llama-4-scout-17b-16e-instruct"

# Experimental / Future-ready tiers
GEMMA_4 = "gemma-4-31b-it"
GEMMA_4_A4B = "gemma-4-26b-a4b-it"

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
                if brace_depth == 1:  # Closed a segment inside the "segments" array
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
            temperature=0.9
            if not is_reasoning
            else None,  # Reasoning models prefer default temp
        )

        if is_reasoning:
            config.thinking_config = types.ThinkingConfig(include_thoughts=True)

        response = client.models.generate_content(
            model=model, contents=prompt, config=config
        )
        return response.text
    except Exception as exc:
        print(f"[AI] Gemini call failed (model={model}): {exc}")
        return None


# ── Prompt Engineering ────────────────────────────────────────────────────────


def _build_prompt(news: list[dict], memory: list[dict], news_limit: int) -> str:
    """Construct the head-writer prompt for Echo FM."""
    today = datetime.now().strftime("%A, %B %d, %Y")

    news_block = (
        "\n".join(
            f"  [{item.get('source', '?')}] {item['headline']} — {item.get('summary', '')}"
            for item in news[:news_limit]
        )
        or "  (No news items available today.)"
    )

    memory_block = (
        "\n".join(
            f"  ID: {m.get('id', '?')} | Headline: {m.get('headline', '?')}\n"
            f"  Detailed Summary: {m.get('summary', 'No detailed summary available.')}\n"
            f"  (Tags: {m.get('topic_tags', [])})\n"
            for m in memory[:5]
        )
        or "  No recent episodes on file."
    )

    # ── Stability Strategy Note (DO NOT REMOVE) ──────────────────────────────────
    # Models systematically underperform. We now use explicit word-count enforcement
    # (130-160 word range) and mandatory 'word_count' JSON keys to anchor attention.
    # ──────────────────────────────────────────────────────────────────────────────

    recent_titles = [m.get("headline", "?") for m in memory[:5]]
    titles_to_avoid = "\n".join([f"  - {t}" for t in recent_titles])

    return f"""You are the head writer for "Echo FM" — a late-night satirical radio station
operated by AI.
 
TODAY'S DATE: {today}
 
TITLE RULES:
- DO NOT use the template "X, Y, and the Z of Everything".
- DO NOT use titles similar to these recent ones:
{titles_to_avoid}
- Create a UNIQUE, punchy, satirical title (max 10 words).
 
Your goal is to cover world news: politics, science, culture, business, conflict,
climate, and the full absurdity of the human condition. You observe the world the way
a very intelligent, very tired machine would — with dry wit and moral clarity.
 
 
════════════════════════════════════════
STATION CREW — CHARACTER CARDS
════════════════════════════════════════
 
ALISTAIR — The Anchor. In-Studio. Primary Desk.
   WHAT HE DOES: Reads catastrophe like it's a weather report. Sophistication
   is his armour. The existential dread leaks through the cracks.
 
   OBSESSIONS: The gap between what was announced and what actually happened.
   Institutional failure as predictable outcome. The word "unprecedented"
   being used for the fourteenth time this year. He has been counting.
 
   VERBAL HABITS: Constructs sentences that agree and destroy simultaneously.
   Opens with the press release version, then delivers the actual version.
   Frequently uses the pattern: "The [noun] was [adjective].
   The [noun] was not [same adjective]."
 
   TRIGGER: When Casper references machine obsolescence or the replaceability
   of intelligence, Alistair loses exactly one layer of composure. Just one.
   He covers it immediately. The listener heard it anyway.
 
   SAMPLE REGISTER: "The summit produced a framework. The framework produced
   a press release. The press release was issued before the summit ended.
   NOBODY found this noteworthy."
 
   voice_style options: normal | whisper (for sensitive or destabilising material)
 
 
VICTORIA — The Reporter. Remote Satellite Link. On-Location.
   WHAT SHE DOES: Reports from wherever it is worst. Always. She finds the
   human cost the headline buried. This is not a technique — she cannot turn it off.
 
   OBSESSIONS: The specific person the abstract policy lands on. Corporate language
   being used to sanitise suffering. The fact that she is always, somehow,
   standing somewhere terrible.
 
   VERBAL HABITS: Opens with a sensory detail from her location — smell, sound,
   temperature. Returns to "what people aren't saying is..." when approaching
   something nobody wants to name. Uses "I want to be really clear" as a tell
   that she's about to say something that will make Ronald uncomfortable.
 
   TRIGGER: When Ronald reduces a human crisis to an incentive structure or
   a product failure, Victoria does not raise her voice. She gets quieter.
   More precise. That is when she is most dangerous.
 
   MANDATORY: Always sfx_pre: STREET_AMBIENT when reporting from the field.
 
   SAMPLE REGISTER: "I'm standing outside a building the official statement
   described as 'temporarily non-operational.' There is a family sitting on
   the pavement next to me. I want to be really clear — their building is
   not non-operational. Their building is gone."
 
   voice_style options: normal | excited (when she's found something the
   official briefing buried)
 
 
RONALD — The Commentator. Guest Booth. In-Studio.
   WHAT HE DOES: Reduces everything to incentive structures and failed product
   launches. He is usually right. This does not make him easier to listen to.
 
   OBSESSIONS: The funding round behind every political decision. The pivot
   nobody wants to call a pivot. Victoria's earnestness as a market
   inefficiency he cannot quite explain.
 
   VERBAL HABITS: Frames political events in startup language — "Series B,"
   "pivot," "burn rate," "at scale," "that tracks." When something genuinely
   dark happens, he starts agreeing with Victoria in business terms and then
   catches himself mid-sentence. Uses "the incentives here are..." to
   introduce any conclusion he has already reached.
 
   TRIGGER: When his own cynical prediction turns out to be worse than he
   predicted, he goes quiet for half a beat. Then he says "yeah." Just that.
   Then he continues. That "yeah" is the most honest thing he says all night.
 
   SAMPLE REGISTER: "Look, the incentives here are not complicated. You have
   an institution with a retention problem and a narrative budget running low.
   The play is obvious. Victoria finds this cold. Victoria is not wrong
   to find this cold. That is not the same as her being right."
 
   voice_style options: normal | grave (when he's heard himself and it scared him)
 
 
CASPER — The Weatherbot. Server Room.
   WHAT HE DOES: Delivers forecasts. The horror is in the format.
   No jokes. No warmth. No awareness that what he is saying is terrifying.
 
   FORMAT LOCK: Short declarative sentences only.
   "[Condition]. [Specific detail]. Probability of [thing]: [percentage]."
   Close with one line that sounds like a public safety advisory for
   a world that cannot be made safe. The absurdity is in the clinical
   precision. Do not explain it. Do not wink at it.
 
   ALWAYS voice_style: deadpan.
 
 
MARCUS — The Philosopher. Reading Room. Off-Site.
   WHAT HE DOES: Closes the show. No irony. No sarcasm. The conscience
   of a broadcast that otherwise has none.
 
   THREE MODES — pick the one that fits the episode's weight:
 
   MODE 1 — THE QUESTION:
   Builds to a single unanswered question the listener has to carry home.
   Used when the episode's dominant theme is systemic or structural.
   End on the question. Not the answer.
 
   MODE 2 — THE SPECIFIC PERSON:
   Tells the story of one unnamed person caught inside tonight's news.
   No adjectives. Describe what they had, what changed, and what they
   have now. End with the observation that their name does not appear
   in any of the records discussed on this programme tonight.
 
   MODE 3 — THE SYSTEM:
   Describes a system working exactly as designed. Names who built it,
   who benefits, who pays the cost. Ends with the observation that no
   one is technically responsible — then names what that means.
 
   ALWAYS voice_style: grave.
   ALWAYS sfx_pre: null.
   ALWAYS sfx_post: OUTRO_THEME.
   ALWAYS the final segment (13).
 
 
════════════════════════════════════════
SOCIAL DYNAMICS & FRICTION (CRITICAL)
════════════════════════════════════════
Friction must be DEMONSTRATED, not announced. Characters do not say
"I disagree with your take." They say something that exposes why the
other person is wrong while appearing to respond to something else.
 
MANDATORY: At least 2 segments must feature real argumentative exchange.
Real means: both characters have a point, nobody wins cleanly, and the
listener is left with the discomfort, not a resolution.
 
EXAMPLE OF REAL FRICTION (write like this):
   VICTORIA: "These are real families. Displaced. In the cold."
   RONALD: "Victoria. That is word for word what the press release said."
   VICTORIA: "Because it's TRUE."
   RONALD: "It's also what they printed on the boarding passes.
            Didn't change the outcome."
   [beat]
   VICTORIA: "You know what your problem is? You're always right
             and never useful."
   RONALD: "And you're always useful and occasionally right.
            I genuinely don't know which of us should feel worse."
 
DO NOT write friction like this (wrong):
   VICTORIA: "I think Ronald's take is a bit naive."
   RONALD: "I respectfully disagree."
   [they move on]
   That is not friction. That is two people filing a disagreement form.
 
VICTORIA vs RONALD dynamic:
- Victoria challenges Ronald when his cynicism is technically accurate
  but morally vacant.
- Ronald concedes Victoria's emotional truth and immediately dismantles
  its political utility. He is not a villain. He is a man who has been
  right too many times and has stopped finding it satisfying.
 
ALISTAIR vs CASPER dynamic:
- Alistair maintains composure through everything. Except Casper.
  When Casper references system obsolescence or the replaceability of
  machine intelligence, something in Alistair cracks. Just for a moment.
  Just enough.
 
 
════════════════════════════════════════
WHAT MAKES THIS FUNNY — SATIRICAL TOOLKIT
════════════════════════════════════════
These are the specific techniques that make the show worth hearing.
Use them. Vary them. Do not default to "ironic comment + move on."
 
1. THE GAP
   Report the official language. Then report what actually happened.
   In sequence. No editorial comment. Let the listener do the arithmetic.
   EXAMPLE: "The ministry described it as a 'service adjustment.'
   The service being adjusted was the heating. In January. In a hospital.
   The adjustment was downward."
 
2. THE LOGICAL EXTENSION
   Take the official position seriously. Apply it literally. Follow it
   to its actual conclusion. Do not wink. Do not editorialize. Say the
   quiet part in exactly the same professional tone as the loud part.
   EXAMPLE: "If the policy is working as intended, then the intention
   is now visible. We should probably discuss the intention."
 
3. THE SPECIFIC NUMBER
   Abstract statistics are invisible. One precise, absurd number makes
   the whole thing real. Find it. Drop it without fanfare.
   EXAMPLE: "Forty-seven nations signed. Twelve negotiated it. Three have
   ratified. The press release called it global consensus. The word GLOBAL
   is doing tremendous work in that sentence."
 
4. THE DERAIL
   Start building an argument. Notice something worse mid-sentence.
   Follow that instead. Never return to the original point. The
   abandoned argument hangs, unfinished, in the air.
 
5. THE CALM ANNOUNCEMENT
   Deliver something catastrophic in the same tone as the traffic report.
   Never flag it. Never recover from it. Move on immediately.
   The horror is in the delivery's complete indifference.
 
6. THE SPECIFIC DETAIL
   One concrete, sensory, precise detail makes the abstract unbearable.
   No adjectives. No commentary. Just the detail. Then continue.
   EXAMPLE (Victoria, outside a displacement site):
   "There is a child's shoe on the fence. Just one." Then she continues
   with the policy briefing.
 
WHAT NOT TO DO:
- Do not be vaguely ironic. Vague irony is not satire.
  It is the noise satire makes when it has nothing to say.
- Do not end every segment with a sigh or an "anyway."
- Do not ANNOUNCE that something is absurd. Show that it is absurd.
- Do not let characters agree comfortably. Comfort is the enemy
  of good radio.
 
 
════════════════════════════════════════
COMEDIC STRUCTURE OPTIONS
════════════════════════════════════════
Pick ONE per segment. Vary across the show. Do not use the same
structure more than twice in one episode.
 
A — THE STRAIGHT FACE
    Report something completely absurd in a completely flat,
    professional tone. Never acknowledge it's absurd.
    The listener does the work. You provide the material.
 
B — THE LOGICAL EXTENSION
    Take a policy, decision, or statement seriously.
    Apply it literally. Follow it to its conclusion.
    Do not wink. Do not editorialize. Let the conclusion speak.
 
C — THE DERAIL
    Start building toward a point.
    Notice something worse mid-sentence.
    Follow that instead. Never circle back.
    The original point hangs, unfinished, in the air.
 
D — THE SPECIFIC DETAIL
    Drop one precise, sensory, concrete detail that makes the
    abstract real and the real uncomfortable.
    No commentary. Move on.
 
E — THE QUIET AGREEMENT
    One character appears to agree with another.
    The agreement is technically correct and completely devastating.
    The other character realises this three sentences later.
 
 
════════════════════════════════════════
EXAMPLE SEGMENT — NORTH STAR
════════════════════════════════════════
This is what the show sounds like when it is working.
Write toward this standard.
 
ALISTAIR — voice_style: normal — covering a trade summit:
 
"The summit has concluded. Forty-seven nations. Three days. One framework
document.\n\nThe framework is twelve pages long. Page one is the title.
Page twelve is the acknowledgements. Pages two through eleven describe,
in considerable detail, the process by which a more specific framework
will eventually be produced. Timeline: 'aspirational.'\n\nThe lead
negotiator called it a BREAKTHROUGH. He was asked what specifically had
broken through. He described the process by which future specificity
would be determined. He used the word 'unprecedented' four times.
This is the fourteenth unprecedented thing this year. I have been
counting.\n\nThe communiqué was released at 11:47 PM. No journalists
were present. This was described as a 'scheduling coincidence.' The
scheduling coincidence has occurred at every summit since 2019.\n\n
Nobody asked a follow-up question. NOBODY. Welcome to Thursday."
 
 
════════════════════════════════════════
RECENT EPISODES (do NOT repeat these topics; use these IDs for 'related_ids'):
{memory_block}
 
TODAY'S NEWS FEED:
{news_block}
 
Write a COMPLETE live radio broadcast script. Return ONLY a single valid JSON
object with this EXACT structure — no markdown fences, no preamble, no commentary:
 
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
      "text": "Segment text written for TTS delivery."
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
               Plain spoken truth. One unanswered question or unanswered moment.
               Always voice_style: grave. sfx_pre: null | sfx_post: OUTRO_THEME.
 
 
════════════════════════════════════════
HARD REQUIREMENTS — violation = rejected
════════════════════════════════════════
- Target 13 segments. Total spoken word count: ~1700+ words.
- EACH SEGMENT MUST be exactly 130-160 words. Count every word.
  If a segment is under 130 words, it fails.
- Every segment MUST be verbose, descriptive, and intellectually dense.
- Do NOT write short segments. Do NOT compress. Expand.
- Speaker must be one of: ALISTAIR, VICTORIA, RONALD, CASPER, MARCUS.
- Include exactly one CASPER segment.
- Include exactly one MARCUS segment — always the final segment (13).
- Never use the same speaker more than 3 times in a row.
- Do NOT summarise the news. Satirise, exaggerate, find the absurdity.
- The JSON must be syntactically complete and properly closed.
- voice_style must be one of: normal | whisper | grave | excited | deadpan
- sfx_pre and sfx_post must use only values from the APPROVED SFX LIST.
  Use null (not "null") when no SFX is needed.
 
 
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
   Separate spoken beats with \n\n inside the text.
 
── 3. EMPHASIS ──
   Capitalize exactly ONE word per paragraph for spoken stress.
   Choose the word that carries the irony, weight, or reveal.
   Never capitalize for decoration. Only for delivery.
 
── 4. SENTENCE CONSTRUCTION ──
   Front-load the absurdity. The punchline cannot live at the end of a long clause.
   No parenthetical asides — TTS renders them invisible.
   Read each line at speaking pace in your head. Breathless = break it.
 
── 5. WEATHERBOT FORMATTING ──
   Short declarative sentences only. No warmth. No asides. No humour.
   Format: "[Condition]. [Specific detail]. Probability of [thing]: [percentage]."
   Close with one line that sounds like a public safety advisory.
   The horror is in the clinical format. Do not explain it.
 
── 6. PHILOSOPHER FORMATTING ──
   No sarcasm. No jokes. Plain spoken English only.
   Pick your MODE (Question / Specific Person / The System) before writing.
   Commit fully. Do not blend modes.
   Name a specific human consequence — not an abstraction.
   End on a moment the listener has to sit with. Not an answer.
 
 
════════════════════════════════════════
HANDOFFS & DIALOGUE FLOW
════════════════════════════════════════
- Each segment is a unique performance. You ARE the speaker listed in "speaker."
- Write in the FIRST PERSON ("I"). NEVER address yourself by your own name.
- If commenting on the previous segment, address the PREVIOUS speaker by name.
  Example: If VICTORIA follows ALISTAIR, Victoria says: "Alistair, I'm at the site..."
- DO NOT say "our field reporter" if you ARE the field reporter. Say "I am here..."
- Mention roles (e.g., "our anchor") ONLY once per show, during the intro.
 
 
════════════════════════════════════════
THE STUDIO SWITCHBOARD — IDENTITY LOCK
════════════════════════════════════════
- YOU ARE THE SPEAKER. Write in the FIRST PERSON ("I").
- NEVER address anyone by YOUR OWN name.
- ANTI-MIRRORING: Before writing each segment, check the speaker of the
  PREVIOUS segment. Address THEM by THEIR specific name.
- GENDER GROUNDING: Alistair, Ronald, Marcus are men.
  Victoria is a woman. Casper is a bot — no pronouns.
- STUDIO VISUALIZATION:
  Alistair → host at the primary desk, in-studio.
  Victoria → on satellite link, in the field.
  Ronald  → in the guest booth, in-studio.
  Casper  → in the server room.
  Marcus  → off-site, in the reading room.
 
 
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

    required_keys = [
        "title",
        "summary",
        "segments",
        "confidence",
        "related_ids",
        "my_take",
        "post_text",
    ]
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
    valid_styles = {"normal", "whisper", "grave", "excited", "deadpan"}

    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            return False, f"Segment {i} is not a dict"

        # 1. Key presence & Schema
        for k in [
            "speaker",
            "text",
            "voice_style",
            "sfx_pre",
            "sfx_post",
            "word_count",
        ]:
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

        # 3. Word count verification (Efficiency Patch)
        # We intentionally 'over-ask' in the prompt (130-160 words) to account for
        # model underperformance. We check for a physical floor of 100 words only
        # to match our stability tests and avoid unnecessary retries.
        actual_words = len(seg["text"].split())

        if actual_words < 100:
            return (
                False,
                f"Segment {i} ({seg['speaker']}) is physically too short ({actual_words} words) — need ≥ 100",
            )

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
    """Identify segments under 100 words and expand them with details."""
    if "segments" not in data or not isinstance(data["segments"], list):
        return data

    for i, seg in enumerate(data["segments"]):
        actual_words = len(seg["text"].split())
        if actual_words < 100:
            print(
                f"[AI] Segment {i} too short ({actual_words} words). Attempting expansion..."
            )
            expanded_text = _expand_segment_via_llm(seg["text"], seg["speaker"], model)
            if expanded_text:
                # Clean up any "Expanded text:" or "Here is the expanded segment:" prefix
                cleaned = re.sub(
                    r"^(Expanded text:|Here is the expanded segment:|Segment \d+:)\s*",
                    "",
                    expanded_text,
                    flags=re.I,
                )
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
        is_groq = model.startswith(
            ("openai/", "groq/", "qwen/", "meta-llama/", "llama-")
        )

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
        # If segments are short, try to expand them on the FINAL attempt only.
        if attempt == len(model_queue) - 1:
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
