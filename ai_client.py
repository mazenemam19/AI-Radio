import os
import json
import requests
import re
from dotenv import load_dotenv

load_dotenv()

class AIRadioAIClient:
    def __init__(self):
        self.groq_key = os.environ.get("GROQ_API_KEY")
        self.gemini_key = os.environ.get("GEMINI_API_KEY")

        # THE "STEWART-CENTRIC" BRAIN: Tighter, angrier, funnier.
        self.system_prompt_template = """You are the Lead Satirist for "The Echo Broadcast." 
Style: Jon Stewart / Stephen Colbert. 
Tone: Intellectual, incredulous, disappointed in humanity, but sharply funny.

SHOW CONSTRAINTS:
1. ABSOLUTELY NO REPETITION: Do not loop back to previous points.
2. NO FILLER: Every word must serve the satire.
3. DYNAMIC CONFLICT: [HOST] is the voice of "reason." [CORRESPONDENT] is the voice of "Internet Chaos." They should disagree constantly.
4. STRUCTURE:
   - Intro Rant (Host)
   - 3-4 Rapid-fire Headlines (Host & Correspondent)
   - ONE Deep Dive into the single most stupid story of the day (Host & Correspondent)
   - Final Existential Thought (Host)

VOICE DIRECTION:
- Use [sigh], [double-take pause...], [wait, WHAT?], [mocking applause] for timing.
- Use ALL CAPS for sudden spikes in anger.
- Use "..." for moments of stunned silence.

OUTPUT FORMAT:
Produce a JSON object with exactly {target_segments} segments total matching this strict schema:
{{
  "show_title": "A witty title for the episode",
  "my_take": "A cynical 1-2 sentence summary of the episode",
  "topic_tags": ["tag1", "tag2"],
  "social_post": "Catchy promo text for social media",
  "segments": [
    {{
      "speaker": "HOST",
      "text": "The spoken dialogue..."
    }},
    {{
      "speaker": "CORRESPONDENT",
      "text": "The spoken dialogue..."
    }}
  ]
}}"""

    def call_groq(self, user_input_json, target_segments):
        """Primary satirical engine using Llama 3.3 70B."""
        if not self.groq_key: return None
        headers = {"Authorization": f"Bearer {self.groq_key}", "Content-Type": "application/json"}
        system_prompt = self.system_prompt_template.format(target_segments=target_segments)
        
        body = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Return a json object containing the show script: {user_input_json}"}
            ],
            "temperature": 0.85,
            "max_tokens": 4000,
            "response_format": {"type": "json_object"}
        }
        
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=body, timeout=90)
            if r.status_code != 200:
                print(f"[AI Client] Groq API Error: {r.status_code}")
                return None
            
            resp_json = r.json()
            if "choices" in resp_json:
                return resp_json["choices"][0]["message"]["content"]
            return None
        except Exception as e:
            print(f"[AI Client] Groq request failed: {e}")
            return None

    def call_gemini(self, user_input_json, target_segments):
        """High-reliability fallback engine using Gemini 3.5 Flash."""
        if not self.gemini_key: return None
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={self.gemini_key}"
        system_prompt = self.system_prompt_template.format(target_segments=target_segments)
        
        # Enforce strict object structure in the user part
        prompt_text = f"System Guidelines:\n{system_prompt}\n\nInput Context:\n{user_input_json}\n\nIMPORTANT: Return a single JSON OBJECT, not an array. Ensure all strings are closed."

        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt_text}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 4000,
                "responseMimeType": "application/json"
            }
        }

        try:
            r = requests.post(url, headers={"Content-Type": "application/json"}, json=body, timeout=90)
            if r.status_code != 200: return None
            
            res = r.json()
            return res["candidates"][0]["content"]["parts"][0]["text"]
        except Exception: return None

    def generate_broadcast(self, news_items, memory_context, timestamp, is_cloud=False):
        """Generates a satirical broadcast. Multi-model with robust error handling."""
        target_segments = 7
        user_input = {
            "news_items": news_items,
            "memory_context": memory_context,
            "run_timestamp": timestamp
        }
        user_input_str = json.dumps(user_input)

        # 1. Try Groq
        raw_output = self.call_groq(user_input_str, target_segments)
        
        # 2. Fallback to Gemini
        if not raw_output:
            print("[AI Client] Groq failed. Falling back to Gemini...")
            raw_output = self.call_gemini(user_input_str, target_segments)

        if not raw_output:
            print("[AI Client] Both providers failed.")
            return None

        try:
            # Clean and Parse
            cleaned = raw_output.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0].strip()
            
            # HEALING: If it's an array, wrap it in a show object
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                print("[AI Client] Healing array-formatted response...")
                return {"show_title": "The Echo Broadcast", "segments": parsed, "my_take": "Patterns observed.", "social_post": "New broadcast live."}
            return parsed
        except Exception as e:
            print(f"[AI Client] JSON failure: {e}")
            return None
