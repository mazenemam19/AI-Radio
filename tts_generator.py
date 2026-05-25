import os
import re
import asyncio
import subprocess
import shutil
import edge_tts

class TTSRadioGenerator:
    def __init__(self, voice="en-US-GuyNeural"):
        self.voice = voice

    def strip_cues(self, text):
        """Strip TTS sound cues like [sigh] or [glitch chuckle] so the neural voice does not read them literally."""
        # Replace brackets and everything inside them with a small pause or empty space
        cleaned_text = re.sub(r'\[.*?\]', ' ', text)
        # Collapse multiple spaces
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        return cleaned_text

    async def generate_audio_async(self, script, output_path):
        """Asynchronous audio generation using edge-tts."""
        cleaned_script = self.strip_cues(script)
        print(f"[TTS Generator] Rendering speech (voice: {self.voice}) to {output_path}...")
        
        communicate = edge_tts.Communicate(cleaned_script, self.voice)
        await communicate.save(output_path)
        print(f"[TTS Generator] Speech audio saved successfully: {output_path}")

    def make_audio(self, script, output_path):
        """Synchronous wrapper to run async audio generation."""
        try:
            asyncio.run(self.generate_audio_async(script, output_path))
            return True
        except Exception as e:
            print(f"[TTS Generator] Error generating audio: {e}")
            return False

    def compile_video(self, audio_path, image_path, output_path):
        """Compile MP3 and static image into an MP4 video using ffmpeg."""
        ffmpeg_cmd = shutil.which("ffmpeg")
        
        # Fallback for common Windows installation path if not in PATH
        if not ffmpeg_cmd:
            windows_fallback = r"C:\ffmpeg\bin\ffmpeg.exe"
            if os.path.exists(windows_fallback):
                ffmpeg_cmd = windows_fallback
            else:
                print("[TTS Generator] [WARNING] ffmpeg is not installed or not in system PATH. Cannot compile video.")
                return False

        if not os.path.exists(audio_path) or not os.path.exists(image_path):
            print(f"[TTS Generator] Missing assets to compile video: Audio exists? {os.path.exists(audio_path)}, Image exists? {os.path.exists(image_path)}")
            return False

        print(f"[TTS Generator] Compiling MP4 video via ffmpeg...")
        # FFmpeg command: loops still image, merges audio, encodes to high-quality YouTube-compatible MP4
        command = [
            ffmpeg_cmd,
            "-y",
            "-loop", "1",
            "-i", image_path,
            "-i", audio_path,
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            output_path
        ]

        try:
            # Run FFmpeg synchronously as a subprocess
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            print(f"[TTS Generator] Video compiled successfully: {output_path}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[TTS Generator] FFmpeg compilation failed: {e.stderr}")
            return False
        except Exception as ex:
            print(f"[TTS Generator] Error running FFmpeg: {ex}")
            return False
