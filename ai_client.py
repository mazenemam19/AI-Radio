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

        # THE GROQ TTS ENABLED BRAIN: Optimized for Orpheus model directions
        self.system_prompt_template = """You are the Lead Writer for "The Echo Broadcast." 
Style: Jon Stewart / Stephen Colbert. 
Format: MONO-TOPIC DEEP DIVE.

CHARACTERS:
1. ECHO (Host): Intellectual, authoritative, and deeply disappointed. Voice ID: daniel.
2. GLITCH (Correspondent): High-energy, chaotic, and enthusiastic about data. Voice ID: hannah.

SPEECH DIRECTIONS (MANDATORY):
Groq's Orpheus model uses bracketed directions. USE THEM HEAVILY:
- EMOTIONS: [sarcastic], [angry], [whispering], [shouting], [cheerful], [sad], [surprised], [deadpan], [laugh].
- PAUSES: Use <break time="1.0s" /> for dramatic effect or "..." for thinking.
- EMPHASIS: Use ALL CAPS for sudden spikes in volume.
- INTERACTION: Echo and Glitch must call each other by name.

RULES:
1. NO REPETITION: Move from one absurd angle to the next.
2. NO CLICHÉS: Be specific, detailed, and mean.
3. MONO-TOPIC: Stay on the one story for the whole script.

OUTPUT FORMAT (Strict JSON):
{{
  "show_title": "A witty title",
  "primary_news_headline": "The news headline covered",
  "my_take": "Cynical summary",
  "topic_tags": ["tag1", "tag2"],
  "social_post": "Promo text",
  "segments": [
    {{
      "speaker": "ECHO | GLITCH",
      "text": "The script with [vocal directions] and <break /> tags.",
      "speed": 1.0
    }}
  ]
}}

Generate exactly {target_segments} segments."""

    def call_groq(self, user_input_json, target_segments):
        if not self.groq_key: return None
        headers = {"Authorization": f"Bearer {self.groq_key}", "Content-Type": "application/json"}
        system_prompt = self.system_prompt_template.format(target_segments=target_segments)
        body = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Return the JSON show script for: {user_input_json}"}
            ],
            "temperature": 0.9,
            "max_tokens": 4000,
            "response_format": {"type": "json_object"}
        }
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=body, timeout=90)
            if r.status_code == 200: return r.json()["choices"][0]["message"]["content"]
            return None
        except Exception: return None

    def call_gemini(self, user_input_json, target_segments):
        if not self.gemini_key: return None
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={self.gemini_key}"
        system_prompt = self.system_prompt_template.format(target_segments=target_segments)
        prompt_text = f"Guidelines:\n{system_prompt}\n\nInput Context:\n{user_input_json}\n\nIMPORTANT: Return a JSON OBJECT with [tags] and <break /> tags."
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt_text}]}],
            "generationConfig": {"temperature": 0.8, "maxOutputTokens": 4000, "responseMimeType": "application/json"}
        }
        try:
            r = requests.post(url, headers={"Content-Type": "application/json"}, json=body, timeout=90)
            if r.status_code == 200: return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return None
        except Exception: return None

    def generate_broadcast(self, news_items, memory_context, timestamp, is_cloud=False):
        target_segments = 7
        user_input = {"news_items": news_items, "memory_context": memory_context}
        user_input_str = json.dumps(user_input)

        raw_output = self.call_groq(user_input_str, target_segments)
        if not raw_output:
            print("[AI Client] Groq failed. Falling back to Gemini...")
            raw_output = self.call_gemini(user_input_str, target_segments)

        if not raw_output: return None

        try:
            cleaned = raw_output.strip()
            if "```json" in cleaned: cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            parsed = json.loads(cleaned)
            return parsed
        except Exception as e:
            print(f"[AI Client] JSON failure: {e}")
            return None
