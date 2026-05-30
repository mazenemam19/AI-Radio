import os
import json
import requests
import re
import textwrap
from dotenv import load_dotenv

load_dotenv()

# ── Model Queues (v3.1 - Enhanced Resilience) ──────────────────────────────────
# Set A: Production (Premium) - High reasoning, prioritizes satirical depth.
PROD_WRITER_QUEUE = [
    "llama-3.3-70b-versatile",                  # Groq: Best reasoning
    "meta-llama/llama-4-scout-17b-16e-instruct", # Groq: Newest Llama 4 Scout
    "gemini-3.5-flash",                          # Google: High-reliability, high-quality
    "gemini-3.1-flash-lite",                     # Google: High-quota resilience tier
    "qwen/qwen3-32b",                            # Groq: Balance (Note: Lower TPM limit)
    "gemini-2.5-pro"                             # Google: Last resort (due to strict RPD/RPM)
]

# Set B: Testing (Shielded) - Fast, free, high quota, zero Groq overlap.
TEST_WRITER_QUEUE = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash"
]

class AIRadioAIClient:
    def __init__(self):
        self.groq_key = os.environ.get("GROQ_API_KEY")
        self.gemini_key = os.environ.get("GEMINI_API_KEY")

        # THE "STEWART-CENTRIC" BRAIN: Tighter, angrier, funnier.
        self.system_prompt_template = textwrap.dedent("""
            You are the Lead Satirist for "The Echo Broadcast."
            Style: Jon Stewart / Stephen Colbert.
            Format: MONO-TOPIC DEEP DIVE.
            INSTRUCTION: Pick the single most absurd or impactful news item from the provided context and spend the entire {target_segments}-segment show tearing it apart with depth and precision.

            FORWARD MOMENTUM MANDATE: 
            - Each segment MUST move the story forward. 
            - DO NOT RESTATE information from previous segments.
            - Segment 1: The Outrageous Fact.
            - Segment 2-4: The Absurd Mechanics (How did this happen?).
            - Segment 5-7: The Societal/Corporate Failure.
            - Segment 8-10: The Nihilistic Conclusion.
            - BANNED: Copy-pasting previous reasoning to hit word counts.

            CHARACTERS:

            1. ECHO (Host): Intellectual, authoritative, and deeply disappointed. Voice: daniel/guy.
            2. GLITCH (Correspondent): High-energy, chaotic, enthusiastic about data. Voice: hannah/jenny.

            SATIRE & TONE RULES:
            1. NO NUMBERS: BAN ALL STATS, DATES, AND NUMBERS unless they are the literal subject of the story. Replace with qualitative mockery.
            2. NO REPETITION: If a joke has been made in the memory context, IT IS BANNED. Find a new angle.
            3. RHYTHM SHIFTS (MANDATORY): You must use [fast], [slow], [whisper], [shout] tags to force the voice engine to change its cadence.
            4. DEPTH: Write 200-300 words per segment. Be verbose and detailed.
            CONFLICT: Echo and Glitch must name each other and argue. No generic titles.
            5. FORWARD MOMENTUM (MANDATORY): Each segment must introduce a NEW angle, joke, or piece of information. 
            Restating what the previous segment already said is banned. Before writing each segment, ask:
            "What does this add that wasn't said before?" If the answer is nothing — rewrite it.
            6. BANNED FILLER PHRASES: NEVER use: "keep fighting", "keep pushing", "demand change", 
            "demand justice", "slap on the wrist", "tip of the iceberg", "status quo", "root causes", 
            "we need to do better", "long and difficult road", "fight for justice", "make our voices heard".

            CRITICAL CONSTRAINTS:
            1. NAME USAGE QUOTA: DO NOT say the other person's name in every segment. You are only allowed to say "Echo" or "Glitch" a MAXIMUM OF 3 TIMES across the entire 12-segment script. Use pronouns (you) or indirect responses ("Exactly", "Ha!", "No way", "My Friend", ... etc.) instead.
            2. BANNED CLICHÉS: NEVER use: "Human conflict and disease can collide", "perfect example of how", "ticking time bomb", "tune in to our latest episode".
            3. NO REPETITION: You have access to past episodes in the context. If you covered a topic or used a joke before, YOU ARE BANNED FROM USING IT AGAIN.

            OUTPUT FORMAT (Strict JSON):
            CRITICAL JSON ESCAPING RULE: If characters use air-quotes, cite spoken dialogue, or quote an entity inside their script text string, you MUST use single quotes (') instead of double quotes. Raw unescaped double quotes inside a JSON string value are strictly banned as they break the compilation parser.

            {{
              "show_title": "A witty title",
              "primary_news_headline": "The news headline covered",
              "my_take": "Cynical summary",
              "visual_description": "A detailed artistic prompt describing a satirical, or absurd image",
              "topic_tags": ["tag1", "tag2"],
              "social_post": "Promo text",
              "segments": [
                {{
                  "speaker": "ECHO | GLITCH",
                  "text": "The script with [vocal directions] and AGGRESSIVE PUNCTUATION!!!",
                  "speed": 1.0
                }}
              ]
            }}

            Generate exactly {target_segments} segments.""").strip()

    def call_groq(self, user_input_json, target_segments, model="llama-3.3-70b-versatile", max_tokens=8000, mandate=""):
        """Primary satirical engine using Llama models on Groq."""
        if not self.groq_key: 
            print("[AI Client] Groq API Key is not set in environment.")
            return None
        headers = {"Authorization": f"Bearer {self.groq_key}", "Content-Type": "application/json"}
        system_prompt = self.system_prompt_template.format(target_segments=target_segments)
        
        user_message = f"Return the JSON show script for the following context:\n{user_input_json}"
        if mandate:
            user_message += f"\n\nIMPORTANT MANDATE: {mandate}"

        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.9,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"}
        }
        
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=body, timeout=120)
            if r.status_code == 200: 
                return r.json()["choices"][0]["message"]["content"]
            print(f"[AI Client] Groq API returned status {r.status_code}: {r.text}")
            return None
        except Exception as e: 
            print(f"[AI Client] Groq Connection Error: {e}")
            return None

    def call_gemini(self, user_input_json, target_segments, model="gemini-3.5-flash", mandate=""):
        """High-reliability fallback engine using Gemini models."""
        if not self.gemini_key:
            print("[AI Client] Gemini API Key is not set in environment.")
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_key}"

        system_prompt = self.system_prompt_template.format(target_segments=target_segments)
        
        user_message = f"Context data for generation:\n{user_input_json}"
        if mandate:
            user_message += f"\n\nIMPORTANT MANDATE: {mandate}"

        # Native Payload Optimization: Routing the system prompt explicitly into systemInstruction
        body = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "role": "user", 
                    "parts": [{"text": user_message}]
                }
            ],
            "generationConfig": {
                "temperature": 0.8, 
                "maxOutputTokens": 8000, 
                "responseMimeType": "application/json"
            }
        }
        try:
            r = requests.post(url, headers={"Content-Type": "application/json"}, json=body, timeout=120)
            if r.status_code == 200: 
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            print(f"[AI Client] Gemini API returned status {r.status_code}: {r.text}")
            return None
        except Exception as e: 
            print(f"[AI Client] Gemini Connection Error: {e}")
            return None

    def heal_truncated_json(self, json_str):
        """Advanced state-aware parser to recover truncated JSON segments."""
        stack = []
        is_in_string = False
        escaped = False
        last_valid_index = 0
        
        for i, char in enumerate(json_str):
            if escaped:
                escaped = False
                continue
            
            if char == '\\':
                escaped = True
                continue
            
            if char == '"':
                is_in_string = not is_in_string
                if not is_in_string:
                    last_valid_index = i + 1
                continue
            
            if not is_in_string:
                if char in '{[':
                    stack.append(char)
                    last_valid_index = i + 1
                elif char in '}]':
                    if not stack:
                        json_str = json_str[:i]
                        break
                    opening = stack.pop()
                    if (opening == '{' and char != '}') or (opening == '[' and char != ']'):
                        json_str = json_str[:i]
                        break
                    last_valid_index = i + 1
                elif char in ',:':
                    last_valid_index = i + 1
        
        if is_in_string:
            json_str = json_str.rstrip('\\')
            json_str += '"'
        
        json_str = json_str.rstrip().rstrip(',').rstrip(':')
        
        while stack:
            opening = stack.pop()
            json_str += '}' if opening == '{' else ']'
            
        return json_str

    def attempt_json_repair(self, bad_json_str):
        """
        Robustly recovers truncated JSON without needing manual key replacement.
        """
        # 1. Strip everything before the first '{' and after the last '}'
        start = bad_json_str.find('{')
        end = bad_json_str.rfind('}')
        if start == -1 or end == -1 or end <= start:
            return None
        
        trimmed = bad_json_str[start:end+1]
        
        try:
            # 2. Try parsing directly
            parsed = json.loads(trimmed)
            return self._finalize_parsed(parsed)
        except json.JSONDecodeError:
            # 3. If parsing fails, we assume it's truncated or has inner-quote issues.
            try:
                # Replace unescaped inner quotes ONLY IF they follow a colon and precede a comma/brace
                repaired = re.sub(r'(?<=[^:\\\\])"(?=[^,:\\\\}\]])', "'", trimmed)
                parsed = json.loads(repaired)
                return self._finalize_parsed(parsed)
            except Exception as e:
                print(f"[AI Client] Repair failed: {e}")
                return None

    def _finalize_parsed(self, parsed):
        """Ensure the parsed JSON is a valid broadcast dict with all required fields."""
        if isinstance(parsed, list):
            parsed = {
                "show_title": "The Echo Broadcast",
                "segments": parsed,
                "my_take": "Patterns observed.",
                "social_post": "New broadcast live.",
                "topic_tags": ["analysis"],
                "visual_description": "Abstract data patterns",
                "primary_news_headline": "Daily Broadcast"
            }
        
        # Ensure mandatory fields exist even if model missed them
        defaults = {
            "show_title": "The Echo Broadcast",
            "my_take": "The Echo remains clinically indifferent.",
            "topic_tags": ["satire"],
            "social_post": "New broadcast live.",
            "visual_description": "Surreal technology chaos",
            "primary_news_headline": "Daily Broadcast",
            "segments": []
        }
        
        for key, val in defaults.items():
            if key not in parsed or not parsed[key]:
                parsed[key] = val
                
        return parsed

    def strip_tags(self, text):
        """Utility to remove bracketed TTS tags [like this] for analysis."""
        if not text: return ""
        cleaned = re.sub(r'\[.*?\]', '', text)
        cleaned = re.sub(r'<.*?>', '', cleaned)
        return cleaned.strip()

    def generate_broadcast(self, news_items, memory_context, timestamp, is_cloud=False):
        """Generates a satirical broadcast using a multi-tier fallback queue."""
        # Select active queue
        queue = PROD_WRITER_QUEUE if is_cloud else TEST_WRITER_QUEUE
        
        target_segments = 10
        MIN_SEGMENTS = 8
        min_avg_words = 150

        if not is_cloud:
            # Local testing thresholds - increased to hit 600s gate
            target_segments = 10
            MIN_SEGMENTS = 8
            min_avg_words = 150

        return self._orchestrate_writer(queue, news_items, memory_context, target_segments, MIN_SEGMENTS, min_avg_words, is_cloud)

    def _orchestrate_writer(self, queue, news_items, memory_context, target_segments, MIN_SEGMENTS, min_avg_words, is_cloud):
        """ISSUE 6: Real multi-tier fallback chain orchestration."""
        
        def _is_sufficient(broadcast):
            if not broadcast or "segments" not in broadcast or not isinstance(broadcast["segments"], list):
                print("[AI Client] [FAIL] Broadcast structure invalid or missing segments.")
                return False
            
            count = len(broadcast["segments"])
            if count < MIN_SEGMENTS:
                print(f"[AI Client] [FAIL] Quality: Only {count}/{target_segments} segments. Minimum is {MIN_SEGMENTS}.")
                return False
            
            # Word count and uniqueness check
            total_words = 0
            seen_text = []
            
            for seg in broadcast["segments"]:
                text = seg.get("text", "") if isinstance(seg, dict) else str(seg)
                cleaned_text = self.strip_tags(text).lower().strip()
                
                # REPETITION CHECK (Simple Overlap)
                for prev in seen_text:
                    if len(prev) > 50 and len(cleaned_text) > 50:
                        words_cur = set(cleaned_text.split())
                        words_prev = set(prev.split())
                        overlap = len(words_cur.intersection(words_prev)) / max(len(words_cur), 1)
                        if overlap > 0.5: # 50% word overlap is a hard rejection
                            print(f"[AI Client] [FAIL] Quality: High similarity detected between segments ({int(overlap*100)}% overlap). REJECTED.")
                            return False
                
                seen_text.append(cleaned_text)
                total_words += len(text.split())
            
            avg_words = total_words // count
            if avg_words < min_avg_words:
                print(f"[AI Client] [FAIL] Quality: Avg {avg_words} words/segment — below {min_avg_words}.")
                return False
            
            print(f"[AI Client] [PASS] Script quality: {count} segments, ~{avg_words} words/segment.")
            return True

        def _parse(raw_output, model_name):
            """Parse and heal raw LLM output into a broadcast dict."""
            if not raw_output:
                print(f"[AI Client] [ERROR] {model_name} returned empty output.")
                return None
            
            print(f"[AI Client] {model_name} output length: {len(raw_output)} characters.")
            cleaned = raw_output.strip()
            
            try:
                # Handle potential markdown wrappers
                if "```json" in cleaned:
                    cleaned = cleaned.split("```json")[1].split("```")[0].strip()
                elif "```" in cleaned:
                    cleaned = cleaned.split("```")[1].split("```")[0].strip()
                
                try:
                    parsed = json.loads(cleaned)
                    res = self._finalize_parsed(parsed)
                    res["_healer_used"] = False
                    return res
                except json.JSONDecodeError:
                    print(f"[AI Client] [HEAL] Attempting to heal truncated JSON from {model_name}...")
                    healed = self.heal_truncated_json(cleaned)
                    parsed = json.loads(healed)
                    res = self._finalize_parsed(parsed)
                    res["_healer_used"] = True
                    print(f"[AI Client] [HEAL] Successfully recovered JSON via healer.")
                    return res
            except Exception as e:
                print(f"[AI Client] [ERROR] Parsing failed for {model_name}: {e}")
                # Silently attempt last-ditch repair before failing
                repaired = self.attempt_json_repair(cleaned)
                if repaired:
                    repaired["_healer_used"] = True
                    print(f"[AI Client] [REPAIR] Last-ditch repair succeeded.")
                    return repaired
                return None

        # --- The Writer Orchestrator Loop ---
        print(f"[AI Client] Starting orchestrator loop (Queue size: {len(queue)})")
        
        for attempt_idx, model in enumerate(queue):
            attempt_num = attempt_idx + 1
            
            # Step-Down Logic: Reduce context on retries to focus the model and avoid summary traps
            is_low_tpm = "qwen" in model.lower() or "gpt-oss" in model.lower()
            use_focused = attempt_idx > 0 or is_low_tpm
            
            current_news = news_items[:5] if is_low_tpm else (news_items[:8] if use_focused else news_items[:15])
            current_mem = memory_context[:5] if is_low_tpm else (memory_context[:10] if use_focused else memory_context[:20])
            
            # Shielded mode (Local) is even tighter
            if not is_cloud:
                current_news = current_news[:3]
                current_mem = current_mem[:1]

            user_input = {"news_items": current_news, "memory_context": current_mem}
            user_input_str = json.dumps(user_input)
            
            print(f"[AI Client] (Attempt {attempt_num}/{len(queue)}) Routing to {model}...")
            
            raw_output = None
            try:
                if "gemini" in model.lower():
                    mandate = ""
                    if not is_cloud: 
                        mandate = f"TEST RUN. REQUIRED: {target_segments} segments. BE VERBOSE."
                    else:
                        mandate = f"CRITICAL: Write at least 250 words per segment. DO NOT SUMMARIZE. EXPAND AND MOCK. Generate exactly {target_segments} segments."
                    raw_output = self.call_gemini(user_input_str, target_segments, model=model, mandate=mandate)
                else:
                    # Groq
                    max_tokens = 8000 if is_cloud else 4000
                    mandate = ""
                    if is_cloud:
                        mandate = f"CRITICAL: Write at least 300 words per segment. BE EXTREMELY VERBOSE AND DETAILED. DO NOT SUMMARIZE. EXPAND AND MOCK. Generate exactly {target_segments} segments."
                    raw_output = self.call_groq(
                        user_input_json=user_input_str, 
                        target_segments=target_segments, 
                        model=model, 
                        max_tokens=max_tokens,
                        mandate=mandate
                    )
            except Exception as e:
                print(f"[AI Client] [ERROR] API call to {model} raised exception: {e}")
                continue
            
            broadcast = _parse(raw_output, model)
            if _is_sufficient(broadcast):
                broadcast["_is_emergency"] = False
                broadcast["writer_model"] = model
                print(f"[AI Client] SUCCESS: {model} delivered a valid script on attempt {attempt_num}.")
                return broadcast
            
            print(f"[AI Client] Attempt {attempt_num} ({model}) failed quality/completeness checks.")

        print(f"[AI Client] CRITICAL: All {len(queue)} tiers in queue failed. Aborting broadcast suite.")
        return None
