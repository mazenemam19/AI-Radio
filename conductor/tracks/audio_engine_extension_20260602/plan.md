# Implementation Plan: Revolutionary Audio Engine (SFX, Styles, Mastering)

## Phase 1: Engine Foundation & Voice Styles
- [x] Task: Create `tests/test_audio_engine.py` for voice style and SFX logic
- [x] Task: Update `requirements.txt` to include `pydub` abcccb1
- [~] Task: Implement `_simulate_reverb` and `_apply_audio_processing` in `tts_generator.py`
- [ ] Task: Update `generate_segment_audio` to accept `voice_style`, `sfx_pre`, and `sfx_post`
- [ ] Task: Map `voice_style` to Cartesia Sonic parameters in `_run_cartesia_tts`
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Foundation & Styles' (Protocol in workflow.md)

## Phase 2: SFX Mixer & Ambient Underlay
- [ ] Task: Create `sfx/` directory and ensure `STREET_AMBIENT.mp3` handling
- [ ] Task: Implement looping ambient underlay in `_apply_audio_processing`
- [ ] Task: Implement `SILENCE.mp3` generator using `pydub`
- [ ] Task: Update `main.py` to pass SFX fields from JSON to `generate_segment_audio`
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Mixer & Ambience' (Protocol in workflow.md)

## Phase 3: Episode Assembler & Mastering
- [ ] Task: Refactor `_concat_audio` in `main.py` to use `pydub`
- [ ] Task: Implement loudness normalization pass targeting -14 LUFS in `_concat_audio`
- [ ] Task: Update dry-run stub in `main.py` to test all new styles and SFX
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Assembler & Mastering' (Protocol in workflow.md)

## Phase 4: Review and Cleanup
- [ ] Task: Execute full production-style dry-run
- [ ] Task: Verify final audio levels and transition smoothness
- [ ] Task: Final code style sweep and documentation update
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Review' (Protocol in workflow.md)
