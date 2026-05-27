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
    def __init__(self, echo_voice="daniel", glitch_voice="hannah", use_cloud=True):
        self.echo_voice = echo_voice
        self.glitch_voice = glitch_voice
        self.use_cloud = use_cloud 
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
        # QUOTA-SAVER: Proactively skip Groq if not in cloud mode
        if not self.use_cloud or not self.api_key:
            asyncio.run(self.generate_edge_fallback(text, voice, path))
            return True

        chunks = self.chunk_text(text)
        chunk_files = []
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        
        try:
            for c_idx, chunk_text in enumerate(chunks):
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
                        if wait_seconds > 60:
                            print(f"[TTS] !!! QUOTA LIMIT !!! Switching to local backup.")
                            raise Exception("Quota Limit")
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
        except Exception:
            asyncio.run(self.generate_edge_fallback(text, voice, path))
            return True

    def make_audio(self, text, output_path):
        """Generate audio from simple text input (used for testing and simple cases)."""
        print(f"[TTS] Generating audio: {output_path}")
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        return self.generate_segment_audio(text, self.echo_voice, output_path)

    def make_broadcast_audio(self, segments, output_path):
        mode = "PREMIUM CLOUD" if self.use_cloud else "STANDARD LOCAL"
        print(f"[TTS] --- STARTING {mode} MASTERING ---")
        temp_files = []
        try:
            for idx, seg in enumerate(segments):
                speaker = str(seg.get("speaker", "ECHO")).upper()
                voice = self.echo_voice if speaker == "ECHO" else self.glitch_voice
                temp_path = f"output/temp_seg_{idx}.mp3"
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
