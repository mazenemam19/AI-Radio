import os
import re
import asyncio
import subprocess
import shutil
import edge_tts

class TTSRadioGenerator:
    def __init__(self, host_voice="en-US-GuyNeural", corr_voice="en-US-JennyNeural"):
        self.host_voice = host_voice
        self.corr_voice = corr_voice

    def strip_cues(self, text):
        cleaned_text = re.sub(r'\[.*?\]', ' ', text)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        return cleaned_text

    async def generate_segment_audio(self, text, voice, path):
        """Generate audio for a single segment."""
        communicate = edge_tts.Communicate(self.strip_cues(text), voice)
        await communicate.save(path)

    def make_broadcast_audio(self, segments, output_path):
        """Processes multiple segments with different voices and merges them."""
        print(f"[TTS] Rendering {len(segments)} segments for broadcast...")
        temp_files = []
        
        try:
            # 1. Generate individual segment files
            for idx, seg in enumerate(segments):
                voice = self.host_voice if seg.get("speaker") == "HOST" else self.corr_voice
                temp_path = f"output/temp_seg_{idx}.mp3"
                asyncio.run(self.generate_segment_audio(seg["text"], voice, temp_path))
                temp_files.append(temp_path)

            # 2. Merge them using FFmpeg concat protocol
            if not temp_files: return False
            
            # Create a list file for ffmpeg
            list_path = "output/concat_list.txt"
            with open(list_path, "w") as f:
                for tf in temp_files:
                    # Escape paths for ffmpeg
                    f.write(f"file '{os.path.abspath(tf)}'\n")

            ffmpeg_cmd = shutil.which("ffmpeg") or r"C:\ffmpeg\bin\ffmpeg.exe"
            merge_cmd = [
                ffmpeg_cmd, "-y", "-f", "concat", "-safe", "0",
                "-i", list_path, "-c", "copy", output_path
            ]
            subprocess.run(merge_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # 3. Cleanup
            for tf in temp_files: os.remove(tf)
            os.remove(list_path)
            print(f"[TTS] Full broadcast audio saved: {output_path}")
            return True
        except Exception as e:
            print(f"[TTS] Error during broadcast generation: {e}")
            return False

    def compile_video(self, audio_path, image_path, output_path):
        """Compile MP3 and static image into an MP4 video using ffmpeg."""
        ffmpeg_cmd = shutil.which("ffmpeg") or r"C:\ffmpeg\bin\ffmpeg.exe"
        
        print(f"[TTS] Compiling final broadcast video (FAST preset)...")
        command = [
            ffmpeg_cmd, "-y", "-loop", "1", "-i", image_path, "-i", audio_path,
            "-c:v", "libx264", "-preset", "fast", # Quality improvement
            "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-shortest", output_path
        ]
        try:
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except Exception as e:
            print(f"[TTS] Video compilation failed: {e}")
            return False
