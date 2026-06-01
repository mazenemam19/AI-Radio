# Implementation Plan: Revolutionary Audio Engine (SFX, Styles, Mastering)

## Phase 1: Engine Foundation & Voice Styles [checkpoint: 5fe9b42]
- [x] Task: Create `tests/test_audio_engine.py` for voice style and SFX logic fa09e58
- [x] Task: Update `requirements.txt` to include `pydub` abcccb1
- [x] Task: Implement `_simulate_reverb` and `_apply_audio_processing` in `tts_generator.py` 015ae5c
- [x] Task: Update `generate_segment_audio` to accept `voice_style`, `sfx_pre`, and `sfx_post` 015ae5c
- [x] Task: Map `voice_style` to Cartesia Sonic parameters in `_run_cartesia_tts` 015ae5c
- [x] Task: Conductor - User Manual Verification 'Phase 1: Foundation & Styles' (Protocol in workflow.md) 015ae5c

## Phase 2: SFX Mixer & Ambient Underlay [checkpoint: eec61bf]
- [x] Task: Create `sfx/` directory and ensure `STREET_AMBIENT.mp3` handling 23c63bd
- [x] Task: Implement looping ambient underlay in `_apply_audio_processing` d54e41e
- [x] Task: Implement `SILENCE.mp3` generator using `pydub` d54e41e
- [x] Task: Update `main.py` to pass SFX fields from JSON to `generate_segment_audio` b91ce79
- [x] Task: Conductor - User Manual Verification 'Phase 2: Mixer & Ambience' (Protocol in workflow.md) b91ce79

## Phase 3: Episode Assembler & Mastering [checkpoint: 8089d39]
- [x] Task: Refactor `_concat_audio` in `main.py` to use `pydub` 8089d39
- [x] Task: Implement loudness normalization pass targeting -14 LUFS in `_concat_audio` 8089d39
- [x] Task: Update dry-run stub in `main.py` to test all new styles and SFX 8089d39
- [x] Task: Conductor - User Manual Verification 'Phase 3: Assembler & Mastering' (Protocol in workflow.md) bf47037

## Phase 4: Review and Cleanup
- [x] Task: Execute full production-style dry-run bf47037
- [x] Task: Verify final audio levels and transition smoothness bf47037
- [x] Task: Final code style sweep and documentation update bf47037
- [x] Task: Conductor - User Manual Verification 'Phase 4: Review' (Protocol in workflow.md) bf47037
