import os
import re
import asyncio
import subprocess
import shutil
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

    def strip_tags(self, text):
        """Removes [tags] and <break /> tags for the fallback edge-tts engine."""
        cleaned = re.sub(r'\[.*?\]', '', text)
        cleaned = re.sub(r'<.*?>', '', cleaned)
        return cleaned.strip()

    def chunk_text(self, text, max_chars=180):
        """Breaks text into small pieces to stay under Groq's 200 character limit."""
        # Split by sentences or punctuation first
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""
        
        for s in sentences:
            if len(current_chunk) + len(s) < max_chars:
                current_chunk += (" " + s if current_chunk else s)
            else:
                if current_chunk: chunks.append(current_chunk.strip())
                # If a single sentence is too long, hard split it
                if len(s) >= max_chars:
                    for i in range(0, len(s), max_chars):
                        chunks.append(s[i:i+max_chars])
                    current_chunk = ""
                else:
                    current_chunk = s
        if current_chunk:
            chunks.append(current_chunk.strip())
        return chunks

    async def generate_edge_fallback(self, text, voice, path):
        """Local fallback using edge-tts if Cloud API fails."""
        edge_voice = "en-US-GuyNeural" if "daniel" in voice else "en-US-JennyNeural"
        communicate = edge_tts.Communicate(self.strip_tags(text), edge_voice)
        await communicate.save(path)

    def generate_segment_audio(self, text, voice, path):
        """Generate audio for a single segment with chunking and wav support."""
        if not self.api_key: return False
        
        chunks = self.chunk_text(text)
        chunk_files = []
        
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        
        try:
            for c_idx, chunk_text in enumerate(chunks):
                # Groq Orpheus requirements: < 200 chars, response_format=wav
                body = {
                    "model": self.model,
                    "input": chunk_text,
                    "voice": voice,
                    "response_format": "wav" 
                }
                
                r = requests.post(self.api_url, headers=headers, json=body, timeout=30)
                if r.status_code == 200:
                    c_path = f"{path}_chunk_{c_idx}.wav"
                    with open(c_path, "wb") as f:
                        f.write(r.content)
                    chunk_files.append(c_path)
                else:
                    print(f"[TTS] Cloud chunk failed ({r.status_code}). Aborting to fallback.")
                    raise Exception("Cloud Failure")

            # Merge wav chunks into one segment mp3
            if chunk_files:
                ffmpeg_cmd = shutil.which("ffmpeg") or r"C:\ffmpeg\bin\ffmpeg.exe"
                list_path = f"{path}_list.txt"
                with open(list_path, "w") as f:
                    for cf in chunk_files: f.write(f"file '{os.path.abspath(cf)}'\n")
                
                subprocess.run([ffmpeg_cmd, "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c:a", "libmp3lame", path], check=True, capture_output=True)
                
                # Cleanup chunks
                for cf in chunk_files: os.remove(cf)
                os.remove(list_path)
                return True

        except Exception as e:
            print(f"[TTS] Groq error or limit reached. Triggering local fallback...")
            # Cleanup any partial chunks
            for cf in chunk_files: 
                if os.path.exists(cf): os.remove(cf)
            asyncio.run(self.generate_edge_fallback(text, voice, path))
            return True

    def make_broadcast_audio(self, segments, output_path):
        print(f"[TTS] Mastering {len(segments)} segments...")
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
