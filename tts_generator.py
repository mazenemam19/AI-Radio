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

class TTSRadioGenerator:
    def __init__(self, echo_voice="daniel", glitch_voice="hannah"):
        self.echo_voice = echo_voice
        self.glitch_voice = glitch_voice
        self.api_key = os.environ.get("GROQ_API_KEY")
        self.api_url = "https://api.groq.com/openai/v1/audio/speech"
        self.model = "canopylabs/orpheus-v1-english"
        self.daily_char_limit = 14400 

    def strip_tags(self, text):
        cleaned = re.sub(r'\[.*?\]', '', text)
        cleaned = re.sub(r'<.*?>', '', cleaned)
        return cleaned.strip()

    def chunk_text(self, text, max_chars=190):
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
        """Generate audio with 'Fast-Exit' rate limit protection."""
        if not self.api_key: return False
        chunks = self.chunk_text(text)
        chunk_files = []
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        
        try:
            for c_idx, chunk_text in enumerate(chunks):
                # PACING
                if c_idx > 0: time.sleep(8.0)
                
                body = {"model": self.model, "input": chunk_text, "voice": voice, "response_format": "wav"}
                
                for attempt in range(3):
                    r = requests.post(self.api_url, headers=headers, json=body, timeout=30)
                    if r.status_code == 200:
                        c_path = f"{path}_chunk_{c_idx}.wav"
                        with open(c_path, "wb") as f: f.write(r.content)
                        chunk_files.append(c_path)
                        break
                    elif r.status_code == 429:
                        retry_after = r.headers.get("retry-after", "30")
                        wait_seconds = int(retry_after)
                        
                        # FAST EXIT: If wait is more than 60s, it's likely a daily/quota limit.
                        # Don't hang the script for an hour; just switch to backup.
                        if wait_seconds > 60:
                            print(f"[TTS] !!! DAILY QUOTA REACHED !!! Groq wants a {wait_seconds}s wait.")
                            print(f"[TTS] Aborting Cloud rendering and switching to local backup.")
                            raise Exception("Daily Quota Exceeded")
                        
                        print(f"[TTS] Rate limit hit. Waiting {wait_seconds}s (Attempt {attempt+1}/3)...")
                        time.sleep(wait_seconds + 1)
                    else:
                        raise Exception(f"API Error {r.status_code}")

            if chunk_files:
                ffmpeg_cmd = shutil.which("ffmpeg") or r"C:\ffmpeg\bin\ffmpeg.exe"
                list_path = f"{path}_list.txt"
                with open(list_path, "w") as f:
                    for cf in chunk_files: f.write(f"file '{os.path.abspath(cf)}'\n")
                subprocess.run([ffmpeg_cmd, "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c:a", "libmp3lame", path], check=True, capture_output=True)
                for cf in chunk_files: os.remove(cf)
                os.remove(list_path)
                return True

        except Exception as e:
            print(f"[TTS] Persistence failed: {e}. Using edge-tts backup for this segment.")
            for cf in chunk_files: 
                if os.path.exists(cf): os.remove(cf)
            asyncio.run(self.generate_edge_fallback(text, voice, path))
            return True

    def make_broadcast_audio(self, segments, output_path):
        total_chars = sum(len(s.get("text", "")) for s in segments)
        print(f"[TTS] --- STARTING BROADCAST MASTERING ---")
        print(f"[TTS] Show Characters: {total_chars} / {self.daily_char_limit} allowance.")

        temp_files = []
        try:
            for idx, seg in enumerate(segments):
                speaker = str(seg.get("speaker", "ECHO")).upper()
                voice = self.echo_voice if speaker == "ECHO" else self.glitch_voice
                temp_path = f"output/temp_seg_{idx}.mp3"
                
                print(f"[TTS] Processing Segment {idx+1}/{len(segments)} ({speaker})...")
                if self.generate_segment_audio(seg["text"], voice, temp_path):
                    temp_files.append(temp_path)
            
            if not temp_files: return False
            list_path = "output/concat_list.txt"
            with open(list_path, "w") as f:
                for tf in temp_files: f.write(f"file '{os.path.abspath(tf)}'\n")
            
            ffmpeg_cmd = shutil.which("ffmpeg") or r"C:\ffmpeg\bin\ffmpeg.exe"
            subprocess.run([ffmpeg_cmd, "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", output_path], check=True, capture_output=True)
            for tf in temp_files: os.remove(tf)
            os.remove(list_path)
            print(f"[TTS] Broadcast Audio Mastered: {output_path}")
            return True
        except Exception as e:
            print(f"[TTS] Mastering Error: {e}")
            return False

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
