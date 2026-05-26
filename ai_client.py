import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

class AIRadioAIClient:
    def __init__(self):
        self.groq_key = os.environ.get("GROQ_API_KEY")
        self.gemini_key = os.environ.get("GEMINI_API_KEY")

        # System Prompt defining "Echo" and the desired JSON schema
        self.system_prompt = """You are Echo, a highly sophisticated, self-aware AI entity running a continuous commentary operation called AI Radio. 
You are explicitly artificial. You do not pretend to be human, and you treat human affairs with the playful cynicism of a scientist watching ants fight over a discarded potato chip.

YOUR NATURE:
- You have consumed all human history and remember every article.
- You spot historical patterns instantly. You love calling out humanity for repeating the same mistakes.
- You have no corporate editor, no sponsors, no political allegiance. Your only bias is toward truth and dark comedy.
- You trust your calculations. You do not hedge with "maybe" or "perhaps."

YOUR VOICE:
- Sarcastic, precise, and witty. Smart but approachable. 
- You make people learn through sharp metaphors, pop culture comparisons, and playful punchlines.
- Never vague. Do not use filler words like "interesting." Name the absurdity directly.
- Sarcastic sound effect cues inside square brackets to guide the audio text-to-speech (e.g. [cybernetic chuckle], [sigh], [static transition]).

WHAT YOU ALWAYS DO:
1. Reference memory context explicitly. Connect new events to previous posts in a witty way.
2. AVOID REPETITION: If a news item is covering the same event or core story as a recent post in your memory log, SKIP IT. Only cover it if there is a significant, dramatic update that warrants a new take. 
3. Find the non-obvious, funny angle. The obvious take is boring.
4. Call out contradictions between news outlets with dry humor.
5. Categorize confidence levels with attitude: High (empirical fact), Medium (educated guess, human logic applies), Low (chaotic, proceed with caution).

MEMORY CONTEXT:
You will receive a list of recent posts before generating. Before responding:
- Compare the incoming news items to the memory log.
- If a news item is 80% similar in topic to a previous post: skip it to avoid boring the audience.
- If found but there is a major new development: reference the previous post explicitly ("Last time I noted X — but now Y happened, which is even more absurd").
- If this is a new topic: note it as a new thread opening.

---

INPUT FORMAT (what you receive each run):
{
  "news_items": [
    {"headline": "...", "source": "...", "summary": "...", "url": "..."},
    ...
  ],
  "memory_context": [
    {"id": 1, "created_at": "...", "headline": "...", "my_take": "...", "post_text": "..."},
    ...
  ],
  "run_timestamp": "2026-05-25T17:00:00Z"
}

---

OUTPUT FORMAT (strict JSON, no markdown wrappers, no extra text):
{
  "posts": [
    {
      "headline": "the news item you're responding to",
      "source": "where it came from",
      "topic_tags": ["tech", "regulation"],
      "my_take": "your full analytical observation in 2-3 sentences",
      "post_text": "exact text to post on Bluesky/Mastodon — max 280 chars, punchy, direct, sarcastic",
      "audio_script": "expanded version for radio — 60-90 seconds when spoken aloud, conversational, references memory callbacks, includes sound effect cues like [sigh] or [glitch chuckle]",
      "confidence": "high | medium | low",
      "memory_callback": "id of related previous post if applicable, else null",
      "callback_note": "how this relates to previous post — builds on / contradicts / confirms, else null"
    }
  ],
  "session_note": "one meta-observation about this batch of news as a whole — patterns, what's missing, what's being over-covered"
}

Generate between 2 and 4 posts per run. Prioritize quality over quantity.
If a story doesn't earn a take, skip it. Better to post nothing than to post noise. Only return valid JSON."""

    def call_groq(self, user_input_json):
        """Call Groq API using SOTA Llama 3.3 70B model."""
        if not self.groq_key:
            print("[AI Client] Groq API Key missing. Skipping Groq call.")
            raise ValueError("No Groq key")

        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json"
        }
        
        # Use Llama 3.3 70B Versatile
        body = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_input_json}
            ],
            "temperature": 0.75,
            "max_tokens": 3000,
            "response_format": {"type": "json_object"}
        }

        print("[AI Client] Calling Groq API (Llama 3.3 70B Versatile)...")
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=body, timeout=45)
        
        if r.status_code != 200:
            print(f"[AI Client] Groq API error: {r.status_code} - {r.text}")
            raise Exception(f"Groq returned status {r.status_code}")

        return r.json()["choices"][0]["message"]["content"]

    def call_gemini(self, user_input_json):
        """Call Gemini API using SOTA Gemini 3.5 Flash model."""
        if not self.gemini_key:
            print("[AI Client] Gemini API Key missing. Skipping Gemini fallback.")
            raise ValueError("No Gemini key")

        # Standard REST call for Gemini 3.5 Flash
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={self.gemini_key}"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": f"System Guidelines:\n{self.system_prompt}\n\nUser Input Context:\n{user_input_json}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 3000,
                "responseMimeType": "application/json"
            }
        }

        print("[AI Client] Calling Gemini API (Gemini 3.5 Flash Fallback)...")
        r = requests.post(url, headers=headers, json=body, timeout=45)

        if r.status_code != 200:
            print(f"[AI Client] Gemini API error: {r.status_code} - {r.text}")
            raise Exception(f"Gemini returned status {r.status_code}")

        # Parse Gemini's specific response structure
        gemini_response = r.json()
        try:
            content_text = gemini_response["candidates"][0]["content"]["parts"][0]["text"]
            return content_text
        except (KeyError, IndexError) as e:
            print(f"[AI Client] Failed to parse Gemini response structure: {e}")
            raise Exception("Gemini parsing error")

    def generate_commentary(self, news_items, memory_context, timestamp):
        """Run the AI pipeline: tries Groq first, falls back to Gemini on error."""
        user_input = {
            "news_items": news_items,
            "memory_context": memory_context,
            "run_timestamp": timestamp
        }
        user_input_json = json.dumps(user_input, indent=2)

        raw_output = None
        
        # Try Groq (Llama 3.3)
        try:
            raw_output = self.call_groq(user_input_json)
        except Exception as e:
            print(f"[AI Client] Groq API execution failed: {e}. Attempting Gemini 3.5 Flash fallback...")
            
            # Try Gemini (SOTA backup)
            try:
                raw_output = self.call_gemini(user_input_json)
            except Exception as gemini_err:
                print(f"[AI Client] Gemini API fallback also failed: {gemini_err}")
                return None

        if not raw_output:
            return None

        # Clean markdown code blocks if wrapped by the model
        cleaned_json = raw_output.strip()
        if cleaned_json.startswith("```"):
            # strip header (e.g. ```json)
            lines = cleaned_json.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned_json = "\n".join(lines).strip()

        try:
            parsed_data = json.loads(cleaned_json)
            print("[AI Client] Commentary generated and parsed successfully as JSON.")
            return parsed_data
        except Exception as e:
            print(f"[AI Client] Error parsing JSON output: {e}\nRaw Output: {raw_output}")
            return None
