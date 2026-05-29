import os
import re
import asyncio
import subprocess
import shutil
import time
import requests
import edge_tts
from dotenv import load_dotenv

load_dotenv()

# ── Voice Queues (v3.1) ───────────────────────────────────────────────────────
PROD_VOICE_QUEUE = ["groq", "google", "edge"]
TEST_VOICE_QUEUE = ["edge"]

class TTSRadioGenerator:
    def __init__(self, echo_voice="daniel", glitch_voice="hannah", use_cloud=True):
        self.echo_voice = echo_voice
        self.glitch_voice = glitch_voice
        self.use_cloud = use_cloud 
        
        # Keys
        self.api_key = os.environ.get("GROQ_API_KEY")
        self.google_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        
        # Groq Config
        self.api_url = "https://api.groq.com/openai/v1/audio/speech"
        self.model = "canopylabs/orpheus-v1-english"
        self.daily_request_count = 0
        self.daily_request_limit = 80
        
        # Google Config (Neural2)
        self.google_voice_map = {
            "daniel": "en-US-Neural2-D", # Echo
            "hannah": "en-US-Neural2-F"  # Glitch
        }

    def strip_tags(self, text):
        cleaned = re.sub(r'\[.*?\]', '', text)
        cleaned = re.sub(r'<.*?>', '', cleaned)
        return cleaned.strip()

    def chunk_text(self, text, max_chars=450):
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""
        for s in sentences:
            if len(current_chunk) + len(s) < max_chars:
                current_chunk += (" " + s if current_chunk else s)
            else:
                if current_chunk: chunks.append(current_chunk.strip())
                if len(s) >= max_chars:
                    for i in range(0, len(s), max_chars): chunks.append(s[i:i+max_chars])
                    current_chunk = ""
                else: current_chunk = s
        if current_chunk: chunks.append(current_chunk.strip())
        return chunks

    async def generate_edge_fallback(self, text, voice, path):
        edge_voice = "en-US-GuyNeural" if "daniel" in voice else "en-US-JennyNeural"
        communicate = edge_tts.Communicate(self.strip_tags(text), edge_voice)
        await communicate.save(path)

    def generate_segment_audio(self, text, voice, path):
        """Tiered Narrator Orchestrator (v3.1)"""
        queue = PROD_VOICE_QUEUE if self.use_cloud else TEST_VOICE_QUEUE
        
        for provider in queue:
            try:
                if provider == "groq":
                    if not self.api_key or self.daily_request_count >= self.daily_request_limit:
                        print(f"[TTS] Groq skipped (No Key or Budget Exhausted).")
                        continue
                    
                    chunks = self.chunk_text(text)
                    chunk_files = []
                    headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
                    
                    for c_idx, chunk_text in enumerate(chunks):
                        if c_idx > 0: time.sleep(8.0)
                        body = {"model": self.model, "input": chunk_text, "voice": voice, "response_format": "wav"}
                        
                        success = False
                        for attempt in range(3):
                            r = requests.post(self.api_url, headers=headers, json=body, timeout=30)
                            if r.status_code == 200:
                                self.daily_request_count += 1
                                c_path = f"{path}_chunk_{c_idx}.wav"
                                with open(c_path, "wb") as f: f.write(r.content)
                                chunk_files.append(c_path)
                                success = True
                                break
                            elif r.status_code == 429:
                                retry_after = int(r.headers.get("retry-after", "30"))
                                if retry_after > 60:
                                    print(f"[TTS] Groq Rate Limit (429) too high. Falling back.")
                                    raise Exception("Rate Limit")
                                time.sleep(retry_after + 1)
                        
                        if not success: raise Exception("Chunk Failed")

                    if chunk_files:
                        ffmpeg_cmd = shutil.which("ffmpeg") or r"C:\ffmpeg\bin\ffmpeg.exe"
                        list_path = f"{path}_list.txt"
                        with open(list_path, "w") as f:
                            for cf in chunk_files: f.write(f"file '{os.path.abspath(cf)}'\n")
                        subprocess.run([ffmpeg_cmd, "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c:a", "libmp3lame", path], check=True, capture_output=True)
                        for cf in chunk_files: os.remove(cf)
                        os.remove(list_path)
                        return provider # Success

                elif provider == "google":
                    if not self.google_key:
                        print(f"[TTS] Google Cloud skipped (No Key).")
                        continue
                    
                    print(f"[TTS] Invoking Google Cloud TTS (Neural2)...")
                    google_voice = self.google_voice_map.get(voice, "en-US-Neural2-D")
                    chunks = self.chunk_text(text)
                    chunk_files = []
                    
                    import base64
                    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={self.google_key}"
                    
                    for c_idx, chunk_text in enumerate(chunks):
                        body = {
                            "input": {"text": self.strip_tags(chunk_text)},
                            "voice": {"languageCode": "en-US", "name": google_voice},
                            "audioConfig": {"audioEncoding": "MP3", "pitch": -2.0 if "daniel" in voice else 2.0}
                        }
                        r = requests.post(url, json=body, timeout=60)
                        if r.status_code == 200:
                            audio_content = r.json().get("audioContent")
                            if audio_content:
                                c_path = f"{path}_gchunk_{c_idx}.mp3"
                                with open(c_path, "wb") as f:
                                    f.write(base64.b64decode(audio_content))
                                chunk_files.append(c_path)
                            else: raise Exception("No audio content in Google response")
                        else:
                            raise Exception(f"Google API Error {r.status_code}: {r.text}")

                    if chunk_files:
                        ffmpeg_cmd = shutil.which("ffmpeg") or r"C:\ffmpeg\bin\ffmpeg.exe"
                        list_path = f"{path}_glist.txt"
                        with open(list_path, "w") as f:
                            for cf in chunk_files: f.write(f"file '{os.path.abspath(cf)}'\n")
                        subprocess.run([ffmpeg_cmd, "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c:a", "libmp3lame", path], check=True, capture_output=True)
                        for cf in chunk_files: os.remove(cf)
                        os.remove(list_path)
                        return provider # Success

                elif provider == "edge":
                    asyncio.run(self.generate_edge_fallback(text, voice, path))
                    return provider # Success

            except Exception as e:
                print(f"[TTS] Provider '{provider}' failed: {e}. Attempting next tier...")
                continue

        print(f"[TTS] CRITICAL: All voice tiers failed. Script at {path} could not be spoken.")
        return False

    def make_audio(self, text, output_path):
        """Generate audio from simple text input (used for testing and simple cases)."""
        print(f"[TTS] Generating audio: {output_path}")
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        return self.generate_segment_audio(text, self.echo_voice, output_path)

    def make_broadcast_audio(self, segments, output_path):
        mode = "PREMIUM CLOUD" if self.use_cloud else "STANDARD LOCAL"
        print(f"[TTS] --- STARTING {mode} MASTERING ---")
        temp_files = []
        last_provider = None
        try:
            for idx, seg in enumerate(segments):
                if idx > 0 and self.use_cloud:
                    time.sleep(3.0)  # pause between segments to respect Groq RPM
                speaker = str(seg.get("speaker", "ECHO")).upper()
                voice = self.echo_voice if speaker == "ECHO" else self.glitch_voice
                temp_path = f"output/temp_seg_{idx}.mp3"
                provider = self.generate_segment_audio(seg["text"], voice, temp_path)
                if provider:
                    temp_files.append(temp_path)
                    last_provider = provider
            
            if not temp_files: return False
            list_path = "output/concat_list.txt"
            with open(list_path, "w") as f:
                for tf in temp_files: f.write(f"file '{os.path.abspath(tf)}'\n")
            
            ffmpeg_cmd = shutil.which("ffmpeg") or r"C:\ffmpeg\bin\ffmpeg.exe"
            subprocess.run([ffmpeg_cmd, "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", output_path], check=True, capture_output=True)
            for tf in temp_files: os.remove(tf)
            os.remove(list_path)
            print(f"[TTS] Broadcast Audio Mastered: {output_path} (Used: {last_provider})")
            return last_provider
        except Exception as e:
            print(f"[TTS] Mastering Error: {e}")
            return False

    def get_audio_duration(self, audio_path):
        ffmpeg_cmd = shutil.which("ffprobe") or r"C:\ffmpeg\bin\ffprobe.exe"
        try:
            result = subprocess.run(
                [ffmpeg_cmd, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
                check=True, capture_output=True, text=True
            )
            return int(float(result.stdout.strip()))
        except Exception as e:
            print(f"[TTS] Duration probe error: {e}")
            return 0

    def compile_video(self, audio_path, image_path, output_path):
        ffmpeg_cmd = shutil.which("ffmpeg") or r"C:\ffmpeg\bin\ffmpeg.exe"
        command = [
            ffmpeg_cmd, "-y", "-loop", "1", "-i", image_path, "-i", audio_path,
            "-c:v", "libx264", "-preset", "fast", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-shortest", output_path
        ]
        try:
            subprocess.run(command, check=True, capture_output=True)
            return True
        except Exception as e:
            print(f"[TTS] Video Error: {e}")
            return False
