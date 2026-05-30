# Feature Spec 002: Neural Art Engine

## 🎯 Purpose
To generate unique, HD satirical visuals for every broadcast background, replacing static placeholders with "dreamed up" art.

## 🛠️ Implementation
- **Provider:** Pollinations.ai (Flux Model).
- **Triggers:** Script-based generation. The AI must produce a `visual_description` for each episode.
- **Constraints:** Must be zero-cost (no tokens used for image generation).
- **Resolution:** Targeted at 1280x720 for native YouTube compatibility.

## ⚙️ Logic
1. AI writes visual prompt in `ai_client.py`.
2. `main.py` fetches the image via high-speed HTTP request.
3. Image is saved to `assets/` and passed to FFmpeg as the primary background layer.
