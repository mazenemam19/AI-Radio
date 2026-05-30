# Feature Spec 001: Hybrid Media Player

## 🎯 Purpose
To provide seamless playback of both remote YouTube broadcasts and local offline test files within a single unified dashboard.

## ⚙️ Logic
- **Detection:** The player scans URLs for the `/output/` or `local://` signature.
- **Sequential Loading:** Config.js loads first, followed by app.js, then YouTube IFrame API (conditionally).
- **Security:** YouTube IFrame uses dynamic `window.location.origin` for the `origin` parameter.
- **Stability:** The `ytPlayerReady` flag and `onReady` event handler prevent race conditions during initialization.
- **Switching:** DOM elements are toggled using the `.hidden` class based on media source detection.


## 🎨 Visualizer
- **Neural Pulse:** Uses procedural canvas animation synced to the "Playing" state to maintain Echo's aesthetic without requiring raw audio binary access from YouTube.
