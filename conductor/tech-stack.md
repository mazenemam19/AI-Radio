# Technology Stack

Echo FM utilizes a hybrid local/cloud stack designed for high availability and zero-token waste.

## Core Language & Runtime
- **Python:** Primary language for orchestration, fetching, and media processing.
- **Node.js (npm):** Used for task orchestration and pipeline management (via `package.json`).

## Artificial Intelligence & Synthesis
- **Google Gemini:** Primary LLM for satirical script generation.
- **Groq Orpheus:** High-tier Text-to-Speech synthesis for production environments.
- **edge-tts:** Local-first, network-resilient TTS fallback for development and CI/CD.

## Data Persistence & Infrastructure
- **Supabase:** Cloud database and storage for production episodes and artifacts.
- **SQLite:** Local database for development, allowing for "air-gapped" testing. The UI provides unified access to both Supabase and SQLite via dedicated `serve:supabase` and `serve:sqlite` scripts.
- **dotenv:** Management of environment profiles (local, production, etc.).

## Media & Distribution
- **FFmpeg:** The "engine" for audio concatenation and MP4 video compilation.
- **Pillow (PIL):** Procedural generation of broadcast cover art and visuals.
- **YouTube Data API:** Automated publishing pipeline for the final broadcasts.
