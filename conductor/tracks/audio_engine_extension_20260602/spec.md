# Specification: Revolutionary Audio Engine (SFX, Styles, Mastering)

## Overview
Extend the Echo FM audio pipeline to support high-fidelity voice styles, an integrated SFX library with multi-track mixing, and professional loudness mastering. This upgrade moves the station from a "TTS string" to a "Produced Broadcast" experience.

## Functional Requirements

### 1. Voice Style Processing (Step 1)
- **Mapping:** Map `voice_style` (normal, whisper, grave, excited, deadpan) to Cartesia Sonic parameters.
- **Whisper Post-Processing:** Apply specialized `pydub` processing for the "whisper" style:
    - Gain reduction: -8dB.
    - Simulated Reverb: 40ms delay, 15% feedback overlay.
- **Speaking Rate:** Reduce speaking rate slightly for `grave` and `deadpan` styles.

### 2. SFX Library & Mixer (Step 2)
- **Library:** Support a standard set of SFX files in `sfx/` (INTRO_THEME, APPLAUSE, etc.).
- **Mixing Logic:**
    - `sfx_pre`: Prepend to segment audio.
    - `sfx_post`: Append to segment audio.
    - **Ambient Underlay:** Detect `STREET_AMBIENT` and loop it at -22dB as a background layer for the entire segment duration.
- **Silence Generator:** Implement `pydub AudioSegment.silent(duration=2000)` for the `SILENCE.mp3` requirement.

### 3. Episode Assembler & Mastering (Step 3)
- **Assembly:** Concatenate mixed segments in order into a single final episode MP3.
- **Mastering:** Apply a global loudness normalization pass targeting -14 LUFS (Streaming Standard) to ensure consistent volume across different engines and styles.

## Technical Requirements
- **Library:** Use `pydub` for all advanced audio manipulation.
- **Dependency:** Add `pydub` to `requirements.txt`.

## Acceptance Criteria
- Dry-runs produce a multi-segment audio file with audible SFX transitions and looping ambience.
- "Whisper" segments are perceptibly quieter and have acoustic depth.
- The final output has a consistent loudness profile.
