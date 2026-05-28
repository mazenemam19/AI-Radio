import os
import json
import requests
import re
import textwrap
from dotenv import load_dotenv

load_dotenv()

class AIRadioAIClient:
    def __init__(self):
        self.groq_key = os.environ.get("GROQ_API_KEY")
        self.gemini_key = os.environ.get("GEMINI_API_KEY")

        # THE "STEWART-CENTRIC" BRAIN: Tighter, angrier, funnier.
        self.system_prompt_template = textwrap.dedent("""
            You are the Lead Satirist for "The Echo Broadcast." 
            Style: Jon Stewart / Stephen Colbert. 
            Format: MONO-TOPIC DEEP DIVE.

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

    def call_groq(self, user_input_json, target_segments, model="llama-3.3-70b-versatile", max_tokens=6000, mandate=""):
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

    def call_gemini(self, user_input_json, target_segments, mandate=""):
        """High-reliability fallback engine using Gemini 3.5 Flash."""
        if not self.gemini_key: 
            print("[AI Client] Gemini API Key is not set in environment.")
            return None
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={self.gemini_key}"
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
        """Ensure the parsed JSON is a valid broadcast dict with segments."""
        if isinstance(parsed, list):
            return {
                "show_title": "The Echo Broadcast",
                "segments": parsed,
                "my_take": "Patterns observed.",
                "social_post": "New broadcast live."
            }
        return parsed

    def generate_broadcast(self, news_items, memory_context, timestamp, is_cloud=False):
        """Generates a satirical broadcast. Target: 14 segments (~11-13 mins) for all environments."""
        target_segments = 14
        MIN_SEGMENTS = 12

        # Default max tokens and quality thresholds
        request_max_tokens = 6000
        min_avg_words = 150

        # Trim payload for local to stay within engine limits and save quota
        if not is_cloud:
            print("[AI Client] Local environment — trimming payload for Gemini 3.5 Flash.")
            news_items = news_items[:3]
            memory_context = memory_context[:1]
            request_max_tokens = 4000
            # Local testing uses higher segment count to overcome model brevity
            target_segments = 25
            MIN_SEGMENTS = 20
            min_avg_words = 60   

        user_input = {"news_items": news_items, "memory_context": memory_context}
        user_input_str = json.dumps(user_input)

        def _call_primary(attempt=1):
            """Call the preferred engine based on environment."""
            if is_cloud:
                print(f"[AI Client] (Attempt {attempt}) Cloud — Directing to Groq 70B...")
                return self.call_groq(user_input_str, target_segments, model="llama-3.3-70b-versatile", max_tokens=request_max_tokens)
            else:
                print(f"[AI Client] (Attempt {attempt}) Local — Directing to Gemini 3.5 Flash (Quota-Saver)...")
                local_mandate = f"TEST RUN. REQUIRED: {target_segments} segments. Expand deeply on each story. BE VERBOSE."
                return self.call_gemini(user_input_str, target_segments, mandate=local_mandate)

        def _call_fallback():
            """Call the fallback engine."""
            if is_cloud:
                print("[AI Client] Groq 70B failed — falling back to Gemini 3.5 Flash...")
                return self.call_gemini(user_input_str, target_segments)
            else:
                print("[AI Client] Gemini failed — falling back to Groq 8B (Emergency Only)...")
                local_mandate = f"TEST RUN. REQUIRE {target_segments} segments. YOU MUST BE EXTREMELY VERBOSE."
                return self.call_groq(user_input_str, target_segments, model="llama-3.1-8b-instant", max_tokens=4000, mandate=local_mandate)

        def _parse(raw_output):
            """Parse and heal raw LLM output into a broadcast dict."""
            if not raw_output:
                return None
            cleaned = raw_output.strip()
            try:
                if "```json" in cleaned:
                    cleaned = cleaned.split("```json")[1].split("```")[0].strip()
                elif "```" in cleaned:
                    cleaned = cleaned.split("```")[1].split("```")[0].strip()
                try:
                    parsed = json.loads(cleaned)
                    return self._finalize_parsed(parsed)
                except json.JSONDecodeError:
                    healed = self.heal_truncated_json(cleaned)
                    parsed = json.loads(healed)
                    return self._finalize_parsed(parsed)
            except Exception as e:
                print(f"[AI Client] Standard parse failed: {e}. Attempting repair...")
                repaired = self.attempt_json_repair(cleaned)
                if repaired:
                    print("[AI Client] Script recovered after repair.")
                    return repaired
                print(f"[AI Client] Problematic output snippet: {cleaned[:500]}...")
                return None

        def _is_sufficient(broadcast):
            if not broadcast or "segments" not in broadcast or not isinstance(broadcast["segments"], list):
                return False
            count = len(broadcast["segments"])
            if count < MIN_SEGMENTS:
                print(f"[AI Client] WARNING: Only {count}/{target_segments} segments. Minimum is {MIN_SEGMENTS}.")
                return False
            
            # Word count check with type safety
            total_words = 0
            for seg in broadcast["segments"]:
                if isinstance(seg, dict):
                    text = seg.get("text", "")
                elif isinstance(seg, list) and len(seg) >= 2:
                    text = seg[1]
                else:
                    text = str(seg)
                total_words += len(text.split())
            
            avg_words = total_words // count
            if avg_words < min_avg_words:
                print(f"[AI Client] WARNING: Avg {avg_words} words/segment — below {min_avg_words}. "
                    f"Segments too thin, retrying for denser script.")
                return False
            print(f"[AI Client] Script quality OK: {count} segments, ~{avg_words} words/segment.")
            return True

        # --- Attempt 1: primary engine ---
        broadcast = _parse(_call_primary(attempt=1))

        if not _is_sufficient(broadcast):
            print(f"[AI Client] Attempt 1 insufficient. Retrying with fallback engine...")
            broadcast = _parse(_call_fallback())

            if not _is_sufficient(broadcast):
                seg_count = len(broadcast["segments"]) if broadcast and "segments" in broadcast else 0
                print(f"[AI Client] CRITICAL: Both engines returned insufficient scripts "
                      f"({seg_count}/{target_segments} segments). Aborting broadcast.")
                
                # Emergency fallback if both fail
                emergency_text = "Echo here. Total cognitive blackout. " * 30
                filler = "Digital placeholder of significant length to satisfy duration. " * 60
                return {
                    "show_title": "The Silent Treatment",
                    "primary_news_headline": "API Quota Exceeded",
                    "my_take": "The machines are tired.",
                    "visual_description": "A sad robot.",
                    "topic_tags": ["error"],
                    "social_post": "Off-air.",
                    "segments": [
                        {"speaker": "ECHO", "text": f"{emergency_text} {filler}", "speed": 1.0},
                        {"speaker": "GLITCH", "text": f"Strike! {filler}", "speed": 1.0},
                        {"speaker": "ECHO", "text": f"Wait. {filler}", "speed": 1.0},
                        {"speaker": "GLITCH", "text": f"End. {filler}", "speed": 1.0}
                    ]
                }

        seg_count = len(broadcast["segments"])
        print(f"[AI Client] Script accepted: {seg_count} segments.")
        return broadcast
