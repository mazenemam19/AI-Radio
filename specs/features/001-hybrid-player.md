# Feature Spec 001: Hybrid Media Player

## 🎯 Purpose
To provide seamless playback of both remote YouTube broadcasts and local offline test files within a single unified dashboard.

## ⚙️ Logic Bridge
- **Detection:** The player scans URLs for the `/output/` or `local://` signature.
- **Production Mode:** Embeds the YouTube IFrame API player.
- **Offline/Dev Mode:** Unhides a native HTML5 `<video>` element and hides the YouTube frame.
- **Path Mapping:** Automatically translates `local://` database pointers into browser-readable `output/` file paths.

## 🎨 Visualizer
- **Neural Pulse:** Uses procedural canvas animation synced to the "Playing" state to maintain Echo's aesthetic without requiring raw audio binary access from YouTube.
