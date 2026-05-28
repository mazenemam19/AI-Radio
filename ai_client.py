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

            CRITICAL CONSTRAINTS:
            1. NAME USAGE QUOTA: DO NOT say the other person's name in every segment. You are only allowed to say "Echo" or "Glitch" a MAXIMUM OF 3 TIMES across the entire 12-segment script. Use pronouns (you) or indirect responses ("Exactly", "Ha!", "No way", "My Friend", ... etc.) instead.
            2. BANNED CLICHÉS: NEVER use: "Human conflict and disease can collide", "perfect example of how", "ticking time bomb", "tune in to our latest episode".
            2. NO REPETITION: You have access to past episodes in the context. If you covered a topic or used a joke before, YOU ARE BANNED FROM USING IT AGAIN.

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

    def call_groq(self, user_input_json, target_segments):
        """Primary satirical engine using Llama 3.3 70B."""
        if not self.groq_key: 
            print("[AI Client] Groq API Key is not set in environment.")
            return None
        headers = {"Authorization": f"Bearer {self.groq_key}", "Content-Type": "application/json"}
        system_prompt = self.system_prompt_template.format(target_segments=target_segments)
        
        body = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Return the JSON show script for: {user_input_json}"}
            ],
            "temperature": 0.9,
            "max_tokens": 6000,
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

    def call_gemini(self, user_input_json, target_segments):
        """High-reliability fallback engine using Gemini 3.5 Flash."""
        if not self.gemini_key: 
            print("[AI Client] Gemini API Key is not set in environment.")
            return None
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={self.gemini_key}"
        system_prompt = self.system_prompt_template.format(target_segments=target_segments)
        
        # Native Payload Optimization: Routing the system prompt explicitly into systemInstruction
        body = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "role": "user", 
                    "parts": [{"text": f"Context data for generation:\n{user_input_json}"}]
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
                        # Unmatched closing bracket, truncate here
                        json_str = json_str[:i]
                        break
                    opening = stack.pop()
                    if (opening == '{' and char != '}') or (opening == '[' and char != ']'):
                        # Mismatched bracket, truncate here
                        json_str = json_str[:i]
                        break
                    last_valid_index = i + 1
                elif char in ',:':
                    last_valid_index = i + 1
        
        # If we're still in a string, close it
        if is_in_string:
            # Strip trailing backslash to avoid escaping the closing quote
            json_str = json_str.rstrip('\\')
            # Check if we were in a key-value pair and just finished the value
            json_str += '"'
        
        # Remove any trailing commas or colons that would make JSON invalid
        json_str = json_str.rstrip().rstrip(',').rstrip(':')
        
        # Close all remaining open brackets in reverse order
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
            return json.loads(trimmed)
        except json.JSONDecodeError:
            # 3. If parsing fails, we assume it's truncated or has inner-quote issues.
            # Only perform the 'replace internal double-quotes' if necessary,
            # but NEVER perform hardcoded key replacements.
            try:
                # Replace unescaped inner quotes ONLY IF they follow a colon and precede a comma/brace
                # This is a much safer, localized approach
                repaired = re.sub(r'(?<=[^:\\\\])"(?=[^,:\\\\}\]])', "'", trimmed)
                return json.loads(repaired)
            except Exception as e:
                print(f"[AI Client] Repair failed: {e}")
                return None

    def generate_broadcast(self, news_items, memory_context, timestamp, is_cloud=False):
        """Generates a satirical broadcast. Target: 12 segments (~8-10 mins) for all environments.
        Retries once if the returned segment count is below the minimum threshold."""
        target_segments = 12
        MIN_SEGMENTS = 10  # Minimum acceptable — below this the episode is too short to publish

        user_input = {"news_items": news_items, "memory_context": memory_context}
        user_input_str = json.dumps(user_input)

        def _call_primary(attempt=1):
            """Call the preferred engine based on environment."""
            if is_cloud:
                print(f"[AI Client] (Attempt {attempt}) Directing to Groq...")
                return self.call_groq(user_input_str, target_segments)
            else:
                print(f"[AI Client] (Attempt {attempt}) Local env — directing to Gemini...")
                return self.call_gemini(user_input_str, target_segments)

        def _call_fallback():
            """Call the other engine as fallback."""
            if is_cloud:
                print("[AI Client] Groq insufficient — falling back to Gemini...")
                return self.call_gemini(user_input_str, target_segments)
            else:
                print("[AI Client] Gemini insufficient — falling back to Groq (quota warning)...")
                return self.call_groq(user_input_str, target_segments)

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
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    healed = self.heal_truncated_json(cleaned)
                    return json.loads(healed)
            except Exception as e:
                print(f"[AI Client] Standard parse failed: {e}. Attempting repair...")
                repaired = self.attempt_json_repair(cleaned)
                if repaired:
                    print("[AI Client] Script recovered after repair.")
                    return repaired
                print(f"[AI Client] Problematic output snippet: {cleaned[:500]}...")
                return None

        def _is_sufficient(broadcast):
            if not broadcast or "segments" not in broadcast:
                return False
            count = len(broadcast["segments"])
            if count < MIN_SEGMENTS:
                print(f"[AI Client] WARNING: Only {count}/{target_segments} segments. Minimum is {MIN_SEGMENTS}.")
                return False
            # Word count check — catches short segments before wasting TTS time
            total_words = sum(len(seg.get("text", "").split()) for seg in broadcast["segments"])
            avg_words = total_words // count
            MIN_AVG_WORDS_PER_SEGMENT = 100  # ~40s per segment at normal speech rate
            if avg_words < MIN_AVG_WORDS_PER_SEGMENT:
                print(f"[AI Client] WARNING: Avg {avg_words} words/segment — below {MIN_AVG_WORDS_PER_SEGMENT}. "
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
                return None

        seg_count = len(broadcast["segments"])
        print(f"[AI Client] Script accepted: {seg_count} segments.")
        return broadcast
        """Generates a satirical broadcast. Target: 12 segments (~8-10 mins) for all environments."""
        target_segments = 12
        user_input = {"news_items": news_items, "memory_context": memory_context}
        user_input_str = json.dumps(user_input)

        raw_output = None
        if is_cloud:
            print("[AI Client] Remote/Cloud environment detected. Directing script generation to Groq...")
            raw_output = self.call_groq(user_input_str, target_segments)
            if not raw_output:
                print("[AI Client] Groq failed. Falling back to Gemini...")
                raw_output = self.call_gemini(user_input_str, target_segments)
        else:
            print("[AI Client] Local environment detected. Bypassing Groq to protect token limits. Directing script generation to Gemini...")
            raw_output = self.call_gemini(user_input_str, target_segments)

        if not raw_output: 
            print("[AI Client] Critical Error: No raw script text received from either LLM engine.")
            return None

        cleaned = raw_output.strip()
        try:
            # Remove markdown fence blocks if present
            if "```json" in cleaned: 
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned: 
                cleaned = cleaned.split("```")[1].split("```")[0].strip()

            # Initial parse attempt
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                # Hand over to the state-aware healer for truncation
                healed = self.heal_truncated_json(cleaned)
                return json.loads(healed)

        except Exception as e:
            print(f"[AI Client] Standard JSON parse failed: {e}. Initiating raw script sanitization...")
            # Hand over to the advanced recovery healer to catch nested dialogue quotes
            repaired_json = self.attempt_json_repair(cleaned)
            if repaired_json:
                print("[AI Client] Script parsed successfully after quote healing.")
                return repaired_json

            # Diagnostics Log
            print(f"[AI Client] Problematic Output Snippet: {cleaned[:500]}... [Truncated]")
            return None